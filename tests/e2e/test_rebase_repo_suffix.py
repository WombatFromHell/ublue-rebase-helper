"""
E2E tests for rebase tag resolution with repository suffix syntax.

Tests the user-facing CLI entry points for:
- Repository suffix syntax (e.g., 'bazzite-nix-nvidia-open:testing')
- Tag resolution with custom repository variants
"""

import sys

import pytest
from pytest_mock import MockerFixture

from src.urh.cli import main as cli_main  # noqa: F401


class TestRebaseRepoSuffixSyntax:
    """Test repository suffix syntax for rebase command."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Setup common test environment for all repo suffix tests."""
        # Mock rpm-ostree and ostree commands to prevent FileNotFoundError
        mock_rpm_ostree_commands()

        # Force non-TTY to avoid gum menu hanging
        mocker.patch("os.isatty", return_value=False)

        # Mock curl check to always succeed
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)

        # Mock deployment info to avoid system calls
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={
                "repository": "wombatfromhell/bazzite-nix",
                "version": "1.0.0",
            },
        )
        mocker.patch(
            "src.urh.deployment.format_deployment_header",
            return_value="Current deployment: wombatfromhell/bazzite-nix (1.0.0)",
        )

    def test_rebase_with_repo_suffix_and_tag(self, mocker: MockerFixture) -> None:
        """Test rebase with repo suffix like 'bazzite-nix-nvidia-open:testing'."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "testing-43.20260326.1",
                "testing-43.20260325.0",
                "stable-42.20260320.0",
            ]
        }
        mock_client_class.return_value = mock_client

        mocker.patch("builtins.input", return_value="y")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "bazzite-nix-nvidia-open:testing"]

        try:
            cli_main()

            # Verify tags were fetched for the correct repository
            mock_client_class.assert_called_once_with(
                "wombatfromhell/bazzite-nix-nvidia-open"
            )

            # Verify command executed with resolved tag
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_repo_suffix_and_short_tag_needs_resolution(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with repo suffix and short tag that needs resolution."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "unstable-43.20260326.1",
                "unstable-43.20260325.0",
            ]
        }
        mock_client_class.return_value = mock_client

        mocker.patch("builtins.input", return_value="y")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "bazzite-nix-nvidia-open:unstable"]

        try:
            cli_main()

            # Verify tags were fetched for the correct repository
            mock_client_class.assert_called_once_with(
                "wombatfromhell/bazzite-nix-nvidia-open"
            )

            # Verify command executed with resolved tag (latest unstable)
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:unstable-43.20260326.1"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_repo_suffix_and_full_tag_no_resolution(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with repo suffix and full tag (no resolution needed)."""
        # Mock OCIClient - should NOT be called since we have a full tag
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "bazzite-nix-nvidia-open:unstable-43.20260326.1"]

        try:
            cli_main()

            # Verify OCIClient was NOT called (no tag resolution needed)
            mock_client_class.assert_not_called()

            # Verify command executed with the exact tag provided
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:unstable-43.20260326.1"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_repo_suffix_and_yes_flag(self, mocker: MockerFixture) -> None:
        """Test rebase with repo suffix and -y flag skips confirmation."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "testing-43.20260326.1",
            ]
        }
        mock_client_class.return_value = mock_client

        # Verify input is NOT called (confirmation skipped)
        mock_input = mocker.patch("builtins.input")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "-y", "bazzite-nix-nvidia-open:testing"]

        try:
            cli_main()

            # Verify confirmation was NOT requested
            mock_input.assert_not_called()

            # Verify command executed
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_repo_suffix_no_matches_shows_error(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with repo suffix and tag that has no matches."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "stable-42.20260320.0",
                "testing-43.20260326.1",
            ]
        }
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "bazzite-nix-nvidia-open:nonexistent"]

        try:
            cli_main()

            # Verify error message
            mock_print.assert_any_call("Error: No tags found matching 'nonexistent'")

            # Verify exit with error
            mock_exit.assert_called_once_with(1)

        finally:
            sys.argv = original_argv
