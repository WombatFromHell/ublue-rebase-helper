"""
Kargs command handler with subcommands: show, append, delete, replace.

Supports both menu-driven (no args) and CLI-driven (with subcommand args) modes.
"""

from typing import Any, Callable, List, Optional

from ..commands.deployment_helpers import MenuSystemProtocol
from ..deployment import build_persistent_header
from ..menu import MenuExitException
from ..system import _run_command, build_command
from .shared import KargsSubcommand


def should_use_sudo_for_kargs(args: List[str]) -> bool:
    """Determine if sudo should be used for kargs command based on arguments."""
    if not args:
        return False

    help_flags = {"--help", "-h", "--help-all"}
    if any(arg in help_flags for arg in args):
        return False

    if args[0] in {KargsSubcommand.SHOW}:
        return False

    if args[0] in {
        KargsSubcommand.APPEND,
        KargsSubcommand.DELETE,
        KargsSubcommand.REPLACE,
    }:
        return True

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

    return False


def _prompt_for_karg_value(prompt_text: str) -> Optional[str]:
    """Prompt user for a kernel argument value."""
    try:
        from ..menu import get_user_input

        return get_user_input(prompt_text)
    except KeyboardInterrupt:
        return None


def _parse_kargs_arguments(args: List[str]) -> List[str]:
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
        parts = arg.split()
        result.extend(parts)
    return result


def _handle_kargs_show(args: List[str]) -> int:
    """Handle kargs show subcommand."""
    if args:
        print("Warning: show subcommand does not take arguments")

    cmd = ["rpm-ostree", "kargs"]
    return _run_command(cmd)


def _execute_kargs_subcommand(
    args: List[str],
    subcommand_name: str,
    validator: Callable[[str], bool],
    flag_builder: Callable[[str], str],
    requires_sudo: bool = True,
) -> int:
    """Execute a kargs subcommand with shared validation and command building logic.

    Args:
        args: Command line arguments.
        subcommand_name: Name of subcommand for error messages.
        validator: Function that validates a single karg string.
        flag_builder: Function that builds the flag string from a karg.
        requires_sudo: Whether the command requires sudo.

    Returns:
        Exit code from _run_command.
    """
    if not args:
        print(f"Error: {subcommand_name} subcommand requires at least one argument")
        print(f"Usage: urh kargs {subcommand_name} <argument> [argument ...]")
        return 1

    kargs = _parse_kargs_arguments(args)

    if not kargs:
        print("Error: No valid kernel arguments provided")
        return 1

    for karg in kargs:
        if not validator(karg):
            print(f"Error: Invalid kernel argument format: {karg}")
            print(f"Usage: urh kargs {subcommand_name} <argument> [argument ...]")
            return 1

    base_cmd = build_command(requires_sudo, ["rpm-ostree", "kargs"])
    cmd = base_cmd + [flag_builder(karg) for karg in kargs]

    return _run_command(cmd)


# Subcommand configuration: (validator, flag_builder) per operation.
_APPEND: tuple[Callable[[str], bool], Callable[[str], str]] = (
    lambda k: "=" in k or k.replace("_", "").replace("-", "").isalnum(),
    lambda k: f"--append-if-missing={k}",
)
_DELETE: tuple[Callable[[str], bool], Callable[[str], str]] = (
    lambda k: k.replace("_", "").replace("-", "").replace(".", "").isalnum(),
    lambda k: f"--delete={k}",
)
_REPLACE: tuple[Callable[[str], bool], Callable[[str], str]] = (
    lambda k: "=" in k,
    lambda k: f"--replace={k}",
)

_SUBCOMMAND_HANDLERS = {
    KargsSubcommand.APPEND: lambda a: _execute_kargs_subcommand(a, "append", *_APPEND),
    KargsSubcommand.DELETE: lambda a: _execute_kargs_subcommand(a, "delete", *_DELETE),
    KargsSubcommand.REPLACE: lambda a: _execute_kargs_subcommand(
        a, "replace", *_REPLACE
    ),
}


def _prompt_and_handle(
    prompt_text: str,
    handler: Callable[[str], int],
    error_message: str,
) -> int:
    """Prompt for a karg value and delegate to the given handler.

    Args:
        prompt_text: Text to display when prompting the user.
        handler: Function that processes the karg string and returns an exit code.
        error_message: Message to display when input is empty.

    Returns:
        Exit code from the handler (0 on cancel, handler's return code otherwise).
    """
    karg = _prompt_for_karg_value(prompt_text)
    if karg is None:
        return 0

    karg = karg.strip()
    if not karg:
        print(f"Error: {error_message}")
        return 1

    return handler(karg)


def _build_kargs_menu_items() -> List[Any]:
    """Build menu items for the kargs submenu."""
    from ..models import ListItem

    return [
        ListItem("show", "Show current kernel arguments (read-only)"),
        ListItem("append", "Append a kernel argument (--append-if-missing)"),
        ListItem("delete", "Delete a kernel argument (--delete-if-present)"),
        ListItem("replace", "Replace a kernel argument (--replace)"),
    ]


def handle_kargs(
    args: List[str], menu_system: Optional[MenuSystemProtocol] = None
) -> int:
    """Handle the kargs command with subcommands.

    Args:
        args: Command line arguments (empty for menu mode).
        menu_system: MenuSystem instance for interactive selection.
    """
    if not args:
        if menu_system is None:
            return 0

        try:
            persistent_header = build_persistent_header()
            items = _build_kargs_menu_items()

            selected = menu_system.show_menu(
                items,
                "Select kargs operation (ESC to cancel):",
                persistent_header=persistent_header,
                is_main_menu=False,
            )

            if selected is None:
                return 0

            _route_menu_selection(selected)
        except MenuExitException:
            return 0
        return 0

    help_flags = {"--help", "-h", "--help-all"}
    if any(arg in help_flags for arg in args):
        cmd = ["rpm-ostree", "kargs"] + args
        return _run_command(cmd)

    subcommand = args[0]
    handler = _SUBCOMMAND_HANDLERS.get(subcommand)

    if handler:
        return handler(args[1:])

    if subcommand == KargsSubcommand.SHOW:
        return _handle_kargs_show(args[1:])

    return _run_legacy(args)


def _route_menu_selection(selected: str) -> int:
    """Route a menu selection to the appropriate handler."""
    if selected == "show":
        return _handle_kargs_show([])

    prompt_map: dict[str, str] = {
        "append": "Enter kernel argument (e.g., quiet or loglevel=3): ",
        "delete": "Enter kernel argument key to delete (e.g., quiet): ",
        "replace": "Enter kernel argument replacement (e.g., loglevel=3): ",
    }
    error_map: dict[str, str] = {
        "append": "No kernel argument provided",
        "delete": "No kernel argument key provided",
        "replace": "No kernel argument provided",
    }
    config_map: dict[str, tuple[Callable[[str], bool], Callable[[str], str]]] = {
        "append": _APPEND,
        "delete": _DELETE,
        "replace": _REPLACE,
    }

    return _prompt_and_handle(
        prompt_map[selected],
        lambda k: _execute_kargs_subcommand([k], selected, *config_map[selected]),
        error_map[selected],
    )


def _run_legacy(args: List[str]) -> int:
    """Run legacy mode: pass arguments directly to rpm-ostree kargs."""
    from .shared import run_command_with_conditional_sudo

    return run_command_with_conditional_sudo(
        ["rpm-ostree", "kargs"],
        args,
        requires_sudo=False,
        conditional_sudo_func=should_use_sudo_for_kargs,
    )
