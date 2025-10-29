#!/usr/bin/env python3
# pyright: strict

import subprocess
import sys
import os
from typing import List, Optional, Callable, Dict, Any


def run_command(cmd: List[str]) -> int:
    """Run a command and return its exit code."""
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"Command not found: {' '.join(cmd)}")
        return 1


def get_commands_with_descriptions() -> List[str]:
    """Get the list of commands with descriptions."""
    return [
        "rebase - Rebase to a container image",
        "check - Check for available updates",
        "upgrade - Upgrade to the latest version",
        "ls - List deployments with details",
        "rollback - Roll back to the previous deployment",
        "pin - Pin a deployment",
        "unpin - Unpin a deployment",
        "rm - Remove a deployment",
        "help - Show this help message",
    ]


def get_container_options() -> List[str]:
    """Get the list of container URL options."""
    return [
        "1: ghcr.io/ublue-os/bazzite:stable",
        "2: ghcr.io/ublue-os/bazzite:testing",
        "3: ghcr.io/ublue-os/bazzite:unstable",
        "*4: ghcr.io/wombatfromhell/bazzite-nix:testing",  # Default option
        "5: ghcr.io/wombatfromhell/bazzite-nix:stable",
        "6: ghcr.io/astrovm/amyos:latest",
    ]


def get_regular_container_options() -> List[str]:
    """Get the list of container URL options without prefixes."""
    return [
        "ghcr.io/ublue-os/bazzite:stable",
        "ghcr.io/ublue-os/bazzite:testing",
        "ghcr.io/ublue-os/bazzite:unstable",
        "ghcr.io/wombatfromhell/bazzite-nix:testing",  # Default option
        "ghcr.io/wombatfromhell/bazzite-nix:stable",
        "ghcr.io/astrovm/amyos:latest",
    ]


def show_commands_non_tty(print_func: Callable[[str], Any] = print) -> str:
    """Show command list when not in TTY context."""
    print_func("Not running in interactive mode. Available commands:")
    for cmd_desc in get_commands_with_descriptions():
        print_func(f"  {cmd_desc}")
    print_func("\nRun 'urh.py help' for more information.")
    return ""


def show_commands_gum_not_found(print_func: Callable[[str], Any] = print) -> str:
    """Show command list when gum is not found."""
    print_func("gum not found. Available commands:")
    for cmd_desc in get_commands_with_descriptions():
        print_func(f"  {cmd_desc}")
    print_func("\nRun 'urh.py help' for more information.")
    return ""


def show_command_menu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> str:
    """Show a menu of available commands using gum."""
    # Use gum to show the menu and get user selection
    try:
        # Check if we're running in a TTY context before using gum
        if is_tty_func():  # stdout is a TTY
            result = subprocess_run_func(
                ["gum", "choose", "--cursor", "→", "--selected-prefix", "✓ "]
                + get_commands_with_descriptions(),
                text=True,
                stdout=subprocess.PIPE,  # Only capture stdout to get user selection
                # stdin and stderr will inherit from the parent process, allowing gum's UI to appear
            )

            if result.returncode == 0:
                selected_with_desc = result.stdout.strip()
                # Extract just the command name from the selected option
                command = (
                    selected_with_desc.split(" - ")[0]
                    if " - " in selected_with_desc
                    else selected_with_desc
                )
                return command
            else:
                # gum failed or no selection made, show help
                print_func("No command selected.")
                return "help"
        else:
            # Not running in TTY, show the command list only (don't return "help" to avoid duplicate output)
            return show_commands_non_tty(print_func)
    except FileNotFoundError:
        # Show full descriptions when gum is not found
        return show_commands_gum_not_found(print_func)


def show_container_options_non_tty(print_func: Callable[[str], Any] = print) -> str:
    """Show container options when not in TTY context."""
    print_func("Available container URLs:")
    regular_options = get_regular_container_options()
    for i, option in enumerate(regular_options, 1):
        prefix = "* " if i == 4 else "  "  # Mark default option with *
        print_func(f"{prefix}{i}. {option}")
    print_func("\nRun 'urh.py rebase <url>' with a specific URL.")
    return ""


def show_container_options_gum_not_found(
    print_func: Callable[[str], Any] = print,
) -> str:
    """Show container options when gum is not found."""
    print_func("gum not found. Available container URLs:")
    regular_options = get_regular_container_options()
    for i, option in enumerate(regular_options, 1):
        prefix = "* " if i == 4 else "  "  # Mark default option with *
        print_func(f"{prefix}{i}. {option}")
    print_func("\nRun 'urh.py rebase <url>' with a specific URL.")
    return ""


