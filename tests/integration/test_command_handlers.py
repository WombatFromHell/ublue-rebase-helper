"""
Integration tests for command handlers.

Tests the CommandRegistry and command handler logic, including:
- Command registration and retrieval
- Command handler execution with mocked subprocess
- Conditional sudo logic (kargs command)
- Submenu flows for commands with options

These tests focus on module-level integration between CommandRegistry,
command handlers, and their dependencies.
"""

import inspect
from typing import List

import pytest
from pytest_mock import MockerFixture

from src.urh.commands.kargs import handle_kargs
from src.urh.commands.pin import handle_pin
from src.urh.commands.rebase import handle_rebase
from src.urh.commands.registry import CommandRegistry  # noqa: F401
from src.urh.commands.remote_ls import handle_remote_ls
from src.urh.commands.rm import handle_rm
from src.urh.commands.simple_ops import (
    handle_check,
    handle_ls,
    handle_rollback,
    handle_upgrade,
)
from src.urh.commands.undeploy import handle_undeploy
from src.urh.commands.unpin import handle_unpin


@pytest.mark.integration
class TestCommandRegistry:
    """Test CommandRegistry functionality."""

    def test_all_commands_registered(self) -> None:
        """Test that all expected commands are registered."""
        registry = CommandRegistry()
        commands = registry.get_commands()

        command_names = {cmd.name for cmd in commands}
        expected_commands = {
            "check",
            "kargs",
            "ls",
            "pin",
            "rebase",
            "remote-ls",
            "rm",
            "rollback",
            "unpin",
            "undeploy",
            "upgrade",
        }

        assert command_names == expected_commands

    def test_get_command_returns_correct_definition(
        self, command_sudo_params: tuple
    ) -> None:
        """Test that get_command returns correct CommandDefinition."""
        registry = CommandRegistry()
        command_name, expected_sudo = command_sudo_params

        cmd = registry.get_command(command_name)

        assert cmd is not None
        assert cmd.name == command_name
        assert cmd.requires_sudo == expected_sudo

    def test_get_command_returns_none_for_unknown_command(self) -> None:
        """Test that get_command returns None for unknown commands."""
        registry = CommandRegistry()

        cmd = registry.get_command("nonexistent-command")

        assert cmd is None


