"""
OCI client implementation for ublue-rebase-helper.
"""

import json
import logging
import subprocess
from typing import Any, Dict, List, NamedTuple, Optional

from .config import get_config
from .system import extract_context_from_url


class DynamicLogger:
    """A logger that dynamically accesses the main module's logger when called."""

    def __getattr__(self, name):
        # Try to get the main module logger for consistency
        try:
            from . import logger
            if logger:
                return getattr(logger, name)
        except ImportError:
            pass

        # Fallback to module-specific logger if main module logger not available
        module_logger = logging.getLogger(__name__)
        return getattr(module_logger, name)


# Set up logging with dynamic access to support patching
logger = DynamicLogger()


class CurlResult(NamedTuple):
    """Result of a curl operation."""

    stdout: str
    stderr: str
    returncode: int
    headers: Optional[Dict[str, str]] = None


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

    def _curl(
        self,
        url: str,
        token: str,
        *,
        capture_headers: bool = False,
        capture_body: bool = True,
        capture_status_code: bool = False,
        timeout: int = 30,
    ) -> CurlResult:
        """Unified curl wrapper with optional header capture."""
        cmd = ["curl", "-s", "--max-time", str(timeout)]

        if capture_status_code:
            # Write HTTP status code to stdout
            cmd.extend(["-w", "%{http_code}"])

        if capture_headers:
            # Use -i to include headers in output
            cmd.append("-i")

        if not capture_body and not capture_status_code:
            cmd.extend(["-o", "/dev/null"])

        cmd.extend(["-H", f"Authorization: Bearer {token}", url])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on non-zero exit
        )

        headers = None
        stdout = result.stdout

        if capture_headers and result.returncode == 0 and not capture_status_code:
            # Split headers and body
            parts = stdout.split("\r\n\r\n", 1)
            if len(parts) == 2:
                headers = self._parse_headers(parts[0])
                stdout = parts[1]

        return CurlResult(stdout, result.stderr, result.returncode, headers)

    def _parse_headers(self, header_text: str) -> Dict[str, str]:
        """Parse HTTP headers from text."""
        headers: Dict[str, str] = {}
        for line in header_text.split("\r\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
        return headers

    def _validate_token_and_retry(self, token: str, url: str) -> Optional[str]:
        """
        Validate the token and retry with a new token if it's expired.

        Args:
            token: The current token to validate
            url: The URL to test the token against

        Returns:
            A valid token if successful, None otherwise
        """
        try:
            # Test the current token with a HEAD-like request
            cmd = [
                "curl",
                "-s",
                "-w",
                "%{http_code}",  # Write HTTP status code
                "-o",
                "/dev/null",  # Discard body
                "-H",
                f"Authorization: Bearer {token}",
                url,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            http_status = int(result.stdout.strip())

            # Token is valid
            if http_status == 200:
                logger.debug("Token validation successful")
                return token

            # Token expired or invalid
            if http_status == 403 or http_status == 401:
                logger.debug(
                    f"Token invalid (HTTP {http_status}). Fetching new token..."
                )
                self.token_manager.invalidate_cache()

                # Get new token
                new_token = self.token_manager.get_token()
                if not new_token:
                    logger.error("Could not obtain a new token")
                    return None

                # Validate new token
                cmd[cmd.index(f"Authorization: Bearer {token}")] = (
                    f"Authorization: Bearer {new_token}"
                )
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                )

                http_status = int(result.stdout.strip())
                if http_status == 200:
                    logger.debug("New token validated successfully")
                    return new_token
                else:
                    logger.error(f"New token also invalid (HTTP {http_status})")
                    return None

            # Other HTTP status
            logger.debug(f"Unexpected HTTP status during validation: {http_status}")
            return token  # Try to continue anyway

        except subprocess.TimeoutExpired:
            logger.error("Timeout during token validation")
            return None
        except Exception as e:
            logger.error(f"Error during token validation: {e}")
            return None

    def get_all_tags(
        self, context_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get all tags with optimized single-request-per-page approach.
        """
        token = self.token_manager.get_token()
        if not token:
            logger.error("Could not obtain authentication token")
            return None

        base_url = f"https://ghcr.io/v2/{self.repository}/tags/list"
        next_url = f"{base_url}?n=200"
        all_tags: List[str] = []
        page_count = 0
        max_pages = 1000

        # Log the specific context if provided, otherwise the repository
        target_name = context_url if context_url else self.repository
        logger.debug(f"Starting pagination for: {target_name}")

        while next_url and page_count < max_pages:
            page_count += 1

            # Construct full URL
            if next_url.startswith("http"):
                full_url = next_url
            elif next_url.startswith("/"):
                full_url = f"https://ghcr.io{next_url}"
            else:
                full_url = f"https://ghcr.io/{next_url}"

            logger.debug(f"Page {page_count}: {full_url}")

            # NEW: Fetch page data AND next URL in single request
            page_data, next_url = self._fetch_page_with_headers(full_url, token)

            if not page_data:
                logger.error(f"Failed to fetch page {page_count}")
                if all_tags:
                    logger.warning(f"Returning {len(all_tags)} tags collected so far")
                    return {"tags": all_tags}
                return None

            # Accumulate tags
            page_tags = page_data.get("tags", [])
            if page_tags:
                all_tags.extend(page_tags)
                logger.debug(
                    f"Page {page_count}: {len(page_tags)} tags (total: {len(all_tags)})"
                )

        if page_count >= max_pages:
            logger.warning(f"Hit maximum page limit ({max_pages})")

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

    def _fetch_page_with_headers(
        self, url: str, token: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Fetch page data AND Link header in a single request.

        Returns:
            Tuple of (page_data, next_url)
        """
        # Initialize variables to help with type checking
        stdout: str = ""
        body: str = ""

        try:
            cmd = [
                "curl",
                "-s",  # Silent
                "-i",  # Include headers in output
                "--http2",  # Force HTTP/2 if available
                "-H",
                f"Authorization: Bearer {token}",
                url,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            # Properly parse the HTTP response which has format:
            # HTTP/1.1 XXX Status
            # Headers...
            #
            # Body
            stdout = result.stdout

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
                return None, None

            # Extract headers part (from after status line to separator)
            headers_and_status = stdout[:double_newline_pos]
            body = stdout[double_newline_pos + separator_len :]  # Skip the separator

            # The first line is the HTTP status line, subsequent lines are headers
            lines = headers_and_status.splitlines()
            if not lines:
                logger.error("Empty response headers")
                return None, None

            # First line is status line, rest are headers
            status_line = lines[0]
            header_lines = lines[1:]

            # Parse headers (case-insensitive)
            headers: Dict[str, str] = {}
            for line in header_lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            # Log status line for debugging
            logger.debug(f"HTTP Status: {status_line}")

            # Check if status indicates an auth error, and if so, try with fresh token
            if "401" in status_line or "403" in status_line:
                logger.debug(
                    f"Received {status_line}, invalidating token and retrying..."
                )
                self.token_manager.invalidate_cache()
                new_token = self.token_manager.get_token()
                if new_token:
                    logger.debug("Got new token, retrying request...")
                    return self._fetch_page_with_headers(url, new_token)
                else:
                    logger.error("Could not obtain new token after auth error")
                    return None, None

            # Get Link header
            link_header = headers.get("link")
            next_url = (
                self.token_manager.parse_link_header(link_header)
                if link_header
                else None
            )

            # Parse JSON body
            if not body.strip():
                logger.debug(f"Empty response body. Full response: {repr(stdout)}")
                return None, None

            logger.debug(f"Response body: {repr(body)}")

            # Check if the response is an error response from GHCR
            # GHCR error responses follow the pattern: {"errors":[...]}
            stripped_body = body.strip()
            if stripped_body.startswith('{"errors":'):
                logger.error(f"GHCR API returned an error: {stripped_body}")
                # This is an error response, not the expected tags response
                # The error suggests authentication/token issue
                return None, None

            data = json.loads(body)

            logger.debug(
                f"Fetched {len(data.get('tags', []))} tags, has_next: {next_url is not None}"
            )

            return data, next_url

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout fetching page: {url}")
            return None, None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in response: {e}")
            logger.debug(f"Response body that failed to parse: {repr(body)}")
            logger.debug(f"Full response that failed to parse: {repr(stdout)}")
            return None, None
        except Exception as e:
            logger.error(f"Error fetching page: {e}")
            return None, None

    def _parse_link_header(self, link_header: Optional[str]) -> Optional[str]:
        """
        Parse the Link header to extract the next URL.
        Note: This method matches the signature expected by tests but is redundant
        with the token manager's parse_link_header method. This is kept for
        test compatibility.
        """
        return self.token_manager.parse_link_header(link_header)
