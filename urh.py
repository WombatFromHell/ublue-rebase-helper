#!/usr/bin/env python3
# pyright: strict

import subprocess
import sys
import os
from typing import List


def run_command(cmd: List[str]) -> int:
    """Run a command and return its exit code."""
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"Command not found: {' '.join(cmd)}")
        return 1


def show_command_menu() -> str:
    """Show a menu of available commands using gum."""
    # Create commands with descriptions for better user experience
    commands_with_descriptions = [
        "rebase - Rebase to a container image",
        "check - Check for available updates",
        "ls - List deployments with details",
        "rollback - Roll back to the previous deployment",
        "pin - Pin a deployment",
        "unpin - Unpin a deployment",
        "rm - Remove a deployment",
        "help - Show this help message",
    ]

    # Use gum to show the menu and get user selection
    try:
        # Check if we're running in a TTY context before using gum
        if os.isatty(0):  # stdin is a TTY
            result = subprocess.run(
                ["gum", "choose", "--cursor", "→", "--selected-prefix", "✓ "]
                + commands_with_descriptions,
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
                print("No command selected.")
                return "help"
        else:
            # Not running in TTY, show the command list only (don't return "help" to avoid duplicate output)
            print("Not running in interactive mode. Available commands:")
            for cmd_desc in commands_with_descriptions:
                print(f"  {cmd_desc}")
            print("\nRun 'urh.py help' for more information.")
            return ""  # Return empty string to indicate no command should be executed
    except FileNotFoundError:
        # Show full descriptions when gum is not found
        print("gum not found. Available commands:")
        for cmd_desc in commands_with_descriptions:
            print(f"  {cmd_desc}")
        print("\nRun 'urh.py help' for more information.")
        # When gum isn't available, return empty string to avoid duplicate output
        return ""


def rebase_command(args: List[str]):
    """Handle the rebase command."""
    if not args:
        print("Usage: urh.py rebase <url>")
        return

    url = args[0]
    cmd = ["sudo", "rpm-ostree", "rebase", url]
    sys.exit(run_command(cmd))


def check_command(args: List[str]):
    """Handle the check command."""
    cmd = ["sudo", "rpm-ostree", "upgrade", "--check"]
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


def help_command(args: List[str]):
    """Show help information."""
    print("ublue-rebase-helper (urh.py) - Wrapper for rpm-ostree and ostree commands")
    print()
    print("Usage: urh.py <command> [args]")
    print()
    print("Commands:")
    print("  rebase <url>     - Rebase to a container image")
    print("  check            - Check for available updates")
    print("  ls               - List deployments with details")
    print("  rollback         - Roll back to the previous deployment")
    print("  pin <num>        - Pin a deployment")
    print("  unpin <num>      - Unpin a deployment")
    print("  rm <num>         - Remove a deployment")
    print("  help             - Show this help message")


def main():
    if len(sys.argv) < 2:
        # No command provided, show menu
        command = show_command_menu()
        # If command is empty string (non-interactive or gum not available), just exit
        if not command:
            sys.exit(0)
    else:
        command = sys.argv[1]

    # Map commands to their respective functions
    command_map = {
        "rebase": rebase_command,
        "check": check_command,
        "ls": ls_command,
        "rollback": rollback_command,
        "pin": pin_command,
        "unpin": unpin_command,
        "rm": rm_command,
        "help": help_command,
    }

    if command in command_map:
        command_map[command](sys.argv[2:])
    else:
        print(f"Unknown command: {command}")
        help_command([])


if __name__ == "__main__":
    main()
