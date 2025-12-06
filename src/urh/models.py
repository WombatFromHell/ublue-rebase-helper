"""
Data models for ublue-rebase-helper.
"""

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass(slots=True)
class MenuItem:
    """Represents a menu item."""

    key: str
    description: str
    value: Any = None

    @property
    def display_text(self) -> str:
        """Get the display text for the menu item."""
        return f"{self.key} - {self.description}"


@dataclass(slots=True)
class ListItem(MenuItem):
    """Represents a list item without key prefix in display."""

    @property
    def display_text(self) -> str:
        """Get the display text for the list item without key prefix."""
        return self.description


@dataclass(slots=True)
class GumCommand:
    """Builder for gum choose commands."""

    options: List[str]
    header: str
    persistent_header: Optional[str] = None
    cursor: str = "→"
    selected_prefix: str = "✓ "
    height: int = 10  # Default height, can be increased for more options
    timeout: int = 300  # 5 minute timeout

    def build(self) -> List[str]:
        """Build the gum command."""
        cmd = [
            "gum",
            "choose",
            "--cursor",
            self.cursor,
            "--selected-prefix",
            self.selected_prefix,
            "--height",
            str(self.height),
            "--header",
            self._build_header(),
        ]
        cmd.extend(self.options)
        return cmd

    def _build_header(self) -> str:
        """Build combined header."""
        if self.persistent_header:
            return f"{self.persistent_header}\n{self.header}"
        return self.header
