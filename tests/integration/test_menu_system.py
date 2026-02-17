"""
Integration tests for the menu system implementation.

Tests the MenuSystem class with injected dependencies, including:
- GumCommand builder
- Text menu fallback
- Non-TTY mode
- Menu selection processing
- ESC key handling

These tests use dependency injection to test menu implementation details
without requiring actual gum or user interaction.
"""

import subprocess

import pytest
from pytest_mock import MockerFixture

from src.urh.menu import MenuExitException, MenuSystem
from src.urh.models import GumCommand, MenuItem


class TestGumCommand:
    """Test GumCommand builder."""

    def test_gum_command_build_creates_correct_command(self) -> None:
        """Test that GumCommand.build() creates the correct gum command."""
        gum_cmd = GumCommand(
            options=["Option 1", "Option 2", "Option 3"],
            header="Test Header",
            cursor="→",
            selected_prefix="✓ ",
            height=3,
            timeout=300,
        )

        cmd = gum_cmd.build()

        assert "gum" in cmd
        assert "choose" in cmd
        assert "--cursor" in cmd
        assert "→" in cmd
        assert "--selected-prefix" in cmd
        assert "✓ " in cmd
        assert "--height" in cmd
        assert "3" in cmd
        assert "--header" in cmd
        assert "Test Header" in cmd
        assert "Option 1" in cmd
        assert "Option 2" in cmd
        assert "Option 3" in cmd

    def test_gum_command_with_persistent_header(self) -> None:
        """Test that GumCommand includes persistent header in header."""
        gum_cmd = GumCommand(
            options=["Option 1"],
            header="Main Header",
            persistent_header="Persistent Header",
        )

        cmd = gum_cmd.build()

        # Find the header argument
        header_index = cmd.index("--header")
        header_value = cmd[header_index + 1]

        assert "Persistent Header" in header_value
        assert "Main Header" in header_value

    def test_gum_command_without_persistent_header(self) -> None:
        """Test that GumCommand works without persistent header."""
        gum_cmd = GumCommand(
            options=["Option 1"],
            header="Main Header",
            persistent_header=None,
        )

        cmd = gum_cmd.build()

        # Find the header argument
        header_index = cmd.index("--header")
        header_value = cmd[header_index + 1]

        assert header_value == "Main Header"


class TestMenuSystemNonTTY:
    """Test MenuSystem in non-TTY mode."""

    def test_non_tty_shows_menu_and_returns_none(self, mocker: MockerFixture) -> None:
        """Test that non-TTY mode displays menu and returns None."""
        mock_print = mocker.patch("builtins.print")

        menu_system = MenuSystem(is_tty=False)
        items = [
            MenuItem("1", "Option 1", "value1"),
            MenuItem("2", "Option 2", "value2"),
        ]

        result = menu_system.show_menu(items, "Test Header")

        assert result is None
        mock_print.assert_any_call("Test Header")
        mock_print.assert_any_call("1 - Option 1")
        mock_print.assert_any_call("2 - Option 2")

    def test_non_tty_with_persistent_header(self, mocker: MockerFixture) -> None:
        """Test that non-TTY mode includes persistent header."""
        mock_print = mocker.patch("builtins.print")

        menu_system = MenuSystem(is_tty=False)
        items = [MenuItem("1", "Option 1")]

        menu_system.show_menu(items, "Test Header", persistent_header="Persistent")

        mock_print.assert_any_call("Persistent")


class TestMenuSystemTextMenu:
    """Test MenuSystem text menu fallback."""

    @pytest.fixture
    def text_menu_system(self, mocker: MockerFixture) -> MenuSystem:
        """Create MenuSystem configured for text menu testing."""
        # Force TTY mode but gum will fail (FileNotFoundError)
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.side_effect = FileNotFoundError("gum not found")

        # Inject mock input function
        mock_input = mocker.MagicMock(return_value="1")

        return MenuSystem(
            is_tty=True, subprocess_runner=mock_subprocess, input_func=mock_input
        )

    def test_text_menu_displays_header_and_items(
        self, mocker: MockerFixture, text_menu_system: MenuSystem
    ) -> None:
        """Test that text menu displays header and items correctly."""
        mock_print = mocker.patch("builtins.print")

        items = [
            MenuItem("1", "Option 1", "value1"),
            MenuItem("2", "Option 2", "value2"),
        ]

        text_menu_system.show_menu(items, "Test Header")

        mock_print.assert_any_call("Test Header")
        mock_print.assert_any_call("Press ESC to cancel")
        mock_print.assert_any_call("1. 1 - Option 1")
        mock_print.assert_any_call("2. 2 - Option 2")

    def test_text_menu_valid_selection_returns_key(
        self, text_menu_system: MenuSystem
    ) -> None:
        """Test that valid text menu selection returns the key."""
        items = [
            MenuItem("1", "Option 1", "value1"),
            MenuItem("2", "Option 2", "value2"),
        ]

        result = text_menu_system.show_menu(items, "Test Header")

        assert result == "1"

    def test_text_menu_valid_selection_returns_value_if_no_key(
        self, mocker: MockerFixture, text_menu_system: MenuSystem
    ) -> None:
        """Test that text menu selection returns value when key is empty."""
        # ListItem has empty key, so value should be returned
        from src.urh.models import ListItem

        items = [
            ListItem("", "Option 1", "value1"),
            ListItem("", "Option 2", "value2"),
        ]

        result = text_menu_system.show_menu(items, "Test Header")

        assert result == "value1"

    def test_text_menu_invalid_choice_prompts_again(
        self, mocker: MockerFixture, text_menu_system: MenuSystem
    ) -> None:
        """Test that invalid choice prompts user again."""
        # Set up input to return invalid then valid
        text_menu_system._input_func.side_effect = ["99", "1"]  # type: ignore
        mock_print = mocker.patch("builtins.print")

        items = [MenuItem("1", "Option 1")]

        text_menu_system.show_menu(items, "Test Header")

        mock_print.assert_any_call("Invalid choice. Please try again.")
        assert text_menu_system._input_func.call_count == 2  # type: ignore

    def test_text_menu_keyboard_interrupt_returns_none(
        self, mocker: MockerFixture, text_menu_system: MenuSystem
    ) -> None:
        """Test that keyboard interrupt (Ctrl+C) returns None."""
        text_menu_system._input_func.side_effect = KeyboardInterrupt()  # type: ignore
        mocker.patch("builtins.print")

        items = [MenuItem("1", "Option 1")]

        result = text_menu_system.show_menu(items, "Test Header")

        assert result is None


