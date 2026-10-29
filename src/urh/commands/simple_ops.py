"""
Simple command handlers: check, ls, upgrade, rollback.

Each handler returns an int exit code instead of calling sys.exit().
"""

from typing import List

from ..system import _run_command, build_command
from .shared import confirm_action


def handle_check(args: List[str]) -> int:
    """Handle the check command."""
    cmd = build_command(True, ["bootc", "upgrade", "--check"])
    return _run_command(cmd)


def handle_ls(args: List[str]) -> int:
    """Render the deployment list; rpm-ostree status --json is readable without root."""
    from ..deployment import format_deployment_summary, get_deployment_info

    print(format_deployment_summary(get_deployment_info()))
    return 0


def handle_upgrade(args: List[str]) -> int:
    """Handle the upgrade command."""
    if not confirm_action("Confirm upgrade? [y/N]: "):
        return 0
    cmd = build_command(True, ["bootc", "upgrade"])
    return _run_command(cmd)


def handle_rollback(args: List[str]) -> int:
    """Handle the rollback command."""
    if not confirm_action("Confirm rollback? [y/N]: "):
        return 0
    cmd = build_command(True, ["rpm-ostree", "rollback"])
    return _run_command(cmd)
