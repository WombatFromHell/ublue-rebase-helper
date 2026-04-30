"""
Undeploy command handler.

Removes a deployment by index with confirmation prompt.
"""

from typing import List, Optional

from ..commands.deployment_helpers import MenuSystemProtocol
from ..deployment import DeploymentInfo
from ..menu import MenuExitException
from .deployment_helpers import (
    get_selected_deployment_info,
    handle_deployment_command,
    select_deployment,
)


def _create_undeploy_confirmation_items():
    """Create confirmation menu items for undeploy operation."""
    from ..models import MenuItem

    return [
        MenuItem("Y", "Yes, undeploy this deployment"),
        MenuItem("N", "No, cancel undeployment"),
    ]


def _get_undeploy_confirmation_header(deployment) -> str:
    """Get confirmation header for undeploy operation."""
    return f"Confirm undeployment of:\n  {deployment.repository} ({deployment.version}) ({deployment.deployment_index}{'*' if deployment.is_pinned else ''})"


def _select_deployment_to_undeploy_with_confirmation(
    menu_system: Optional[MenuSystemProtocol], deployments: List[DeploymentInfo]
) -> Optional[int]:
    """Show menu to select deployment for undeploying with confirmation."""
    try:
        while True:  # Loop to return to selection if user cancels
            selected = select_deployment(
                menu_system,
                deployments,
                "Select deployment to undeploy (ESC to cancel):",
            )

            if selected is None:
                return None

            deployment_num = selected

            # Get deployment info for confirmation message
            selected_deployment = get_selected_deployment_info(deployments, selected)

            if selected_deployment:
                # Create confirmation items
                confirmation_items = _create_undeploy_confirmation_items()

                # Create confirmation header
                confirmation_header = _get_undeploy_confirmation_header(
                    selected_deployment
                )

                confirmation = menu_system.show_menu(  # type: ignore[union-attr]
                    confirmation_items,
                    confirmation_header,
                    persistent_header="",
                    is_main_menu=False,
                )

                if confirmation and confirmation.lower() == "y":
                    # User confirmed, proceed with undeploy
                    return deployment_num
                else:
                    # User cancelled, continue to show selection again
                    continue
            else:
                # This shouldn't happen in normal flow, but just in case
                return None
    except MenuExitException:
        return None


def handle_undeploy(
    args: List[str], menu_system: Optional[MenuSystemProtocol] = None
) -> int:
    """Handle the undeploy command.

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
        return _select_deployment_to_undeploy_with_confirmation(
            menu_system, deployments
        )

    return handle_deployment_command(
        args,
        menu_system,
        select_func,
        ["ostree", "admin", "undeploy"],
        [],
    )
