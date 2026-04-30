"""
Command registry for ublue-rebase-helper.

Wires up all command handlers from their respective modules.
"""

from typing import Dict, List, Optional

# Import all handler modules
from . import (
    kargs,
    pin,
    rebase,
    remote_ls,
    rm,
    simple_ops,
    undeploy,
    unpin,
)
from .shared import CommandDefinition


class CommandRegistry:
    """Registry for all available commands."""

    def __init__(self, menu_system=None):
        from ..menu import _menu_system

        self._menu_system = menu_system or _menu_system
        self._commands: Dict[str, CommandDefinition] = {}
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands."""
        self._commands = {
            "check": CommandDefinition(
                name="check",
                description="Check for available updates",
                handler=lambda args: simple_ops.handle_check(args),
                requires_sudo=False,
            ),
            "kargs": CommandDefinition(
                name="kargs",
                description="Manage kernel arguments (kargs)",
                handler=lambda args: kargs.handle_kargs(args, self._menu_system),
                requires_sudo=False,  # Default value for compatibility with tests
                conditional_sudo_func=self._should_use_sudo_for_kargs,  # Use function for conditional sudo
            ),
            "ls": CommandDefinition(
                name="ls",
                description="List deployments with details",
                handler=lambda args: simple_ops.handle_ls(args),
                requires_sudo=False,
            ),
            "rebase": CommandDefinition(
                name="rebase",
                description="Rebase to a container image",
                handler=lambda args, skip_confirmation=False: rebase.handle_rebase(
                    args,
                    skip_confirmation=skip_confirmation,
                    menu_system=self._menu_system,
                ),
                requires_sudo=True,
                has_submenu=True,
            ),
            "remote-ls": CommandDefinition(
                name="remote-ls",
                description="List available tags for a container image",
                handler=lambda args: remote_ls.handle_remote_ls(
                    args, self._menu_system
                ),
                requires_sudo=False,
                has_submenu=True,
            ),
            "upgrade": CommandDefinition(
                name="upgrade",
                description="Upgrade to the latest version",
                handler=lambda args: simple_ops.handle_upgrade(args),
                requires_sudo=True,
            ),
            "rollback": CommandDefinition(
                name="rollback",
                description="Roll back to the previous deployment",
                handler=lambda args: simple_ops.handle_rollback(args),
                requires_sudo=True,
            ),
            "pin": CommandDefinition(
                name="pin",
                description="Pin a deployment",
                handler=lambda args: pin.handle_pin(args, self._menu_system),
                requires_sudo=True,
                has_submenu=True,
            ),
            "unpin": CommandDefinition(
                name="unpin",
                description="Unpin a deployment",
                handler=lambda args: unpin.handle_unpin(args, self._menu_system),
                requires_sudo=True,
                has_submenu=True,
            ),
            "rm": CommandDefinition(
                name="rm",
                description="Remove a deployment",
                handler=lambda args: rm.handle_rm(args, self._menu_system),
                requires_sudo=True,
                has_submenu=True,
            ),
            "undeploy": CommandDefinition(
                name="undeploy",
                description="Remove a deployment by index",
                handler=lambda args: undeploy.handle_undeploy(args, self._menu_system),
                requires_sudo=True,
                has_submenu=True,
            ),
        }

    def _should_use_sudo_for_kargs(self, args: List[str]) -> bool:
        """Determine if sudo should be used for kargs command based on arguments."""
        return kargs.should_use_sudo_for_kargs(args)

    def get_commands(self) -> List[CommandDefinition]:
        """Get all registered commands."""
        return list(self._commands.values())

    def get_command(self, name: str) -> Optional[CommandDefinition]:
        """Get a specific command by name."""
        return self._commands.get(name)
