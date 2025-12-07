"""
System utilities for ublue-rebase-helper.
"""

import logging
import subprocess
from typing import List, Optional


def run_command(cmd: List[str], timeout: Optional[int] = None) -> int:
    """Run a command and return its exit code."""
    try:
        if timeout is None:
            result = subprocess.run(
                cmd, check=False
            )  # Original behavior for backward compatibility
        else:
            result = subprocess.run(
                cmd, check=False, timeout=timeout
            )  # With timeout if specified
        return result.returncode
    except FileNotFoundError:
        logger.error(f"Command not found: {' '.join(cmd)}")
        print(f"Command not found: {' '.join(cmd)}")  # Also print for user visibility
        return 1
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        print(
            f"Command timed out after {timeout}s: {' '.join(cmd)}"
        )  # Also print for user visibility
        return 124  # Standard timeout exit code
    except Exception as e:
        logger.error(f"Error running command: {e}")
        print(f"Error running command: {e}")  # Also print for user visibility
        return 1  # Return error code for any other type of exception


def run_command_safe(base_cmd: str, *args: str, timeout: Optional[int] = 300) -> int:
    """Run a command with type-level injection prevention.

    The base_cmd must be a literal string, preventing variable injection.
    """
    cmd = [base_cmd, *args]
    try:
        if timeout is None:
            result = subprocess.run(
                cmd, check=False
            )  # Original behavior for backward compatibility
        else:
            result = subprocess.run(
                cmd, check=False, timeout=timeout
            )  # With timeout if specified
        return result.returncode
    except FileNotFoundError:
        logger.error(f"Command not found: {' '.join(cmd)}")
        print(f"Command not found: {' '.join(cmd)}")  # Also print for user visibility
        return 1
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        print(
            f"Command timed out after {timeout}s: {' '.join(cmd)}"
        )  # Also print for user visibility
        return 124  # Standard timeout exit code
    except Exception as e:
        logger.error(f"Error running command: {e}")
        print(f"Error running command: {e}")  # Also print for user visibility
        return 1  # Return error code for any other type of exception


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
    if url.startswith(("ghcr.io/", "docker.io/", "quay.io/", "gcr.io/")):
        registry_removed = url.split("/", 1)[1]
        repo_part = registry_removed.split(":")[0]
    else:
        repo_part = url.split(":")[0] if ":" in url else url
    return repo_part


def extract_context_from_url(url: str) -> Optional[str]:
    """Extract the tag context from a URL."""
    if ":" in url:
        url_tag = url.split(":")[-1]
        # Import the TagContext enum from the deployment module
        from .deployment import TagContext

        if url_tag in TagContext:
            return url_tag
    return None


def ensure_ostree_prefix(url: str) -> str:
    """Ensure the URL has the ostree-image-signed:docker:// prefix if not already present."""
    if url.startswith("ostree-image-signed:docker://") or url.startswith(
        "ostree-image-unsigned:docker://"
    ):
        return url
    elif url.startswith("docker://"):
        # If it already has docker:// prefix, just add the ostree-image-signed part
        return f"ostree-image-signed:{url}"
    else:
        # Add the complete prefix
        return f"ostree-image-signed:docker://{url}"


# Set up logging
logger = logging.getLogger(__name__)
