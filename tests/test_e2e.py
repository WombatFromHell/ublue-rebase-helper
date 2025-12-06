import pytest

from src.urh.commands import CommandRegistry
from src.urh.config import ConfigManager, URHConfig, get_config
from src.urh.deployment import DeploymentInfo
from src.urh.menu import MenuExitException


class TestMainWorkflow:
    """Test main application workflow."""

    @pytest.mark.parametrize(
        "command,args,expected_calls",
        [
            ("check", [], [("get_command", "check"), ("handler", [])]),
            (
                "rebase",
                ["ghcr.io/test/repo:testing"],
                [("get_command", "rebase"), ("handler", ["ghcr.io/test/repo:testing"])],
            ),
        ],
    )
    def test_main_with_command(self, mocker, command, args, expected_calls):
        """Test main function with a command."""
        mock_command_registry = mocker.MagicMock()
        mock_command = mocker.MagicMock()
        mock_command_registry.get_command.return_value = mock_command

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py", command] + args
        # Mock sys.exit to track the exit code without actually exiting
        mock_exit = mocker.MagicMock()
        mocker.patch("sys.exit", mock_exit)

        try:
            # Mock object for subprocess.run that returns appropriate values
            mock_subprocess_result = mocker.MagicMock()
            mock_subprocess_result.returncode = (
                0  # For "which curl" command to return True
            )

            # Patch all necessary functions before importing main to prevent privilege escalation
            # IMPORTANT: The main function imports CommandRegistry from .commands (src.urh.commands)
            mocker.patch(
                "src.urh.cli.CommandRegistry", return_value=mock_command_registry
            )
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Main module location for direct calls
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
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
            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            for method_name, expected_arg in expected_calls:
                if method_name == "get_command":
                    mock_command_registry.get_command.assert_called_once_with(
                        expected_arg
                    )
                else:
                    getattr(mock_command, method_name).assert_called_once_with(
                        expected_arg
                    )
        finally:
            sys.argv = original_argv

    def test_main_with_invalid_command(self, mocker):
        """Test main function with an invalid command."""
        # Set environment variable to force non-gum behavior (avoid hanging during tests)
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
        mocker.patch("os.isatty", return_value=True)

        mock_command_registry = mocker.MagicMock()
        mock_command_registry.get_command.return_value = None
        mock_command_registry.get_commands.return_value = []  # Empty list of commands for invalid command test

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py", "invalid_command"]
        mock_exit = mocker.patch("sys.exit")

        try:
            # Mock object for subprocess.run that returns appropriate values
            mock_subprocess_result = mocker.MagicMock()
            mock_subprocess_result.returncode = (
                0  # For "which curl" command to return True
            )

            # Patch CommandRegistry and both locations of run_command to prevent privilege escalation
            # IMPORTANT: The main function imports CommandRegistry from .commands (src.urh.commands)
            mocker.patch(
                "src.urh.cli.CommandRegistry", return_value=mock_command_registry
            )
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Main module location for direct calls
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
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

            # Patch menu system to prevent gum from appearing
            mocker.patch("src.urh.cli._menu_system")
            mocker.patch("src.urh.commands._menu_system")

            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            mock_command_registry.get_command.assert_called_once_with("invalid_command")
            mock_exit.assert_called_once_with(1)
        finally:
            sys.argv = original_argv

    def test_main_with_menu(self, mocker):
        """Test main function with interactive menu."""

        # Mock the _main_menu_loop to control its behavior and avoid infinite loop in tests
        def mock_main_menu_loop(max_iterations=None):
            # Mock functions that make system calls to prevent hanging
            mocker.patch(
                "src.urh.deployment.get_current_deployment_info",
                return_value={"repository": "test", "version": "v1.0"},
            )
            mocker.patch(
                "src.urh.deployment.format_deployment_header",
                return_value="Current deployment: test (v1.0)",
            )

            # Simulate selecting a command and executing it once
            mock_menu_system = mocker.MagicMock()
            mock_menu_system.show_menu.return_value = "check"
            mocker.patch("src.urh.commands._menu_system", mock_menu_system)

            # Execute the command once
            mock_command_registry = mocker.MagicMock()
            mock_command = mocker.MagicMock()
            mock_command_registry.get_command.return_value = mock_command
            mocker.patch(
                "src.urh.commands.CommandRegistry", return_value=mock_command_registry
            )

            mock_command.handler([])

            # Instead of raising an exception, just return to simulate single iteration
            return

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py"]
        mocker.patch("sys.exit")

        try:
            mocker.patch("src.urh.cli._main_menu_loop", side_effect=mock_main_menu_loop)
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            # Verify the command was called - we can't really test the full behavior here
            # since we're mocking the core loop, but at least the function should complete
            pass
        finally:
            sys.argv = original_argv

    def test_main_with_menu_esc(self, mocker):
        """Test main function with interactive menu and ESC."""
        # Set environment variable to force non-gum behavior (avoid hanging during tests)
        import os

        mocker.patch.dict(os.environ, {"URH_AVOID_GUM": "1"})
        # Make sure os.isatty(1) returns True so the menu system thinks it's in a TTY
        mocker.patch("os.isatty", return_value=True)

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py"]
        mock_exit = mocker.patch("sys.exit")

        try:
            # Mock object for subprocess.run that returns appropriate values
            mock_subprocess_result = mocker.MagicMock()
            mock_subprocess_result.returncode = (
                0  # For "which curl" command to return True
            )

            # Mock _main_menu_loop to simulate ESC press in main menu
            def mock_main_menu_loop():
                # Raise MenuExitException(is_main_menu=True) to simulate ESC in main menu
                raise MenuExitException(is_main_menu=True)

            # Patch _main_menu_loop and other necessary functions to prevent privilege escalation
            # Main function imports directly from .menu (src.urh.menu)
            mocker.patch("src.urh.cli._main_menu_loop", side_effect=mock_main_menu_loop)
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Original location for compatibility
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Main module location for direct calls
            mocker.patch(
                "src.urh.commands._run_command", return_value=0
            )  # Actual implementation location
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
            # IMPORTANT: The main function imports CommandRegistry from .commands (src.urh.commands)
            mock_command_registry = mocker.MagicMock()
            mocker.patch(
                "src.urh.cli.CommandRegistry", return_value=mock_command_registry
            )
            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            mock_exit.assert_called_once_with(0)
        finally:
            sys.argv = original_argv


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

    @pytest.mark.parametrize(
        "command,cmd_suffix,expected_cmd",
        [
            (
                "pin",
                ["ostree", "admin", "pin", "1"],
                ["sudo", "ostree", "admin", "pin", "1"],
            ),
            (
                "unpin",
                ["ostree", "admin", "pin", "-u", "1"],
                ["sudo", "ostree", "admin", "pin", "-u", "1"],
            ),
            (
                "rm",
                ["rpm-ostree", "cleanup", "-r", "1"],
                ["sudo", "rpm-ostree", "cleanup", "-r", "1"],
            ),
        ],
    )
    def test_deployment_command_workflows_with_args(
        self, mocker, command, cmd_suffix, expected_cmd
    ):
        """Test complete deployment management command workflows with arguments."""
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

        # CRITICAL: Mock the expensive system calls that were causing slow performance
        # These are called even when arguments are provided due to early validation
        mocker.patch(
            "src.urh.deployment.get_deployment_info",
            return_value=[
                DeploymentInfo(
                    deployment_index=1,
                    is_current=True,
                    repository="test/repo",
                    version="1.0.0",
                    is_pinned=False,
                )
            ],
        )

        registry = CommandRegistry()
        handler = getattr(registry, f"_handle_{command}")
        handler(["1"])

        mock_run_command.assert_called_once_with(expected_cmd)
        mock_sys_exit.assert_called_once_with(0)

    @pytest.mark.parametrize(
        "command, is_pinned, menu_selection",
        [
            ("pin", False, "0"),  # Pin an unpinned deployment
            ("unpin", True, "0"),  # Unpin a pinned deployment
            ("rm", False, "0"),  # Remove any deployment
        ],
    )
    def test_deployment_command_workflows_with_menu(
        self, mocker, command, is_pinned, menu_selection, sample_deployment_info
    ):
        """Test complete deployment command workflows with menu."""
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

        # Mock _run_command function
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")
        mock_get_current_deployment_info = mocker.patch(
            "src.urh.deployment.get_current_deployment_info"
        )
        mock_format_deployment_header = mocker.patch(
            "src.urh.deployment.format_deployment_header"
        )
        # The handler functions import _menu_system from .menu (src.urh.menu) at module level
        # Mock the menu system where it's imported
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        # Mock menu selection
        mock_menu_system.show_menu.return_value = menu_selection

        # Create appropriate deployment sample for the command type
        if command == "unpin":
            # Create a sample with at least one pinned deployment for unpin command
            deployment_with_pinned = [
                DeploymentInfo(
                    deployment_index=0,
                    is_current=True,
                    repository="bazzite-nix",
                    version="42.20231115.0",
                    is_pinned=True,  # Pinned for unpin command
                )
            ]
            deployments = deployment_with_pinned
        elif command == "pin":
            # Create a sample with at least one unpinned deployment for pin command
            deployment_with_unpinned = [
                DeploymentInfo(
                    deployment_index=0,
                    is_current=True,
                    repository="bazzite-nix",
                    version="42.20231115.0",
                    is_pinned=False,  # Unpinned for pin command
                )
            ]
            deployments = deployment_with_unpinned
        else:  # rm command
            # Use sample deployment info for rm command
            deployments = sample_deployment_info

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        # Mock current deployment info
        current_deployment_info = {
            "repository": "bazzite-nix",
            "version": "42.20231115.0",
        }
        mock_get_current_deployment_info.return_value = current_deployment_info
        mock_format_deployment_header.return_value = (
            "Current deployment: bazzite-nix (42.20231115.0)"
        )

        registry = CommandRegistry()
        handler = getattr(registry, f"_handle_{command}")
        handler([])

        # Determine expected command based on command type
        if command == "pin":
            expected_cmd = ["sudo", "ostree", "admin", "pin", menu_selection]
        elif command == "unpin":
            expected_cmd = ["sudo", "ostree", "admin", "pin", "-u", menu_selection]
        elif command == "rm":
            expected_cmd = ["sudo", "rpm-ostree", "cleanup", "-r", menu_selection]
        else:
            expected_cmd = []

        mock_run_command.assert_called_once_with(expected_cmd)
        mock_sys_exit.assert_called_once_with(0)

    def test_pin_command_workflow_with_menu(self, mocker, sample_deployment_info):
        """Test complete pin command workflow with menu."""
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
        mocker.patch(
            "src.urh.deployment.get_status_output", return_value=None
        )  # Needed for get_deployment_info
        # Patch config function to avoid file system access
        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:testing"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)
        # Also patch setup_logging in the cli module
        mocker.patch("src.urh.cli.setup_logging", return_value=None)

        # Mock the functions this specific test needs
        mock_get_deployment_info = mocker.patch(
            "src.urh.deployment.get_deployment_info"
        )
        mock_get_current_deployment_info = mocker.patch(
            "src.urh.deployment.get_current_deployment_info"
        )
        mock_format_deployment_header = mocker.patch(
            "src.urh.deployment.format_deployment_header"
        )
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        current_deployment_info = {
            "repository": "bazzite-nix",
            "version": "42.20231115.0",
        }

        mock_get_deployment_info.return_value = sample_deployment_info
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


