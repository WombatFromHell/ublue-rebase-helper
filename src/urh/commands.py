"""
Command definitions and registry for ublue-rebase-helper.
"""

import logging
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import (
    Callable,
    Dict,
    Generic,
    List,
    LiteralString,
    Optional,
    TypeVar,
)
from typing import Optional as OptionalType

from .menu import MenuExitException, MenuSystem, _menu_system
from .oci_client import OCIClient
from .system import ensure_ostree_prefix

# Set up logging
logger = logging.getLogger(__name__)


# Type for functions that determine if sudo is required based on arguments
SudoConditionFunc = Callable[[List[str]], bool]


class CommandType(StrEnum):
    """Enumeration of available commands."""

    CHECK = "check"
    KARGS = "kargs"
    LS = "ls"
    PIN = "pin"
    REBASE = "rebase"
    REMOTE_LS = "remote-ls"
    RM = "rm"
    ROLLBACK = "rollback"
    UNPIN = "unpin"
    UPGRADE = "upgrade"


@dataclass(slots=True, kw_only=True)
class CommandDefinition:
    """Definition of a command."""

    name: str
    description: str
    handler: Callable[[List[str]], None]
    requires_sudo: bool = False
    conditional_sudo_func: Optional[SudoConditionFunc] = (
        None  # Function to determine sudo conditionally when needed
    )
    has_submenu: bool = False


T = TypeVar("T")


def run_command_with_conditional_sudo(
    base_cmd: List[str],
    args: List[str],
    requires_sudo: bool,
    conditional_sudo_func: Optional[SudoConditionFunc] = None,
) -> None:
    """Execute a command with conditional sudo based on the requires_sudo setting."""
    # Determine if sudo is needed
    if conditional_sudo_func is not None:
        # Use the conditional function to determine if sudo is needed
        needs_sudo = conditional_sudo_func(args)
    else:
        # Use the static boolean value
        needs_sudo = requires_sudo

    # Build the command
    if needs_sudo:
        cmd = ["sudo", *base_cmd]
    else:
        cmd = base_cmd[:]

    cmd.extend(args)

    sys.exit(_run_command(cmd))


def _run_command(cmd: List[str], timeout: Optional[int] = None) -> int:
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


def run_command_safe(
    base_cmd: LiteralString, *args: str, timeout: Optional[int] = 300
) -> int:
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


class ArgumentParser(Generic[T]):
    """Generic argument parser with validation."""

    def parse_or_prompt(
        self,
        args: List[str],
        prompt_func: Callable[[], OptionalType[T]],
        validator: OptionalType[Callable[[str], T]] = None,
    ) -> OptionalType[T]:
        """Parse argument or show prompt if not provided."""
        if not args:
            try:
                return prompt_func()
            except MenuExitException:
                return None

        if validator:
            try:
                return validator(args[0])
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid argument: {e}")
                print(f"Invalid argument: {e}")
                sys.exit(1)

        # If no validator provided, return the raw argument
        # This might need to be handled differently based on your needs
        if args:
            return args[0]  # type: ignore
        return None


