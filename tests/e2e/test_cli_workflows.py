"""
E2E tests for CLI workflows.

Tests the user-facing CLI entry points, exercising the full command execution
flow from argument parsing to command handler execution.

These tests mock only external I/O (subprocess, file system) and test the
actual application logic end-to-end.
"""

import sys
from typing import List

import pytest
from pytest_mock import MockerFixture

from src.urh.cli import main as cli_main  # noqa: F401
from src.urh.menu import MenuExitException


class TestCLIDirectCommandExecution:
    """Test direct command execution via CLI arguments."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, mocker: MockerFixture) -> None:
        """Setup common test environment for all CLI tests."""
        # Force non-TTY to avoid gum menu hanging
        mocker.patch("os.isatty", return_value=False)

        # Mock curl check to always succeed
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock deployment info to avoid system calls
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )
        mocker.patch(
            "src.urh.deployment.format_deployment_header",
            return_value="Current deployment: test-repo (1.0.0)",
        )

    @pytest.mark.parametrize(
        "command,args,expected_base_cmd,exit_code",
        [
            ("check", [], ["rpm-ostree", "upgrade", "--check"], 0),
            ("ls", [], ["rpm-ostree", "status", "-v"], 0),
            ("upgrade", [], ["sudo", "rpm-ostree", "upgrade"], 0),
            ("rollback", [], ["sudo", "rpm-ostree", "rollback"], 0),
        ],
    )
    def test_simple_commands_execute_correctly(
        self,
        mocker: MockerFixture,
        command: str,
        args: List[str],
        expected_base_cmd: List[str],
        exit_code: int,
    ) -> None:
        """Test that simple commands execute the correct subprocess command."""
        # Mock subprocess.run to capture the command
        mock_run = mocker.patch("subprocess.run")
        # First call is curl check (returns success), second is actual command
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=exit_code),  # actual command
        ]

        # Mock sys.exit to prevent actual exit
        mock_exit = mocker.patch("sys.exit")

        # Set up sys.argv for the command
        original_argv = sys.argv
        sys.argv = ["urh", command] + args

        try:
            # Run CLI
            cli_main()

            # Verify subprocess.run was called at least twice (curl check + command)
            assert mock_run.call_count >= 2

            # Verify the last call was with expected command
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert last_call_args == expected_base_cmd

            # Verify sys.exit was called with correct code
            mock_exit.assert_called_once_with(exit_code)

        finally:
            sys.argv = original_argv

    def test_rebase_command_with_url_argument(self, mocker: MockerFixture) -> None:
        """Test rebase command with explicit URL argument."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "ghcr.io/test/repo:tag"]

        try:
            cli_main()

            # Verify command includes ostree prefix (last call)
            assert mock_run.call_count >= 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert "sudo" in last_call_args
            assert "rpm-ostree" in last_call_args
            assert "rebase" in last_call_args
            assert (
                "ostree-image-signed:docker://ghcr.io/test/repo:tag" in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_kargs_command_no_args_no_sudo(self, mocker: MockerFixture) -> None:
        """Test kargs command without arguments doesn't use sudo."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # kargs command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "kargs"]

        try:
            cli_main()

            assert mock_run.call_count >= 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert last_call_args == ["rpm-ostree", "kargs"]
            assert "sudo" not in last_call_args

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_unknown_command_shows_help_and_exits(self, mocker: MockerFixture) -> None:
        """Test unknown command shows help and exits with error."""
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "nonexistent-command"]

        try:
            cli_main()

            # Verify error message was printed
            mock_print.assert_any_call("Unknown command: nonexistent-command")

            # Verify exit with error code
            mock_exit.assert_called_once_with(1)

        finally:
            sys.argv = original_argv


class TestCLIMenuNavigation:
    """Test menu-driven command selection and navigation."""

    @pytest.fixture(autouse=True)
    def setup_menu_test_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for menu navigation tests."""
        # Mock subprocess with default return value for any call
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value = mocker.MagicMock(returncode=0, stdout="")

        # Force TTY mode to trigger menu system (but we'll mock gum)
        mocker.patch("os.isatty", return_value=True)

        # Mock curl check to always succeed
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock deployment info
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )
        mocker.patch(
            "src.urh.deployment.format_deployment_header",
            return_value="Current deployment: test-repo (1.0.0)",
        )

        # Mock sys.exit to prevent actual exit
        mocker.patch("sys.exit")

    def test_no_args_shows_main_menu(self, mocker: MockerFixture) -> None:
        """Test that running without arguments shows the main menu."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.return_value = "check"  # Simulate user selecting "check"

        original_argv = sys.argv
        sys.argv = ["urh"]  # No arguments

        try:
            cli_main()

            # Verify menu was shown
            mock_menu_show.assert_called_once()

        finally:
            sys.argv = original_argv

    def test_esc_in_main_menu_exits(self, mocker: MockerFixture) -> None:
        """Test that pressing ESC in main menu exits the application."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = MenuExitException(is_main_menu=True)

        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh"]

        try:
            cli_main()

            # Verify exit was called
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_esc_in_submenu_returns_to_main_menu(self, mocker: MockerFixture) -> None:
        """Test that pressing ESC in submenu returns to main menu."""
        # Override the fixture's mock with our specific side_effect
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")

        # First call (main menu) returns "rebase"
        # Second call (rebase submenu) raises ESC
        # Third call (back to main menu) returns "check"
        mock_menu_show.side_effect = [
            "rebase",  # Main menu selection
            MenuExitException(is_main_menu=False),  # ESC in submenu
            "check",  # Back to main menu, select check
        ]

        original_argv = sys.argv
        sys.argv = ["urh"]

        try:
            cli_main()

            # Verify menu was shown at least twice (main menu -> submenu, then main menu again)
            assert mock_menu_show.call_count >= 2

        finally:
            sys.argv = original_argv


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""

    @pytest.fixture(autouse=True)
    def setup_error_test_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for error handling tests."""
        mocker.patch("os.isatty", return_value=False)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )

    def test_curl_missing_exits_with_error(self, mocker: MockerFixture) -> None:
        """Test that missing curl dependency exits with error."""
        # Override fixture to simulate curl missing
        mocker.patch("src.urh.system.check_curl_presence", return_value=False)
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")

        # Also need to mock subprocess for the curl check
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=1, stdout="")

        original_argv = sys.argv
        sys.argv = ["urh", "check"]

        try:
            cli_main()

            # Verify error message
            mock_print.assert_any_call(
                "Error: curl is required for this application but was not found."
            )

            # Verify exit with error
            mock_exit.assert_called_once_with(1)

        finally:
            sys.argv = original_argv

    def test_command_failure_propagates_exit_code(self, mocker: MockerFixture) -> None:
        """Test that command failure exit code is propagated."""
        # Mock subprocess - first call is curl check (success), second is command (failure)
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0, stdout="/usr/bin/curl"),  # curl check
            mocker.MagicMock(returncode=42),  # command failure
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "check"]

        try:
            cli_main()

            # Verify exit with command's error code
            mock_exit.assert_called_once_with(42)

        finally:
            sys.argv = original_argv

    def test_subprocess_timeout_handled_gracefully(self, mocker: MockerFixture) -> None:
        """Test that subprocess timeout is handled gracefully."""
        import subprocess

        # Mock subprocess - first call is curl check (success), second times out
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0, stdout="/usr/bin/curl"),  # curl check
            subprocess.TimeoutExpired(
                cmd=["rpm-ostree", "upgrade", "--check"], timeout=300
            ),  # command timeout
        ]

        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "check"]

        try:
            cli_main()

            # Verify timeout exit code
            mock_exit.assert_called_once_with(124)

        finally:
            sys.argv = original_argv


class TestCLIArgumentParsing:
    """Test CLI argument parsing and validation."""

    @pytest.fixture(autouse=True)
    def setup_arg_test_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for argument parsing tests."""
        mocker.patch("os.isatty", return_value=False)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )

    def test_pin_command_with_valid_deployment_number(
        self, mocker: MockerFixture
    ) -> None:
        """Test pin command accepts valid deployment number."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # pin command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "pin", "0"]

        try:
            cli_main()

            assert mock_run.call_count >= 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert "ostree" in last_call_args
            assert "admin" in last_call_args
            assert "pin" in last_call_args
            assert "0" in last_call_args

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_pin_command_with_invalid_deployment_number(
        self, mocker: MockerFixture
    ) -> None:
        """Test pin command rejects invalid deployment number."""
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "pin", "not-a-number"]

        try:
            cli_main()

            mock_print.assert_any_call("Invalid deployment number: not-a-number")
            mock_exit.assert_called_once_with(1)

        finally:
            sys.argv = original_argv

    def test_remote_ls_command_with_url(self, mocker: MockerFixture) -> None:
        """Test remote-ls command with URL argument."""
        # Mock OCIClient
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": ["v1.0", "v2.0", "v3.0"]
        }
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "remote-ls", "ghcr.io/test/repo:tag"]

        try:
            cli_main()

            # Verify tags were printed
            mock_print.assert_any_call("Tags for ghcr.io/test/repo:tag:")

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv
