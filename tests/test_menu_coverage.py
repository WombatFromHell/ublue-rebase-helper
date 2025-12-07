"""
Tests for menu system to improve coverage.
"""

import os
from unittest.mock import patch

import pytest

from src.urh.menu import MenuExitException, MenuSystem
from src.urh.models import MenuItem


class TestMenuSystemCoverage:
    """Test MenuSystem functionality to improve coverage."""

    def test_show_non_tty_mode(self, mocker, capsys):
        """Test _show_non_tty functionality."""
        menu_system = MenuSystem()

        # Create test items
        items = [
            MenuItem("key1", "Display 1", "value1"),
            MenuItem("key2", "Display 2", "value2"),
        ]

        # Force non-tty mode by setting is_tty to False
        with patch.object(menu_system, "is_tty", False):
            result = menu_system.show_menu(items, "Test Header", "Persistent Header")

        assert result is None

        # Capture print output to verify it was called
        captured = capsys.readouterr()
        assert "Test Header" in captured.out
        assert "Display 1" in captured.out
        assert "Display 2" in captured.out

    def test_show_menu_with_gum_not_found(self, mocker):
        """Test fallback to text menu when gum is not available."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Mock gum command to raise FileNotFoundError (gum not found)
        # Also mock input to return a value so the text menu doesn't hang
        with patch.object(menu_system, "is_tty", True):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with patch("builtins.input", return_value="1"):  # Return first option
                    result = menu_system.show_menu(
                        items, "Test Header", "Persistent Header"
                    )

        # Should return the key since it's non-empty
        assert result == "key1"

    def test_show_gum_menu_timeout(self, mocker):
        """Test _show_gum_menu with timeout exception."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Mock subprocess to raise TimeoutExpired
        with patch.object(menu_system, "is_tty", True):
            with patch("subprocess.run") as mock_run:
                from subprocess import TimeoutExpired

                mock_run.side_effect = TimeoutExpired(cmd=["gum", "choose"], timeout=5)

                result = menu_system._show_gum_menu(
                    items, "Test Header", "Persistent Header", False
                )

        # Should return None on timeout
        assert result is None

    def test_show_gum_menu_esc_pressed(self, mocker):
        """Test _show_gum_menu when ESC is pressed (CalledProcessError with returncode=1)."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Mock subprocess to raise CalledProcessError with returncode=1 (ESC pressed)
        with patch.object(menu_system, "is_tty", True):
            with patch("subprocess.run") as mock_run:
                from subprocess import CalledProcessError

                mock_run.side_effect = CalledProcessError(1, ["gum", "choose"])

                # When testing with pytest, PYTEST_CURRENT_TEST is set, so the exception should be raised
                with pytest.raises(MenuExitException):
                    menu_system._show_gum_menu(
                        items, "Test Header", "Persistent Header", False
                    )

    def test_show_gum_menu_esc_pressed_in_test_mode(self, mocker):
        """Test _show_gum_menu when ESC is pressed in test mode with URH_TEST_NO_EXCEPTION."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Set the test environment variable
        os.environ["URH_TEST_NO_EXCEPTION"] = "1"

        try:
            with patch.object(menu_system, "is_tty", True):
                with patch("subprocess.run") as mock_run:
                    from subprocess import CalledProcessError

                    mock_run.side_effect = CalledProcessError(1, ["gum", "choose"])

                    result = menu_system._show_gum_menu(
                        items, "Test Header", "Persistent Header", False
                    )

            # Should return None in test mode with URH_TEST_NO_EXCEPTION
            assert result is None
        finally:
            del os.environ["URH_TEST_NO_EXCEPTION"]

    def test_show_text_menu_with_keyboard_interrupt_main_menu(self, mocker):
        """Test text menu with keyboard interrupt on main menu."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Mock input to raise KeyboardInterrupt only once
        call_count = 0

        def input_side_effect(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt()
            else:
                # This shouldn't normally be reached, but if it is, return something to break
                return ""  # This will cause the function to return None

        with patch.object(menu_system, "is_tty", True):
            with patch("builtins.input", side_effect=input_side_effect):
                with patch("sys.exit") as mock_sys_exit:
                    menu_system._show_text_menu(
                        items, "Test Header", "Persistent Header", True
                    )

        # For main menu, sys.exit should be called with code 0
        mock_sys_exit.assert_called_once_with(0)

    def test_show_text_menu_with_keyboard_interrupt_submenu(self, mocker):
        """Test text menu with keyboard interrupt on submenu."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Mock input to raise KeyboardInterrupt on submenu
        with patch.object(menu_system, "is_tty", True):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                result = menu_system._show_text_menu(
                    items, "Test Header", "Persistent Header", False
                )

        # For submenu, should return None
        assert result is None

    def test_show_text_menu_valid_input(self, mocker):
        """Test text menu with valid input."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Mock input to return valid choice
        with patch.object(menu_system, "is_tty", True):
            with patch("builtins.input", return_value="1"):
                result = menu_system._show_text_menu(
                    items, "Test Header", "Persistent Header", False
                )

        # Should return the key since it's non-empty
        assert result == "key1"

    def test_show_text_menu_invalid_input(self, mocker):
        """Test text menu with invalid input."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Mock input to return invalid choices then valid one
        with patch.object(menu_system, "is_tty", True):
            with patch("builtins.input", side_effect=["invalid", "999", "1"]):
                with patch(
                    "builtins.print"
                ) as mock_print:  # Mock print to avoid side effects
                    result = menu_system._show_text_menu(
                        items, "Test Header", "Persistent Header", False
                    )

        # Should eventually return the key after invalid attempts (since key is non-empty)
        assert result == "key1"
        # Verify print was called for invalid input messages
        assert mock_print.called

    def test_show_menu_with_urh_avoid_gum_env(self, mocker, capsys):
        """Test show_menu when URH_AVOID_GUM environment variable is set."""
        menu_system = MenuSystem()

        items = [MenuItem("key1", "Display 1", "value1")]

        # Set the URH_AVOID_GUM environment variable
        os.environ["URH_AVOID_GUM"] = "1"

        try:
            result = menu_system.show_menu(
                items, "Test Header", "Persistent Header", False
            )
            assert result is None

            # Capture the output to verify non-tty path was taken
            captured = capsys.readouterr()
            assert "Test Header" in captured.out
        finally:
            del os.environ["URH_AVOID_GUM"]

    def test_show_menu_with_non_tty(self, mocker, capsys):
        """Test show_menu when not in TTY mode."""
        menu_system = MenuSystem()

        # Force is_tty to be False directly
        menu_system.is_tty = False

        items = [MenuItem("key1", "Display 1", "value1")]

        result = menu_system.show_menu(items, "Test Header", "Persistent Header", False)
        assert result is None

        # Capture the output to verify non-tty path was taken
        captured = capsys.readouterr()
        assert "Test Header" in captured.out
