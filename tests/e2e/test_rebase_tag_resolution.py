"""
E2E tests for rebase tag resolution and confirmation prompt features.

Tests the user-facing CLI entry points for:
- Tag resolution (e.g., 'unstable' -> 'unstable-43.20260326.1')
- Confirmation prompts for ambiguous rebase URLs
- The -y/--yes flag to bypass confirmation
"""

import sys

import pytest
from pytest_mock import MockerFixture

from src.urh.cli import main as cli_main  # noqa: F401


class TestRebaseTagResolution:
    """Test tag resolution functionality for rebase command."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Setup common test environment for all tag resolution tests."""
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

    def test_rebase_with_full_tag_shows_confirmation(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with full tag shows confirmation when repo is implicit."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        # Mock input for confirmation (user confirms with 'y')
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"

        original_argv = sys.argv
        sys.argv = [
            "urh",
            "rebase",
            "unstable-43.20260326.1",
        ]

        try:
            cli_main()

            # Verify confirmation was requested
            mock_input.assert_called_once()
            confirmation_prompt = mock_input.call_args[0][0]
            assert "unstable-43.20260326.1" in confirmation_prompt

            # Verify command executed with confirmation
            assert mock_run.call_count == 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert "sudo" in last_call_args
            assert "rpm-ostree" in last_call_args
            assert "rebase" in last_call_args
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:unstable-43.20260326.1"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_primary_alias_uses_registry_pointer(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with primary alias ('unstable', 'testing') uses registry pointer directly."""
        # Mock input for confirmation (user confirms with 'y')
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "unstable"]

        try:
            cli_main()

            # Verify NO tag resolution was performed (uses registry alias directly)
            # OCIClient should NOT be called for primary aliases

            # Verify confirmation was requested with alias message
            mock_input.assert_called_once()
            confirmation_prompt = mock_input.call_args[0][0]
            assert 'Confirm rebase to "unstable"?' in confirmation_prompt

            # Verify info messages were printed
            printed_messages = [
                call[0][0]
                for call in mock_print.call_args_list
                if len(call[0]) > 0 and isinstance(call[0][0], str)
            ]
            all_printed_text = "\n".join(printed_messages)
            assert (
                "Using target: ghcr.io/wombatfromhell/bazzite-nix:unstable"
                in all_printed_text
            )

            # Verify command executed with alias (not resolved tag)
            assert mock_run.call_count == 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:unstable"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_short_tag_resolves_to_current(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with short tag 'foo' resolves to latest foo release."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "foo-43.20260326.1",
                "foo-43.20260325.0",
                "stable-42.20260320.0",
            ]
        }
        mock_client_class.return_value = mock_client

        # Mock input for confirmation (user confirms with 'y')
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        # Use a non-primary short tag that needs resolution
        sys.argv = ["urh", "rebase", "foo"]

        try:
            cli_main()

            # Verify tags were fetched
            mock_client.fetch_repository_tags.assert_called_once()

            # Verify confirmation was requested
            mock_input.assert_called_once()
            confirmation_prompt = mock_input.call_args[0][0]
            assert "foo-43.20260326.1" in confirmation_prompt

            # Verify command executed with resolved tag
            assert mock_run.call_count == 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:foo-43.20260326.1"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_primary_alias_and_yes_flag_no_confirmation(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with primary alias and -y flag skips confirmation."""
        # Mock input to verify it's NOT called
        mock_input = mocker.patch("builtins.input")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "-y", "unstable"]

        try:
            cli_main()

            # Verify confirmation was NOT requested
            mock_input.assert_not_called()

            # Verify command executed with alias (not resolved tag)
            assert mock_run.call_count == 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:unstable"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_with_yes_long_flag_no_confirmation(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with --yes flag skips confirmation."""
        mock_input = mocker.patch("builtins.input")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "--yes", "unstable"]

        try:
            cli_main()

            # Verify confirmation was NOT requested
            mock_input.assert_not_called()

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_primary_alias_user_declines_confirmation(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with primary alias when user declines confirmation."""
        # Mock input for confirmation (user declines with 'n')
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "n"

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check only
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "unstable"]

        try:
            cli_main()

            # Verify confirmation was requested
            mock_input.assert_called_once()

            # Verify rebase command was NOT executed
            assert mock_run.call_count == 1

            # Verify exit without executing rebase
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_ambiguous_tag_shows_all_matches(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with ambiguous tag shows all matching tags in confirmation."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "foo-43.20260326.1",
                "foo-43.20260325.0",
                "foo-43.20260324.0",
            ]
        }
        mock_client_class.return_value = mock_client

        # Mock input for confirmation
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"

        # Mock print to capture output
        mock_print = mocker.patch("builtins.print")

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "foo"]

        try:
            cli_main()

            # Verify all matches were printed (not in the prompt, but as separate print calls)
            printed_messages = [
                call[0][0]
                for call in mock_print.call_args_list
                if len(call[0]) > 0 and isinstance(call[0][0], str)
            ]
            all_printed_text = "\n".join(printed_messages)

            assert "foo-43.20260326.1" in all_printed_text
            assert "foo-43.20260325.0" in all_printed_text
            assert "foo-43.20260324.0" in all_printed_text

            # Should resolve to latest (first match)
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:foo-43.20260326.1"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_short_tag_no_matches_shows_error(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with short tag that has no matches shows error."""
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
        sys.argv = ["urh", "rebase", "nonexistent"]

        try:
            cli_main()

            # Verify error message
            mock_print.assert_any_call("Error: No tags found matching 'nonexistent'")

            # Verify exit with error
            mock_exit.assert_called_once_with(1)

        finally:
            sys.argv = original_argv

    def test_rebase_with_explicit_repo_no_confirmation(
        self, mocker: MockerFixture
    ) -> None:
        """Test rebase with explicit repo:tag syntax skips confirmation."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        # Explicitly specify repository with colon syntax
        sys.argv = ["urh", "rebase", "bazzite-nix-nvidia-open:testing-43.20260326.1"]

        try:
            cli_main()

            # Verify NO confirmation was requested (repo explicitly specified)
            # Only curl check and rebase command should run
            assert mock_run.call_count == 2
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1"
                in last_call_args
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv


class TestRebaseURLResolution:
    """Test URL resolution for different repository contexts."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Setup test environment for URL resolution tests."""
        mock_rpm_ostree_commands()
        mocker.patch("os.isatty", return_value=False)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

    def test_rebase_stable_uses_registry_alias(self, mocker: MockerFixture) -> None:
        """Test 'stable' primary alias uses registry pointer directly."""
        mocker.patch("builtins.input", return_value="y")
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "stable"]

        try:
            cli_main()

            # Should use alias directly, not resolved tag
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable"
                in last_call_args
            )
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_rebase_testing_uses_registry_alias(self, mocker: MockerFixture) -> None:
        """Test 'testing' primary alias uses registry pointer directly."""
        mocker.patch("builtins.input", return_value="y")
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "testing"]

        try:
            cli_main()

            # Should use alias directly, not resolved tag
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing"
                in last_call_args
            )
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv


