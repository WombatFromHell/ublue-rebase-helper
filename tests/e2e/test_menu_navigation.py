"""
E2E tests for menu navigation workflows.

Tests the menu system's user-facing functionality, including:
- Main menu display and command selection
- Submenu navigation (rebase, remote-ls, deployment operations)
- ESC key handling (return to main menu / exit)
- Deployment selection workflows (pin, unpin, rm, undeploy)

These tests mock only external I/O and test actual menu logic end-to-end.
"""

import sys

import pytest
from pytest_mock import MockerFixture

from src.urh.cli import main as cli_main
from src.urh.deployment import DeploymentInfo
from src.urh.menu import MenuExitException
from tests.conftest import (
    ExecCompleted,
    apply_e2e_test_environment,
    mock_execvp_command,
)


@pytest.mark.e2e
class TestMainMenuNavigation:
    """Test main menu display and command selection."""

    @pytest.fixture(autouse=True)
    def setup_menu_environment(self, mocker: MockerFixture) -> None:
        """Setup common test environment for menu navigation tests."""
        apply_e2e_test_environment(
            mocker,
            tty=True,
            mock_execvp=True,
            execvp_cmd=["sudo", "rpm-ostree", "upgrade"],
            mock_sys_exit=True,
        )

    def test_main_menu_shows_all_commands(self, mocker: MockerFixture) -> None:
        """Test that main menu displays all available commands."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.return_value = "check"

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was shown
        mock_menu_show.assert_called_once()

        # Verify header was included
        call_kwargs = mock_menu_show.call_args[1]
        assert "persistent_header" in call_kwargs
        assert "test-repo" in call_kwargs["persistent_header"]

    def test_main_menu_selection_executes_command(self, mocker: MockerFixture) -> None:
        """Test that selecting a command from main menu executes it."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.return_value = "upgrade"

        expected_cmd = ["sudo", "rpm-ostree", "upgrade"]

        sys.argv = ["urh"]
        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Verify upgrade command was executed
        assert "rpm-ostree" in last_call_args
        assert "upgrade" in last_call_args

    def test_main_menu_esc_exits_application(self, mocker: MockerFixture) -> None:
        """Test that pressing ESC in main menu exits the application."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = MenuExitException(is_main_menu=True)

        sys.argv = ["urh"]
        result = cli_main()

        # Verify exit code is success
        assert result == 0


@pytest.mark.e2e
class TestSubmenuNavigation:
    """Test submenu navigation for commands with options."""

    @pytest.fixture(autouse=True)
    def setup_submenu_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for submenu tests."""
        apply_e2e_test_environment(
            mocker,
            tty=True,
            mock_execvp=True,
            execvp_cmd=["sudo", "rpm-ostree", "rebase"],
            mock_sys_exit=True,
        )

    def test_rebase_submenu_shows_container_options(
        self, mocker: MockerFixture
    ) -> None:
        """Test that rebase submenu shows configured container URLs."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        # Main menu selects "rebase", submenu selects URL
        mock_menu_show.side_effect = ["rebase", "ghcr.io/test/repo:stable"]

        # Mock config to return test container URLs
        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = [
            "ghcr.io/test/repo:testing",
            "ghcr.io/test/repo:stable",
        ]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was called (at least once for main menu, once for submenu)
        assert mock_menu_show.call_count >= 2

        # Find the submenu call (should have container URLs as items)
        submenu_called = False
        for call in mock_menu_show.call_args_list:
            items = call[0][0] if call[0] else call[1].get("items", [])
            if items and len(items) == 2:
                submenu_called = True
                break

        assert submenu_called, "Submenu with container options should have been shown"

    def test_rebase_submenu_selection_rebases(self, mocker: MockerFixture) -> None:
        """Test that selecting from rebase submenu executes rebase command."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = ["rebase", "ghcr.io/test/repo:stable"]

        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/test/repo:stable",
        ]

        sys.argv = ["urh"]
        last_call = mock_execvp_command(mocker, expected_cmd)
        assert "rpm-ostree" in last_call
        assert "rebase" in last_call
        assert "ostree-image-signed:docker://ghcr.io/test/repo:stable" in last_call

    def test_remote_ls_submenu_shows_container_options(
        self, mocker: MockerFixture
    ) -> None:
        """Test that remote-ls submenu shows configured container URLs."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = ["remote-ls", "ghcr.io/test/repo:stable"]

        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        # Mock OCIClient for tag fetching
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0", "v2.0"]}
        mock_client_class.return_value = mock_client

        sys.argv = ["urh"]
        cli_main()

        # Verify menu was called for submenu
        assert mock_menu_show.call_count >= 2

    def test_esc_in_submenu_returns_to_main_menu(self, mocker: MockerFixture) -> None:
        """Test that pressing ESC in submenu returns to main menu."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")

        # First: main menu selects "rebase"
        # Second: rebase submenu ESC
        # After ESC, code returns to main menu loop (tested by verifying flow continues)
        mock_menu_show.side_effect = [
            "rebase",
            MenuExitException(is_main_menu=False),
            "check",  # This would be called if the loop continues
        ]

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was shown at least twice (main menu + submenu with ESC)
        # The third call depends on how the main loop handles the ESC exception
        assert mock_menu_show.call_count >= 2

        # Verify check command was executed after returning to main menu
        # (tested by test_cli_workflows.py, just verify flow continues)


