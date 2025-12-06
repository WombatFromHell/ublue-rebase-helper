"""Unit tests for the menu module."""

import pytest

from src.urh.menu import MenuExitException, MenuSystem
from src.urh.models import MenuItem


class TestMenu:
    """Test menu functionality."""

    @pytest.fixture
    def sample_menu_items(self):
        """Sample menu items for testing."""
        return [
            MenuItem("1", "Option 1"),
            MenuItem("2", "Option 2"),
            MenuItem("3", "Option 3"),
        ]

    def test_menu_system_with_subprocess(self, mocker, sample_menu_items):
        """Test MenuSystem integration with subprocess."""
        mocker.patch("os.isatty", return_value=True)
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = "1 - Option 1"

        menu_system = MenuSystem()
        result = menu_system.show_menu(sample_menu_items, "Test Header")

        assert result == "1"
        mock_subprocess.assert_called_once()

    def test_menu_system_with_persistent_header(self, mocker, sample_menu_items):
        """Test MenuSystem with persistent header."""
        mocker.patch("os.isatty", return_value=True)
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = "1 - Option 1"

        menu_system = MenuSystem()
        result = menu_system.show_menu(
            items=sample_menu_items,
            header="Test Header",
            persistent_header="Current deployment: test-repo (v1.0.0)",
        )

        assert result == "1"

        # Verify persistent header was included in the command
        call_args = mock_subprocess.call_args[0][0]
        header_index = call_args.index("--header") + 1
        header_value = call_args[header_index]
        assert "Current deployment: test-repo (v1.0.0)" in header_value
        assert "Test Header" in header_value

    def test_menu_system_fallback_to_text(self, mocker, sample_menu_items):
        """Test MenuSystem fallback to text menu when gum is not available."""
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)
        mock_input = mocker.patch("builtins.input", return_value="1")

        menu_system = MenuSystem()
        result = menu_system.show_menu(sample_menu_items, "Test Header")

        assert result == "1"
        mock_input.assert_called_once_with("\nEnter choice (number): ")

    def test_menu_exit_exception(self):
        """Test MenuExitException functionality."""
        # Test exception without is_main_menu parameter
        exc = MenuExitException()
        assert exc.is_main_menu is False

        # Test exception with is_main_menu=True
        exc_main = MenuExitException(is_main_menu=True)
        assert exc_main.is_main_menu is True

        # Test exception with is_main_menu=False
        exc_sub = MenuExitException(is_main_menu=False)
        assert exc_sub.is_main_menu is False
