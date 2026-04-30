"""
Unpin command handler.

Unpins a deployment, allowing it to be removed during cleanup.
"""

from typing import List, Optional

from ..commands.deployment_helpers import MenuSystemProtocol
from .deployment_helpers import (
    filter_pinned_deployments,
    handle_deployment_command,
    select_deployment,
)


def handle_unpin(
    args: List[str], menu_system: Optional[MenuSystemProtocol] = None
) -> int:
    """Handle the unpin command.

    Args:
        args: Command line arguments (deployment number or empty for menu mode).
        menu_system: MenuSystem instance for interactive selection.
    """
    from ..deployment import get_deployment_info

    def select_func():
        deployments = get_deployment_info()
        if not deployments:
            print("No deployments found.")
            return None
        return select_deployment(
            menu_system,
            deployments,
            "Select deployment to unpin (ESC to cancel):",
            filter_func=filter_pinned_deployments,
            filter_message="No deployments are pinned.",
        )

    return handle_deployment_command(
        args,
        menu_system,
        select_func,
        ["ostree", "admin", "pin", "-u"],
        [],
    )
