"""
Shared deployment selection helpers for deployment-related commands.

Provides common patterns for:
- Filtering deployments by pinned/unpinned status
- Creating menu items from deployment lists
- Selecting deployments via menu
- Validating deployment selection
"""

from typing import TYPE_CHECKING, Any, Callable, List, Optional, Protocol, Sequence

from ..deployment import DeploymentInfo, build_persistent_header
from ..system import _run_command, build_command

if TYPE_CHECKING:
    from ..models import ListItem, MenuItem


class MenuSystemProtocol(Protocol):
    """Protocol for menu system objects."""

    def show_menu(
        self,
        items: Sequence["MenuItem"],
        header: str,
        persistent_header: Optional[str] = None,
        is_main_menu: bool = False,
    ) -> Optional[Any]: ...


FilterFunc = Callable[[List[DeploymentInfo]], List[DeploymentInfo]]
ValidationFunc = Callable[[List[DeploymentInfo], int], bool]


def filter_unpinned_deployments(
    deployments: List[DeploymentInfo],
) -> List[DeploymentInfo]:
    """Filter deployments to get only unpinned ones."""
    return [d for d in deployments if not d.is_pinned]


def filter_pinned_deployments(
    deployments: List[DeploymentInfo],
) -> List[DeploymentInfo]:
    """Filter deployments to get only pinned ones."""
    return [d for d in deployments if d.is_pinned]


def format_deployment_display(d: DeploymentInfo) -> str:
    """Format a deployment for display in menus."""
    return f"{d.repository} ({d.version}) ({d.deployment_index}{'*' if d.is_pinned else ''})"


def create_deployment_menu_items(deployments: List[DeploymentInfo]) -> List["ListItem"]:
    """Create menu items for deployment selection.

    Shows ALL deployments in ascending order (newest first).
    This allows users to see which deployments are already pinned.
    """
    from ..models import ListItem

    # Reverse order to show newest first
    all_deployments = deployments[::-1]

    return [
        ListItem("", format_deployment_display(d), d.deployment_index)
        for d in all_deployments
    ]


def create_pinned_deployment_menu_items(
    deployments: List[DeploymentInfo],
) -> List["ListItem"]:
    """Create menu items for pinned deployment selection."""
    from ..models import ListItem

    pinned = filter_pinned_deployments(deployments)
    return [
        ListItem(
            "",
            f"{d.repository} ({d.version}) ({d.deployment_index}*)",
            d.deployment_index,
        )
        for d in pinned
    ]


def get_selected_deployment_info(
    deployments: List[DeploymentInfo], selected_index: int
) -> Optional[DeploymentInfo]:
    """Get deployment info for the selected deployment index."""
    all_deployments = deployments[::-1]  # Reverse order to show newest first
    return next(
        (d for d in all_deployments if d.deployment_index == selected_index),
        None,
    )


def validate_deployment_not_pinned(
    deployments: List[DeploymentInfo], selected_index: int
) -> bool:
    """Validate that selected deployment is not already pinned."""
    all_deployments = deployments[::-1]  # Reverse order to show newest first
    selected_deployment = next(
        (d for d in all_deployments if d.deployment_index == selected_index), None
    )
    if selected_deployment and selected_deployment.is_pinned:
        print(f"Deployment {selected_index} is already pinned.")
        return False
    return True


def select_deployment(
    menu_system: Optional["MenuSystemProtocol"],
    deployments: List[DeploymentInfo],
    prompt: str,
    filter_func: Optional[FilterFunc] = None,
    filter_message: Optional[str] = None,
    validation_func: Optional[ValidationFunc] = None,
) -> Optional[int]:
    """Show menu to select a deployment with optional filtering and validation.

    Args:
        menu_system: The MenuSystem instance to use for showing menus.
        deployments: List of DeploymentInfo objects.
        prompt: The prompt to show in the menu.
        filter_func: Optional function to filter deployments before showing menu.
        filter_message: Message to show if filter results in no deployments.
        validation_func: Optional function to validate selection. Called with
            (deployments, selected_index). Should return True if valid.

    Returns:
        Selected deployment index, or None if cancelled/invalid.
    """
    if menu_system is None:
        return None

    # Apply filter if provided
    if filter_func:
        filtered = filter_func(deployments)
        if not filtered:
            if filter_message:
                print(filter_message)
            return None
    else:
        filtered = deployments

    # Create menu items
    items = create_deployment_menu_items(deployments)

    persistent_header = build_persistent_header()

    selected = menu_system.show_menu(
        items,
        prompt,
        persistent_header=persistent_header,
        is_main_menu=False,
    )

    if selected is None:
        return None

    # Validate selection if validation function provided
    if validation_func:
        if not validation_func(deployments, selected):
            return None

    return selected


def parse_deployment_number(args: List[str]) -> Optional[int]:
    """Parse deployment number from arguments.

    Returns the deployment number if valid, or prints error and returns None if invalid.
    """
    if not args:
        return None

    try:
        return int(args[0])
    except ValueError:
        print(f"Invalid deployment number: {args[0]}")
        return None


def execute_deployment_command(
    deployment_num: int,
    cmd_prefix: List[str],
    cmd_suffix: List[str],
) -> int:
    """Execute a command with the deployment number.

    Args:
        deployment_num: The deployment number to operate on.
        cmd_prefix: Command prefix without sudo (e.g., ["ostree", "admin"]).
        cmd_suffix: Command suffix (e.g., ["pin"]).

    Returns:
        Exit code from _run_command.
    """
    cmd = build_command(True, cmd_prefix) + cmd_suffix + [str(deployment_num)]
    return _run_command(cmd)


def handle_deployment_command(
    args: List[str],
    menu_system: Optional["MenuSystemProtocol"],
    select_func: Callable[[], Optional[int]],
    cmd_prefix: List[str],
    cmd_suffix: List[str],
) -> int:
    """Handle a deployment command with optional args or menu selection.

    Encapsulates the common pattern:
    - If args provided: parse deployment number
    - If no args: show menu and select deployment
    - Execute command with selected deployment

    Args:
        args: Command line arguments (deployment number or empty for menu mode).
        menu_system: MenuSystem instance for interactive selection.
        select_func: Callable that returns the selected deployment index.
            Called only when args is empty and menu_system is not None.
            Should return None if user cancels or no deployments available.
        cmd_prefix: Command prefix without sudo (e.g., ["ostree", "admin"]).
        cmd_suffix: Command suffix (e.g., ["pin"]).

    Returns:
        Exit code from _run_command, or 0 if cancelled/invalid.
    """
    deployment_num = None

    if args:
        deployment_num = parse_deployment_number(args)
        if deployment_num is None:
            return 1
    else:
        if menu_system is None:
            return 0

        deployment_num = select_func()
        if deployment_num is None:
            return 0

    if deployment_num is not None:
        return execute_deployment_command(deployment_num, cmd_prefix, cmd_suffix)
    return 0