class TestMenuSystemGumMenu:
    """Test MenuSystem gum menu with mocked subprocess."""

    @pytest.fixture
    def gum_menu_system(self, mocker: MockerFixture) -> MenuSystem:
        """Create MenuSystem configured for gum menu testing."""
        mock_subprocess = mocker.MagicMock()
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 - Option 1", stderr=""
        )

        return MenuSystem(is_tty=True, subprocess_runner=mock_subprocess)

    def test_gum_menu_executes_gum_command(self, gum_menu_system: MenuSystem) -> None:
        """Test that gum menu executes gum command."""
        items = [MenuItem("1", "Option 1")]

        gum_menu_system.show_menu(items, "Test Header")

        # Verify subprocess was called
        assert gum_menu_system._subprocess_runner.call_count > 0  # type: ignore[attr-defined]

    def test_gum_menu_returns_selected_key(
        self, mocker: MockerFixture, gum_menu_system: MenuSystem
    ) -> None:
        """Test that gum menu returns the selected key."""
        mock_subprocess = mocker.MagicMock()
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 - Option 1", stderr=""
        )
        gum_menu_system._subprocess_runner = mock_subprocess

        items = [MenuItem("1", "Option 1", "value1")]

        result = gum_menu_system.show_menu(items, "Test Header")

        assert result == "1"

    def test_gum_menu_returns_value_if_key_empty(
        self, mocker: MockerFixture, gum_menu_system: MenuSystem
    ) -> None:
        """Test that gum menu returns value when key is empty."""
        mock_subprocess = mocker.MagicMock()
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Option 1", stderr=""
        )
        gum_menu_system._subprocess_runner = mock_subprocess

        from src.urh.models import ListItem

        items = [ListItem("", "Option 1", "value1")]

        result = gum_menu_system.show_menu(items, "Test Header")

        assert result == "value1"

    def test_gum_menu_esc_raises_menu_exit_exception(
        self, mocker: MockerFixture, gum_menu_system: MenuSystem
    ) -> None:
        """Test that gum menu ESC key raises MenuExitException."""
        mock_subprocess = mocker.MagicMock()
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gum"]
        )
        gum_menu_system._subprocess_runner = mock_subprocess

        items = [MenuItem("1", "Option 1")]

        with pytest.raises(MenuExitException) as exc_info:
            gum_menu_system.show_menu(items, "Test Header", is_main_menu=True)

        assert exc_info.value.is_main_menu is True

    def test_gum_menu_timeout_returns_none(
        self, mocker: MockerFixture, gum_menu_system: MenuSystem
    ) -> None:
        """Test that gum menu timeout returns None."""
        mock_subprocess = mocker.MagicMock()
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd=["gum"], timeout=300
        )
        gum_menu_system._subprocess_runner = mock_subprocess

        mock_print = mocker.patch("builtins.print")

        items = [MenuItem("1", "Option 1")]

        result = gum_menu_system.show_menu(items, "Test Header")

        assert result is None
        mock_print.assert_any_call("Menu selection timed out.")


class TestMenuSystemESCHandling:
    """Test ESC key handling in menus."""

    def test_esc_in_main_menu_raises_exception_with_flag(
        self, mocker: MockerFixture
    ) -> None:
        """Test that ESC in main menu raises exception with is_main_menu=True."""
        mock_subprocess = mocker.MagicMock()
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gum"]
        )

        menu_system = MenuSystem(is_tty=True, subprocess_runner=mock_subprocess)
        items = [MenuItem("1", "Option 1")]

        with pytest.raises(MenuExitException) as exc_info:
            menu_system.show_menu(items, "Test Header", is_main_menu=True)

        assert exc_info.value.is_main_menu is True

    def test_esc_in_submenu_raises_exception_with_flag(
        self, mocker: MockerFixture
    ) -> None:
        """Test that ESC in submenu raises exception with is_main_menu=False."""
        mock_subprocess = mocker.MagicMock()
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gum"]
        )

        menu_system = MenuSystem(is_tty=True, subprocess_runner=mock_subprocess)
        items = [MenuItem("1", "Option 1")]

        with pytest.raises(MenuExitException) as exc_info:
            menu_system.show_menu(items, "Test Header", is_main_menu=False)

        assert exc_info.value.is_main_menu is False

    def test_esc_in_test_environment_returns_none(self, mocker: MockerFixture) -> None:
        """Test that ESC in test environment returns None (no exception)."""
        mocker.patch.dict("os.environ", {"URH_TEST_NO_EXCEPTION": "1"})

        mock_subprocess = mocker.MagicMock()
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["gum"]
        )

        menu_system = MenuSystem(is_tty=True, subprocess_runner=mock_subprocess)
        mock_print = mocker.patch("builtins.print")

        items = [MenuItem("1", "Option 1")]

        result = menu_system.show_menu(items, "Test Header", is_main_menu=True)

        assert result is None
        mock_print.assert_any_call("No option selected.")
