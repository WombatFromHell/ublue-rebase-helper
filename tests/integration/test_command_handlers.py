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

import pytest
from pytest_mock import MockerFixture

from src.urh.commands import CommandRegistry  # noqa: F401


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


class TestSimpleCommandHandlers:
    """Test simple command handlers (no submenu)."""

    @pytest.fixture(autouse=True)
    def setup_handler_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for command handler tests."""
        mocker.patch("sys.exit")

    @pytest.mark.parametrize(
        "command,expected_cmd",
        [
            ("check", ["rpm-ostree", "upgrade", "--check"]),
            ("upgrade", ["sudo", "rpm-ostree", "upgrade"]),
            ("rollback", ["sudo", "rpm-ostree", "rollback"]),
        ],
    )
    def test_simple_command_handlers_build_correct_command(
        self, mocker: MockerFixture, command: str, expected_cmd: list
    ) -> None:
        """Test that simple command handlers build the correct subprocess command."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        handler = getattr(registry, f"_handle_{command}")
        handler([])

        mock_run.assert_called_once_with(expected_cmd)

    def test_ls_command_prints_status_output(self, mocker: MockerFixture) -> None:
        """Test that ls command prints rpm-ostree status output."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(
            returncode=0, stdout="Status output here"
        )
        mock_print = mocker.patch("builtins.print")

        registry = CommandRegistry()
        registry._handle_ls([])

        mock_print.assert_called_with("Status output here")


class TestKargsCommand:
    """Test kargs command with conditional sudo logic."""

    @pytest.fixture(autouse=True)
    def setup_kargs_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for kargs tests."""
        mocker.patch("sys.exit")

    def test_kargs_no_args_no_sudo(self, mocker: MockerFixture) -> None:
        """Test kargs command without arguments doesn't use sudo."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_kargs([])

        mock_run.assert_called_once_with(["rpm-ostree", "kargs"])

    def test_kargs_with_help_flag_no_sudo(self, mocker: MockerFixture) -> None:
        """Test kargs command with --help flag doesn't use sudo."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_kargs(["--help"])

        # Should not include sudo for help flag
        call_args = mock_run.call_args[0][0]
        assert "sudo" not in call_args

    def test_kargs_with_modification_args_uses_sudo(
        self, mocker: MockerFixture
    ) -> None:
        """Test kargs command with modification arguments uses sudo."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_kargs(["--append", "quiet"])

        # Should include sudo for modification args
        call_args = mock_run.call_args[0][0]
        assert "sudo" in call_args
        assert "rpm-ostree" in call_args
        assert "kargs" in call_args


class TestRebaseCommand:
    """Test rebase command handler."""

    @pytest.fixture(autouse=True)
    def setup_rebase_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for rebase tests."""
        mocker.patch("sys.exit")

    def test_rebase_with_url_argument(self, mocker: MockerFixture) -> None:
        """Test rebase command with URL argument."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_rebase(["ghcr.io/test/repo:tag"])

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "sudo" in call_args
        assert "rpm-ostree" in call_args
        assert "rebase" in call_args
        assert "ostree-image-signed:docker://ghcr.io/test/repo:tag" in call_args

    def test_rebase_with_menu_selection(self, mocker: MockerFixture) -> None:
        """Test rebase command with menu selection."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.return_value = "ghcr.io/test/repo:stable"

        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_rebase([])  # No args, shows menu

        mock_menu_show.assert_called_once()
        mock_run.assert_called_once()


class TestRemoteLsCommand:
    """Test remote-ls command handler."""

    @pytest.fixture(autouse=True)
    def setup_remote_ls_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for remote-ls tests."""
        mocker.patch("sys.exit")

    def test_remote_ls_with_url_argument(self, mocker: MockerFixture) -> None:
        """Test remote-ls command with URL argument."""
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        registry = CommandRegistry()
        registry._handle_remote_ls(["ghcr.io/test/repo:tag"])

        mock_client_class.assert_called_once_with("test/repo")
        mock_client.fetch_repository_tags.assert_called_once()

    def test_remote_ls_with_menu_selection(self, mocker: MockerFixture) -> None:
        """Test remote-ls command with menu selection."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.return_value = "ghcr.io/test/repo:stable"

        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        registry = CommandRegistry()
        registry._handle_remote_ls([])  # No args, shows menu

        mock_menu_show.assert_called_once()


class TestDeploymentCommands:
    """Test deployment-related command handlers (pin, unpin, rm, undeploy)."""

    @pytest.fixture(autouse=True)
    def setup_deployment_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for deployment command tests."""
        mocker.patch("sys.exit")

    def test_pin_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test pin command with deployment number argument."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_pin(["0"])

        mock_run.assert_called_once_with(["sudo", "ostree", "admin", "pin", "0"])

    def test_pin_with_invalid_number_exits(self, mocker: MockerFixture) -> None:
        """Test pin command with invalid deployment number."""
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_pin(["not-a-number"])

        mock_print.assert_called_with("Invalid deployment number: not-a-number")
        mock_exit.assert_called_once_with(1)

    def test_unpin_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test unpin command with deployment number argument."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_unpin(["0"])

        mock_run.assert_called_once_with(["sudo", "ostree", "admin", "pin", "-u", "0"])

    def test_rm_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test rm command with deployment number argument."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_rm(["0"])

        mock_run.assert_called_once_with(["sudo", "rpm-ostree", "cleanup", "-r", "0"])

    def test_undeploy_with_deployment_number(self, mocker: MockerFixture) -> None:
        """Test undeploy command with deployment number argument."""
        mock_run = mocker.patch("src.urh.commands._run_command", return_value=0)

        registry = CommandRegistry()
        registry._handle_undeploy(["0"])

        mock_run.assert_called_once_with(["sudo", "ostree", "admin", "undeploy", "0"])
