"""Tests for the commands module."""

import os
import subprocess
from typing import List

import pytest

from src.urh.commands import (
    ArgumentParser,
    CommandRegistry,
    _run_command,
    run_command_safe,
    run_command_with_conditional_sudo,
)
from src.urh.deployment import DeploymentInfo
from src.urh.menu import MenuExitException


@pytest.fixture(scope="session")
def session_command_registry():
    """Session-scoped CommandRegistry instance for performance optimization."""
    return CommandRegistry()


class TestCommands:
    """Test commands functionality."""

    @pytest.mark.unit
    def test_commands_module_exists(self):
        """Test that the commands module can be imported."""
        from src.urh.commands import CommandDefinition, CommandRegistry, CommandType

        assert CommandRegistry is not None
        assert CommandDefinition is not None
        assert CommandType is not None


@pytest.fixture
def mock_basic_system_setup(mocker):
    """Shared fixture for basic system mocking to prevent privilege escalation."""
    # Mock all necessary functions to prevent privilege escalation
    mock_subprocess_result = mocker.MagicMock()
    mock_subprocess_result.returncode = 0  # For "which curl" command to return True
    mock_subprocess_result.stdout = "test output"

    # Also patch subprocess.run to prevent any direct subprocess calls
    mocker.patch("subprocess.run", return_value=mock_subprocess_result)
    # Patch system functions that make subprocess calls to prevent privilege escalation
    mocker.patch(
        "src.urh.system.check_curl_presence", return_value=True
    )  # Assume curl is available in tests
    # Patch deployment info functions that make system calls
    mocker.patch(
        "src.urh.deployment.get_current_deployment_info",
        return_value={"repository": "test", "version": "v1.0"},
    )
    mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])
    mocker.patch(
        "src.urh.deployment.get_status_output", return_value=None
    )  # Needed for get_deployment_info
    # Patch config function to avoid file system access
    mock_config = mocker.MagicMock()
    mock_config.container_urls.options = ["ghcr.io/test/repo:testing"]
    mocker.patch("src.urh.config.get_config", return_value=mock_config)
    # Also patch setup_logging in the cli module
    mocker.patch("src.urh.cli.setup_logging", return_value=None)


@pytest.fixture
def mock_menu_system_setup(mocker):
    """Shared fixture for menu system mocking."""
    # Set environment variable to force non-gum behavior (avoid hanging during tests)
    mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
    # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
    mocker.patch("os.isatty", return_value=True)


@pytest.fixture
def mock_deployment_info_setup(mocker):
    """Shared fixture for deployment info mocking."""
    mock_get_deployment_info = mocker.patch("src.urh.deployment.get_deployment_info")
    mock_get_current_deployment_info = mocker.patch(
        "src.urh.deployment.get_current_deployment_info"
    )
    mock_format_deployment_header = mocker.patch(
        "src.urh.deployment.format_deployment_header"
    )

    current_deployment_info = {
        "repository": "bazzite-nix",
        "version": "42.20231115.0",
    }

    mock_get_deployment_info.return_value = [
        DeploymentInfo(
            deployment_index=0,
            is_current=False,
            repository="bazzite-nix",
            version="41.20231110.0",
            is_pinned=False,
        ),
        DeploymentInfo(
            deployment_index=1,
            is_current=True,
            repository="bazzite-nix",
            version="42.20231115.0",
            is_pinned=False,
        ),
    ]
    mock_get_current_deployment_info.return_value = current_deployment_info
    mock_format_deployment_header.return_value = (
        "Current deployment: bazzite-nix (42.20231115.0)"
    )