class TestConfirmationPrompt:
    """Test confirmation prompt behavior for rebase command."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Setup test environment for confirmation prompt tests."""
        mock_rpm_ostree_commands()
        mocker.patch("os.isatty", return_value=False)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
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

    def test_confirmation_prompt_shows_repository_and_tag(
        self, mocker: MockerFixture
    ) -> None:
        """Test confirmation prompt displays repository and tag information."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "testing-43.20260326.1"]

        try:
            cli_main()

            # Verify input was called with correct prompt
            mock_input.assert_called_once()
            prompt = mock_input.call_args[0][0]
            assert 'Confirm rebase to "testing-43.20260326.1"?' in prompt
            assert "[y/N]:" in prompt

            # Verify sudo command was called AFTER confirmation
            assert mock_run.call_count == 2
            rebase_call = mock_run.call_args_list[1][0][0]
            assert "sudo" in rebase_call
            assert "rpm-ostree" in rebase_call
            assert "rebase" in rebase_call

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_confirmation_declined_rebase_not_executed(
        self, mocker: MockerFixture
    ) -> None:
        """Test declining confirmation prevents sudo rebase command."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check only
        ]
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "n"
        mock_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "testing-43.20260326.1"]

        try:
            cli_main()

            # Verify confirmation was requested
            mock_input.assert_called_once()

            # Verify sudo rebase command was NOT executed
            assert mock_run.call_count == 1

            # Verify cancellation message
            mock_print.assert_any_call("Rebase cancelled.")

            # Verify exit without executing rebase
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_confirmation_cancelled_with_ctrl_c(self, mocker: MockerFixture) -> None:
        """Test pressing Ctrl+C during confirmation cancels rebase."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check only
        ]
        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = KeyboardInterrupt()
        mock_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "testing-43.20260326.1"]

        try:
            cli_main()

            # Verify confirmation was requested
            mock_input.assert_called_once()

            # Verify sudo rebase command was NOT executed
            assert mock_run.call_count == 1

            # Verify cancellation message
            mock_print.assert_any_call("\nRebase cancelled.")

            # Verify exit without executing rebase
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_yes_flag_skips_confirmation_prompt(self, mocker: MockerFixture) -> None:
        """Test -y flag skips confirmation and executes sudo directly."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_input = mocker.patch("builtins.input")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "-y", "testing-43.20260326.1"]

        try:
            cli_main()

            # Verify NO confirmation was requested
            mock_input.assert_not_called()

            # Verify sudo command was executed directly
            assert mock_run.call_count == 2
            rebase_call = mock_run.call_args_list[1][0][0]
            assert "sudo" in rebase_call
            assert "rpm-ostree" in rebase_call
            assert "rebase" in rebase_call
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing-43.20260326.1"
                in rebase_call
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_yes_long_flag_skips_confirmation_prompt(
        self, mocker: MockerFixture
    ) -> None:
        """Test --yes flag skips confirmation and executes sudo directly."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),  # curl check
            mocker.MagicMock(returncode=0),  # rebase command
        ]
        mock_input = mocker.patch("builtins.input")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "--yes", "testing-43.20260326.1"]

        try:
            cli_main()

            # Verify NO confirmation was requested
            mock_input.assert_not_called()

            # Verify sudo command was executed directly
            assert mock_run.call_count == 2
            rebase_call = mock_run.call_args_list[1][0][0]
            assert "sudo" in rebase_call
            assert "rpm-ostree" in rebase_call

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_confirmation_uppercase_y_accepted(self, mocker: MockerFixture) -> None:
        """Test uppercase 'Y' is accepted for confirmation."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "Y"
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "testing-43.20260326.1"]

        try:
            cli_main()

            # Verify confirmation accepted
            mock_input.assert_called_once()

            # Verify sudo command was executed
            assert mock_run.call_count == 2

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_explicit_repo_syntax_skips_confirmation(
        self, mocker: MockerFixture
    ) -> None:
        """Test repo:tag syntax skips confirmation (explicit repo)."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_input = mocker.patch("builtins.input")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "bazzite-nix-nvidia-open:testing-43.20260326.1"]

        try:
            cli_main()

            # Verify NO confirmation was requested (explicit repo)
            mock_input.assert_not_called()

            # Verify sudo command was executed
            assert mock_run.call_count == 2
            rebase_call = mock_run.call_args_list[1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1"
                in rebase_call
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_full_url_skips_confirmation(self, mocker: MockerFixture) -> None:
        """Test full URL (ghcr.io/...) skips confirmation."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_input = mocker.patch("builtins.input")
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = [
            "urh",
            "rebase",
            "ghcr.io/custom/repo:tag-1.2.3",
        ]

        try:
            cli_main()

            # Verify NO confirmation was requested (full URL)
            mock_input.assert_not_called()

            # Verify sudo command was executed with URL as-is (with ostree prefix)
            assert mock_run.call_count == 2
            rebase_call = mock_run.call_args_list[1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/custom/repo:tag-1.2.3"
                in rebase_call
            )

            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv


