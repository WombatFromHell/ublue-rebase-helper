"""
Shared types, dataclasses, and utility functions for command implementations.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import (
    Callable,
    List,
    Optional,
    TypeVar,
)

from ..system import _run_command, get_elevation_command, is_running_as_root

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
    EDITOR = "editor"
    REPLACE = "replace"
    SHOW = "show"


@dataclass(slots=True, kw_only=True)
class CommandDefinition:
    """Definition of a command."""

    name: str
    description: str
    handler: Callable[..., int]
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
) -> int:
    """Execute a command with conditional elevation based on the requires_sudo setting.

    Uses pkexec when in a graphical session with pkexec available, falling back
    to sudo otherwise.
    """
    # Determine if elevation is needed
    if conditional_sudo_func is not None:
        # Use the conditional function to determine if elevation is needed
        needs_elevation = conditional_sudo_func(args)
    else:
        # Use the static boolean value
        needs_elevation = requires_sudo

    # Build the command (skip elevation if already running as root)
    if needs_elevation and not is_running_as_root():
        elevation = get_elevation_command()
        if elevation is not None:
            cmd = [elevation, *base_cmd]
        else:
            cmd = base_cmd[:]
    else:
        cmd = base_cmd[:]

    cmd.extend(args)

    return _run_command(cmd)
