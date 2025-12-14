"""
Tests for command submenu functionality to improve coverage in commands.py module.
"""

from unittest.mock import Mock

from src.urh.commands import CommandRegistry
from src.urh.menu import MenuExitException


class TestCommandSubmenus:
    """Test submenu functionality in commands module."""

    def test_pin_command_submenu_with_valid_selection(self, mocker):
        """Test pin command submenu with valid selection."""
        # Mock the menu system to return a specific selection
        mocker.patch("src.urh.menu._menu_system.show_menu", return_value=1)
        mock_deployments = [
            Mock(deployment_index=1, repository="repo1", version="v1", is_pinned=False)
        ]
        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployments
        )
        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_pin([])

        # Verify the command was called
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_pin_command_submenu_with_menu_exit(self, mocker):
        """Test pin command submenu when menu is exited with ESC."""
        # Mock the menu system to raise MenuExitException
        mocker.patch(
            "src.urh.menu._menu_system.show_menu",
            side_effect=MenuExitException(is_main_menu=False),
        )
        mock_deployments = [
            Mock(deployment_index=1, repository="repo1", version="v1", is_pinned=False)
        ]
        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployments
        )
        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_pin([])  # Should not raise exception or call sys.exit

        # Verify sys.exit was not called since the function should return early
        mock_sys_exit.assert_not_called()

    def test_pin_command_submenu_with_invalid_number(self, mocker):
        """Test pin command with invalid number argument."""
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call with invalid number to trigger ValueError
        registry._handle_pin(["invalid_number"])

        # Verify sys.exit was called with error code 1
        mock_sys_exit.assert_called_once_with(1)

    def test_unpin_command_submenu_with_valid_selection(self, mocker):
        """Test unpin command submenu with valid selection."""
        # Mock the menu system to return a specific selection
        mocker.patch("src.urh.menu._menu_system.show_menu", return_value=1)
        mock_deployments = [
            Mock(deployment_index=1, repository="repo1", version="v1", is_pinned=True)
        ]
        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployments
        )
        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_unpin([])

        # Verify the command was called
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "-u", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_unpin_command_submenu_with_menu_exit(self, mocker):
        """Test unpin command submenu when menu is exited with ESC."""
        # Mock the menu system to raise MenuExitException
        mocker.patch(
            "src.urh.menu._menu_system.show_menu",
            side_effect=MenuExitException(is_main_menu=False),
        )
        mock_deployments = [
            Mock(deployment_index=1, repository="repo1", version="v1", is_pinned=True)
        ]
        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployments
        )
        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_unpin([])  # Should not raise exception or call sys.exit

        # Verify sys.exit was not called since the function should return early
        mock_sys_exit.assert_not_called()

    def test_rm_command_submenu_with_valid_selection(self, mocker):
        """Test rm command submenu with valid selection."""
        # Mock the menu system to return a specific selection
        mocker.patch("src.urh.menu._menu_system.show_menu", return_value=1)
        mock_deployments = [
            Mock(deployment_index=1, repository="repo1", version="v1", is_pinned=False)
        ]
        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployments
        )
        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )
        mock_run_command = mocker.patch("src.urh.commands._run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_rm([])

        # Verify the command was called
        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "cleanup", "-r", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_submenu_with_valid_selection(self, mocker):
        """Test remote-ls command submenu with valid selection."""
        # Mock the menu system to return a specific selection
        mock_menu_show = mocker.patch(
            "src.urh.menu._menu_system.show_menu",
            return_value="ghcr.io/user/repo:latest",
        )
        mock_config = Mock()
        mock_config.container_urls.options = [
            "ghcr.io/user/repo:latest",
            "ghcr.io/user/repo:testing",
        ]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)
        mock_extract_repo = mocker.patch(
            "src.urh.system.extract_repository_from_url",
            return_value="user/repo:latest",
        )
        # Mock the entire OCIClient class to return a mock instance - patch where it's used
        mock_oci_client_cls = mocker.patch("src.urh.commands.OCIClient")
        mock_oci_instance = Mock()
        mock_oci_instance.fetch_repository_tags.return_value = {
            "tags": ["latest", "testing"]
        }
        mock_oci_client_cls.return_value = mock_oci_instance
        mock_sys_exit = mocker.patch("sys.exit")

        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_remote_ls([])

        # Verify the functions were called
        mock_menu_show.assert_called()
        mock_extract_repo.assert_called_with("ghcr.io/user/repo:latest")
        mock_oci_instance.fetch_repository_tags.assert_called_with(
            "ghcr.io/user/repo:latest"
        )
        # sys.exit(0) should be called at the end for successful case
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_submenu_with_menu_exit(self, mocker):
        """Test remote-ls command submenu when menu is exited with ESC."""
        # Mock the menu system to raise MenuExitException
        mocker.patch(
            "src.urh.menu._menu_system.show_menu",
            side_effect=MenuExitException(is_main_menu=False),
        )
        mock_config = Mock()
        mock_config.container_urls.options = ["ghcr.io/user/repo:latest"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )

        # Mock get_deployment_info to avoid expensive subprocess calls
        mock_deployments = []
        mocker.patch(
            "src.urh.deployment.get_deployment_info", return_value=mock_deployments
        )

        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_remote_ls([])  # Should not raise exception or call sys.exit

        # Verify sys.exit was not called since the function should return early
        mock_sys_exit.assert_not_called()

    def test_remote_ls_command_no_tags_found(self, mocker):
        """Test remote-ls command when no tags are found."""
        # Mock the menu system to return a specific selection
        mocker.patch(
            "src.urh.menu._menu_system.show_menu",
            return_value="ghcr.io/user/repo:latest",
        )
        mock_config = Mock()
        mock_config.container_urls.options = ["ghcr.io/user/repo:latest"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)
        mocker.patch(
            "src.urh.system.extract_repository_from_url",
            return_value="user/repo:latest",
        )
        # Mock the entire OCIClient class to return a mock instance - patch where it's used
        mock_oci_client_cls = mocker.patch("src.urh.commands.OCIClient")
        mock_oci_instance = Mock()
        mock_oci_instance.fetch_repository_tags.return_value = {
            "tags": []
        }  # No tags found
        mock_oci_client_cls.return_value = mock_oci_instance
        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_remote_ls([])

        # Verify sys.exit(0) was called since no tags were found (not an error)
        mock_sys_exit.assert_called_once_with(0)

    def test_remote_ls_command_error_fetching_tags(self, mocker):
        """Test remote-ls command when error occurs fetching tags."""
        # Mock the menu system to return a specific selection
        mocker.patch(
            "src.urh.menu._menu_system.show_menu",
            return_value="ghcr.io/user/repo:latest",
        )
        mock_config = Mock()
        mock_config.container_urls.options = ["ghcr.io/user/repo:latest"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)
        mocker.patch(
            "src.urh.system.extract_repository_from_url",
            return_value="user/repo:latest",
        )
        mock_oci_client_cls = mocker.patch("src.urh.commands.OCIClient")
        mock_oci_instance = Mock()
        mock_oci_instance.fetch_repository_tags.return_value = {}  # Error case
        mock_oci_client_cls.return_value = mock_oci_instance
        # Mock get_current_deployment_info to avoid expensive subprocess calls
        mock_deployment_info = {"repository": "test-repo", "version": "1.0.0"}
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value=mock_deployment_info,
        )
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()

        # Call the handler with no arguments to trigger menu
        registry._handle_remote_ls([])

        # Verify sys.exit(1) was called for error case
        mock_sys_exit.assert_called_once_with(1)
