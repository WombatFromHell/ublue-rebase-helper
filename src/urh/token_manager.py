"""
Token management for ublue-rebase-helper.
"""

import json
import logging
import os
import re
import subprocess
from typing import Optional

from .constants import CACHE_FILE_PATH

# Set up logging
logger = logging.getLogger(__name__)


class OCITokenManager:
    """Manages OAuth2 tokens for OCI registries using curl."""

    def __init__(self, repository: str, cache_path: Optional[str] = None):
        self.repository = repository
        self.cache_path = cache_path or CACHE_FILE_PATH

    def _get_cache_filepath(self) -> str:
        """Get the full path to the cache file."""
        return self.cache_path

    def _cache_token(self, token: str) -> None:
        """Cache the token to the cache file."""
        cache_filepath = self._get_cache_filepath()
        try:
            with open(cache_filepath, "w") as f:
                f.write(token)
            logger.debug(f"Successfully cached new token to {cache_filepath}")
        except (IOError, OSError) as e:
            logger.debug(f"Could not write token to cache {cache_filepath}: {e}")

    def get_token(self) -> Optional[str]:
        """
        Get an OAuth2 token for the repository, using a cached token if available.

        Returns:
            The token string if successful, None otherwise.
        """
        cache_filepath = self._get_cache_filepath()

        # 1. Check for a cached token
        if os.path.exists(cache_filepath):
            try:
                with open(cache_filepath, "r") as f:
                    logger.debug(f"Found cached token at {cache_filepath}")
                    return f.read().strip()
            except (IOError, OSError) as e:
                logger.warning(f"Could not read cached token at {cache_filepath}: {e}")

        # 2. If no cache, fetch a new token
        logger.debug("No valid cached token found. Fetching a new one...")
        scope = f"repository:{self.repository}:pull"
        # Note: The scope needs to be passed as a single argument to curl
        url = f"https://ghcr.io/token?scope={scope}"

        try:
            result = subprocess.run(
                [
                    "curl",
                    "-s",
                    "--http2",
                    "--compressed",
                    url,
                ],  # Added -s for silent mode, --http2 for performance, --compressed for content compression
                capture_output=True,
                text=True,
                check=True,
            )
            response = json.loads(result.stdout)
            token = response.get("token")

            if token:
                # 3. Cache the new token for future use
                self._cache_token(token)
                return token
            return None
        except Exception as e:
            logger.error(f"Error getting token: {e}")
            print(f"Error getting token: {e}")  # Also print for user visibility
            return None

    def invalidate_cache(self) -> None:
        """Deletes the cached token file if it exists."""
        cache_filepath = self._get_cache_filepath()
        try:
            os.remove(cache_filepath)
            logger.debug(f"Invalidated and removed cache file: {cache_filepath}")
        except FileNotFoundError:
            # Cache file doesn't exist, nothing to do.
            logger.debug(f"Cache file does not exist: {cache_filepath}")

    def parse_link_header(self, link_header: Optional[str]) -> Optional[str]:
        """
        Parse the Link header to extract the next URL.
        Example: Link: </v2/WombatFromHell/bazzite-nix/tags/list?last=1.2.0&n=200>; rel="next"

        Args:
            link_header: The raw Link header value

        Returns:
            The next URL if found, None otherwise
        """
        if not link_header:
            return None

        # Look for the next link in the Link header
        # Pattern: </v2/...>; rel="next" or similar variations with spaces
        # Using a comprehensive pattern to match various formats
        # This pattern handles: '<url>; rel="next"' including possible spaces
        next_match = re.search(
            r'<\s*([^>]+?)\s*>\s*;\s*rel\s*=\s*["\']next["\']', link_header
        )
        if next_match:
            return next_match.group(1)
        return None
