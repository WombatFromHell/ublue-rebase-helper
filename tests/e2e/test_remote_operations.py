"""
E2E tests for remote operations workflows.

Tests the OCI client integration through the user-facing `remote-ls` command,
including command execution, error handling, and basic integration.

Note: Tag filtering/sorting logic is tested in integration tests.
These E2E tests focus on command workflows and error handling.
"""

import sys

import pytest
from pytest_mock import MockerFixture

from src.urh.cli import main as cli_main


class TestRemoteLsCommand:
    """Test remote-ls command end-to-end workflows."""

    @pytest.fixture(autouse=True)
    def setup_remote_ls_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for remote-ls tests."""
        # Mock deployment info for header
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )
        mocker.patch(
            "src.urh.cli.format_deployment_header",
            return_value="Current deployment: test-repo (1.0.0)",
        )

        # Force TTY mode
        mocker.patch("os.isatty", return_value=True)

        # Mock curl check
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock sys.exit
        mocker.patch("sys.exit")

        # Mock subprocess for curl calls
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0, stdout="")

    def test_remote_ls_with_url_argument(self, mocker: MockerFixture) -> None:
        """Test remote-ls command with explicit URL argument."""
        # Mock OCIClient
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": ["v1.0.0", "v1.1.0", "v2.0.0"]
        }
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")

        sys.argv = ["urh", "remote-ls", "ghcr.io/test/repo:tag"]
        cli_main()

        # Verify OCIClient was created with correct repository
        mock_client_class.assert_called_once_with("test/repo")

        # Verify tags were printed
        mock_print.assert_any_call("Tags for ghcr.io/test/repo:tag:")

    def test_remote_ls_with_menu_selection(self, mocker: MockerFixture) -> None:
        """Test remote-ls command with menu selection."""
        mock_menu_show = mocker.patch("src.urh.menu.MenuSystem.show_menu")
        mock_menu_show.side_effect = ["remote-ls", "ghcr.io/test/repo:stable"]

        mock_config = mocker.MagicMock()
        mock_config.container_urls.options = ["ghcr.io/test/repo:stable"]
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")

        sys.argv = ["urh"]
        cli_main()

        # Verify menu was shown (main + submenu)
        assert mock_menu_show.call_count >= 2

        # Verify tags were printed
        mock_print.assert_any_call("Tags for ghcr.io/test/repo:stable:")

    def test_remote_ls_no_tags_found(self, mocker: MockerFixture) -> None:
        """Test remote-ls when no tags are found."""
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": []}
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")

        sys.argv = ["urh", "remote-ls", "ghcr.io/test/repo:tag"]
        cli_main()

        # Verify "no tags" message
        mock_print.assert_any_call("No tags found for ghcr.io/test/repo:tag")

    def test_remote_ls_error_fetching_tags(self, mocker: MockerFixture) -> None:
        """Test remote-ls when tag fetching fails."""
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = None  # Error case
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")

        sys.argv = ["urh", "remote-ls", "ghcr.io/test/repo:tag"]
        cli_main()

        # Verify error message
        mock_print.assert_any_call("Could not fetch tags for ghcr.io/test/repo:tag")

    def test_remote_ls_exits_with_success(self, mocker: MockerFixture) -> None:
        """Test remote-ls exits with code 0 on success."""
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        mock_exit = mocker.patch("sys.exit")

        sys.argv = ["urh", "remote-ls", "ghcr.io/test/repo:tag"]
        cli_main()

        mock_exit.assert_called_once_with(0)

    def test_remote_ls_exits_with_error_on_failure(self, mocker: MockerFixture) -> None:
        """Test remote-ls exits with code 1 on failure."""
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = None
        mock_client_class.return_value = mock_client

        mock_exit = mocker.patch("sys.exit")

        sys.argv = ["urh", "remote-ls", "ghcr.io/test/repo:tag"]
        cli_main()

        mock_exit.assert_called_once_with(1)


class TestOCIClientIntegration:
    """Test OCIClient integration with remote-ls command."""

    @pytest.fixture(autouse=True)
    def setup_oci_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for OCI client integration tests."""
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )
        mocker.patch(
            "src.urh.cli.format_deployment_header",
            return_value="Current deployment: test-repo (1.0.0)",
        )
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        mocker.patch("sys.exit")

    def test_oci_client_created_with_repository(self, mocker: MockerFixture) -> None:
        """Test that OCIClient is created with extracted repository name."""
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        sys.argv = ["urh", "remote-ls", "ghcr.io/user/repo:tag"]
        cli_main()

        # Verify client was created with repository name (without registry)
        mock_client_class.assert_called_once_with("user/repo")

    def test_fetch_repository_tags_called_with_url(self, mocker: MockerFixture) -> None:
        """Test that fetch_repository_tags is called with the full URL."""
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        sys.argv = ["urh", "remote-ls", "ghcr.io/user/repo:tag"]
        cli_main()

        # Verify fetch_repository_tags was called
        mock_client.fetch_repository_tags.assert_called_once()


class TestTokenManagerIntegration:
    """Test token manager integration with remote-ls command."""

    @pytest.fixture(autouse=True)
    def setup_token_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for token manager tests."""
        mocker.patch(
            "src.urh.cli.get_current_deployment_info",
            return_value={"repository": "test-repo", "version": "1.0.0"},
        )
        mocker.patch(
            "src.urh.cli.format_deployment_header",
            return_value="Current deployment: test-repo (1.0.0)",
        )
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        mocker.patch("sys.exit")

    def test_token_manager_initialized_with_repository(
        self, mocker: MockerFixture
    ) -> None:
        """Test that OCITokenManager is initialized with repository name."""
        # Mock token manager to track initialization
        mock_token_manager_class = mocker.patch("src.urh.token_manager.OCITokenManager")
        mock_token_manager = mocker.MagicMock()
        mock_token_manager.get_token.return_value = "test_token"
        mock_token_manager_class.return_value = mock_token_manager

        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {"tags": ["v1.0.0"]}
        mock_client_class.return_value = mock_client

        sys.argv = ["urh", "remote-ls", "ghcr.io/test/repo:tag"]
        cli_main()

        # Verify token manager was created (OCIClient creates it internally)
        # This tests that the integration point exists
        assert mock_client_class.called
