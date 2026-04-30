"""
OCI client implementation for ublue-rebase-helper.
"""

import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

from .config import get_config
from .system import extract_context_from_url

# Set up logging
logger = logging.getLogger(__name__)


class OCIClient:
    """A client for OCI Container Registry interactions using curl."""

    def __init__(
        self, repository: str, cache_path: Optional[str] = None, debug: bool = False
    ):
        self.repository = repository
        self.debug = debug
        self.config = get_config()
        from .token_manager import OCITokenManager

        self.token_manager = OCITokenManager(repository, cache_path)

    def _validate_token(self) -> Optional[str]:
        """Get and validate authentication token."""
        token = self.token_manager.get_token()
        if not token:
            logger.error("Could not obtain authentication token")
            return None
        return token

    def _normalize_pagination_url(self, url: str) -> str:
        """Normalize pagination URL to full URL format."""
        if url.startswith("http"):
            return url
        elif url.startswith("/"):
            return f"https://ghcr.io{url}"
        else:
            return f"https://ghcr.io/{url}"

    def _handle_page_fetch_error(
        self, page_count: int, all_tags: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Handle page fetch errors and return partial results if available."""
        logger.error(f"Failed to fetch page {page_count}")
        if all_tags:
            logger.warning(f"Returning {len(all_tags)} tags collected so far")
            return {"tags": all_tags}
        return None

    def _log_pagination_progress(
        self, page_count: int, page_tags: List[str], all_tags: List[str], full_url: str
    ) -> None:
        """Log pagination progress information."""
        logger.debug(f"Page {page_count}: {full_url}")
        if page_tags:
            logger.debug(
                f"Page {page_count}: {len(page_tags)} tags (total: {len(all_tags)})"
            )

    def get_all_tags(
        self, context_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get all tags with optimized single-request-per-page approach.
        """
        # Validate token
        token = self._validate_token()
        if not token:
            return None

        # Initialize pagination
        base_url = f"https://ghcr.io/v2/{self.repository}/tags/list"
        next_url = f"{base_url}?n=200"
        all_tags: List[str] = []
        page_count = 0
        max_pages = 1000

        # Log the specific context if provided, otherwise the repository
        target_name = context_url if context_url else self.repository
        logger.debug(f"Starting pagination for: {target_name}")

        # Pagination loop
        while next_url and page_count < max_pages:
            page_count += 1

            # Normalize URL
            full_url = self._normalize_pagination_url(next_url)

            # Log progress
            logger.debug(f"Page {page_count}: {full_url}")

            # Fetch page data AND next URL in single request
            page_data, next_url = self._fetch_page_with_headers(full_url, token)

            # Handle fetch errors
            if not page_data:
                return self._handle_page_fetch_error(page_count, all_tags)

            # Accumulate tags
            page_tags = page_data.get("tags", [])
            if page_tags:
                all_tags.extend(page_tags)
                self._log_pagination_progress(page_count, page_tags, all_tags, full_url)

        # Check if we hit page limit
        if page_count >= max_pages:
            logger.warning(f"Hit maximum page limit ({max_pages})")

        # Log completion
        logger.debug(
            f"Pagination complete: {len(all_tags)} tags across {page_count} pages"
        )

        return {"tags": all_tags}

    def fetch_repository_tags(
        self, url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get filtered and sorted tags for the repository."""
        # Fix: Pass the url to get_all_tags so the logs reflect the actual endpoint
        tags_data = self.get_all_tags(context_url=url)
        if not tags_data:
            return None

        # Extract context from URL if provided
        context = None
        if url:
            context = extract_context_from_url(url)

        # Create tag filter with context
        from .tag_filter import OCITagFilter

        tag_filter = OCITagFilter(self.repository, self.config, context)

        filtered_tags = tag_filter.filter_and_sort_tags(
            tags_data["tags"], limit=self.config.settings.max_tags_display
        )

        return {"tags": filtered_tags}

    def _build_curl_command(self, url: str, token: str) -> List[str]:
        """Build curl command for fetching OCI registry data."""
        return [
            "curl",
            "-s",  # Silent
            "-i",  # Include headers in output
            "--http2",  # Force HTTP/2 if available
            "-H",
            f"Authorization: Bearer {token}",
            url,
        ]

    def _parse_http_response(
        self, stdout: str
    ) -> tuple[Optional[str], Optional[str], Optional[Dict[str, str]]]:
        """
        Parse HTTP response into status line, headers, and body.

        Returns:
            Tuple of (status_line, body, headers_dict) or (None, None, None) on error
        """
        # Split the response into HTTP status line, headers, and body
        # First, find the index of the double newline that separates headers from body
        double_crlf_pos = stdout.find("\r\n\r\n")
        double_lf_pos = stdout.find("\n\n")

        # Check which separator appears first and use it
        if double_crlf_pos != -1 and (
            double_lf_pos == -1 or double_crlf_pos < double_lf_pos
        ):
            # Use \r\n\r\n separator (4 characters)
            double_newline_pos = double_crlf_pos
            separator_len = 4
        elif double_lf_pos != -1:
            # Use \n\n separator (2 characters)
            double_newline_pos = double_lf_pos
            separator_len = 2
        else:
            logger.error("Could not find header/body separator in response")
            logger.debug(f"Response content: {repr(stdout)}")
            return None, None, None

        # Extract headers part (from after status line to separator)
        headers_and_status = stdout[:double_newline_pos]
        body = stdout[double_newline_pos + separator_len :]  # Skip the separator

        # The first line is the HTTP status line, subsequent lines are headers
        lines = headers_and_status.splitlines()
        if not lines:
            logger.error("Empty response headers")
            return None, None, None

        # First line is status line, rest are headers
        status_line = lines[0]
        header_lines = lines[1:]

        # Parse headers (case-insensitive)
        headers: Dict[str, str] = {}
        for line in header_lines:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        return status_line, body, headers

    def _handle_auth_error(
        self, status_line: str, url: str, token: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Handle authentication errors by invalidating token and retrying."""
        logger.debug(f"Received {status_line}, invalidating token and retrying...")
        self.token_manager.invalidate_cache()
        new_token = self.token_manager.get_token()
        if new_token:
            logger.debug("Got new token, retrying request...")
            return self._fetch_page_with_headers(url, new_token)
        else:
            logger.error("Could not obtain new token after auth error")
            return None, None

    def _parse_response_body(self, body: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response body and handle errors."""
        if not body.strip():
            logger.debug("Empty response body")
            return None

        logger.debug(f"Response body: {repr(body)}")

        # Check if the response is an error response from GHCR
        # GHCR error responses follow the pattern: {"errors":[...]}
        stripped_body = body.strip()
        if stripped_body.startswith('{"errors":'):
            logger.error(f"GHCR API returned an error: {stripped_body}")
            # This is an error response, not the expected tags response
            # The error suggests authentication/token issue
            return None

        try:
            data = json.loads(body)
            logger.debug(f"Fetched {len(data.get('tags', []))} tags")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in response: {e}")
            logger.debug(f"Response body that failed to parse: {repr(body)}")
            return None

    def _fetch_page_with_headers(
        self, url: str, token: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch page data AND Link header in a single request.

        Returns:
            Tuple of (page_data, next_url)
        """
        try:
            cmd = self._build_curl_command(url, token)
            result = self._execute_curl_command(cmd)

            status_line, body, headers = self._parse_http_response(result.stdout)
            if status_line is None or body is None or headers is None:
                return None, None

            logger.debug(f"HTTP Status: {status_line}")

            if auth_result := self._check_auth_error(status_line, url, token):
                return auth_result

            next_url = self._extract_next_url(headers)
            data = self._parse_response_body(body) if body else None

            if data is None:
                return None, None

            logger.debug(f"Fetched tags, has_next: {next_url is not None}")

            return data, next_url

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout fetching page: {url}")
            return None, None
        except Exception as e:
            logger.error(f"Error fetching page: {e}")
            return None, None

    def _execute_curl_command(self, cmd: List[str]) -> subprocess.CompletedProcess[str]:
        """Execute curl command and return result."""
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

    def _check_auth_error(
        self, status_line: str, url: str, token: str
    ) -> Optional[tuple[Optional[Dict[str, Any]], Optional[str]]]:
        """Check for auth errors and handle them."""
        if status_line and ("401" in status_line or "403" in status_line):
            return self._handle_auth_error(status_line, url, token)
        return None

    def _extract_next_url(self, headers: Optional[Dict[str, str]]) -> Optional[str]:
        """Extract next URL from Link header."""
        link_header = headers.get("link") if headers else None
        return (
            self.token_manager.parse_link_header(link_header) if link_header else None
        )
