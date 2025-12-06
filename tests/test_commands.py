"""Tests for the commands module."""

import pytest

from src.urh.commands import CommandRegistry


class TestCommands:
    """Test commands functionality."""

    def test_commands_module_exists(self):
        """Test that the commands module can be imported."""
        from src.urh.commands import CommandDefinition, CommandRegistry, CommandType

        assert CommandRegistry is not None
        assert CommandDefinition is not None
        assert CommandType is not None


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
        self, mocker, command, expected_cmd, requires_sudo
    ):
        """Test simple command workflows."""
        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        handler = getattr(registry, f"_handle_{command}")
        handler([])

        # Check that _run_command was called with the expected command
        mock_run_command.assert_called_once_with(expected_cmd)

        mock_sys_exit.assert_called_once_with(0)

    def test_ls_command_workflow(self, mocker):
        """Test complete ls command workflow."""
        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.stdout = (
            "test output"  # For the subprocess call in _handle_ls
        )
        mock_subprocess_result.returncode = 0

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        # Patch deployment info functions that make system calls
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test", "version": "v1.0"},
        )
        mocker.patch("src.urh.deployment.get_deployment_info", return_value=[])
        mocker.patch(
            "subprocess.run", return_value=mock_subprocess_result
        )  # Handle subprocess call in _handle_ls
        # Patch config function to avoid file system access
        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:testing"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)
        # Also patch setup_logging in the cli module
        mocker.patch("src.urh.cli.setup_logging", return_value=None)

        mock_print = mocker.patch("builtins.print")
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_ls([])

        # The _handle_ls function now calls subprocess.run directly instead of get_status_output
        mock_print.assert_called_once_with("test output")
        mock_sys_exit.assert_called_once_with(0)

    def test_rebase_command_workflow_with_args(self, mocker):
        """Test complete rebase command workflow with arguments."""
        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

    def test_rebase_command_workflow_with_menu(self, mocker):
        """Test complete rebase command workflow with menu."""
        # Set environment variable to force non-gum behavior (avoid hanging during tests)
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
        mocker.patch("os.isatty", return_value=True)

        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

    def test_command_registry_with_menu_system(self, mocker):
        """Test CommandRegistry integration with MenuSystem."""
        # Set environment variable to force non-gum behavior (avoid hanging during tests)
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
        mocker.patch("os.isatty", return_value=True)

        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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
        # Mock the expensive system calls that were causing slow performance
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={"repository": "test", "version": "v1.0"},
        )
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

    def test_command_registry_with_deployment_info(self, mocker):
        """Test CommandRegistry integration with deployment info."""
        # Set environment variable to force non-gum behavior (avoid hanging during tests)
        import os

        from src.urh.deployment import DeploymentInfo

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
        mocker.patch("os.isatty", return_value=True)

        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

        mock_get_deployment_info = mocker.patch(
            "src.urh.deployment.get_deployment_info"
        )
        mock_get_current_deployment_info = mocker.patch(
            "src.urh.deployment.get_current_deployment_info"
        )
        mock_format_deployment_header = mocker.patch(
            "src.urh.deployment.format_deployment_header"
        )
        # The _handle_pin function imports _menu_system from .menu (src.urh.menu) at module level
        # Mock the menu system where it's imported
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

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
        mock_menu_system.show_menu.return_value = 1

        registry = CommandRegistry()
        registry._handle_pin([])

        mock_get_deployment_info.assert_called_once()
        mock_get_current_deployment_info.assert_called_once()
        mock_format_deployment_header.assert_called_once_with(current_deployment_info)
        mock_menu_system.show_menu.assert_called_once()
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_oci_client(self, mocker):
        """Test CommandRegistry integration with OCIClient."""
        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

    def test_command_registry_with_kargs_no_args(self, mocker):
        """Test CommandRegistry integration with kargs command (no args)."""
        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_kargs([])

        mock_run_command.assert_called_once_with(["rpm-ostree", "kargs"])
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_kargs_command(self, mocker):
        """Test CommandRegistry integration with kargs command."""
        # Mock all necessary functions to prevent privilege escalation
        mock_subprocess_result = mocker.MagicMock()
        mock_subprocess_result.returncode = 0  # For "which curl" command to return True

        # Also patch subprocess.run to prevent any direct subprocess calls
        mocker.patch("subprocess.run", return_value=mock_subprocess_result)
        # Patch system functions that make subprocess calls to prevent privilege escalation
        mocker.patch(
            "src.urh.system.check_curl_presence", return_value=True
        )  # Assume curl is available in tests
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_kargs(["--append=console=ttyS0"])

        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "kargs", "--append=console=ttyS0"]
        )
        mock_sys_exit.assert_called_once_with(0)
