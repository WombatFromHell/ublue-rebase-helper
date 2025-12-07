"""Comprehensive tests for the commands module to improve coverage."""

from src.urh.commands import (
    CommandRegistry,
    _run_command,
    run_command_safe,
    run_command_with_conditional_sudo,
)
from src.urh.menu import MenuExitException


class TestCommandRegistryHandlers:
    """Test all command handler methods for better coverage."""

    def test_handle_pin_with_args(self, mocker):
        """Test _handle_pin with arguments provided."""
        registry = CommandRegistry()

        # Mock all necessary functions
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")
        mocker.patch("builtins.print")

        registry._handle_pin(["1"])

        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_handle_pin_with_invalid_args(self, mocker):
        """Test _handle_pin with invalid argument."""
        registry = CommandRegistry()

        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_pin(["invalid"])

        mock_print.assert_called_once_with("Invalid deployment number: invalid")
        mock_sys_exit.assert_called_once_with(1)

    def test_handle_pin_no_deployments(self, mocker):
        """Test _handle_pin when no deployments are found."""
        mock_get_deployment_info = mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=[]
        )
        mock_print = mocker.patch("builtins.print")
        registry = CommandRegistry()

        registry._handle_pin([])

        mock_get_deployment_info.assert_called_once()
        mock_print.assert_called_once_with("No deployments found.")

    def test_handle_unpin_with_args(self, mocker):
        """Test _handle_unpin with arguments provided."""
        registry = CommandRegistry()

        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_unpin(["1"])

        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "-u", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_handle_unpin_with_invalid_args(self, mocker):
        """Test _handle_unpin with invalid argument."""
        registry = CommandRegistry()

        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_unpin(["invalid"])

        mock_print.assert_called_once_with("Invalid deployment number: invalid")
        mock_sys_exit.assert_called_once_with(1)

    def test_handle_rm_with_args(self, mocker):
        """Test _handle_rm with arguments provided."""
        registry = CommandRegistry()

        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_rm(["1"])

        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "cleanup", "-r", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_handle_rm_with_invalid_args(self, mocker):
        """Test _handle_rm with invalid argument."""
        registry = CommandRegistry()

        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_rm(["invalid"])

        mock_print.assert_called_once_with("Invalid deployment number: invalid")
        mock_sys_exit.assert_called_once_with(1)

    def test_handle_undeploy_with_args(self, mocker):
        """Test _handle_undeploy with arguments provided."""
        registry = CommandRegistry()

        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_undeploy(["1"])

        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "undeploy", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_handle_undeploy_with_invalid_args(self, mocker):
        """Test _handle_undeploy with invalid argument."""
        registry = CommandRegistry()

        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_undeploy(["invalid"])

        mock_print.assert_called_once_with("Invalid deployment number: invalid")
        mock_sys_exit.assert_called_once_with(1)

    def test_get_deployment_number_for_pin_with_menu_exit(self, mocker):
        """Test _get_deployment_number_for_pin handles MenuExitException."""
        registry = CommandRegistry()

        # Mock the select function to raise MenuExitException
        mocker.patch.object(
            registry, "_select_deployment_to_pin", side_effect=MenuExitException()
        )

        result = registry._get_deployment_number_for_pin([], [])

        assert result is None

    def test_get_deployment_number_for_unpin_with_menu_exit(self, mocker):
        """Test _get_deployment_number_for_unpin handles MenuExitException."""
        registry = CommandRegistry()

        # Mock the select function to raise MenuExitException
        mocker.patch.object(
            registry, "_select_deployment_to_unpin", side_effect=MenuExitException()
        )

        result = registry._get_deployment_number_for_unpin([], [])

        assert result is None

    def test_get_deployment_number_for_undeploy_with_menu_exit(self, mocker):
        """Test _get_deployment_number_for_undeploy handles MenuExitException."""
        registry = CommandRegistry()

        # Mock the select function to raise MenuExitException
        mocker.patch.object(
            registry,
            "_select_deployment_to_undeploy_with_confirmation",
            side_effect=MenuExitException(),
        )

        result = registry._get_deployment_number_for_undeploy([], [])

        assert result is None

    def test_should_use_sudo_for_kargs_help_flags(self):
        """Test _should_use_sudo_for_kargs with help flags."""
        registry = CommandRegistry()

        # Test help flags that should not use sudo
        assert not registry._should_use_sudo_for_kargs(["--help"])
        assert not registry._should_use_sudo_for_kargs(["-h"])
        assert not registry._should_use_sudo_for_kargs(["--help-all"])

        # Test other flags that should use sudo
        assert registry._should_use_sudo_for_kargs(["--append=test"])

    def test_get_all_commands(self):
        """Test get_commands returns all expected commands."""
        registry = CommandRegistry()
        commands = registry.get_commands()

        assert len(commands) > 0
        command_names = [cmd.name for cmd in commands]

        # Check that all expected commands are present
        expected_commands = [
            "check",
            "kargs",
            "ls",
            "rebase",
            "remote-ls",
            "upgrade",
            "rollback",
            "pin",
            "unpin",
            "rm",
            "undeploy",
        ]
        for cmd in expected_commands:
            assert cmd in command_names

    def test_get_specific_command(self):
        """Test get_command returns specific command."""
        registry = CommandRegistry()

        cmd = registry.get_command("check")
        assert cmd is not None
        assert cmd.name == "check"

        cmd = registry.get_command("nonexistent")
        assert cmd is None


