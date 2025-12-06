"""
Menu system implementation for ublue-rebase-helper.
"""

import logging
import os
import subprocess
import sys
from typing import Any, Optional, Sequence

from .models import GumCommand, MenuItem

# Set up logging
logger = logging.getLogger(__name__)


class MenuExitException(Exception):
    """Exception raised when ESC is pressed in a menu."""

    def __init__(self, is_main_menu: bool = False):
        self.is_main_menu = is_main_menu
        super().__init__()


class MenuSystem:
    """Unified menu system using native Python."""

    def __init__(self):
        self.is_tty = os.isatty(1)

    def show_menu(
        self,
        items: Sequence[MenuItem],  # Changed from List[MenuItem] to Sequence[MenuItem]
        header: str,
        persistent_header: Optional[str] = None,
        is_main_menu: bool = False,
    ) -> Optional[Any]:
        """Show a menu and return the selected value."""
        # Check if we should force non-gum behavior (e.g., to avoid hanging during tests)
        force_non_gum = os.environ.get("URH_AVOID_GUM", "").lower() in (
            "1",
            "true",
            "yes",
        )

        if not self.is_tty or force_non_gum:
            self._show_non_tty(items, header, persistent_header)
            return None

        try:
            # Try to use gum if available
            return self._show_gum_menu(items, header, persistent_header, is_main_menu)
        except FileNotFoundError:
            # Fallback to simple text menu
            return self._show_text_menu(items, header, persistent_header, is_main_menu)

    def _show_non_tty(
        self, items: Sequence[MenuItem], header: str, persistent_header: Optional[str]
    ) -> None:
        """Show menu in non-TTY mode."""
        if persistent_header:
            print(persistent_header)
        print(header)
        for item in items:
            print(item.display_text)
        print("\nRun 'urh.py with a specific option.'")

    def _show_gum_menu(
        self,
        items: Sequence[MenuItem],
        header: str,
        persistent_header: Optional[str],
        is_main_menu: bool,
    ) -> Optional[Any]:
        """Show menu using gum with builder pattern."""
        options = [item.display_text for item in items]

        # Set height to show all options in the menu
        # Use the exact number of options to display them all without scrolling
        gum_cmd = GumCommand(
            options=options,
            header=header,
            persistent_header=persistent_header,
            height=len(options),  # Show all options
        )

        try:
            result = subprocess.run(
                gum_cmd.build(),
                text=True,
                stdout=subprocess.PIPE,
                check=True,
                timeout=gum_cmd.timeout,  # 5 minute timeout
            )
            selected_text = result.stdout.strip()

            # Use walrus operator and next() for cleaner lookup
            if selected := next(
                (item for item in items if item.display_text == selected_text), None
            ):
                return (
                    selected.key
                    if selected.key and selected.key.strip()
                    else selected.value
                )

            return None
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                # ESC pressed
                # Check if we're in a test that expects different behavior
                if "URH_TEST_NO_EXCEPTION" in os.environ:
                    print("No option selected.")
                    return None
                else:
                    # Clear the line in non-test environments
                    if "PYTEST_CURRENT_TEST" not in os.environ:
                        sys.stdout.write("\033[F\033[K")
                        sys.stdout.flush()

                    raise MenuExitException(is_main_menu=is_main_menu)
            return None
        except subprocess.TimeoutExpired:
            logger.warning("Menu selection timed out.")
            print("Menu selection timed out.")
            return None

    def _show_text_menu(
        self,
        items: Sequence[MenuItem],
        header: str,
        persistent_header: Optional[str],
        is_main_menu: bool,
    ) -> Optional[Any]:
        """Show menu using plain text."""
        if persistent_header:
            print(persistent_header)
        print(header)
        print("Press ESC to cancel")

        for i, item in enumerate(items, 1):
            print(f"{i}. {item.display_text}")

        while True:
            try:
                choice = input("\nEnter choice (number): ").strip()
                if not choice:
                    return None

                choice_num = int(choice)
                if 1 <= choice_num <= len(items):
                    # If item has a meaningful key (non-empty), return it; otherwise return value
                    item = items[choice_num - 1]
                    if item.key and item.key.strip():
                        return item.key
                    else:
                        return item.value
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Invalid choice. Please try again.")
            except KeyboardInterrupt:
                if is_main_menu:
                    sys.exit(0)
                else:
                    return None


# Global menu system instance
_menu_system = MenuSystem()