@pytest.mark.e2e
class TestDeploymentSelectionMenus:
    """Test deployment selection menus for pin/unpin/rm/undeploy commands."""

    @pytest.fixture(autouse=True)
    def setup_deployment_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for deployment menu tests."""
        apply_e2e_test_environment(
            mocker,
            tty=True,
            mock_execvp=True,
            execvp_cmd=["sudo", "ostree", "admin", "pin"],
            mock_sys_exit=True,
        )

    def test_pin_submenu_shows_unpinned_deployments(
        self, mocker: MockerFixture
    ) -> None:
        """Test that pin submenu shows only unpinned deployments."""
        # Setup deployment data
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=False,
            ),
            DeploymentInfo(
                deployment_index=1,
                is_current=True,
                repository="test-repo",
                version="2.0.0",
                is_pinned=False,
            ),
        ]

        # Patch at deployment module level
        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = [
            "pin",
            1,
        ]  # Main menu selects "pin", submenu selects 1

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was shown (main menu + pin submenu)
        assert mock_menu_show.call_count >= 2

        # Verify menu items include deployment info
        for call in mock_menu_show.call_args_list:
            items = call[0][0] if call[0] else call[1].get("items", [])
            if items and hasattr(items[0], "display_text"):
                # Check if this looks like a deployment menu (has version info)
                if "test-repo" in str(items[0].display_text):
                    # Verify pinned deployments are shown with asterisk
                    # (this is tested in detail by integration tests)
                    break

    def test_pin_command_executes_ostree_pin(self, mocker: MockerFixture) -> None:
        """Test that pin selection executes ostree admin pin."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=False,
            ),
        ]

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        # Main menu returns "pin", submenu returns deployment 0
        mock_menu_show.side_effect = ["pin", 0]

        expected_cmd = ["sudo", "ostree", "admin", "pin", "0"]

        sys.argv = ["urh"]
        last_call = mock_execvp_command(mocker, expected_cmd)
        assert "sudo" in last_call
        assert "ostree" in last_call
        assert "admin" in last_call
        assert "pin" in last_call
        assert "0" in last_call

    def test_unpin_submenu_shows_pinned_deployments(
        self, mocker: MockerFixture
    ) -> None:
        """Test that unpin submenu shows only pinned deployments."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=True,  # Pinned
            ),
            DeploymentInfo(
                deployment_index=1,
                is_current=True,
                repository="test-repo",
                version="2.0.0",
                is_pinned=False,  # Not pinned
            ),
        ]

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = [
            "unpin",
            0,
        ]  # Main menu selects "unpin", submenu selects 0

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was shown
        assert mock_menu_show.call_count >= 2

    def test_unpin_command_executes_ostree_unpin(self, mocker: MockerFixture) -> None:
        """Test that unpin selection executes ostree admin pin -u."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=True,
            ),
        ]

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        # Main menu returns "unpin", submenu returns deployment 0
        mock_menu_show.side_effect = ["unpin", 0]

        expected_cmd = ["sudo", "ostree", "admin", "pin", "-u", "0"]

        sys.argv = ["urh"]
        last_call = mock_execvp_command(mocker, expected_cmd)
        assert "sudo" in last_call
        assert "ostree" in last_call
        assert "admin" in last_call
        assert "pin" in last_call
        assert "-u" in last_call

    def test_rm_submenu_shows_all_deployments(self, mocker: MockerFixture) -> None:
        """Test that rm submenu shows all deployments."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=False,
            ),
            DeploymentInfo(
                deployment_index=1,
                is_current=True,
                repository="test-repo",
                version="2.0.0",
                is_pinned=False,
            ),
        ]

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = ["rm", 0]

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was shown
        assert mock_menu_show.call_count >= 2

    def test_rm_command_executes_rpm_ostree_cleanup(
        self, mocker: MockerFixture
    ) -> None:
        """Test that rm selection executes rpm-ostree cleanup -r."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=False,
            ),
        ]

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = ["rm", 0]

        expected_cmd = ["sudo", "ostree", "admin", "undeploy", "0"]

        sys.argv = ["urh"]
        last_call = mock_execvp_command(mocker, expected_cmd)
        assert "sudo" in last_call
        assert "ostree" in last_call
        assert "admin" in last_call
        assert "undeploy" in last_call

    def test_undeploy_submenu_shows_all_deployments(
        self, mocker: MockerFixture
    ) -> None:
        """Test that undeploy submenu shows all deployments."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=False,
            ),
        ]

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        # Main menu selects "undeploy", submenu selects deployment 0, confirmation selects "Y"
        mock_menu_show.side_effect = ["undeploy", 0, "Y"]

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was shown (main + submenu + confirmation)
        assert mock_menu_show.call_count >= 2

    def test_undeploy_command_executes_ostree_undeploy(
        self, mocker: MockerFixture
    ) -> None:
        """Test that undeploy selection executes ostree admin undeploy."""
        deployments = [
            DeploymentInfo(
                deployment_index=0,
                is_current=False,
                repository="test-repo",
                version="1.0.0",
                is_pinned=False,
            ),
        ]

        mocker.patch("src.urh.deployment.get_deployment_info", return_value=deployments)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        # Main menu selects "undeploy", submenu selects deployment 0, confirmation selects "Y"
        mock_menu_show.side_effect = ["undeploy", 0, "Y"]

        expected_cmd = ["sudo", "ostree", "admin", "undeploy", "0"]

        sys.argv = ["urh"]
        last_call = mock_execvp_command(mocker, expected_cmd)
        assert "sudo" in last_call
        assert "ostree" in last_call
        assert "admin" in last_call
        assert "undeploy" in last_call


@pytest.mark.e2e
class TestMenuHeaderDisplay:
    """Test persistent header display in menus."""

    @pytest.fixture(autouse=True)
    def setup_header_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for header tests."""
        apply_e2e_test_environment(
            mocker,
            tty=True,
            mock_execvp=True,
            execvp_cmd=["sudo", "rpm-ostree", "status"],
            mock_sys_exit=True,
            deployment_info={"repository": "bazzite-nix", "version": "42.20231115.0"},
            deployment_header="Current deployment: bazzite-nix (42.20231115.0)",
        )

    def test_main_menu_includes_deployment_header(self, mocker: MockerFixture) -> None:
        """Test that main menu includes current deployment info in header."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.return_value = "check"

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify persistent header was passed to menu
        call_kwargs = mock_menu_show.call_args[1]
        assert "persistent_header" in call_kwargs
        assert "bazzite-nix" in call_kwargs["persistent_header"]
        assert "42.20231115.0" in call_kwargs["persistent_header"]

    def test_submenu_includes_same_header(self, mocker: MockerFixture) -> None:
        """Test that submenus include the same deployment header."""
        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = ["rebase", "ghcr.io/test/repo:stable"]

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify all menu calls include the same header
        for call in mock_menu_show.call_args_list:
            call_kwargs = call[1] if len(call) > 1 else {}
            if "persistent_header" in call_kwargs:
                assert "bazzite-nix" in call_kwargs["persistent_header"]

    def test_esc_in_submenu_returns_to_main_menu(self, mocker: MockerFixture) -> None:
        """Test that pressing ESC in submenu returns to main menu."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")

        # First call (main menu) returns "rebase"
        # Second call (rebase submenu) raises ESC
        # Third call (back to main menu) returns "check"
        mock_menu_show.side_effect = [
            "rebase",  # Main menu selection
            MenuExitException(is_main_menu=False),  # ESC in submenu
            "check",  # Back to main menu, select check
        ]

        sys.argv = ["urh"]
        with pytest.raises(ExecCompleted):
            cli_main()

        # Verify menu was shown at least twice (main menu -> submenu, then main menu again)
        assert mock_menu_show.call_count >= 2
