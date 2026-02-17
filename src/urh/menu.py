"""
Menu system implementation for ublue-rebase-helper.
"""

import logging
import os
import subprocess
import sys
from typing import Any, Callable, List, Optional, Sequence

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

    def __init__(
        self,
        is_tty: Optional[bool] = None,
        subprocess_runner: Optional[Callable] = None,
        input_func: Optional[Callable[[str], str]] = None,
        exit_func: Optional[Callable[[int], None]] = None,
    ):
        """
        Initialize MenuSystem with optional dependency injection for testability.

        Args:
            is_tty: Whether we're in a TTY environment (default: auto-detect)
            subprocess_runner: subprocess.run replacement (default: subprocess.run)
            input_func: input() replacement (default: built-in input)
            exit_func: sys.exit replacement (default: sys.exit)
        """
        self.is_tty = is_tty if is_tty is not None else os.isatty(1)
        self._subprocess_runner = subprocess_runner or subprocess.run
        self._input_func = input_func or input
        self._exit_func = exit_func or sys.exit

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
        options = self._create_gum_options(items)
        gum_cmd = self._create_gum_command(options, header, persistent_header)

        try:
            result = self._execute_gum_command(gum_cmd)
            selected_text = result.stdout.strip()

            return self._process_gum_selection(selected_text, items)

        except subprocess.CalledProcessError as e:
            return self._handle_gum_error(e, is_main_menu)
        except subprocess.TimeoutExpired:
            return self._handle_gum_timeout()

    def _create_gum_options(self, items: Sequence[MenuItem]) -> List[str]:
        """Create gum menu options from menu items."""
        return [item.display_text for item in items]

    def _create_gum_command(
        self, options: List[str], header: str, persistent_header: Optional[str]
    ) -> GumCommand:
        """Create a GumCommand with appropriate settings."""
        return GumCommand(
            options=options,
            header=header,
            persistent_header=persistent_header,
            height=len(options),  # Show all options
        )

    def _execute_gum_command(
        self, gum_cmd: GumCommand
    ) -> subprocess.CompletedProcess[str]:
        """Execute the gum command and return the result."""
        return self._subprocess_runner(
            gum_cmd.build(),
            text=True,
            stdout=subprocess.PIPE,
            check=True,
            timeout=gum_cmd.timeout,  # 5 minute timeout
        )

    def _process_gum_selection(
        self, selected_text: str, items: Sequence[MenuItem]
    ) -> Optional[Any]:
        """Process the gum selection and return the appropriate value."""
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

    def _handle_gum_error(
        self, e: subprocess.CalledProcessError, is_main_menu: bool
    ) -> Optional[Any]:
        """Handle gum command errors."""
        if e.returncode == 1:
            # ESC pressed
            return self._handle_esc_pressed(is_main_menu)
        return None

    def _handle_esc_pressed(self, is_main_menu: bool) -> Optional[Any]:
        """Handle ESC key press in gum menu."""
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

    def _handle_gum_timeout(self) -> Optional[Any]:
        """Handle gum menu timeout."""
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
        self._display_text_menu_header(persistent_header, header)
        self._display_text_menu_items(items)

        return self._process_text_menu_input(items, is_main_menu)

    def _display_text_menu_header(
        self, persistent_header: Optional[str], header: str
    ) -> None:
        """Display the text menu header."""
        if persistent_header:
            print(persistent_header)
        print(header)
        print("Press ESC to cancel")

    def _display_text_menu_items(self, items: Sequence[MenuItem]) -> None:
        """Display the text menu items."""
        for i, item in enumerate(items, 1):
            print(f"{i}. {item.display_text}")

    def _process_text_menu_input(
        self, items: Sequence[MenuItem], is_main_menu: bool
    ) -> Optional[Any]:
        """Process text menu input and return the selected value."""
        while True:
            try:
                choice = self._get_user_choice()
                if not choice:
                    return None

                choice_num = self._parse_choice_number(choice, items)
                return self._handle_valid_choice(choice_num, items)

            except ValueError:
                self._handle_invalid_choice()
            except KeyboardInterrupt:
                return self._handle_keyboard_interrupt(is_main_menu)

    def _get_user_choice(self) -> str:
        """Get user choice input."""
        return self._input_func("\nEnter choice (number): ").strip()

    def _parse_choice_number(self, choice: str, items: Sequence[MenuItem]) -> int:
        """Parse and validate the choice number."""
        choice_num = int(choice)
        if 1 <= choice_num <= len(items):
            return choice_num
        raise ValueError("Invalid choice")

    def _handle_valid_choice(
        self, choice_num: int, items: Sequence[MenuItem]
    ) -> Optional[Any]:
        """Handle a valid choice and return the appropriate value."""
        item = items[choice_num - 1]
        if item.key and item.key.strip():
            return item.key
        else:
            return item.value

    def _handle_invalid_choice(self) -> None:
        """Handle an invalid choice."""
        print("Invalid choice. Please try again.")

    def _handle_keyboard_interrupt(self, is_main_menu: bool) -> Optional[Any]:
        """Handle keyboard interrupt (ESC)."""
        if is_main_menu:
            self._exit_func(0)
        else:
            return None


# Global menu system instance
_menu_system = MenuSystem()