def show_rebase_submenu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> str:
    """Show a submenu of common container URLs using gum."""
    try:
        # Check if we're running in a TTY context before using gum
        if is_tty_func():  # stdout is a TTY
            result = subprocess_run_func(
                [
                    "gum",
                    "choose",
                    "--cursor",
                    "→",
                    "--selected-prefix",
                    "✓ ",
                    "--header",
                    "Select container image (ESC to cancel):",
                ]
                + get_container_options(),
                text=True,
                stdout=subprocess.PIPE,  # Only capture stdout to get user selection
                # stdin and stderr will inherit from the parent process, allowing gum's UI to appear
            )

            if result.returncode == 0:
                selected_option = result.stdout.strip()
                # Extract the actual URL by removing the number prefix and default indicator
                # Format: "*4: url" or "3: url"
                if selected_option.startswith("*"):
                    selected_option = selected_option[1:]  # Remove asterisk
                # Remove the "N: " part to get just the URL
                if ": " in selected_option:
                    url = selected_option.split(": ", 1)[
                        1
                    ]  # Split once and get the URL part
                    return url
                else:
                    return selected_option  # Fallback in case format is unexpected
            else:
                # gum failed or no selection made (ESC or Ctrl+C)
                print_func("No option selected.")
                return ""
        else:
            # Not running in TTY, show the list only
            return show_container_options_non_tty(print_func)
    except FileNotFoundError:
        # gum not found, show the list only
        return show_container_options_gum_not_found(print_func)


def rebase_command(
    args: List[str], show_rebase_submenu_func: Optional[Callable[[], str]] = None
):
    """Handle the rebase command."""
    if show_rebase_submenu_func is None:
        show_rebase_submenu_func = show_rebase_submenu

    if not args:
        # No URL provided, show submenu to select from common container URLs
        selected_url = show_rebase_submenu_func()
        if not selected_url:
            return  # No selection made, exit gracefully
        url = selected_url
    else:
        url = args[0]

    cmd = ["sudo", "rpm-ostree", "rebase", url]
    sys.exit(run_command(cmd))


def check_command(args: List[str]):
    """Handle the check command."""
    cmd = ["rpm-ostree", "upgrade", "--check"]
    sys.exit(run_command(cmd))


def ls_command(args: List[str]):
    """Handle the ls command."""
    cmd = ["rpm-ostree", "status", "-v"]
    sys.exit(run_command(cmd))


def rollback_command(args: List[str]):
    """Handle the rollback command."""
    cmd = ["sudo", "rpm-ostree", "rollback"]
    sys.exit(run_command(cmd))


def pin_command(args: List[str]):
    """Handle the pin command."""
    if not args:
        print("Usage: urh.py pin <num>")
        return

    try:
        deploy_num = int(args[0])
        cmd = ["sudo", "ostree", "admin", "pin", str(deploy_num)]
        sys.exit(run_command(cmd))
    except ValueError:
        print(f"Invalid deployment number: {args[0]}")


def unpin_command(args: List[str]):
    """Handle the unpin command."""
    if not args:
        print("Usage: urh.py unpin <num>")
        return

    try:
        deploy_num = int(args[0])
        cmd = ["sudo", "ostree", "admin", "pin", "-u", str(deploy_num)]
        sys.exit(run_command(cmd))
    except ValueError:
        print(f"Invalid deployment number: {args[0]}")


def rm_command(args: List[str]):
    """Handle the rm command."""
    if not args:
        print("Usage: urh.py rm <num>")
        return

    try:
        deploy_num = int(args[0])
        cmd = ["sudo", "ostree", "cleanup", "-r", str(deploy_num)]
        sys.exit(run_command(cmd))
    except ValueError:
        print(f"Invalid deployment number: {args[0]}")


def upgrade_command(args: List[str]):
    """Handle the upgrade command."""
    cmd = ["sudo", "rpm-ostree", "upgrade"]
    sys.exit(run_command(cmd))


def help_command(args: List[str], print_func: Callable[[str], Any] = print):
    """Show help information."""
    print_func(
        "ublue-rebase-helper (urh.py) - Wrapper for rpm-ostree and ostree commands"
    )
    print_func("")
    print_func("Usage: urh.py <command> [args]")
    print_func("")
    print_func("Commands:")
    print_func("  rebase <url>     - Rebase to a container image")
    print_func("  check            - Check for available updates")
    print_func("  upgrade          - Upgrade to the latest version")
    print_func("  ls               - List deployments with details")
    print_func("  rollback         - Roll back to the previous deployment")
    print_func("  pin <num>        - Pin a deployment")
    print_func("  unpin <num>      - Unpin a deployment")
    print_func("  rm <num>         - Remove a deployment")
    print_func("  help             - Show this help message")


def main(argv: Optional[List[str]] = None):
    if argv is None:
        argv = sys.argv

    if len(argv) < 2:
        # No command provided, show menu
        command = show_command_menu()
        # If command is empty string (non-interactive or gum not available), just exit
        if not command:
            sys.exit(0)
    else:
        command = argv[1]

    # Map commands to their respective functions
    command_map: Dict[str, Callable[[List[str]], None]] = {
        "rebase": rebase_command,
        "check": check_command,
        "upgrade": upgrade_command,
        "ls": ls_command,
        "rollback": rollback_command,
        "pin": pin_command,
        "unpin": unpin_command,
        "rm": rm_command,
        "help": help_command,
    }

    if command in command_map:
        command_map[command](argv[2:])
    else:
        print(f"Unknown command: {command}")
        help_command([])


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
