"""
E2E tests for rebase command workflows.

Tests the user-facing CLI entry points for:
- Tag resolution (e.g., 'unstable' -> 'unstable-43.20260326.1')
- Repository suffix syntax (e.g., 'bazzite-nix-nvidia-open:testing')
- Confirmation prompts for ambiguous rebase URLs
- The -y/--yes flag to bypass confirmation
- Custom default repository from urh.toml
"""

import pytest
from pytest_mock import MockerFixture

from src.urh.cli import main as cli_main  # noqa: F401
from tests.conftest import (
    _make_mock_process,
    apply_e2e_test_environment,
    mock_execvp_command,
)


@pytest.mark.e2e
class TestRebaseTagResolution:
    """Test tag resolution functionality for rebase command."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, mocker: MockerFixture) -> None:
        """Setup common test environment for all tag resolution tests."""
        apply_e2e_test_environment(
            mocker,
            tty=False,
            deployment_info={
                "repository": "wombatfromhell/bazzite-nix",
                "version": "1.0.0",
            },
            deployment_header="Current deployment: wombatfromhell/bazzite-nix (1.0.0)",
        )

    def test_rebase_with_full_tag_shows_confirmation(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with full tag shows confirmation when repo is implicit."""

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)  # curl check

        # Mock input for confirmation (user confirms with 'y')
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:unstable-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "unstable-43.20260326.1"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Verify confirmation was requested
        mock_input.assert_called_once()
        confirmation_prompt = mock_input.call_args[0][0]
        assert "unstable-43.20260326.1" in confirmation_prompt

        # Verify command executed with confirmation
        assert "sudo" in last_call_args
        assert "rpm-ostree" in last_call_args
        assert "rebase" in last_call_args
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:unstable-43.20260326.1"
            in last_call_args
        )

    def test_rebase_with_primary_alias_uses_registry_pointer(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with primary alias ('unstable', 'testing') uses registry pointer directly."""

        # Mock input for confirmation (user confirms with 'y')
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)  # curl check

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:unstable",
        ]
        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "rebase", "unstable"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

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
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:unstable"
            in last_call_args
        )

    def test_rebase_with_short_tag_resolves_to_current(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with short tag 'foo' resolves to latest foo release."""

        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
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

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:foo-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "foo"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Verify tags were fetched
        mock_client.fetch_repository_tags.assert_called_once()

        # Verify confirmation was requested
        mock_input.assert_called_once()
        confirmation_prompt = mock_input.call_args[0][0]
        assert "foo-43.20260326.1" in confirmation_prompt

        # Verify command executed with resolved tag
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:foo-43.20260326.1"
            in last_call_args
        )

    def test_rebase_ambiguous_tag_shows_all_matches(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with ambiguous tag shows all matching tags in confirmation."""

        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
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

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:foo-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "foo"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

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
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:foo-43.20260326.1"
            in last_call_args
        )

    def test_rebase_short_tag_no_matches_shows_error(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with short tag that has no matches shows error."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "stable-42.20260320.0",
                "testing-43.20260326.1",
            ]
        }
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "rebase", "nonexistent"])

        result = cli_main()

        # Verify error message
        mock_print.assert_any_call("Error: No tags found matching 'nonexistent'")

        # Verify exit with error
        assert result == 1

    def test_rebase_with_explicit_repo_no_confirmation(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with explicit repo:tag syntax skips confirmation."""

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)  # curl check

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "bazzite-nix-nvidia-open:testing-43.20260326.1"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Verify NO confirmation was requested (repo explicitly specified)
        # Only curl check and rebase command should run
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1"
            in last_call_args
        )

    def test_rebase_stable_uses_registry_alias(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test 'stable' primary alias uses registry pointer directly."""

        mocker.patch("builtins.input", return_value="y")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable",
        ]

        cli_command(["urh", "rebase", "stable"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable"
            in last_call_args
        )

    def test_rebase_testing_uses_registry_alias(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test 'testing' primary alias uses registry pointer directly."""

        mocker.patch("builtins.input", return_value="y")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing",
        ]

        cli_command(["urh", "rebase", "testing"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing"
            in last_call_args
        )


@pytest.mark.e2e
class TestRebaseRepoSuffix:
    """Test repository suffix syntax for rebase command."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, mocker: MockerFixture) -> None:
        """Setup common test environment for all repo suffix tests."""
        apply_e2e_test_environment(
            mocker,
            tty=False,
            deployment_info={
                "repository": "wombatfromhell/bazzite-nix",
                "version": "1.0.0",
            },
            deployment_header="Current deployment: wombatfromhell/bazzite-nix (1.0.0)",
        )

    def test_rebase_with_repo_suffix_and_tag(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with repo suffix like 'bazzite-nix-nvidia-open:testing'."""

        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
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

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "bazzite-nix-nvidia-open:testing"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Verify tags were fetched for the correct repository
        mock_client_class.assert_called_once_with(
            "wombatfromhell/bazzite-nix-nvidia-open"
        )

        # Verify command executed with resolved tag
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1"
            in last_call_args
        )

    def test_rebase_with_repo_suffix_and_short_tag_needs_resolution(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with repo suffix and short tag that needs resolution."""

        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "unstable-43.20260326.1",
                "unstable-43.20260325.0",
            ]
        }
        mock_client_class.return_value = mock_client

        mocker.patch("builtins.input", return_value="y")

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:unstable-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "bazzite-nix-nvidia-open:unstable"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Verify tags were fetched for the correct repository
        mock_client_class.assert_called_once_with(
            "wombatfromhell/bazzite-nix-nvidia-open"
        )

        # Verify command executed with resolved tag (latest unstable)
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:unstable-43.20260326.1"
            in last_call_args
        )

    def test_rebase_with_repo_suffix_and_full_tag_no_resolution(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with repo suffix and full tag (no resolution needed)."""

        # Mock OCIClient - should NOT be called since we have a full tag
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:unstable-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "bazzite-nix-nvidia-open:unstable-43.20260326.1"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Verify OCIClient was NOT called (no tag resolution needed)
        mock_client_class.assert_not_called()

        # Verify command executed with the exact tag provided
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:unstable-43.20260326.1"
            in last_call_args
        )

    def test_rebase_with_repo_suffix_and_yes_flag(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with repo suffix and -y flag skips confirmation."""

        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "testing-43.20260326.1",
            ]
        }
        mock_client_class.return_value = mock_client

        # Verify input is NOT called (confirmation skipped)
        mock_input = mocker.patch("builtins.input")

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "-y", "bazzite-nix-nvidia-open:testing"])

        mock_execvp_command(mocker, expected_cmd)

        # Verify confirmation was NOT requested
        mock_input.assert_not_called()

    def test_rebase_with_repo_suffix_no_matches_shows_error(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test rebase with repo suffix and tag that has no matches."""
        # Mock OCIClient to fetch tags
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
        mock_client = mocker.MagicMock()
        mock_client.fetch_repository_tags.return_value = {
            "tags": [
                "stable-42.20260320.0",
                "testing-43.20260326.1",
            ]
        }
        mock_client_class.return_value = mock_client

        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "rebase", "bazzite-nix-nvidia-open:nonexistent"])

        result = cli_main()

        # Verify error message
        mock_print.assert_any_call("Error: No tags found matching 'nonexistent'")

        # Verify exit with error
        assert result == 1


