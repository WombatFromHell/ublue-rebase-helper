"""
Constants for ublue-rebase-helper.
"""

# Version - injected at build time by Makefile
__version__ = "1.2.0"

# Constants
DEFAULT_CONFIG_PATH = "~/.config/urh.toml"
XDG_CONFIG_PATH = "$XDG_CONFIG_HOME/urh.toml"
CACHE_FILE_PATH = "/tmp/oci_ghcr_token"
MAX_TAGS_DISPLAY = 30
DEFAULT_REGISTRY = "ghcr.io"
GITHUB_TOKEN_URL = "https://ghcr.io/token"