class CommandRegistry:
    """Registry for all available commands."""

    def __init__(self, menu_system: Optional[MenuSystem] = None):
        self._menu_system = menu_system or _menu_system
        self._commands: Dict[str, CommandDefinition] = {}
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands."""
        self._commands = {
            "check": CommandDefinition(
                name="check",
                description="Check for available updates",
                handler=self._handle_check,
                requires_sudo=False,
            ),
            "kargs": CommandDefinition(
                name="kargs",
                description="Manage kernel arguments (kargs)",
                handler=self._handle_kargs,
                requires_sudo=False,  # Default value for compatibility with tests
                conditional_sudo_func=self._should_use_sudo_for_kargs,  # Use function for conditional sudo
            ),
            "ls": CommandDefinition(
                name="ls",
                description="List deployments with details",
                handler=self._handle_ls,
                requires_sudo=False,
            ),
            "rebase": CommandDefinition(
                name="rebase",
                description="Rebase to a container image",
                handler=self._handle_rebase,
                requires_sudo=True,
                has_submenu=True,
            ),
            "remote-ls": CommandDefinition(
                name="remote-ls",
                description="List available tags for a container image",
                handler=self._handle_remote_ls,
                requires_sudo=False,
                has_submenu=True,
            ),
            "upgrade": CommandDefinition(
                name="upgrade",
                description="Upgrade to the latest version",
                handler=self._handle_upgrade,
                requires_sudo=True,
            ),
            "rollback": CommandDefinition(
                name="rollback",
                description="Roll back to the previous deployment",
                handler=self._handle_rollback,
                requires_sudo=True,
            ),
            "pin": CommandDefinition(
                name="pin",
                description="Pin a deployment",
                handler=self._handle_pin,
                requires_sudo=True,
                has_submenu=True,
            ),
            "unpin": CommandDefinition(
                name="unpin",
                description="Unpin a deployment",
                handler=self._handle_unpin,
                requires_sudo=True,
                has_submenu=True,
            ),
            "rm": CommandDefinition(
                name="rm",
                description="Remove a deployment",
                handler=self._handle_rm,
                requires_sudo=True,
                has_submenu=True,
            ),
            "undeploy": CommandDefinition(
                name="undeploy",
                description="Remove a deployment by index",
                handler=self._handle_undeploy,
                requires_sudo=True,
                has_submenu=True,
            ),
        }

    def get_commands(self) -> List[CommandDefinition]:
        """Get all registered commands."""
        return list(self._commands.values())

    def get_command(self, name: str) -> Optional[CommandDefinition]:
        """Get a specific command by name."""
        return self._commands.get(name)

    def _handle_check(self, args: List[str]) -> None:
        """Handle the check command."""
        cmd = ["rpm-ostree", "upgrade", "--check"]
        exit_code = _run_command(cmd)
        sys.exit(exit_code)

    def _handle_ls(self, args: List[str]) -> None:
        """Handle the ls command."""
        # Get the status output and display it
        try:
            result = subprocess.run(
                ["rpm-ostree", "status", "-v"],
                capture_output=True,
                text=True,
                check=True,
            )
            print(result.stdout)
            sys.exit(0)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error getting status: {e}")
            sys.exit(1)

    def _should_use_sudo_for_kargs(self, args: List[str]) -> bool:
        """Determine if sudo should be used for kargs command based on arguments."""
        if not args:
            return False  # No args case is read-only

        # Check for help flags that are read-only operations
        help_flags = {"--help", "-h", "--help-all"}
        if any(arg in help_flags for arg in args):
            return False

        # Check for other potentially read-only operations (like just listing current)
        # If args contain only flags for inspection (not modification), return False
        # For kargs, typically modification operations involve --append, --delete, etc.
        # while inspection operations like --help don't need sudo
        return True  # Default to using sudo for any other argument combinations

    def _handle_kargs(self, args: List[str]) -> None:
        """Handle the kargs command."""
        # Use the general conditional sudo mechanism
        run_command_with_conditional_sudo(
            ["rpm-ostree", "kargs"],
            args,
            requires_sudo=False,  # This value is ignored when conditional_sudo_func is provided
            conditional_sudo_func=self._should_use_sudo_for_kargs,
        )

    def _handle_rebase(self, args: List[str]) -> None:
        """Handle the rebase command."""
        from .config import get_config

        config = get_config()

        if not args:
            try:
                # Show submenu using ListItem instead of MenuItem
                from .models import ListItem  # Import here to avoid circular import

                options: List[str] = list(config.container_urls.options)
                items = [ListItem("", url, url) for url in options]

                # Get current deployment info for persistent header
                from .deployment import (
                    format_deployment_header,
                    get_current_deployment_info,
                )

                deployment_info_header = get_current_deployment_info()
                persistent_header = format_deployment_header(deployment_info_header)

                selected = self._menu_system.show_menu(
                    items,
                    "Select container image (ESC to cancel):",
                    persistent_header=persistent_header,
                    is_main_menu=False,
                )

                if selected is None:
                    return

                url = selected
            except MenuExitException as _:
                # ESC pressed in submenu, return to main menu
                return
        else:
            url = args[0]

        # Ensure the URL has the proper ostree prefix for rpm-ostree
        prefixed_url = ensure_ostree_prefix(url)
        cmd = ["sudo", "rpm-ostree", "rebase", prefixed_url]
        sys.exit(_run_command(cmd))

    def _handle_remote_ls(self, args: List[str]) -> None:
        """Handle the remote-ls command."""
        from .config import get_config

        config = get_config()
        url = self._get_url_for_remote_ls(args, config)

        if url is None:
            return  # User cancelled selection

        self._display_tags_for_url(url)

    def _get_url_for_remote_ls(self, args: List[str], config) -> Optional[str]:
        """Get URL from arguments or user selection for remote-ls."""
        if not args:
            try:
                return self._select_url_for_remote_ls(config)
            except MenuExitException:
                # ESC pressed in submenu, return to main menu
                return None
        else:
            return args[0]

    def _select_url_for_remote_ls(self, config) -> Optional[str]:
        """Show menu to select URL for remote-ls."""
        from .deployment import format_deployment_header, get_current_deployment_info
        from .models import ListItem

        # Show submenu using ListItem instead of MenuItem
        options: List[str] = list(config.container_urls.options)
        items = [ListItem("", url, url) for url in options]

        # Get current deployment info for persistent header
        deployment_info_header = get_current_deployment_info()
        persistent_header = format_deployment_header(deployment_info_header)

        selected = self._menu_system.show_menu(
            items,
            "Select container image (ESC to cancel):",
            persistent_header=persistent_header,
            is_main_menu=False,
        )

        return selected

    def _display_tags_for_url(self, url: str) -> None:
        """Display tags for the given URL."""
        from .system import extract_repository_from_url

        # Extract repository from URL
        repository = extract_repository_from_url(url)

        # Create OCI client and fetch tags
        client = OCIClient(repository)
        tags_data = client.fetch_repository_tags(url)

        if tags_data and "tags" in tags_data and tags_data["tags"]:
            print(f"Tags for {url}:")  # Keep print for user output of the actual tags
            for tag in tags_data["tags"]:
                print(f"  {tag}")
            sys.exit(0)  # Exit with success code after successful completion
        elif tags_data and "tags" in tags_data and not tags_data["tags"]:
            # No tags found
            logger.info(f"No tags found for {url}")
            print(f"No tags found for {url}")  # Print for user visibility
            sys.exit(0)
        else:
            # Error occurred
            logger.error(f"Could not fetch tags for {url}")
            print(f"Could not fetch tags for {url}")  # Print for user visibility
            sys.exit(1)

    def _handle_upgrade(self, args: List[str]) -> None:
        """Handle the upgrade command."""
        cmd = ["sudo", "rpm-ostree", "upgrade"]
        sys.exit(_run_command(cmd))

    def _handle_rollback(self, args: List[str]) -> None:
        """Handle the rollback command."""
        cmd = ["sudo", "rpm-ostree", "rollback"]
        sys.exit(_run_command(cmd))

    def _handle_pin(self, args: List[str]) -> None:
        """Handle the pin command."""
        deployment_num = None

        if args:
            # When arguments are provided, we don't need deployment info
            try:
                deployment_num = int(args[0])
            except ValueError:
                print(
                    f"Invalid deployment number: {args[0]}"
                )  # Keep as print for test compatibility
                sys.exit(1)
        else:
            # When no arguments are provided, show menu and get deployment info
            from .deployment import get_deployment_info

            deployments = get_deployment_info()
            if not deployments:
                print("No deployments found.")  # Keep as print for test compatibility
                return

            deployment_num = self._get_deployment_number_for_pin(args, deployments)

            if deployment_num is None:
                return  # User cancelled or invalid input

        if deployment_num is not None:
            cmd = ["sudo", "ostree", "admin", "pin", str(deployment_num)]
            sys.exit(_run_command(cmd))

    def _get_deployment_number_for_pin(
        self, args: List[str], deployments: List
    ) -> Optional[int]:
        """Get deployment number from arguments or user selection for pinning."""

        if not args:
            try:
                return self._select_deployment_to_pin(deployments)
            except MenuExitException:
                # ESC pressed in submenu, return to main menu
                return None
        else:
            try:
                return int(args[0])
            except ValueError:
                print(
                    f"Invalid deployment number: {args[0]}"
                )  # Keep as print for test compatibility
                sys.exit(1)

    def _filter_unpinned_deployments(self, deployments: List) -> List:
        """Filter deployments to get only unpinned ones."""
        return [d for d in deployments if not d.is_pinned]

    def _create_deployment_menu_items(self, deployments: List) -> List:
        """Create menu items for deployment selection."""
        from .models import ListItem

        # Show ALL deployments in ascending order (newest first)
        # This allows users to see which deployments are already pinned
        all_deployments = deployments[::-1]  # Reverse order to show newest first

        return [
            ListItem(
                "",
                f"{d.repository} ({d.version}) ({d.deployment_index}{'*' if d.is_pinned else ''})",
                d.deployment_index,
            )
            for d in all_deployments
        ]

    def _get_deployment_header(self) -> str:
        """Get current deployment info for persistent header."""
        from .deployment import format_deployment_header, get_current_deployment_info

        deployment_info_header = get_current_deployment_info()
        return format_deployment_header(deployment_info_header)

    def _validate_deployment_not_pinned(
        self, deployments: List, selected_index: int
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

    def _select_deployment_to_pin(self, deployments: List) -> Optional[int]:
        """Show menu to select deployment for pinning."""
        # Check if there are any unpinned deployments first
        unpinned_deployments = self._filter_unpinned_deployments(deployments)

        if not unpinned_deployments:
            print("No deployments available to pin.")  # Keep this user-facing message
            return None

        # Create menu items
        items = self._create_deployment_menu_items(deployments)

        # Get persistent header
        persistent_header = self._get_deployment_header()

        # Show menu and get selection
        selected = self._menu_system.show_menu(
            items,
            "Select deployment to pin (ESC to cancel):",
            persistent_header=persistent_header,
            is_main_menu=False,
        )

        if selected is None:
            return None

        # Validate selection
        if not self._validate_deployment_not_pinned(deployments, selected):
            return None

        return selected

    def _handle_unpin(self, args: List[str]) -> None:
        """Handle the unpin command."""
        deployment_num = None

        if args:
            # When arguments are provided, we don't need deployment info
            try:
                deployment_num = int(args[0])
            except ValueError:
                print(
                    f"Invalid deployment number: {args[0]}"
                )  # Keep as print for test compatibility
                sys.exit(1)
        else:
            # When no arguments are provided, show menu and get deployment info
            from .deployment import get_deployment_info

            deployments = get_deployment_info()
            if not deployments:
                print("No deployments found.")  # Keep as print for test compatibility
                return

            deployment_num = self._get_deployment_number_for_unpin(args, deployments)

            if deployment_num is None:
                return  # User cancelled or invalid input

        if deployment_num is not None:
            cmd = ["sudo", "ostree", "admin", "pin", "-u", str(deployment_num)]
            sys.exit(_run_command(cmd))

    def _get_deployment_number_for_unpin(
        self, args: List[str], deployments: List
    ) -> Optional[int]:
        """Get deployment number from arguments or user selection for unpinning."""
        if not args:
            try:
                return self._select_deployment_to_unpin(deployments)
            except MenuExitException:
                # ESC pressed in submenu, return to main menu
                return None
        else:
            try:
                return int(args[0])
            except ValueError:
                print(
                    f"Invalid deployment number: {args[0]}"
                )  # Keep as print for test compatibility
                sys.exit(1)

    def _select_deployment_to_unpin(self, deployments: List) -> Optional[int]:
        """Show menu to select deployment for unpinning."""
        from .deployment import format_deployment_header, get_current_deployment_info
        from .models import ListItem

        # Show only pinned deployments
        pinned_deployments = [d for d in deployments if d.is_pinned]

        if not pinned_deployments:
            print("No deployments are pinned.")
            return None

        items = [
            ListItem(
                "",
                f"{d.repository} ({d.version}) ({d.deployment_index}*)",
                d.deployment_index,
            )
            for d in pinned_deployments
        ]

        # Get current deployment info for persistent header
        deployment_info_header = get_current_deployment_info()
        persistent_header = format_deployment_header(deployment_info_header)

        selected = self._menu_system.show_menu(
            items,
            "Select deployment to unpin (ESC to cancel):",
            persistent_header=persistent_header,
            is_main_menu=False,
        )

        return selected

    def _handle_rm(self, args: List[str]) -> None:
        """Handle the rm command."""
        deployment_num = None  # Initialize variable

        if not args:
            # When no arguments are provided, show menu and get deployment info
            from .deployment import get_deployment_info

            deployments = get_deployment_info()
            if not deployments:
                print("No deployments found.")  # Keep as print for test compatibility
                return

            try:
                from .models import ListItem  # Import here to avoid circular import

                items = [
                    ListItem(
                        "",
                        f"{d.repository} ({d.version}) ({d.deployment_index}{'*' if d.is_pinned else ''})",
                        d.deployment_index,
                    )
                    for d in deployments
                ][::-1]

                # Get current deployment info for persistent header
                from .deployment import (
                    format_deployment_header,
                    get_current_deployment_info,
                )

                deployment_info_header = get_current_deployment_info()
                persistent_header = format_deployment_header(deployment_info_header)

                selected = self._menu_system.show_menu(
                    items,
                    "Select deployment to remove (ESC to cancel):",
                    persistent_header=persistent_header,
                    is_main_menu=False,
                )

                if selected is None:
                    return

                deployment_num = selected
            except MenuExitException as _:
                # ESC pressed in submenu, return to main menu
                return
        else:
            # When arguments are provided, we don't need deployment info
            try:
                deployment_num = int(args[0])
            except ValueError:
                print(
                    f"Invalid deployment number: {args[0]}"
                )  # Keep as print for test compatibility
                sys.exit(1)
                return  # Exit after error to avoid executing the command

        if deployment_num is not None:
            cmd = ["sudo", "rpm-ostree", "cleanup", "-r", str(deployment_num)]
            from .commands import _run_command

            sys.exit(_run_command(cmd))

    def _handle_undeploy(self, args: List[str]) -> None:
        """Handle the undeploy command."""
        deployment_num = None

        if args:
            # When arguments are provided, we don't need deployment info
            try:
                deployment_num = int(args[0])
            except ValueError:
                print(
                    f"Invalid deployment number: {args[0]}"
                )  # Keep as print for test compatibility
                sys.exit(1)
        else:
            # When no arguments are provided, show menu and get deployment info
            from .deployment import get_deployment_info

            deployments = get_deployment_info()
            if not deployments:
                print("No deployments found.")  # Keep as print for test compatibility
                return

            deployment_num = self._get_deployment_number_for_undeploy(args, deployments)

            if deployment_num is None:
                return  # User cancelled or invalid input

        if deployment_num is not None:
            cmd = ["sudo", "ostree", "admin", "undeploy", str(deployment_num)]
            sys.exit(_run_command(cmd))

    def _get_deployment_number_for_undeploy(
        self, args: List[str], deployments: List
    ) -> Optional[int]:
        """Get deployment number from arguments or user selection for undeploying."""
        if not args:
            try:
                return self._select_deployment_to_undeploy_with_confirmation(
                    deployments
                )
            except MenuExitException:
                # ESC pressed in submenu, return to main menu
                return None
        else:
            try:
                return int(args[0])
            except ValueError:
                print(
                    f"Invalid deployment number: {args[0]}"
                )  # Keep as print for test compatibility
                sys.exit(1)

    def _create_undeploy_confirmation_items(self) -> List:
        """Create confirmation menu items for undeploy operation."""
        from .models import MenuItem

        return [
            MenuItem("Y", "Yes, undeploy this deployment"),
            MenuItem("N", "No, cancel undeployment"),
        ]

    def _get_undeploy_confirmation_header(self, deployment) -> str:
        """Get confirmation header for undeploy operation."""
        return f"Confirm undeployment of:\n  {deployment.repository} ({deployment.version}) ({deployment.deployment_index}{'*' if deployment.is_pinned else ''})"

    def _get_selected_deployment_info(self, deployments: List, selected_index: int):
        """Get deployment info for the selected deployment index."""
        all_deployments = deployments[::-1]  # Reverse order to show newest first
        return next(
            (d for d in all_deployments if d.deployment_index == selected_index),
            None,
        )

    def _select_deployment_to_undeploy_with_confirmation(
        self, deployments: List
    ) -> Optional[int]:
        """Show menu to select deployment for undeploying with confirmation."""

        # Create menu items using existing helper
        items = self._create_deployment_menu_items(deployments)

        # Get persistent header using existing helper
        persistent_header = self._get_deployment_header()

        while True:  # Loop to return to selection if user cancels
            selected = self._menu_system.show_menu(
                items,
                "Select deployment to undeploy (ESC to cancel):",
                persistent_header=persistent_header,
                is_main_menu=False,
            )

            if selected is None:
                return None

            deployment_num = selected

            # Get deployment info for confirmation message
            selected_deployment = self._get_selected_deployment_info(
                deployments, selected
            )

            if selected_deployment:
                # Create confirmation items
                confirmation_items = self._create_undeploy_confirmation_items()

                # Create confirmation header
                confirmation_header = self._get_undeploy_confirmation_header(
                    selected_deployment
                )

                confirmation = self._menu_system.show_menu(
                    confirmation_items,
                    confirmation_header,
                    persistent_header=persistent_header,
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
