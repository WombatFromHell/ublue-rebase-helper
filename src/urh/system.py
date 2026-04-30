"""
System utilities for ublue-rebase-helper.
"""

import logging
import os
import subprocess
from typing import List

from .constants import OSTREE_IMAGE_PREFIX, REGISTRY_PREFIXES

logger = logging.getLogger(__name__)

_cache_is_root: bool | None = None


def is_running_as_root() -> bool:
    """Check if the current process is running as root.

    Result is cached after the first call since the effective UID does not change
    during the lifetime of the process.
    """
    global _cache_is_root
    if _cache_is_root is None:
        _cache_is_root = os.geteuid() == 0
    return _cache_is_root


def build_command(requires_sudo: bool, base_cmd: List[str]) -> List[str]:
    """Build a command list, prepending sudo only if elevation is required.

    Args:
        requires_sudo: Whether the command needs root privileges.
        base_cmd: The command to run (without sudo).

    Returns:
        Command list with sudo prepended if needed.
    """
    if requires_sudo and not is_running_as_root():
        return ["sudo", *base_cmd]
    return base_cmd[:]


def _run_command(cmd: List[str]) -> int:
    """Run a command by replacing the current process.

    The process is replaced via os.execvp, so sudo gets the foreground TTY
    naturally and Ctrl+C works as expected.
    """
    try:
        os.execvp(cmd[0], cmd)
    except FileNotFoundError:
        logger.error("Command not found: %s", " ".join(cmd))
        print(f"Command not found: {' '.join(cmd)}")
        return 1


def check_curl_presence() -> bool:
    """Check if curl is available in the system."""
    try:
        result = subprocess.run(
            ["which", "curl"], capture_output=True, text=True, check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def extract_repository_from_url(url: str) -> str:
    """Extract the repository name from a container URL."""
    if url.startswith(REGISTRY_PREFIXES):
        registry_removed = url.split("/", 1)[1]
        repo_part = registry_removed.split(":")[0]
    else:
        repo_part = url.split(":")[0] if ":" in url else url
    return repo_part


def extract_context_from_url(url: str) -> str | None:
    """Extract the tag context from a URL."""
    if ":" in url:
        url_tag = url.split(":")[-1]
        from .deployment import TagContext

        if url_tag in TagContext:
            return url_tag
    return None


def ensure_ostree_prefix(url: str) -> str:
    """Ensure the URL has the ostree-image-signed:docker:// prefix if not already present."""
    if url.startswith(OSTREE_IMAGE_PREFIX) or url.startswith(
        "ostree-image-unsigned:docker://"
    ):
        return url
    elif url.startswith("docker://"):
        return f"ostree-image-signed:{url}"
    else:
        return f"{OSTREE_IMAGE_PREFIX}{url}"
