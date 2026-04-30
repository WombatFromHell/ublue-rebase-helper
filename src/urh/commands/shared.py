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

from ..system import _run_command, is_running_as_root

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
    handler: Callable[[List[str]], int]
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
    """Execute a command with conditional sudo based on the requires_sudo setting."""
    # Determine if sudo is needed
    if conditional_sudo_func is not None:
        # Use the conditional function to determine if sudo is needed
        needs_sudo = conditional_sudo_func(args)
    else:
        # Use the static boolean value
        needs_sudo = requires_sudo

    # Build the command (skip sudo if already running as root)
    if needs_sudo and not is_running_as_root():
        cmd = ["sudo", *base_cmd]
    else:
        cmd = base_cmd[:]

    cmd.extend(args)

    return _run_command(cmd)