class TestRunCommandFunctions:
    """Test run_command functions for better coverage."""

    def test_run_command_safe_with_timeout(self, mocker):
        """Test run_command_safe with timeout."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess_run = mocker.patch("subprocess.run", return_value=mock_result)

        result = run_command_safe("echo", "test", timeout=10)

        assert result == 0
        mock_subprocess_run.assert_called_once()

    def test_run_command_safe_timeout_expired(self, mocker):
        """Test run_command_safe when timeout occurs."""
        import subprocess

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["echo"], timeout=10),
        )

        result = run_command_safe("echo", "test", timeout=10)

        assert result == 124  # Standard timeout exit code

    def test_run_command_safe_command_not_found(self, mocker):
        """Test run_command_safe when command is not found."""
        import subprocess

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["nonexistent"]),
        )

        # Actually, the FileNotFoundError is raised differently
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        result = run_command_safe("nonexistent")

        assert result == 1  # Error exit code

    def test_run_command_with_timeout(self, mocker):
        """Test _run_command with timeout."""
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        result = _run_command(["echo", "test"], timeout=10)

        assert result == 0

    def test_run_command_timeout_expired(self, mocker):
        """Test _run_command when timeout occurs."""
        import subprocess

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["echo"], timeout=10),
        )

        result = _run_command(["echo", "test"], timeout=10)

        assert result == 124  # Standard timeout exit code

    def test_run_command_command_not_found(self, mocker):
        """Test _run_command when command is not found."""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        result = _run_command(["nonexistent"])

        assert result == 1  # Error exit code


class TestRunCommandWithConditionalSudo:
    """Test run_command_with_conditional_sudo function."""

    def test_run_command_with_conditional_sudo_static(self, mocker):
        """Test run_command_with_conditional_sudo with static sudo setting."""
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        run_command_with_conditional_sudo(["echo", "test"], ["arg"], requires_sudo=True)

        mock_run_command.assert_called_once_with(["sudo", "echo", "test", "arg"])
        mock_sys_exit.assert_called_once_with(0)

    def test_run_command_with_conditional_sudo_conditional(self, mocker):
        """Test run_command_with_conditional_sudo with conditional function."""
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        def conditional_func(args):
            return len(args) > 0

        run_command_with_conditional_sudo(
            ["echo", "test"],
            ["arg"],
            requires_sudo=False,  # This should be ignored
            conditional_sudo_func=conditional_func,
        )

        mock_run_command.assert_called_once_with(["sudo", "echo", "test", "arg"])
        mock_sys_exit.assert_called_once_with(0)

    def test_run_command_with_conditional_sudo_no_sudo(self, mocker):
        """Test run_command_with_conditional_sudo without sudo."""
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        def conditional_func(args):
            return len(args) == 0

        run_command_with_conditional_sudo(
            ["echo", "test"],
            ["arg"],
            requires_sudo=True,  # This should be ignored
            conditional_sudo_func=conditional_func,
        )

        mock_run_command.assert_called_once_with(["echo", "test", "arg"])
        mock_sys_exit.assert_called_once_with(0)


class TestCommandArgumentParser:
    """Test ArgumentParser functionality."""

    def test_argument_parser_parse_or_prompt_with_args(self):
        """Test ArgumentParser parse_or_prompt with arguments."""
        from src.urh.commands import ArgumentParser

        parser = ArgumentParser()
        result = parser.parse_or_prompt(["test"], lambda: "prompt_result")

        assert result == "test"

    def test_argument_parser_parse_or_prompt_with_menu_exit(self):
        """Test ArgumentParser parse_or_prompt with MenuExitException."""
        from src.urh.commands import ArgumentParser

        def prompt_func():
            raise MenuExitException()

        parser = ArgumentParser()
        result = parser.parse_or_prompt([], prompt_func)

        assert result is None

    def test_argument_parser_parse_or_prompt_with_validator(self):
        """Test ArgumentParser parse_or_prompt with validator."""
        from src.urh.commands import ArgumentParser

        def validator(x):
            return x.upper()

        parser = ArgumentParser()
        result = parser.parse_or_prompt(["test"], lambda: "prompt_result", validator)

        assert result == "TEST"

    def test_argument_parser_parse_or_prompt_with_invalid_validator(self, mocker):
        """Test ArgumentParser parse_or_prompt with invalid validator."""

        from src.urh.commands import ArgumentParser

        def validator(x):
            raise ValueError("Invalid value")

        mocker.patch("src.urh.commands.logger.error")
        mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        parser = ArgumentParser()
        # This should catch the ValueError and exit
        parser.parse_or_prompt(["test"], lambda: "prompt_result", validator)

        # Validate that print and sys.exit were called
        mock_sys_exit.assert_called_once_with(1)


class TestCommandHandlerErrorPaths:
    """Test error paths in command handlers."""

    def test_handle_ls_error(self, mocker):
        """Test _handle_ls when subprocess raises CalledProcessError."""
        import subprocess

        registry = CommandRegistry()

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(
                1, ["rpm-ostree", "status", "-v"]
            ),
        )
        mocker.patch("builtins.print")
        mocker.patch("src.urh.commands.logger.error")
        mock_sys_exit = mocker.patch("sys.exit")

        registry._handle_ls([])

        # Since CalledProcessError is caught, it should call logger.error and sys.exit(1)
        mock_sys_exit.assert_called_once_with(1)

    def test_get_url_for_remote_ls_no_args(self, mocker):
        """Test _get_url_for_remote_ls when no args and menu selection."""
        registry = CommandRegistry()
        config = mocker.MagicMock()
        config.container_urls.options = ["repo1", "repo2"]

        # Simulate menu selection
        mock_select_url = mocker.patch.object(
            registry, "_select_url_for_remote_ls", return_value="selected_repo"
        )

        url = registry._get_url_for_remote_ls([], config)

        assert url == "selected_repo"
        mock_select_url.assert_called_once_with(config)

    def test_get_url_for_remote_ls_with_menu_exit(self, mocker):
        """Test _get_url_for_remote_ls with MenuExitException."""
        registry = CommandRegistry()
        config = mocker.MagicMock()

        # Mock to raise MenuExitException
        mocker.patch.object(
            registry, "_select_url_for_remote_ls", side_effect=MenuExitException()
        )

        url = registry._get_url_for_remote_ls([], config)

        assert url is None

    def test_select_deployment_to_pin_no_unpinned_deployments(self, mocker):
        """Test _select_deployment_to_pin when no unpinned deployments."""
        from src.urh.deployment import DeploymentInfo

        registry = CommandRegistry()
        mock_print = mocker.patch("builtins.print")

        deployments = [
            DeploymentInfo(0, True, "repo1", "v1", True),  # pinned
            DeploymentInfo(1, False, "repo2", "v2", True),  # pinned
        ]

        result = registry._select_deployment_to_pin(deployments)

        assert result is None
        mock_print.assert_called_once_with("No deployments available to pin.")

    def test_select_deployment_to_unpin_no_pinned_deployments(self, mocker):
        """Test _select_deployment_to_unpin when no pinned deployments."""
        from src.urh.deployment import DeploymentInfo

        registry = CommandRegistry()
        mock_print = mocker.patch("builtins.print")

        deployments = [
            DeploymentInfo(0, True, "repo1", "v1", False),  # not pinned
            DeploymentInfo(1, False, "repo2", "v2", False),  # not pinned
        ]

        result = registry._select_deployment_to_unpin(deployments)

        assert result is None
        mock_print.assert_called_once_with("No deployments are pinned.")

    def test_select_deployment_to_pin_already_pinned(self, mocker):
        """Test _select_deployment_to_pin when selected deployment is already pinned."""
        # Set up environment for non-gum behavior
        import os

        from src.urh.deployment import DeploymentInfo

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        mocker.patch("os.isatty", return_value=True)

        registry = CommandRegistry()
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        mock_print = mocker.patch("builtins.print")
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repo": "test", "version": "v1"},
        )
        mocker.patch(
            "src.urh.deployment.format_deployment_header", return_value="test header"
        )

        # Need to have at least one unpinned deployment so the menu is shown,
        # then select a pinned deployment
        deployments = [
            DeploymentInfo(0, True, "repo1", "v1", False),  # not pinned
            DeploymentInfo(1, False, "repo2", "v2", True),  # pinned
        ]

        # Mock menu selection to return the pinned deployment
        mock_menu_system.show_menu.return_value = (
            1  # Select deployment 1 which is pinned
        )

        result = registry._select_deployment_to_pin(deployments)

        assert result is None
        mock_print.assert_called_once_with("Deployment 1 is already pinned.")

    def test_remote_ls_no_tags_found(self, mocker):
        """Test _handle_remote_ls when no tags are found."""
        registry = CommandRegistry()

        mocker.patch(
            "src.urh.system.extract_repository_from_url", return_value="test/repo"
        )
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_sys_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")
        mock_logger_info = mocker.patch("src.urh.commands.logger.info")

        mock_instance = mocker.MagicMock()
        mock_instance.fetch_repository_tags.return_value = {"tags": []}
        mock_client_class.return_value = mock_instance

        registry._handle_remote_ls(["ghcr.io/test/repo:testing"])

        mock_logger_info.assert_called_once_with(
            "No tags found for ghcr.io/test/repo:testing"
        )
        mock_print.assert_called_once_with(
            "No tags found for ghcr.io/test/repo:testing"
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_cannot_fetch_tags(self, mocker):
        """Test _handle_remote_ls when cannot fetch tags."""
        registry = CommandRegistry()

        mocker.patch(
            "src.urh.system.extract_repository_from_url", return_value="test/repo"
        )
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_sys_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")
        mock_logger_error = mocker.patch("src.urh.commands.logger.error")

        mock_instance = mocker.MagicMock()
        mock_instance.fetch_repository_tags.return_value = None  # Indicates error
        mock_client_class.return_value = mock_instance

        registry._handle_remote_ls(["ghcr.io/test/repo:testing"])

        mock_logger_error.assert_called_once_with(
            "Could not fetch tags for ghcr.io/test/repo:testing"
        )
        mock_print.assert_called_once_with(
            "Could not fetch tags for ghcr.io/test/repo:testing"
        )
        mock_sys_exit.assert_called_once_with(1)