class TestErrorHandlingWorkflows:
    """Test error handling in complete workflows."""

    def test_command_not_found_workflow(self, mocker):
        """Test workflow when command is not found."""
        mock_command_registry = mocker.MagicMock()
        mock_command_registry.get_command.return_value = None
        mocker.patch("builtins.print")

        import sys

        original_argv = sys.argv
        sys.argv = ["urh.py", "nonexistent"]
        mock_exit = mocker.patch("sys.exit")

        try:
            mocker.patch(
                "src.urh.cli.CommandRegistry", return_value=mock_command_registry
            )
            # Import here to avoid issues with mocking
            from src.urh.core import main

            main()

            mock_command_registry.get_command.assert_called_once_with("nonexistent")
            mock_exit.assert_called_once_with(1)
        finally:
            sys.argv = original_argv

    def test_subprocess_error_workflow(self, mocker):
        """Test workflow when subprocess command fails."""
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=1)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_check([])

        mock_run_command.assert_called_once_with(["rpm-ostree", "upgrade", "--check"])
        mock_sys_exit.assert_called_once_with(1)

    def test_menu_esc_workflow(self, mocker):
        """Test workflow when ESC is pressed in menu."""
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

        # Mock the functions this specific test needs
        mock_get_config = mocker.patch("src.urh.config.get_config")
        mock_menu_system = mocker.patch("src.urh.commands._menu_system")

        # CRITICAL: Mock the expensive system calls that were causing slow performance
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
        mock_get_config.return_value = config

        mock_menu_system.show_menu.side_effect = MenuExitException(is_main_menu=False)

        registry = CommandRegistry()
        registry._handle_rebase([])

        mock_get_config.assert_called_once()
        mock_menu_system.show_menu.assert_called_once()

    def test_no_deployments_workflow(self, mocker):
        """Test workflow when no deployments are available."""
        # Return deployments that are all already pinned (so none available to pin)
        mock_get_deployment_info = mocker.patch(
            "src.urh.deployment.get_deployment_info",
            return_value=[
                DeploymentInfo(
                    deployment_index=0,
                    is_current=True,
                    repository="bazzite-nix",
                    version="42.20231115.0",
                    is_pinned=True,  # Already pinned
                ),
                DeploymentInfo(
                    deployment_index=1,
                    is_current=False,
                    repository="bazzite-nix",
                    version="41.20231110.0",
                    is_pinned=True,  # Already pinned
                ),
            ],
        )
        mock_print = mocker.patch("builtins.print")

        registry = CommandRegistry()
        registry._handle_pin([])

        mock_get_deployment_info.assert_called_once()
        mock_print.assert_called_once_with("No deployments available to pin.")


class TestConfigurationWorkflows:
    """Test configuration management workflows."""

    def test_config_loading_workflow(self, mocker):
        """Test complete configuration loading workflow."""
        mock_config_manager = mocker.MagicMock()
        mock_config = mocker.MagicMock()
        mock_config_manager.load_config.return_value = mock_config

        mocker.patch("src.urh.config._config_manager", mock_config_manager)
        config = get_config()

        assert config == mock_config
        mock_config_manager.load_config.assert_called_once()

    def test_config_creation_workflow(self, mocker):
        """Test complete configuration creation workflow."""
        mock_config_path = mocker.MagicMock()
        mock_config_path.exists.return_value = False

        config_manager = ConfigManager()
        config_manager.get_config_path = mocker.MagicMock(return_value=mock_config_path)

        mock_create = mocker.patch.object(config_manager, "create_default_config")
        mock_get_default = mocker.patch.object(URHConfig, "get_default")
        mock_config = mocker.MagicMock()
        mock_get_default.return_value = mock_config

        result = config_manager.load_config()

        assert result == mock_config
        mock_create.assert_called_once()
        mock_get_default.assert_called_once()