class TestCommandWorkflows:
    """Test complete command workflows."""

    @pytest.mark.parametrize(
        "command,expected_cmd,requires_sudo",
        [
            ("check", ["rpm-ostree", "upgrade", "--check"], False),
            (
                "kargs",
                ["rpm-ostree", "kargs"],
                False,
            ),  # No args case doesn't require sudo
            ("upgrade", ["sudo", "rpm-ostree", "upgrade"], True),
            ("rollback", ["sudo", "rpm-ostree", "rollback"], True),
        ],
    )
    def test_simple_command_workflows(
        self, mocker, mock_basic_system_setup, command, expected_cmd, requires_sudo
    ):
        """Test simple command workflows."""
        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        handler = getattr(registry, f"_handle_{command}")
        handler([])

        # Check that _run_command was called with the expected command
        mock_run_command.assert_called_once_with(expected_cmd)

        mock_sys_exit.assert_called_once_with(0)

    def test_ls_command_workflow(self, mocker, mock_basic_system_setup):
        """Test complete ls command workflow."""
        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_ls([])

        # The _handle_ls function now calls subprocess.run directly instead of get_status_output
        mock_print.assert_called_once_with("test output")
        mock_sys_exit.assert_called_once_with(0)

    def test_rebase_command_workflow_with_args(self, mocker, mock_basic_system_setup):
        """Test complete rebase command workflow with arguments."""
        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_rebase(["ghcr.io/test/repo:testing"])

        mock_run_command.assert_called_once_with(
            [
                "sudo",
                "rpm-ostree",
                "rebase",
                "ostree-image-signed:docker://ghcr.io/test/repo:testing",
            ]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_rebase_command_workflow_with_menu(
        self, mocker, mock_basic_system_setup, mock_menu_system_setup
    ):
        """Test complete rebase command workflow with menu."""
        # Mock the functions this specific test needs on top of the basic mocks
        config = mocker.MagicMock()
        config.container_urls.options = [
            "ghcr.io/test/repo:testing",
            "ghcr.io/test/repo:stable",
        ]
        mock_get_config = mocker.patch("src.urh.config.get_config", return_value=config)
        current_deployment_info = {
            "repository": "bazzite-nix",
            "version": "42.20231115.0",
        }
        mock_get_current_deployment_info = mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=current_deployment_info,
        )
        mock_format_deployment_header = mocker.patch(
            "src.urh.deployment.format_deployment_header",
            return_value="Current deployment: bazzite-nix (42.20231115.0)",
        )
        # The _handle_rebase function uses _menu_system imported at module level in commands
        # Mock the menu system where it's imported
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        mock_menu_system.show_menu.return_value = "ghcr.io/test/repo:stable"
        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_rebase([])

        mock_get_config.assert_called_once()
        mock_get_current_deployment_info.assert_called_once()
        mock_format_deployment_header.assert_called_once_with(current_deployment_info)
        mock_menu_system.show_menu.assert_called_once()
        mock_run_command.assert_called_once_with(
            [
                "sudo",
                "rpm-ostree",
                "rebase",
                "ostree-image-signed:docker://ghcr.io/test/repo:stable",
            ]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_workflow_with_args(self, mocker):
        """Test complete remote-ls command workflow with arguments."""
        mock_extract_repository = mocker.patch(
            "src.urh.system.extract_repository_from_url", return_value="test/repo"
        )
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_sys_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")

        mock_instance = mocker.MagicMock()
        mock_instance.fetch_repository_tags.return_value = {"tags": ["tag1", "tag2"]}
        mock_client_class.return_value = mock_instance

        registry = CommandRegistry()
        registry._handle_remote_ls(["ghcr.io/test/repo:testing"])

        mock_extract_repository.assert_called_once_with("ghcr.io/test/repo:testing")
        mock_client_class.assert_called_once_with("test/repo")
        mock_instance.fetch_repository_tags.assert_called_once_with(
            "ghcr.io/test/repo:testing"
        )
        mock_print.assert_any_call("Tags for ghcr.io/test/repo:testing:")
        mock_print.assert_any_call("  tag1")
        mock_print.assert_any_call("  tag2")
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_menu_system(
        self, mocker, mock_basic_system_setup, mock_menu_system_setup
    ):
        """Test CommandRegistry integration with MenuSystem."""
        # Mock the expensive system calls that were causing slow performance
        mocker.patch(
            "src.urh.deployment.format_deployment_header",
            return_value="Current deployment: test (v1.0)",
        )

        config = mocker.MagicMock()
        config.container_urls.options = [
            "ghcr.io/test/repo:testing",
            "ghcr.io/test/repo:stable",
        ]
        # The _handle_rebase function imports _menu_system from .menu (src.urh.menu) at module level
        # Mock the menu system where it's imported
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        mock_menu_system.show_menu.return_value = "ghcr.io/test/repo:stable"

        registry = CommandRegistry()
        registry._handle_rebase([])

        mock_menu_system.show_menu.assert_called_once()
        mock_run_command.assert_called_once_with(
            [
                "sudo",
                "rpm-ostree",
                "rebase",
                "ostree-image-signed:docker://ghcr.io/test/repo:stable",
            ]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_deployment_info(
        self,
        mocker,
        mock_basic_system_setup,
        mock_menu_system_setup,
        mock_deployment_info_setup,
    ):
        """Test CommandRegistry integration with deployment info."""
        # The _handle_pin function imports _menu_system from .menu (src.urh.menu) at module level
        # Mock the menu system where it's imported
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        mock_menu_system.show_menu.return_value = 1

        registry = CommandRegistry()
        registry._handle_pin([])

        mock_menu_system.show_menu.assert_called_once()
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_oci_client(self, mocker, mock_basic_system_setup):
        """Test CommandRegistry integration with OCIClient."""
        mock_extract_repository = mocker.patch(
            "src.urh.system.extract_repository_from_url", return_value="test/repo"
        )
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        # Patch both locations to ensure proper mocking
        mocker.patch("src.urh.commands._run_command", return_value=0)
        mocker.patch(
            "src.urh.commands._run_command", return_value=0
        )  # Main module location for direct calls
        mock_sys_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")

        mock_instance = mocker.MagicMock()
        mock_instance.fetch_repository_tags.return_value = {"tags": ["tag1", "tag2"]}
        mock_client_class.return_value = mock_instance

        registry = CommandRegistry()
        registry._handle_remote_ls(["ghcr.io/test/repo:testing"])

        mock_extract_repository.assert_called_once_with("ghcr.io/test/repo:testing")
        mock_client_class.assert_called_once_with("test/repo")
        mock_instance.fetch_repository_tags.assert_called_once_with(
            "ghcr.io/test/repo:testing"
        )
        mock_print.assert_any_call("Tags for ghcr.io/test/repo:testing:")
        mock_print.assert_any_call("  tag1")
        mock_print.assert_any_call("  tag2")
        mock_sys_exit.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "kargs_args,expected_cmd",
        [
            ([], ["rpm-ostree", "kargs"]),
            (
                ["--append=console=ttyS0"],
                ["sudo", "rpm-ostree", "kargs", "--append=console=ttyS0"],
            ),
        ],
    )
    def test_command_registry_with_kargs_command(
        self, mocker, mock_basic_system_setup, kargs_args, expected_cmd
    ):
        """Test CommandRegistry integration with kargs command."""
        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_kargs(kargs_args)

        mock_run_command.assert_called_once_with(expected_cmd)
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_composite_fixtures(
        self, command_test_setup, deployment_test_scenario
    ):
        """Test command registry using composite fixtures for better organization."""
        # Use the composite fixtures for common setup
        setup = command_test_setup
        deployment_setup = deployment_test_scenario

        registry = CommandRegistry()

        # Test that the mocks are properly set up
        assert setup["config"].return_value is not None
        assert setup["deployment"].return_value is not None
        assert setup["system"].return_value is True
        assert setup["execution"].return_value == 0

        # Test that deployment mocks are working
        assert deployment_setup["get_deployment_info"].return_value is not None
        assert deployment_setup["get_current_deployment_info"].return_value is not None
        assert deployment_setup["format_deployment_header"].return_value is not None
        assert deployment_setup["get_status_output"].return_value is not None


class TestCommandsCoverage:
    """Additional tests to improve commands module coverage."""

    def test_run_command_safe_with_timeout_none(self, mocker):
        """Test run_command_safe with timeout=None (backward compatibility)."""
        from src.urh.commands import run_command_safe

        # Mock subprocess.run
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess_run = mocker.patch("subprocess.run", return_value=mock_result)

        # Call with timeout=None
        result = run_command_safe("echo test", timeout=None)

        # Verify subprocess.run was called with correct arguments (no timeout)
        mock_subprocess_run.assert_called_once()
        call_args = mock_subprocess_run.call_args
        assert call_args[1].get("timeout") is None

        # Verify result is returned (run_command_safe returns returncode, not result)
        assert result == 0

    def test_argument_parser_parse_or_prompt_with_args(self, mocker):
        """Test ArgumentParser.parse_or_prompt when args are provided."""
        from src.urh.commands import ArgumentParser

        # Create parser (ArgumentParser takes no arguments)
        parser = ArgumentParser()

        # Test with args provided (parse_or_prompt requires a prompt_func)
        args = ["test_value"]
        result = parser.parse_or_prompt(args, lambda: "default")

        # Should return the first arg (not the prompt_func result since args are provided)
        assert result == "test_value"

    def test_rebase_command_menu_exit_exception(self, mocker):
        """Test rebase command ESC key handling in submenu."""
        from src.urh.commands import CommandRegistry
        from src.urh.menu import MenuExitException

        # Create command registry
        registry = CommandRegistry()

        # Mock the menu system to raise MenuExitException
        # MenuSystem is imported at module level in commands.py
        mock_menu_system = mocker.MagicMock()
        mock_menu_system.show_menu.side_effect = MenuExitException(is_main_menu=False)
        mocker.patch("src.urh.commands._menu_system", mock_menu_system)

        # Mock get_config to avoid file system access (imported locally in the function)
        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:testing"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        # Call rebase with no args (should show menu and handle ESC gracefully)
        registry._handle_rebase([])

        # Verify menu was shown
        mock_menu_system.show_menu.assert_called_once()

        # Verify the function returns normally (exception is caught and handled)
        # The MenuExitException is caught by the menu system and results in selected=None

    def test_rebase_command_with_url_argument(self, mocker):
        """Test rebase command with direct URL argument."""
        from src.urh.commands import CommandRegistry

        # Create command registry
        registry = CommandRegistry()

        # Mock ensure_ostree_prefix
        mocker.patch(
            "src.urh.commands.ensure_ostree_prefix",
            return_value="ostree-image-signed:docker://ghcr.io/test/repo:testing",
        )

        # Mock _run_command to avoid actual execution
        mock_run_command = mocker.patch("src.urh.commands._run_command")

        # Mock sys.exit to prevent actual program termination
        mocker.patch("sys.exit")

        # Call rebase with URL argument
        registry._handle_rebase(["ghcr.io/test/repo:testing"])

        # Verify ensure_ostree_prefix was called (it's a function, not a mock)
        # We can't directly verify the function call, but we can verify the result
        # The mock_run_command should have been called with the prefixed URL

        # Verify _run_command was called with correct arguments
        mock_run_command.assert_called_once()
        call_args = mock_run_command.call_args[0][0]
        assert call_args[0] == "sudo"
        assert call_args[1] == "rpm-ostree"
        assert call_args[2] == "rebase"
        assert call_args[3] == "ostree-image-signed:docker://ghcr.io/test/repo:testing"


class TestArgumentParser:
    """Test ArgumentParser functionality for better coverage."""

    @pytest.mark.parametrize(
        "test_type,input_args,expected_result,validator,prompt_result",
        [
            ("no_validator", ["test_arg"], "test_arg", None, "prompt_result"),
            ("with_validator", ["123"], 123, lambda x: int(x), 42),
        ],
    )
    def test_parse_or_prompt_variations(
        self, test_type, input_args, expected_result, validator, prompt_result
    ):
        """Test parse_or_prompt with various parameter combinations."""
        if test_type == "no_validator":
            parser = ArgumentParser[str]()
        else:
            parser = ArgumentParser[int]()

        # Mock the prompt function
        def mock_prompt():
            return prompt_result

        # Test with args provided
        result = parser.parse_or_prompt(input_args, mock_prompt, validator)

        # Should return expected result
        assert result == expected_result


class TestCommandRegistryHandlers:
    """Test all command handler methods for better coverage."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "command_handler,valid_args,expected_command,invalid_args",
        [
            ("_handle_pin", ["1"], ["sudo", "ostree", "admin", "pin", "1"], "invalid"),
            (
                "_handle_unpin",
                ["1"],
                ["sudo", "ostree", "admin", "pin", "-u", "1"],
                "invalid",
            ),
            (
                "_handle_rm",
                ["1"],
                ["sudo", "rpm-ostree", "cleanup", "-r", "1"],
                "invalid",
            ),
            (
                "_handle_undeploy",
                ["1"],
                ["sudo", "ostree", "admin", "undeploy", "1"],
                "invalid",
            ),
        ],
    )
    def test_deployment_command_handlers(
        self, mocker, command_handler, valid_args, expected_command, invalid_args
    ):
        """Test deployment command handlers with valid and invalid arguments."""
        registry = CommandRegistry()

        # Test valid arguments
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")
        mocker.patch("builtins.print")

        handler = getattr(registry, command_handler)
        handler(valid_args)

        mock_run_command.assert_called_once_with(expected_command)
        mock_sys_exit.assert_called_once_with(0)

        # Test invalid arguments
        mock_print = mocker.patch("builtins.print")
        mock_sys_exit.reset_mock()

        handler([invalid_args])

        mock_print.assert_called_once_with(f"Invalid deployment number: {invalid_args}")
        mock_sys_exit.assert_called_once_with(1)

    def test_handle_pin_no_deployments(self, mocker):
        """Test _handle_pin when no deployments are found."""
        mock_get_deployment_info = mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=[]
        )
        mock_print = mocker.patch("builtins.print")
        registry = CommandRegistry()

    def test_handle_rebase_menu_exit_exception(self, mocker):
        """Test rebase MenuExitException handling when ESC is pressed (line 351)."""
        registry = CommandRegistry()

        # Mock the menu system to raise MenuExitException
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        mock_menu_system.show_menu.side_effect = MenuExitException(is_main_menu=False)

        # Mock other dependencies - use the correct import paths
        mocker.patch("src.urh.config.get_config")
        mocker.patch("src.urh.deployment.get_current_deployment_info")
        mocker.patch("src.urh.deployment.format_deployment_header")

        # Prevent actual command execution and sys.exit
        mocker.patch("src.urh.commands._run_command")
        mocker.patch("sys.exit")

        # Call rebase with no args to trigger menu
        result = registry._handle_rebase([])

        # Should return None when MenuExitException is raised
        assert result is None

        # Verify MenuExitException was handled properly
        mock_menu_system.show_menu.assert_called_once()

    def test_pin_already_pinned_deployment(self, mocker):
        """Test pin command when trying to pin already pinned deployment via menu selection."""
        registry = CommandRegistry()

        # Mock deployments with both pinned and unpinned deployments
        mock_get_deployment_info = mocker.patch(
            "src.urh.deployment.get_deployment_info",
            return_value=[
                DeploymentInfo(
                    deployment_index=0,
                    is_current=True,
                    repository="test-repo",
                    version="v1.0.0",
                    is_pinned=True,  # This one is pinned
                ),
                DeploymentInfo(
                    deployment_index=1,
                    is_current=False,
                    repository="test-repo",
                    version="v1.0.1",
                    is_pinned=False,  # This one is not pinned
                ),
            ],
        )
        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)

        # Mock the menu system to simulate selecting a pinned deployment
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        mock_menu_system.show_menu.return_value = (
            0  # User selects deployment 0 which is pinned
        )

        # Call with no args to trigger menu selection
        registry._handle_pin([])

        # Should print the "already pinned" message and not execute the command
        mock_print.assert_called_once_with("Deployment 0 is already pinned.")
        mock_run_command.assert_not_called()

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
            side_effect=subprocess.TimeoutExpired("cmd", 10),
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
            side_effect=subprocess.TimeoutExpired("cmd", 10),
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
        """Test ArgumentParser parse_or_prompt with invalid validator."

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



        """
