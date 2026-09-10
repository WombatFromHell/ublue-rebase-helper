"""
Constants for ublue-rebase-helper.
"""

from importlib.metadata import PackageNotFoundError, version

__version__ = "DEV"


def _get_version() -> str:
    """Get version from embedded value or package metadata fallback."""
    if __version__ != "DEV":
        return __version__
    try:
        return version("ublue-rebase-helper")
    except PackageNotFoundError:
        return "unknown"


def format_version_header() -> str:
    """Format the version string for display in menu headers."""
    return f"ublue-rebase-helper v{_get_version()}"


def format_menu_separator() -> str:
    """Format a visual separator for menu sections."""
    return "─" * 50


# Constants
DEFAULT_CONFIG_PATH = "~/.config/urh.toml"
XDG_CONFIG_PATH = "$XDG_CONFIG_HOME/urh.toml"
CACHE_FILE_PATH = "/tmp/oci_ghcr_token"
MAX_TAGS_DISPLAY = 30
DEFAULT_REGISTRY = "ghcr.io"
GITHUB_TOKEN_URL = "https://ghcr.io/token"

# OCI/registry constants
OSTREE_IMAGE_PREFIX = "ostree-image-signed:docker://"
REGISTRY_PREFIXES = ("ghcr.io/", "docker.io/", "quay.io/")

# Test environment variable names
PYTEST_CURRENT_TEST = "PYTEST_CURRENT_TEST"
URH_AVOID_GUM = "URH_AVOID_GUM"
URH_TEST_NO_EXCEPTION = "URH_TEST_NO_EXCEPTION"