@pytest.mark.e2e
class TestRebaseConfirmation:
    """Test confirmation prompt behavior for rebase command."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment for confirmation prompt tests."""
        apply_e2e_test_environment(
            mocker,
            tty=False,
            deployment_info={
                "repository": "wombatfromhell/bazzite-nix",
                "version": "1.0.0",
            },
            deployment_header="Current deployment: wombatfromhell/bazzite-nix (1.0.0)",
        )

    @pytest.mark.parametrize(
        "input_value,expect_executed,expect_message",
        [
            pytest.param("y", True, None, id="confirm_lowercase_y"),
            pytest.param("Y", True, None, id="confirm_uppercase_Y"),
            pytest.param("n", False, "Rebase cancelled.", id="declined_n"),
        ],
    )
    def test_confirmation_prompt_responses(
        self,
        mocker: MockerFixture,
        cli_command,
        input_value: str,
        expect_executed: bool,
        expect_message: str | None,
    ) -> None:
        """Test confirmation prompt accepts y/Y to confirm and n to decline."""
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)
        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = input_value

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing-43.20260326.1",
        ]

        if expect_executed:
            cli_command(["urh", "rebase", "testing-43.20260326.1"])
            rebase_call = mock_execvp_command(mocker, expected_cmd)

            # Verify input was called with correct prompt
            mock_input.assert_called_once()
            prompt = mock_input.call_args[0][0]
            assert 'Confirm rebase to "testing-43.20260326.1"?' in prompt
            assert "[y/N]:" in prompt

            # Verify sudo command was executed
            assert "sudo" in rebase_call
            assert "rpm-ostree" in rebase_call
            assert "rebase" in rebase_call
        else:
            mock_print = mocker.patch("builtins.print")
            cli_command(["urh", "rebase", "testing-43.20260326.1"])
            result = cli_main()

            # Verify confirmation was requested
            mock_input.assert_called_once()

            # Verify sudo rebase command was NOT executed
            assert mock_popen.call_count == 0

            # Verify cancellation message
            mock_print.assert_any_call(expect_message)

            # Verify exit without executing rebase
            assert result == 0

    def test_confirmation_cancelled_with_ctrl_c(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test pressing Ctrl+C during confirmation cancels rebase."""
        mock_popen = mocker.patch("subprocess.Popen")
        mock_input = mocker.patch("builtins.input")
        mock_input.side_effect = KeyboardInterrupt()
        mock_print = mocker.patch("builtins.print")

        cli_command(["urh", "rebase", "testing-43.20260326.1"])

        result = cli_main()

        # Verify confirmation was requested
        mock_input.assert_called_once()

        # Verify sudo rebase command was NOT executed (curl check is also mocked)
        assert mock_popen.call_count == 0

        # Verify cancellation message
        mock_print.assert_any_call("\nRebase cancelled.")

        # Verify exit without executing rebase
        assert result == 0

    @pytest.mark.parametrize(
        "yes_flag",
        [
            pytest.param("-y", id="short_flag"),
            pytest.param("--yes", id="long_flag"),
        ],
    )
    def test_yes_flag_skips_confirmation_prompt(
        self,
        mocker: MockerFixture,
        cli_command,
        yes_flag: str,
    ) -> None:
        """Test -y/--yes flag skips confirmation and executes sudo directly."""
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)
        mock_input = mocker.patch("builtins.input")

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing-43.20260326.1",
        ]

        cli_command(["urh", "rebase", yes_flag, "testing-43.20260326.1"])

        rebase_call = mock_execvp_command(mocker, expected_cmd)

        # Verify NO confirmation was requested
        mock_input.assert_not_called()

        # Verify sudo command was executed directly
        assert "sudo" in rebase_call
        assert "rpm-ostree" in rebase_call
        assert "rebase" in rebase_call
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing-43.20260326.1"
            in rebase_call
        )

    def test_explicit_repo_syntax_skips_confirmation(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test repo:tag syntax skips confirmation (explicit repo)."""

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)
        mock_input = mocker.patch("builtins.input")

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1",
        ]

        cli_command(["urh", "rebase", "bazzite-nix-nvidia-open:testing-43.20260326.1"])

        rebase_call = mock_execvp_command(mocker, expected_cmd)

        # Verify NO confirmation was requested (explicit repo)
        mock_input.assert_not_called()

        # Verify sudo command was executed
        assert (
            "ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix-nvidia-open:testing-43.20260326.1"
            in rebase_call
        )

    def test_full_url_skips_confirmation(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test full URL (ghcr.io/...) skips confirmation."""

        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)
        mock_input = mocker.patch("builtins.input")

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/custom/repo:tag-1.2.3",
        ]

        cli_command(["urh", "rebase", "ghcr.io/custom/repo:tag-1.2.3"])

        rebase_call = mock_execvp_command(mocker, expected_cmd)

        # Verify NO confirmation was requested (full URL)
        mock_input.assert_not_called()

        # Verify sudo command was executed with URL as-is (with ostree prefix)
        assert (
            "ostree-image-signed:docker://ghcr.io/custom/repo:tag-1.2.3" in rebase_call
        )


@pytest.mark.e2e
class TestRebaseCustomRepository:
    """Test short alias resolution with custom default repository from urh.toml."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self, mocker: MockerFixture) -> None:
        """Setup test environment with custom default repository."""
        apply_e2e_test_environment(
            mocker,
            tty=False,
            deployment_info={
                "repository": "ublue-os/bazzite",
                "version": "1.0.0",
            },
            deployment_header="Current deployment: ublue-os/bazzite (1.0.0)",
        )
        # Extra patch for format_menu_header (specific to this test class)
        mocker.patch(
            "src.urh.deployment.format_menu_header",
            return_value="Current deployment: ublue-os/bazzite (1.0.0)",
        )

    def test_custom_default_repo_stable_alias_resolves_correctly(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test 'stable' alias resolves to custom default repo (ublue-os/bazzite)."""

        # Mock config to use ublue-os/bazzite as default
        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mocker.patch("builtins.input", return_value="y")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable",
        ]

        cli_command(["urh", "rebase", "stable"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Should resolve to ublue-os/bazzite, NOT wombatfromhell/bazzite-nix
        assert (
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable"
            in last_call_args
        )
        assert "wombatfromhell" not in last_call_args[3]

    def test_custom_default_repo_testing_alias_resolves_correctly(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test 'testing' alias resolves to custom default repo."""

        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mocker.patch("builtins.input", return_value="y")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:testing",
        ]

        cli_command(["urh", "rebase", "testing"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)
        assert (
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:testing"
            in last_call_args
        )

    def test_custom_default_repo_full_tag_shows_confirmation(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test full version tag shows confirmation for custom default repo."""

        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        mock_input = mocker.patch("builtins.input")
        mock_input.return_value = "y"
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable-42.20260331",
        ]

        cli_command(["urh", "rebase", "stable-42.20260331"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Should show confirmation for implicit repo
        mock_input.assert_called_once()
        prompt = mock_input.call_args[0][0]
        assert 'Confirm rebase to "stable-42.20260331"?' in prompt

        assert (
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite:stable-42.20260331"
            in last_call_args
        )

    def test_custom_default_repo_explicit_repo_with_alias_resolves_tags(
        self, mocker: MockerFixture, cli_command
    ) -> None:
        """Test explicit repo:tag syntax still resolves tags for non-default repos."""

        mock_config = mocker.MagicMock()
        mock_config.container_urls.default = "ghcr.io/ublue-os/bazzite:testing"
        mocker.patch("src.urh.config.get_config", return_value=mock_config)

        # Mock OCIClient to fetch tags for the explicit repo
        mock_client_class = mocker.patch("src.urh.commands.rebase.OCIClient")
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
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)

        expected_cmd = [
            "sudo",
            "rpm-ostree",
            "rebase",
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite-deck:stable-42.20260331",
        ]

        cli_command(["urh", "rebase", "bazzite-deck:stable"])

        last_call_args = mock_execvp_command(mocker, expected_cmd)

        # Should fetch tags for the explicit repo
        mock_client_class.assert_called_once_with("ublue-os/bazzite-deck")

        # Should show confirmation with resolved tag
        mock_input.assert_called_once()
        prompt = mock_input.call_args[0][0]
        assert "stable-42.20260331" in prompt

        assert (
            "ostree-image-signed:docker://ghcr.io/ublue-os/bazzite-deck:stable-42.20260331"
            in last_call_args
        )
