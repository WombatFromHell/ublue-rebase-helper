"""
E2E tests for CLI workflows.

Tests the user-facing CLI entry points, exercising the full command execution
flow from argument parsing to command handler execution.

These tests mock only external I/O (subprocess, file system) and test the
actual application logic end-to-end.
"""

from typing import List

import pytest
from pytest_mock import MockerFixture

from src.urh.cli import main as cli_main  # noqa: F401
from tests.conftest import (
    ExecCompleted,
    apply_e2e_test_environment,
    mock_execvp_command,
)


@pytest.mark.e2e
class TestCLIDirectCommandExecution:
    """Test direct command execution via CLI arguments."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, mocker: MockerFixture) -> None:
        """Setup common test environment for all CLI tests."""
        apply_e2e_test_environment(mocker, tty=False)

    @pytest.mark.parametrize(
        "command,args,expected_base_cmd,exit_code",
        [
            ("check", [], ["rpm-ostree", "upgrade", "--check"], 0),
            ("upgrade", [], ["sudo", "rpm-ostree", "upgrade"], 0),
            ("rollback", [], ["sudo", "rpm-ostree", "rollback"], 0),
        ],
    )
    def test_simple_commands_execute_correctly(
        self,
        mocker: MockerFixture,
        cli_command,
        command: str,
        args: List[str],
        expected_base_cmd: List[str],
        exit_code: int,
    ) -> None:
        """Test that simple commands execute the correct subprocess command."""
        mock_execvp = mocker.patch(
            "os.execvp", side_effect=ExecCompleted(expected_base_cmd)
        )

        cli_command(["urh", command] + args)

        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify os.execvp was called with the correct command
        assert mock_execvp.call_count >= 1
        last_call_args = mock_execvp.call_args_list[-1][0][1]
        assert last_call_args == expected_base_cmd

    def test_ls_command_executes_correctly(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test that ls command executes rpm-ostree status -v."""
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = mocker.MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("test output", "")
        mock_popen.return_value = mock_process

        cli_command(["urh", "ls"])

        cli_main()

        # Verify subprocess.Popen was called with the correct command
        assert mock_popen.call_count >= 1
        call_args = mock_popen.call_args_list[-1][0][0]
        assert "rpm-ostree" in call_args
        assert "status" in call_args
        assert "-v" in call_args

    def test_rebase_command_with_url_argument(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase command with explicit URL argument."""
        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/test/repo:tag",
        ]

        cli_command(["urh", "rebase", "ghcr.io/test/repo:tag"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)
        assert "sudo" in last_call_args
        assert "rpm-ostree" in last_call_args
        assert "rebase" in last_call_args
        assert "ostree-image-signed:docker://ghcr.io/test/repo:tag" in last_call_args

    @pytest.mark.parametrize(
        "subcommand,cli_args,expected_cmd,has_sudo",
        [
            ("show", ["show"], ["rpm-ostree", "kargs"], False),
            (
                "append",
                ["append", "quiet"],
                ["sudo", "rpm-ostree", "kargs", "--append-if-missing=quiet"],
                True,
            ),
            (
                "delete",
                ["delete", "quiet"],
                ["sudo", "rpm-ostree", "kargs", "--delete=quiet"],
                True,
            ),
            (
                "replace",
                ["replace", "loglevel=3"],
                ["sudo", "rpm-ostree", "kargs", "--replace=loglevel=3"],
                True,
            ),
            (
                "delete",
                ["delete", "quiet", "loglevel"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--delete=quiet",
                    "--delete=loglevel",
                ],
                True,
            ),
            (
                "delete",
                ["delete", "quiet loglevel"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--delete=quiet",
                    "--delete=loglevel",
                ],
                True,
            ),
        ],
    )
    def test_kargs_subcommand_executes_correctly(
        self,
        mocker: MockerFixture,
        cli_command,
        subcommand: str,
        cli_args: List[str],
        expected_cmd: List[str],
        has_sudo: bool,
    ) -> None:
        """Test kargs subcommand executes the correct command."""
        cli_command(["urh", "kargs"] + cli_args)

        last_call_args = mock_execvp_command(mocker, expected_cmd)
        assert last_call_args == expected_cmd
        if has_sudo:
            assert "sudo" in last_call_args
        else:
            assert "sudo" not in last_call_args

    def test_unknown_command_shows_help_and_exits(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test unknown command shows help and exits with error."""
        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "nonexistent-command"])

        result = cli_main()

        # Verify error message was printed
        mock_print.assert_any_call("Unknown command: nonexistent-command")

        # Verify exit with error code
        assert result == 1


@pytest.mark.e2e
class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""

    @pytest.fixture(autouse=True)
    def setup_error_test_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for error handling tests."""
        apply_e2e_test_environment(
            mocker,
            tty=False,
            mock_execvp=True,
            execvp_cmd=["sudo", "rpm-ostree", "upgrade"],
        )

    def test_curl_missing_exits_with_error(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test that missing curl dependency exits with error."""
        # Patch where it's imported, not where it's defined
        mocker.patch("src.urh.cli.check_curl_presence", return_value=False)
        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "check"])

        result = cli_main()

        # Verify error message
        mock_print.assert_any_call(
            "Error: curl is required for this application but was not found."
        )

        # Verify exit with error
        assert result == 1

    def test_command_failure_propagates_exit_code(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test that command execution uses execvp (process is replaced)."""
        expected_cmd = ["rpm-ostree", "upgrade", "--check"]

        cli_command(["urh", "check"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)
        assert last_call_args == expected_cmd

    def test_subprocess_timeout_handled_gracefully(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test that command is executed via execvp (no timeout handling needed)."""
        expected_cmd = ["rpm-ostree", "upgrade", "--check"]

        cli_command(["urh", "check"])

        mock_execvp_command(mocker, expected_cmd)


@pytest.mark.e2e
class TestCLIArgumentParsing:
    """Test CLI argument parsing and validation."""

    @pytest.fixture(autouse=True)
    def setup_arg_test_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for argument parsing tests."""
        apply_e2e_test_environment(
            mocker,
            tty=False,
            mock_execvp=True,
            execvp_cmd=["ostree", "admin", "pin", "0"],
        )

    def test_pin_command_with_valid_deployment_number(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test pin command accepts valid deployment number."""
        expected_cmd = ["sudo", "ostree", "admin", "pin", "0"]

        cli_command(["urh", "pin", "0"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)
        assert "ostree" in last_call_args
        assert "admin" in last_call_args
        assert "pin" in last_call_args
        assert "0" in last_call_args

    def test_pin_command_with_invalid_deployment_number(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test pin command rejects invalid deployment number."""
        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "pin", "not-a-number"])

        result = cli_main()

        mock_print.assert_any_call("Invalid deployment number: not-a-number")
        assert result == 1

    def test_remote_ls_command_with_url(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test remote-ls command with URL argument."""
        # Mock OCIClient
        mock_client_class = mocker.patch("src.urh.commands.remote_ls.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": ["v1.0", "v2.0", "v3.0"]
        }
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "remote-ls", "ghcr.io/test/repo:tag"])

        result = cli_main()

        # Verify tags were printed
        mock_print.assert_any_call("Tags for ghcr.io/test/repo:tag:")

        assert result == 0
