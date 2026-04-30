"""
Simple command handlers: check, ls, upgrade, rollback.

Each handler returns an int exit code instead of calling sys.exit().
"""

from typing import List

from ..system import _run_command, build_command


def handle_check(args: List[str]) -> int:
    """Handle the check command."""
    cmd = ["rpm-ostree", "upgrade", "--check"]
    return _run_command(cmd)


def handle_ls(args: List[str]) -> int:
    """Handle the ls command."""
    import subprocess

    try:
        process = subprocess.Popen(
            ["rpm-ostree", "status", "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            print(stdout)
        return process.returncode
    except FileNotFoundError:
        import logging

        logger = logging.getLogger(__name__)
        logger.error("Command not found: rpm-ostree")
        return 1


def handle_upgrade(args: List[str]) -> int:
    """Handle the upgrade command."""
    cmd = build_command(True, ["rpm-ostree", "upgrade"])
    return _run_command(cmd)


def handle_rollback(args: List[str]) -> int:
    """Handle the rollback command."""
    cmd = build_command(True, ["rpm-ostree", "rollback"])
    return _run_command(cmd)
