"""
Command definitions and registry for ublue-rebase-helper.
"""

import logging
import re
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

from .constants import format_version_header
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


class KargsSubcommand(StrEnum):
    """Enumeration of kargs subcommands."""

    APPEND = "append"
    DELETE = "delete"
    REPLACE = "replace"
    SHOW = "show"


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
            return False  # No args case is read-only (shows current kargs)

        # Check for help flags that are read-only operations
        help_flags = {"--help", "-h", "--help-all"}
        if any(arg in help_flags for arg in args):
            return False

        # First argument might be a subcommand
        if args[0] in {KargsSubcommand.SHOW}:
            return False

        # All modification subcommands (append, delete, replace) require sudo
        if args[0] in {
            KargsSubcommand.APPEND,
            KargsSubcommand.DELETE,
            KargsSubcommand.REPLACE,
        }:
            return True

        # Legacy mode: if no recognized subcommand, assume it's a direct rpm-ostree kargs argument
        # Direct modification flags require sudo
        modification_flags = {
            "--append",
            "--append-if-missing",
            "--delete",
            "--delete-if-present",
            "--replace",
            "--edit",
        }
        if any(
            arg.split("=")[0] in modification_flags or arg in modification_flags
            for arg in args
        ):
            return True

        # Default to no sudo for unknown cases (safer)
        return False

    def _handle_kargs(self, args: List[str]) -> None:
        """Handle the kargs command with subcommands."""
        if not args:
            # No arguments: show submenu for kargs operations
            try:
                from .models import ListItem

                items = [
                    ListItem("show", "Show current kernel arguments (read-only)"),
                    ListItem(
                        "append", "Append a kernel argument (--append-if-missing)"
                    ),
                    ListItem(
                        "delete", "Delete a kernel argument (--delete-if-present)"
                    ),
                    ListItem("replace", "Replace a kernel argument (--replace)"),
                ]

                # Get current deployment info for persistent header
                from .deployment import format_menu_header, get_current_deployment_info

                deployment_info = get_current_deployment_info()
                persistent_header = format_menu_header(
                    format_version_header(), deployment_info
                )

                selected = self._menu_system.show_menu(
                    items,
                    "Select kargs operation (ESC to cancel):",
                    persistent_header=persistent_header,
                    is_main_menu=False,
                )

                if selected is None:
                    return

                # Route to selected subcommand
                if selected == "show":
                    self._handle_kargs_show([])
                elif selected == "append":
                    self._prompt_and_handle_kargs_append()
                elif selected == "delete":
                    self._prompt_and_handle_kargs_delete()
                elif selected == "replace":
                    self._prompt_and_handle_kargs_replace()
            except MenuExitException:
                # ESC pressed in submenu, return to main menu
                return
            return

        # Check for help flags first
        help_flags = {"--help", "-h", "--help-all"}
        if any(arg in help_flags for arg in args):
            cmd = ["rpm-ostree", "kargs"] + args
            sys.exit(_run_command(cmd))
            return

        # Parse subcommand
        subcommand = args[0]

        if subcommand == KargsSubcommand.APPEND:
            self._handle_kargs_append(args[1:])
        elif subcommand == KargsSubcommand.DELETE:
            self._handle_kargs_delete(args[1:])
        elif subcommand == KargsSubcommand.REPLACE:
            self._handle_kargs_replace(args[1:])
        elif subcommand == KargsSubcommand.SHOW:
            self._handle_kargs_show(args[1:])
        else:
            # Legacy mode: pass arguments directly to rpm-ostree kargs
            run_command_with_conditional_sudo(
                ["rpm-ostree", "kargs"],
                args,
                requires_sudo=False,
                conditional_sudo_func=self._should_use_sudo_for_kargs,
            )

    def _prompt_for_karg_value(self, prompt_text: str) -> Optional[str]:
        """Prompt user for a kernel argument value."""
        try:
            from .menu import get_user_input

            return get_user_input(prompt_text)
        except KeyboardInterrupt:
            return None

    def _prompt_and_handle_kargs_append(self) -> None:
        """Prompt for kernel argument and handle append operation."""
        karg = self._prompt_for_karg_value(
            "Enter kernel argument (e.g., quiet or loglevel=3): "
        )
        if karg is None:
            return

        karg = karg.strip()
        if not karg:
            print("Error: No kernel argument provided")
            sys.exit(1)

        self._handle_kargs_append([karg])

    def _prompt_and_handle_kargs_delete(self) -> None:
        """Prompt for kernel argument key and handle delete operation."""
        karg = self._prompt_for_karg_value(
            "Enter kernel argument key to delete (e.g., quiet): "
        )
        if karg is None:
            return

        karg = karg.strip()
        if not karg:
            print("Error: No kernel argument key provided")
            sys.exit(1)

        self._handle_kargs_delete([karg])

    def _prompt_and_handle_kargs_replace(self) -> None:
        """Prompt for kernel argument replacement and handle replace operation."""
        karg = self._prompt_for_karg_value(
            "Enter kernel argument replacement (e.g., loglevel=3): "
        )
        if karg is None:
            return

        karg = karg.strip()
        if not karg:
            print("Error: No kernel argument provided")
            sys.exit(1)

        self._handle_kargs_replace([karg])

    def _handle_kargs_append(self, args: List[str]) -> None:
        """Handle kargs append subcommand with support for multiple arguments."""
        if not args:
            print("Error: append subcommand requires at least one key=value argument")
            print("Usage: urh kargs append <key=value> [key=value ...]")
            print("Example: urh kargs append quiet loglevel=3")
            sys.exit(1)
            return

        # Parse arguments: support both separate args and space-delimited in quotes
        kargs = self._parse_kargs_arguments(args)

        if not kargs:
            print("Error: No valid kernel arguments provided")
            sys.exit(1)
            return

        # Validate each argument
        for karg in kargs:
            if "=" not in karg and not karg.replace("_", "").replace("-", "").isalnum():
                print(f"Error: Invalid kernel argument format: {karg}")
                print("Usage: urh kargs append <key=value> [key=value ...]")
                sys.exit(1)
                return

        # Build command with multiple --append-if-missing flags
        cmd = ["sudo", "rpm-ostree", "kargs"]
        for karg in kargs:
            cmd.append(f"--append-if-missing={karg}")

        sys.exit(_run_command(cmd))

    def _handle_kargs_delete(self, args: List[str]) -> None:
        """Handle kargs delete subcommand with support for multiple arguments."""
        if not args:
            print("Error: delete subcommand requires at least one key argument")
            print("Usage: urh kargs delete <key> [key ...]")
            print("Example: urh kargs delete quiet loglevel")
            sys.exit(1)
            return

        # Parse arguments: support both separate args and space-delimited in quotes
        kargs = self._parse_kargs_arguments(args)

        if not kargs:
            print("Error: No valid kernel arguments provided")
            sys.exit(1)
            return

        # Validate each argument
        for karg in kargs:
            if not karg.replace("_", "").replace("-", "").replace(".", "").isalnum():
                print(f"Error: Invalid kernel argument key: {karg}")
                print("Usage: urh kargs delete <key> [key ...]")
                sys.exit(1)
                return

        # Build command with multiple --delete flags
        cmd = ["sudo", "rpm-ostree", "kargs"]
        for karg in kargs:
            cmd.append(f"--delete={karg}")

        sys.exit(_run_command(cmd))

    def _handle_kargs_replace(self, args: List[str]) -> None:
        """Handle kargs replace subcommand with support for multiple arguments."""
        if not args:
            print("Error: replace subcommand requires at least one old=new argument")
            print("Usage: urh kargs replace <old=new> [old=new ...]")
            print("Example: urh kargs replace loglevel=3")
            sys.exit(1)
            return

        # Parse arguments: support both separate args and space-delimited in quotes
        kargs = self._parse_kargs_arguments(args)

        if not kargs:
            print("Error: No valid kernel arguments provided")
            sys.exit(1)
            return

        # Validate each argument (must contain =)
        for karg in kargs:
            if "=" not in karg:
                print(f"Error: Invalid kernel argument format: {karg}")
                print("Usage: urh kargs replace <old=new> [old=new ...]")
                sys.exit(1)
                return

        # Build command with multiple --replace flags
        cmd = ["sudo", "rpm-ostree", "kargs"]
        for karg in kargs:
            cmd.append(f"--replace={karg}")

        sys.exit(_run_command(cmd))

    def _parse_kargs_arguments(self, args: List[str]) -> List[str]:
        """Parse kernel argument list, supporting space-delimited strings.

        This method handles both:
        - Multiple separate arguments: ['arg1', 'arg2', 'arg3']
        - Space-delimited in quotes: ['arg1 arg2 arg3']

        Args:
            args: List of arguments from command line

        Returns:
            Flattened list of individual kernel arguments
        """
        result = []
        for arg in args:
            # Split on whitespace to handle space-delimited arguments
            parts = arg.split()
            result.extend(parts)
        return result

    def _handle_kargs_show(self, args: List[str]) -> None:
        """Handle kargs show subcommand."""
        if args:
            print("Warning: show subcommand does not take arguments")

        cmd = ["rpm-ostree", "kargs"]
        sys.exit(_run_command(cmd))

    def _handle_rebase(self, args: List[str], skip_confirmation: bool = False) -> None:
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
                from .deployment import format_menu_header, get_current_deployment_info

                deployment_info = get_current_deployment_info()
                persistent_header = format_menu_header(
                    format_version_header(), deployment_info
                )

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
            # Parse the tag/URL argument
            url = args[0]

            # Check if this is a short tag that needs resolution
            resolved_url = self._resolve_tag_to_full_url(url, skip_confirmation)
            if resolved_url is None:
                # Resolution failed or was cancelled
                return
            url = resolved_url

        # Ensure the URL has the proper ostree prefix for rpm-ostree
        prefixed_url = ensure_ostree_prefix(url)
        cmd = ["sudo", "rpm-ostree", "rebase", prefixed_url]
        sys.exit(_run_command(cmd))

    def _resolve_tag_to_full_url(
        self, tag_or_url: str, skip_confirmation: bool = False
    ) -> Optional[str]:
        """
        Resolve a short tag (e.g., 'unstable') to a full URL.

        Supports syntax:
        - 'unstable' -> resolves to latest unstable tag from default repo
        - 'unstable-43.20260326.1' -> resolves to full URL with default repo
        - 'bazzite-nix-nvidia-open:testing' -> resolves to latest testing tag from specified repo variant
        - 'bazzite-nix-nvidia-open:unstable-43.20260326.1' -> full URL with specified repo
        - Full URLs (with ://) are returned as-is

        Shows confirmation prompt unless skip_confirmation is True.

        Args:
            tag_or_url: The tag or URL to resolve
            skip_confirmation: If True, skip the confirmation prompt

        Returns:
            The resolved full URL, or None if resolution failed/cancelled
        """
        from .config import get_config
        from .system import extract_repository_from_url

        config = get_config()

        # Get the base repository from the default URL (e.g., 'wombatfromhell/bazzite-nix')
        default_url = config.container_urls.default
        base_repository = extract_repository_from_url(default_url)

        # If it looks like a full URL (contains :// or starts with registry), return as-is
        if "://" in tag_or_url or tag_or_url.startswith(
            ("ghcr.io/", "docker.io/", "quay.io/", "gcr.io/")
        ):
            return tag_or_url

        # Check for repo suffix syntax: 'repo-suffix:tag'
        # e.g., 'bazzite-nix-nvidia-open:testing'
        repository = base_repository
        tag_part = tag_or_url
        repo_explicitly_specified = False

        if ":" in tag_or_url:
            # Split on the first colon to get repo suffix and tag
            parts = tag_or_url.split(":", 1)
            repo_suffix = parts[0]
            tag_part = parts[1]

            # If repo_suffix contains a slash, it's a full repo path
            if "/" in repo_suffix:
                repository = repo_suffix
                repo_explicitly_specified = True
            else:
                # Otherwise, it's a repo name (with optional suffix) to use with the base owner
                # e.g., base='wombatfromhell/bazzite-nix' + suffix='nvidia-open'
                # -> 'wombatfromhell/bazzite-nix-nvidia-open'
                # OR base='wombatfromhell/bazzite-nix' + suffix='bazzite-nix-nvidia-open'
                # -> 'wombatfromhell/bazzite-nix-nvidia-open'
                # Extract the owner from the base repository
                if "/" in base_repository:
                    owner, _ = base_repository.split("/", 1)
                    # Use the repo_suffix as the full repo name with the base owner
                    repository = f"{owner}/{repo_suffix}"
                else:
                    # No owner in base, use repo_suffix as-is
                    repository = repo_suffix
                repo_explicitly_specified = True

        # Check if this is a primary alias for the default repository
        # For default repo (wombatfromhell/bazzite-nix), aliases like 'testing' and 'unstable'
        # are maintained by the registry and point to the latest version
        # In this case, use the alias directly without client-side resolution
        #
        # Primary aliases are tags that match the default tag pattern for a repository
        # (e.g., 'testing', 'unstable', 'stable' for bazzite-nix)
        # These are maintained by the registry and always point to the latest version
        is_primary_alias = (
            not repo_explicitly_specified
            and repository == base_repository
            and tag_part in ("testing", "unstable", "stable", "latest")
        )

        if is_primary_alias:
            # Use the alias directly - registry maintains the pointer
            # Still show confirmation since repo is implicit
            if not skip_confirmation:
                full_url = f"ghcr.io/{repository}:{tag_part}"
                print(f"Using target: {full_url}")
                try:
                    from .menu import get_user_input

                    response = get_user_input(
                        f'Confirm rebase to "{tag_part}"? [y/N]: '
                    )
                    if response.lower() != "y":
                        print("Rebase cancelled.")
                        sys.exit(0)
                        return None
                except KeyboardInterrupt:
                    print("\nRebase cancelled.")
                    sys.exit(0)
                    return None

            return f"ghcr.io/{repository}:{tag_part}"

        # Check if we need to resolve a short tag to the latest version
        # For primary aliases on the default repo, we use the registry pointer directly
        # For explicitly specified repos, we still resolve to find the latest version
        needs_resolution = not re.search(r"-\d+\.\d+", tag_part)

        if needs_resolution:
            # This is a short tag like 'unstable', 'stable', 'testing'
            # Fetch available tags and find matches
            # Create OCI client and fetch tags
            client = OCIClient(repository)
            tags_data = client.fetch_repository_tags(f"ghcr.io/{repository}")

            if not tags_data or "tags" not in tags_data:
                logger.error(f"Could not fetch tags for {repository}")
                print(f"Error: Could not fetch tags for {repository}")
                sys.exit(1)
                return None

            all_tags = tags_data["tags"]

            # Find tags that start with the short tag followed by '-' or match exactly
            # e.g., 'unstable' matches 'unstable-43.20260326.1', 'unstable-43.20260325.0', etc.
            matching_tags = []
            for t in all_tags:
                if t == tag_part or t.startswith(f"{tag_part}-"):
                    matching_tags.append(t)

            if not matching_tags:
                print(f"Error: No tags found matching '{tag_part}'")
                sys.exit(1)
                return None

            # Sort tags to get the latest version first
            # Tags are expected to be in format: <context>-<XX>.<YYYYMMDD>.<SUBVER>
            # Sort by the version part (after the context prefix)
            def extract_version_for_sort(t: str) -> tuple:
                """Extract version tuple for sorting (series, date, subver)."""
                # Remove context prefix if present
                version_part = t
                for prefix in ["unstable-", "stable-", "testing-", "latest."]:
                    if t.startswith(prefix):
                        version_part = t[len(prefix) :]
                        break

                # Parse version: XX.YYYYMMDD.SUBVER or XX.YYYYMMDD or YYYYMMDD.SUBVER
                parts = version_part.split(".")
                try:
                    if len(parts) >= 3:
                        series = int(parts[0])
                        date = int(parts[1])
                        subver = int(parts[2]) if parts[2].isdigit() else 0
                    elif len(parts) == 2:
                        # Could be XX.YYYYMMDD or YYYYMMDD.SUBVER
                        if len(parts[0]) == 8 and parts[0].isdigit():
                            # YYYYMMDD format
                            series = 0
                            date = int(parts[0])
                            subver = int(parts[1]) if parts[1].isdigit() else 0
                        else:
                            series = int(parts[0])
                            date = int(parts[1])
                            subver = 0
                    elif len(parts) == 1 and parts[0].isdigit():
                        # Just a number
                        series = 0
                        date = int(parts[0])
                        subver = 0
                    else:
                        series = 0
                        date = 0
                        subver = 0
                except (ValueError, IndexError):
                    series = 0
                    date = 0
                    subver = 0

                return (series, date, subver)

            # Sort descending (latest first)
            matching_tags.sort(key=extract_version_for_sort, reverse=True)
            latest_tag = matching_tags[0]

            # Build the full URL
            full_url = f"ghcr.io/{repository}:{latest_tag}"

            # Show confirmation if there are multiple matches or if skip_confirmation is False
            if len(matching_tags) > 1 and not skip_confirmation:
                print(f"Tag '{tag_part}' matches {len(matching_tags)} available tags:")
                for t in matching_tags[:10]:  # Show first 10
                    print(f"  - {t}")
                if len(matching_tags) > 10:
                    print(f"  ... and {len(matching_tags) - 10} more")
                print(f"\nResolving to: {latest_tag}")

                try:
                    from .menu import get_user_input

                    response = get_user_input(
                        f"Confirm rebase to {latest_tag}? [y/N]: "
                    )
                    if response.lower() != "y":
                        print("Rebase cancelled.")
                        sys.exit(0)
                        return None
                except KeyboardInterrupt:
                    print("\nRebase cancelled.")
                    sys.exit(0)
                    return None
            elif not skip_confirmation:
                # Single match, still confirm
                print(f"Resolving '{tag_part}' to: {latest_tag}")
                try:
                    from .menu import get_user_input

                    response = get_user_input(
                        f"Confirm rebase to {latest_tag}? [y/N]: "
                    )
                    if response.lower() != "y":
                        print("Rebase cancelled.")
                        sys.exit(0)
                        return None
                except KeyboardInterrupt:
                    print("\nRebase cancelled.")
                    sys.exit(0)
                    return None

            return full_url
        else:
            # This is a complete tag like 'unstable-43.20260326.1'
            # Just add the repository prefix, but confirm if repo was implicit
            full_url = f"ghcr.io/{repository}:{tag_part}"

            # Show confirmation if repository was not explicitly specified
            if not repo_explicitly_specified and not skip_confirmation:
                print(f"Using target: {full_url}")
                try:
                    from .menu import get_user_input

                    response = get_user_input(
                        f'Confirm rebase to "{tag_part}"? [y/N]: '
                    )
                    if response.lower() != "y":
                        print("Rebase cancelled.")
                        sys.exit(0)
                        return None
                except KeyboardInterrupt:
                    print("\nRebase cancelled.")
                    sys.exit(0)
                    return None

            return full_url

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
        from .deployment import format_menu_header, get_current_deployment_info
        from .models import ListItem

        # Show submenu using ListItem instead of MenuItem
        options: List[str] = list(config.container_urls.options)
        items = [ListItem("", url, url) for url in options]

        # Get current deployment info for persistent header
        deployment_info = get_current_deployment_info()
        persistent_header = format_menu_header(format_version_header(), deployment_info)

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

        # Get persistent header with version and deployment info
        from .deployment import (
            format_menu_header,
            get_current_deployment_info,
        )

        deployment_info = get_current_deployment_info()
        persistent_header = format_menu_header(format_version_header(), deployment_info)

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
        from .deployment import (
            format_menu_header,
            get_current_deployment_info,
        )
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
        deployment_info = get_current_deployment_info()
        persistent_header = format_menu_header(format_version_header(), deployment_info)

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
                from .deployment import format_menu_header, get_current_deployment_info

                deployment_info = get_current_deployment_info()
                persistent_header = format_menu_header(
                    format_version_header(), deployment_info
                )

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

        # Get persistent header with version and deployment info
        from .deployment import (
            format_menu_header,
            get_current_deployment_info,
        )

        deployment_info = get_current_deployment_info()
        persistent_header = format_menu_header(format_version_header(), deployment_info)

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
