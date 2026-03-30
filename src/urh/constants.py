"""
Constants for ublue-rebase-helper.
"""

# Version - injected at build time by Makefile
__version__ = "1.2.5"


def format_version_header() -> str:
    """Format the version string for display in menu headers."""
    return f"ublue-rebase-helper v{__version__}"


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
