"""
Remote-ls command handler.

Lists available tags for a container image from the OCI registry.
"""

from typing import List, Optional

from ..commands.deployment_helpers import MenuSystemProtocol
from ..deployment import build_persistent_header
from ..oci_client import OCIClient


def _get_url_for_remote_ls(
    args: List[str], config, menu_system: Optional[MenuSystemProtocol]
) -> Optional[str]:
    """Get URL from arguments or user selection for remote-ls."""
    if not args:
        if menu_system is None:
            return None
        return _select_url_for_remote_ls(config, menu_system)
    else:
        return args[0]


def _select_url_for_remote_ls(config, menu_system: MenuSystemProtocol) -> Optional[str]:
    """Show menu to select URL for remote-ls."""
    from ..models import ListItem

    # Show submenu using ListItem instead of MenuItem
    options: List[str] = list(config.container_urls.options)
    items = [ListItem("", url, url) for url in options]

    persistent_header = build_persistent_header()

    selected = menu_system.show_menu(
        items,
        "Select container image (ESC to cancel):",
        persistent_header=persistent_header,
        is_main_menu=False,
    )
    return selected


def _display_tags_for_url(url: str) -> int:
    """Display tags for the given URL."""
    import logging

    from ..system import extract_repository_from_url

    logger = logging.getLogger(__name__)

    # Extract repository from URL
    repository = extract_repository_from_url(url)

    # Create OCI client and fetch tags
    client = OCIClient(repository)
    tags_data = client.fetch_repository_tags(url)

    if tags_data and "tags" in tags_data and tags_data["tags"]:
        print(f"Tags for {url}:")  # Keep print for user output of the actual tags
        for tag in tags_data["tags"]:
            print(f"  {tag}")
        return 0  # Exit with success code after successful completion
    elif tags_data and "tags" in tags_data and not tags_data["tags"]:
        # No tags found
        logger.info(f"No tags found for {url}")
        print(f"No tags found for {url}")  # Print for user visibility
        return 0
    else:
        # Error occurred
        logger.error(f"Could not fetch tags for {url}")
        print(f"Could not fetch tags for {url}")  # Print for user visibility
        return 1


def handle_remote_ls(
    args: List[str], menu_system: Optional[MenuSystemProtocol] = None
) -> int:
    """Handle the remote-ls command.

    Args:
        args: Command line arguments (empty for menu mode).
        menu_system: MenuSystem instance for interactive selection.
    """
    from ..config import get_config

    config = get_config()
    url = _get_url_for_remote_ls(args, config, menu_system)

    if url is None:
        return 0  # User cancelled selection

    return _display_tags_for_url(url)
