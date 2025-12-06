"""Tests for the system module."""

import pytest

from src.urh.system import (
    check_curl_presence,
    extract_context_from_url,
    extract_repository_from_url,
    run_command,
)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_run_command_success(self, mock_subprocess_run_success):
        """Test running a successful command."""
        cmd = ["echo", "hello"]
        result = run_command(cmd)
        assert result == 0
        mock_subprocess_run_success.assert_called_once_with(cmd, check=False)

    def test_run_command_failure(self, mock_subprocess_run_failure):
        """Test running a command that fails."""
        cmd = ["false"]  # This command always fails
        result = run_command(cmd)
        assert result == 1

    def test_run_command_not_found(self, mock_subprocess_run_not_found):
        """Test running a command that doesn't exist."""
        cmd = ["nonexistent_command"]
        result = run_command(cmd)
        assert result == 1

    def test_check_curl_presence_success(self, mocker):
        """Test checking for curl presence when curl is available."""
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.returncode = 0

        result = check_curl_presence()
        assert result is True
        mock_subprocess.assert_called_once_with(
            ["which", "curl"], capture_output=True, text=True, check=False
        )

    def test_check_curl_presence_failure(self, mocker):
        """Test checking for curl presence when curl is not available."""
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.returncode = 1

        result = check_curl_presence()
        assert result is False
        mock_subprocess.assert_called_once_with(
            ["which", "curl"], capture_output=True, text=True, check=False
        )

    def test_check_curl_presence_file_not_found(self, mocker):
        """Test checking for curl presence when 'which' command is not found."""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)

        result = check_curl_presence()
        assert result is False


class TestUtilityIntegration:
    """Test utility function integration."""

    def test_extract_functions_integration(self):
        """Test integration between extract functions."""
        url = "ghcr.io/wombatfromhell/bazzite-nix:testing"

        repository = extract_repository_from_url(url)
        context = extract_context_from_url(url)

        assert repository == "wombatfromhell/bazzite-nix"
        assert context == "testing"

    @pytest.mark.parametrize(
        "cmd,returncode,expected",
        [
            (["echo", "hello"], 0, 0),
            (["false"], 1, 1),  # This command always fails
            (["nonexistent_command"], 1, 1),
        ],
    )
    def test_run_command_integration(self, mocker, cmd, returncode, expected):
        """Test run_command integration with subprocess using parametrization."""
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.returncode = returncode

        result = run_command(cmd)

        assert result == expected
        mock_subprocess.assert_called_once_with(cmd, check=False)