class TestCustomDefaultRepository:
    """Test short alias resolution with custom default repository from urh.toml."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(
        self, mocker: MockerFixture, mock_rpm_ostree_commands
    ) -> None:
        """Setup test environment with custom default repository."""
        mock_rpm_ostree_commands()
        mocker.patch("os.isatty", return_value=False)
        mocker.patch("src.urh.system.check_curl_presence", return_value=True)
        # Mock deployment info with custom repo
        mocker.patch(
            "src.urh.deployment.get_current_deployment_info",
            return_value={
                "repository": "ublue-os/bazzite",
                "version": "1.0.0",
            },
        )
        mocker.patch(
            "src.urh.deployment.format_deployment_header",
            return_value="Current deployment: ublue-os/bazzite (1.0.0)",
        )
        mocker.patch(
            "src.urh.deployment.format_menu_header",
            return_value="Current deployment: ublue-os/bazzite (1.0.0)",
        )

    def test_custom_default_repo_stable_alias_resolves_correctly(
        self, mocker: MockerFixture
    ) -> None:
        """Test 'stable' alias resolves to custom default repo (ublue-os/bazzite)."""
        # Mock config to use ublue-os/bazzite as default
        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mocker.patch("builtins.input", return_value="y")
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "stable"]

        try:
            cli_main()

            # Should resolve to ublue-os/bazzite, NOT wombatfromhell/bazzite-nix
            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable"
                in last_call_args
            )
            assert "wombatfromhell" not in last_call_args[3]
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_custom_default_repo_testing_alias_resolves_correctly(
        self, mocker: MockerFixture
    ) -> None:
        """Test 'testing' alias resolves to custom default repo."""
        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mocker.patch("builtins.input", return_value="y")
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "testing"]

        try:
            cli_main()

            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:testing"
                in last_call_args
            )
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_custom_default_repo_full_tag_shows_confirmation(
        self, mocker: MockerFixture
    ) -> None:
        """Test full version tag shows confirmation for custom default repo."""
        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "stable-42.20260331"]

        try:
            cli_main()

            # Should show confirmation for implicit repo
            mock_input.assert_called_once()
            prompt = mock_input.call_args[0][0]
            assert 'Confirm rebase to "stable-42.20260331"?' in prompt

            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable-42.20260331"
                in last_call_args
            )
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv

    def test_custom_default_repo_explicit_repo_with_alias_resolves_tags(
        self, mocker: MockerFixture
    ) -> None:
        """Test explicit repo:tag syntax still resolves tags for non-default repos."""
        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        # Mock OCIClient to fetch tags for the explicit repo
        mock_client_class = mocker.patch("src.urh.commands.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "stable-42.20260331",
                "stable-42.20260330",
            ]
        }
        mock_client_class.return_value = mock_client

        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            mocker.MagicMock(returncode=0),
            mocker.MagicMock(returncode=0),
        ]
        mock_exit = mocker.patch("sys.exit")

        original_argv = sys.argv
        sys.argv = ["urh", "rebase", "bazzite-deck:stable"]

        try:
            cli_main()

            # Should fetch tags for the explicit repo
            mock_client_class.assert_called_once_with("ublue-os/bazzite-deck")

            # Should show confirmation with resolved tag
            mock_input.assert_called_once()
            prompt = mock_input.call_args[0][0]
            assert "stable-42.20260331" in prompt

            last_call_args = mock_run.call_args_list[-1][0][0]
            assert (
                "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite-deck:stable-42.20260331"
                in last_call_args
            )
            mock_exit.assert_called_once_with(0)

        finally:
            sys.argv = original_argv
