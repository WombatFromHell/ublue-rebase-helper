"""
Rm command handler.

Removes a deployment by index using `ostree admin undeploy`.
"""

from typing import List, Optional

from ..commands.deployment_helpers import MenuSystemProtocol
from .deployment_helpers import (
    handle_deployment_command,
    select_deployment,
)


def handle_rm(args: List[str], menu_system: Optional[MenuSystemProtocol] = None) -> int:
    """Handle the rm command.

    Removes a deployment by index using `sudo ostree admin undeploy <index>`.

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
            "Select deployment to remove (ESC to cancel):",
        )

    return handle_deployment_command(
        args,
        menu_system,
        select_func,
        ["ostree", "admin", "undeploy"],
        [],
    )
