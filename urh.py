#!/usr/bin/env python3

import subprocess
import sys
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
    commands = [
        "rebase <url>     - Rebase to a container image",
        "check            - Check for available updates",
        "ls               - List deployments with details",
        "rollback         - Roll back to the previous deployment",
        "pin <num>        - Pin a deployment",
        "unpin <num>      - Unpin a deployment",
        "rm <num>         - Remove a deployment",
        "help             - Show this help message",
    ]

    # Use gum to show the menu and get user selection
    try:
        result = subprocess.run(
            ["gum", "choose", "--cursor", "→", "--selected.cursor", "✓"] + commands,
            text=True,
            capture_output=True,
        )

        if result.returncode == 0:
            # Extract the command name from the selection
            selected = result.stdout.strip().split()[0]
            return selected
        else:
            print("No command selected or gum not available.")
            return "help"
    except FileNotFoundError:
        print("gum not found. Available commands:")
        for cmd in commands:
            print(f"  {cmd}")
        return "help"


def main():
    if len(sys.argv) < 2:
        # No command provided, show menu
        command = show_command_menu()
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


if __name__ == "__main__":
    main()