@pytest.mark.integration
class TestSimpleCommandHandlers:
    """Test simple command handlers (no submenu)."""

    @pytest.fixture(autouse=True)
    def setup_handler_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for command handler tests."""
        mocker.patch("sys.exit")
        mocker.patch("src.urh.menu.get_user_input", return_value="y")

    @pytest.mark.parametrize(
        "command,expected_cmd",
        [
            ("check", ["sudo", "bootc", "upgrade", "--check"]),
            ("upgrade", ["sudo", "bootc", "upgrade"]),
            ("rollback", ["sudo", "rpm-ostree", "rollback"]),
        ],
    )
    def test_simple_command_handlers_build_correct_command(
        self, mocker: MockerFixture, command: str, expected_cmd: list
    ) -> None:
        """Test that simple command handlers build the correct subprocess command."""
        mock_run = mocker.patch(
            "src.urh.commands.simple_ops._run_command", return_value=0
        )

        handler = {
            "check": handle_check,
            "ls": handle_ls,
            "upgrade": handle_upgrade,
            "rollback": handle_rollback,
        }[command]
        handler([])

        mock_run.assert_called_once_with(expected_cmd)

    def test_handle_ls_prints_parsed_summary_without_elevation(
        self, mocker: MockerFixture, capsys
    ) -> None:
        """ls renders the parsed deployment list; rpm-ostree status --json needs no root."""
        from src.urh.deployment import DeploymentInfo

        mocker.patch(
            "src.urh.deployment.get_deployment_info",
            return_value=[
                DeploymentInfo(
                    deployment_index=0,
                    is_current=True,
                    is_pinned=False,
                    repository="test/repo:testing",
                    version="42.20231115.0",
                    image_ref="ghcr.io/test/repo:testing",
                ),
                DeploymentInfo(
                    deployment_index=1,
                    is_current=False,
                    is_pinned=True,
                    repository="test/repo:stable",
                    version="41.20231110.0",
                    image_ref="ghcr.io/test/repo:stable",
                ),
            ],
        )
        mock_run = mocker.patch("src.urh.commands.simple_ops._run_command")

        assert handle_ls([]) == 0
        assert mock_run.called is False

        out = capsys.readouterr().out
        assert "● 0  ghcr.io/test/repo:testing" in out
        assert "    Version: 42.20231115.0" in out
        assert "* 1  ghcr.io/test/repo:stable" in out
        assert "     Pinned: yes" in out
        assert "Indices match urh pin / unpin / rm / undeploy." in out


@pytest.mark.integration
class TestKargsCommand:
    """Test kargs command with subcommands and conditional sudo logic."""

    @pytest.fixture(autouse=True)
    def setup_kargs_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for kargs tests."""
        mocker.patch("sys.exit")
        mocker.patch("src.urh.menu.get_user_input", return_value="y")

    def test_kargs_no_args_shows_menu(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs command without arguments shows submenu."""
        # Mock rpm-ostree commands (status, kargs) to avoid FileNotFoundError

        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        # Use dependency injection: create mock menu system and inject it
        mock_menu = mocker.MagicMock()
        mock_menu.show_menu.return_value = "show"

        handle_kargs([], menu_system=mock_menu)

        mock_menu.show_menu.assert_called_once()
        mock_run.assert_called_once_with(["rpm-ostree", "kargs"])

    def test_kargs_show_subcommand(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs show subcommand (read-only, no sudo)."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["show"], menu_system=None)

        mock_run.assert_called_once_with(["rpm-ostree", "kargs"])

    @pytest.mark.parametrize(
        "subcommand,cli_args,expected_cmd",
        [
            (
                "append",
                ["append", "quiet"],
                ["sudo", "rpm-ostree", "kargs", "--append-if-missing=quiet"],
            ),
            (
                "append",
                ["append", "quiet", "loglevel=3"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--append-if-missing=quiet",
                    "--append-if-missing=loglevel=3",
                ],
            ),
            (
                "append",
                ["append", "quiet loglevel=3"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--append-if-missing=quiet",
                    "--append-if-missing=loglevel=3",
                ],
            ),
            (
                "delete",
                ["delete", "quiet"],
                ["sudo", "rpm-ostree", "kargs", "--delete-if-present=quiet"],
            ),
            (
                "delete",
                ["delete", "quiet", "loglevel"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--delete-if-present=quiet",
                    "--delete-if-present=loglevel",
                ],
            ),
            (
                "delete",
                ["delete", "quiet loglevel"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--delete-if-present=quiet",
                    "--delete-if-present=loglevel",
                ],
            ),
            (
                "replace",
                ["replace", "loglevel=3"],
                ["sudo", "rpm-ostree", "kargs", "--replace=loglevel=3"],
            ),
            (
                "replace",
                ["replace", "loglevel=3", "splash=silent"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--replace=loglevel=3",
                    "--replace=splash=silent",
                ],
            ),
            (
                "replace",
                ["replace", "loglevel=3 splash=silent"],
                [
                    "sudo",
                    "rpm-ostree",
                    "kargs",
                    "--replace=loglevel=3",
                    "--replace=splash=silent",
                ],
            ),
            (
                "editor",
                ["editor"],
                ["sudo", "rpm-ostree", "kargs", "--editor"],
            ),
        ],
    )
    def test_kargs_subcommand_executes_correctly(
        self,
        mocker: MockerFixture,
        mock_rpm_ostree_commands,
        subcommand: str,
        cli_args: List[str],
        expected_cmd: List[str],
    ) -> None:
        """Test kargs subcommand executes the correct command."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(cli_args, menu_system=None)

        call_args = mock_run.call_args[0][0]
        assert call_args == expected_cmd

    def test_kargs_append_subcommand_no_args_error(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs append subcommand errors without arguments."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mock_print = mocker.patch("builtins.print")

        handle_kargs(["append"], menu_system=None)

        mock_print.assert_called()
        mock_run.assert_not_called()

    def test_kargs_delete_subcommand_with_sudo(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs delete subcommand uses sudo."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["delete", "quiet"], menu_system=None)

        call_args = mock_run.call_args[0][0]
        assert call_args == ["sudo", "rpm-ostree", "kargs", "--delete-if-present=quiet"]

    def test_kargs_delete_subcommand_multiple_args(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs delete subcommand with multiple arguments."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["delete", "quiet", "loglevel"], menu_system=None)

        call_args = mock_run.call_args[0][0]
        assert call_args == [
            "sudo",
            "rpm-ostree",
            "kargs",
            "--delete-if-present=quiet",
            "--delete-if-present=loglevel",
        ]

    def test_kargs_delete_subcommand_space_delimited(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs delete subcommand with space-delimited arguments."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["delete", "quiet loglevel"], menu_system=None)

        call_args = mock_run.call_args[0][0]
        assert call_args == [
            "sudo",
            "rpm-ostree",
            "kargs",
            "--delete-if-present=quiet",
            "--delete-if-present=loglevel",
        ]

    def test_kargs_delete_subcommand_no_args_error(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs delete subcommand errors without arguments."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mock_print = mocker.patch("builtins.print")

        handle_kargs(["delete"], menu_system=None)

        mock_print.assert_called()
        mock_run.assert_not_called()

    def test_kargs_replace_subcommand_with_sudo(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs replace subcommand uses sudo."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["replace", "loglevel=3"], menu_system=None)

        call_args = mock_run.call_args[0][0]
        assert call_args == ["sudo", "rpm-ostree", "kargs", "--replace=loglevel=3"]

    def test_kargs_replace_subcommand_multiple_args(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs replace subcommand with multiple arguments."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["replace", "loglevel=3", "splash=silent"], menu_system=None)

        call_args = mock_run.call_args[0][0]
        assert call_args == [
            "sudo",
            "rpm-ostree",
            "kargs",
            "--replace=loglevel=3",
            "--replace=splash=silent",
        ]

    def test_kargs_replace_subcommand_space_delimited(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs replace subcommand with space-delimited arguments."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["replace", "loglevel=3 splash=silent"], menu_system=None)

        call_args = mock_run.call_args[0][0]
        assert call_args == [
            "sudo",
            "rpm-ostree",
            "kargs",
            "--replace=loglevel=3",
            "--replace=splash=silent",
        ]

    def test_kargs_replace_subcommand_no_args_error(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs replace subcommand errors without arguments."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mock_print = mocker.patch("builtins.print")

        handle_kargs(["replace"], menu_system=None)

        mock_print.assert_called()
        mock_run.assert_not_called()

    def test_kargs_replace_subcommand_invalid_format(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs replace subcommand errors with invalid format."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mock_print = mocker.patch("builtins.print")

        handle_kargs(["replace", "invalid_no_equals"], menu_system=None)

        mock_print.assert_called()
        mock_run.assert_not_called()

    def test_kargs_with_help_flag_no_sudo(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs command with --help flag doesn't use sudo."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)

        handle_kargs(["--help"], menu_system=None)

        # Should not include sudo for help flag
        call_args = mock_run.call_args[0][0]
        assert "sudo" not in call_args
        assert "rpm-ostree" in call_args
        assert "kargs" in call_args
        assert "--help" in call_args

    def test_kargs_legacy_mode_direct_args(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test kargs command in legacy mode with direct arguments."""
        mock_run = mocker.patch("src.urh.commands.shared._run_command", return_value=0)

        handle_kargs(["--append-if-missing=quiet"], menu_system=None)

        # Legacy mode should use sudo for modification flags
        call_args = mock_run.call_args[0][0]
        assert "sudo" in call_args
        assert "rpm-ostree" in call_args
        assert "kargs" in call_args

    @pytest.mark.parametrize(
        "menu_selection,user_input,expected_flags",
        [
            ("append", "quiet", ["--append-if-missing=quiet"]),
            (
                "append",
                "quiet loglevel=3",
                ["--append-if-missing=quiet", "--append-if-missing=loglevel=3"],
            ),
            ("delete", "quiet", ["--delete-if-present=quiet"]),
            (
                "delete",
                "quiet loglevel",
                ["--delete-if-present=quiet", "--delete-if-present=loglevel"],
            ),
            ("replace", "loglevel=3", ["--replace=loglevel=3"]),
            (
                "replace",
                "loglevel=3 splash=silent",
                ["--replace=loglevel=3", "--replace=splash=silent"],
            ),
        ],
    )
    def test_kargs_menu_subcommand_single_and_multi_karg(
        self,
        mocker: MockerFixture,
        mock_rpm_ostree_commands,
        menu_selection: str,
        user_input: str,
        expected_flags: list,
    ) -> None:
        """Test menu path passes correct flags for single and multiple kargs."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mocker.patch(
            "src.urh.commands.kargs._prompt_for_karg_value", return_value=user_input
        )
        mock_menu = mocker.MagicMock()
        mock_menu.show_menu.return_value = menu_selection

        handle_kargs([], menu_system=mock_menu)

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "sudo"
        assert call_args[1:3] == ["rpm-ostree", "kargs"]
        assert call_args[3:] == expected_flags

    def test_kargs_menu_editor_subcommand(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test menu path for editor subcommand runs --editor."""
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mock_menu = mocker.MagicMock()
        mock_menu.show_menu.return_value = "editor"

        handle_kargs([], menu_system=mock_menu)

        call_args = mock_run.call_args[0][0]
        assert call_args == ["sudo", "rpm-ostree", "kargs", "--editor"]

    def test_kargs_menu_empty_input_returns_error(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test menu path returns error on empty input."""
        mocker.patch("src.urh.commands.kargs._prompt_for_karg_value", return_value="  ")
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mocker.patch("builtins.print")
        mock_menu = mocker.MagicMock()
        mock_menu.show_menu.return_value = "append"

        result = handle_kargs([], menu_system=mock_menu)

        assert result == 1
        mock_run.assert_not_called()

    def test_kargs_menu_cancel_returns_zero(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Test menu path returns 0 on prompt cancel (None)."""
        mocker.patch("src.urh.commands.kargs._prompt_for_karg_value", return_value=None)
        mock_run = mocker.patch("src.urh.commands.kargs._run_command", return_value=0)
        mock_menu = mocker.MagicMock()
        mock_menu.show_menu.return_value = "delete"

        result = handle_kargs([], menu_system=mock_menu)

        assert result == 0
        mock_run.assert_not_called()


@pytest.mark.integration
class TestRebaseCommand:
    """Test rebase command handler."""

    @pytest.fixture(autouse=True)
    def setup_rebase_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for rebase tests."""
        mocker.patch("sys.exit")

    def test_rebase_with_url_argument(self, mocker: MockerFixture) -> None:
        """Test rebase command with URL argument."""
        mock_run = mocker.patch("src.urh.commands.rebase._run_command", return_value=0)

        handle_rebase(["ghcr.io/test/repo:tag"], menu_system=None)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "sudo" in call_args
        assert "rpm-ostree" in call_args
        assert "rebase" in call_args
        assert "ostree-image-signed:docker://ghcr.io/test/repo:tag" in call_args

    def test_rebase_with_menu_selection(self, mocker: MockerFixture) -> None:
        """Test rebase command with menu selection."""
        mock_menu = mocker.MagicMock()
        mock_menu.show_menu.return_value = "ghcr.io/test/repo:stable"

        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        # Mock deployment info to avoid rpm-ostree calls
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )
        mocker.patch(
            "src.urh.deployment.format_menu_header", return_value="Test Header"
        )

        mock_run = mocker.patch("src.urh.commands.rebase._run_command", return_value=0)

        handle_rebase([], menu_system=mock_menu)  # No args, shows menu

        mock_menu.show_menu.assert_called_once()
        mock_run.assert_called_once()


@pytest.mark.integration
class TestRemoteLsCommand:
    """Test remote-ls command handler."""

    @pytest.fixture(autouse=True)
    def setup_remote_ls_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for remote-ls tests."""
        mocker.patch("sys.exit")

    def test_remote_ls_with_url_argument(self, mocker: MockerFixture) -> None:
        """Test remote-ls command with URL argument."""
        mock_client_class = mocker.patch("src.urh.commands.remote_ls.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        handle_remote_ls(["ghcr.io/test/repo:tag"], menu_system=None)

        mock_client_class.assert_called_once_with("test/repo")
        mock_client.fetch_repository_tags.assert_called_once()

    def test_remote_ls_with_menu_selection(self, mocker: MockerFixture) -> None:
        """Test remote-ls command with menu selection."""
        mock_menu = mocker.MagicMock()
        mock_menu.show_menu.return_value = "ghcr.io/test/repo:stable"

        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        # Mock deployment info to avoid rpm-ostree calls
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )
        mocker.patch(
            "src.urh.deployment.format_menu_header", return_value="Test Header"
        )

        mock_client_class = mocker.patch("src.urh.commands.remote_ls.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        handle_remote_ls([], menu_system=mock_menu)  # No args, shows menu

        mock_menu.show_menu.assert_called_once()


@pytest.mark.integration
class TestActionConfirmation:
    """Mutating actions ask for confirmation; read-only actions never do."""

    @pytest.fixture(autouse=True)
    def setup_confirmation_environment(self, mocker: MockerFixture) -> None:
        """Patch every command module's exec path and the y/N prompt."""
        mocker.patch("sys.exit")
        self.ask = mocker.patch("src.urh.menu.get_user_input", return_value="y")
        self.simple_run = mocker.patch(
            "src.urh.commands.simple_ops._run_command", return_value=0
        )
        self.deploy_run = mocker.patch(
            "src.urh.commands.deployment_helpers._run_command", return_value=0
        )
        self.kargs_run = mocker.patch(
            "src.urh.commands.kargs._run_command", return_value=0
        )

    @staticmethod
    def _invoke(handler, args: List[str]) -> int:
        """Call a handler with the signature it actually declares."""
        if "menu_system" in inspect.signature(handler).parameters:
            return handler(args, menu_system=None)
        return handler(args)

    def _ran(self) -> list[str]:
        """The command actually execvp'd, from whichever module ran it."""
        for mock in (self.simple_run, self.deploy_run, self.kargs_run):
            if mock.called:
                return mock.call_args[0][0]
        raise AssertionError("nothing was executed")

    @pytest.mark.parametrize(
        "handler,args,expected_cmd",
        [
            (handle_upgrade, [], ["sudo", "bootc", "upgrade"]),
            (handle_rollback, [], ["sudo", "rpm-ostree", "rollback"]),
            (handle_pin, ["0"], ["sudo", "ostree", "admin", "pin", "0"]),
            (handle_unpin, ["0"], ["sudo", "ostree", "admin", "pin", "-u", "0"]),
            (handle_rm, ["0"], ["sudo", "ostree", "admin", "undeploy", "0"]),
            (handle_undeploy, ["0"], ["sudo", "ostree", "admin", "undeploy", "0"]),
            (
                handle_kargs,
                ["append", "quiet"],
                ["sudo", "rpm-ostree", "kargs", "--append-if-missing=quiet"],
            ),
        ],
    )
    def test_confirmed_action_runs_once(
        self, handler, args: List[str], expected_cmd: List[str]
    ) -> None:
        """Answering y runs the command once after exactly one prompt."""
        assert self._invoke(handler, args) == 0
        assert self.ask.call_count == 1
        assert self._ran() == expected_cmd

    @pytest.mark.parametrize(
        "handler,args",
        [
            (handle_upgrade, []),
            (handle_rollback, []),
            (handle_pin, ["0"]),
            (handle_unpin, ["0"]),
            (handle_rm, ["0"]),
            (handle_undeploy, ["0"]),
            (handle_kargs, ["append", "quiet"]),
        ],
    )
    def test_declined_action_runs_nothing(
        self, handler, args: List[str], capsys
    ) -> None:
        """Any answer other than y (default [N]) execvp's nothing and exits 0."""
        self.ask.return_value = "n"

        assert self._invoke(handler, args) == 0
        assert self.ask.call_count == 1
        assert (
            self.simple_run.called,
            self.deploy_run.called,
            self.kargs_run.called,
        ) == (
            False,
            False,
            False,
        )
        assert "Cancelled" in capsys.readouterr().out

    @pytest.mark.parametrize(
        "handler,expected_cmd",
        [
            (handle_check, ["sudo", "bootc", "upgrade", "--check"]),
        ],
    )
    def test_read_only_actions_never_ask(
        self, handler, expected_cmd: List[str]
    ) -> None:
        """check changes nothing, so prompting for it is a bug."""
        self.ask.side_effect = AssertionError("read-only command prompted the user")

        self._invoke(handler, [])

        assert self.simple_run.call_args[0][0] == expected_cmd

    def test_ls_is_read_only_and_never_asked(self, capsys) -> None:
        """ls renders locally, prompts nobody and execvp's nothing."""
        self.ask.side_effect = AssertionError("read-only command prompted the user")

        assert self._invoke(handle_ls, []) == 0
        assert self.simple_run.called is False
        assert "Deployments:" in capsys.readouterr().out

    def test_cancelled_stdin_declines(self, mocker: MockerFixture) -> None:
        """Closed stdin or Ctrl-C counts as a decline, not a crash."""
        from src.urh.commands.shared import confirm_action

        for error in (EOFError, KeyboardInterrupt):
            mocker.patch("src.urh.menu.get_user_input", side_effect=error)
            assert confirm_action("Confirm? [y/N]: ") is False


@pytest.mark.integration
class TestDeploymentCommands:
    """Test deployment-related command handlers (pin, unpin, rm, undeploy)."""

    @pytest.fixture(autouse=True)
    def setup_deployment_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for deployment command tests."""
        mocker.patch("sys.exit")
        mocker.patch("src.urh.menu.get_user_input", return_value="y")

    def test_pin_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test pin command with deployment number argument."""
        mock_run = mocker.patch(
            "src.urh.commands.deployment_helpers._run_command", return_value=0
        )

        handle_pin(["0"], menu_system=None)

        mock_run.assert_called_once_with(["sudo", "ostree", "admin", "pin", "0"])

    def test_pin_with_invalid_number_exits(self, mocker: MockerFixture) -> None:
        """Test pin command with invalid deployment number."""
        mock_print = mocker.patch("builtins.print")

        result = handle_pin(["not-a-number"], menu_system=None)

        mock_print.assert_called_with("Invalid deployment number: not-a-number")
        assert result == 1

    def test_unpin_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test unpin command with deployment number argument."""
        mock_run = mocker.patch(
            "src.urh.commands.deployment_helpers._run_command", return_value=0
        )

        handle_unpin(["0"], menu_system=None)

        mock_run.assert_called_once_with(["sudo", "ostree", "admin", "pin", "-u", "0"])

    def test_rm_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test rm command with deployment number argument."""
        mock_run = mocker.patch(
            "src.urh.commands.deployment_helpers._run_command", return_value=0
        )

        handle_rm(["0"], menu_system=None)

        mock_run.assert_called_once_with(["sudo", "ostree", "admin", "undeploy", "0"])

    def test_undeploy_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test undeploy command with deployment number argument."""
        mock_run = mocker.patch(
            "src.urh.commands.deployment_helpers._run_command", return_value=0
        )

        handle_undeploy(["0"], menu_system=None)

        mock_run.assert_called_once_with(["sudo", "ostree", "admin", "undeploy", "0"])
