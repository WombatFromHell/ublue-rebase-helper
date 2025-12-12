"""Tests for the system module."""

import subprocess
from unittest.mock import Mock

import pytest

from src.urh.system import (
    check_curl_presence,
    ensure_ostree_prefix,
    extract_context_from_url,
    extract_repository_from_url,
    run_command,
    run_command_safe,
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


class TestRunCommandFunctions:
    """Test run_command and run_command_safe functions for better coverage."""

    def test_run_command_success(self, mocker):
        """Test run_command with successful execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)
        mocker.patch("src.urh.system.logger")
        mocker.patch("builtins.print")

        result = run_command(["echo", "test"])

        assert result == 0
        assert mock_result.returncode == 0

    def test_run_command_with_timeout(self, mocker):
        """Test run_command with timeout specified."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess_run = mocker.patch("subprocess.run", return_value=mock_result)

        result = run_command(["echo", "test"], timeout=30)

        assert result == 0
        # Verify subprocess.run was called
        mock_subprocess_run.assert_called()

    def test_run_command_timeout_expired(self, mocker):
        """Test run_command when timeout occurs."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["echo"], timeout=10),
        )
        mock_logger = mocker.patch("src.urh.system.logger")
        mock_print = mocker.patch("builtins.print")

        result = run_command(["echo", "test"], timeout=10)

        assert result == 124  # Standard timeout exit code
        mock_logger.error.assert_called_once()
        mock_print.assert_called_once()

    def test_run_command_command_not_found(self, mocker):
        """Test run_command when command is not found."""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        mock_logger = mocker.patch("src.urh.system.logger")
        mock_print = mocker.patch("builtins.print")

        result = run_command(["nonexistent_command"])

        assert result == 1  # Error exit code
        mock_logger.error.assert_called()
        mock_print.assert_called()

    def test_run_command_safe_success(self, mocker):
        """Test run_command_safe with successful execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)
        mocker.patch("src.urh.system.logger")
        mocker.patch("builtins.print")

        result = run_command_safe("echo", "test")

        assert result == 0

    def test_run_command_safe_with_timeout(self, mocker):
        """Test run_command_safe with timeout."""
        mock_result = Mock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        result = run_command_safe("echo", "test", timeout=30)

        assert result == 0

    def test_run_command_safe_timeout_expired(self, mocker):
        """Test run_command_safe when timeout occurs."""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["echo"], timeout=10),
        )
        mock_logger = mocker.patch("src.urh.system.logger")
        mock_print = mocker.patch("builtins.print")

        result = run_command_safe("echo", "test", timeout=10)

        assert result == 124  # Standard timeout exit code
        mock_logger.error.assert_called_once()
        mock_print.assert_called_once()

    def test_run_command_safe_command_not_found(self, mocker):
        """Test run_command_safe when command is not found."""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        mock_logger = mocker.patch("src.urh.system.logger")
        mock_print = mocker.patch("builtins.print")

        result = run_command_safe("nonexistent_command")

        assert result == 1  # Error exit code
        mock_logger.error.assert_called()
        mock_print.assert_called()


class TestCurlPresence:
    """Test check_curl_presence function."""

    def test_check_curl_presence_success(self, mocker):
        """Test check_curl_presence when curl is available."""
        mock_result = Mock()
        mock_result.returncode = 0
        mocker.patch("subprocess.run", return_value=mock_result)

        result = check_curl_presence()

        assert result is True

    def test_check_curl_presence_not_found(self, mocker):
        """Test check_curl_presence when curl is not available."""
        mock_result = Mock()
        mock_result.returncode = 1  # which curl returns 1 when not found
        mocker.patch("subprocess.run", return_value=mock_result)

        result = check_curl_presence()

        assert result is False

    def test_check_curl_presence_command_error(self, mocker):
        """Test check_curl_presence when command fails."""
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())

        result = check_curl_presence()

        assert result is False


class TestURLExtractionFunctions:
    """Test URL extraction and transformation functions."""

    @pytest.mark.parametrize(
        "url,expected_repo",
        [
            ("ghcr.io/test/repo:tag", "test/repo"),
            ("docker.io/library/nginx:latest", "library/nginx"),
            ("quay.io/project/app:v1.0", "project/app"),
            ("gcr.io/my-project/my-app:latest", "my-project/my-app"),
            ("simple-repo:tag", "simple-repo"),
            ("repo-without-tag", "repo-without-tag"),
            ("complex/namespace/repo:tag", "complex/namespace/repo"),
            ("ghcr.io/owner/repo/sub", "owner/repo/sub"),
        ],
    )
    def test_extract_repository_from_url(self, url, expected_repo):
        """Test extract_repository_from_url with various formats."""
        result = extract_repository_from_url(url)

        assert result == expected_repo

    def test_extract_context_from_url(self, mocker):
        """Test extract_context_from_url function."""
        # Mock the TagContext enum import
        from enum import Enum

        class MockTagContext(Enum):
            testing = "testing"
            stable = "stable"
            unstable = "unstable"
            latest = "latest"

        # Need to mock the deployment module's TagContext
        mocker.patch("src.urh.deployment.TagContext", MockTagContext)

        # Test with contexts
        assert extract_context_from_url("repo:testing") == "testing"
        assert extract_context_from_url("repo:stable") == "stable"
        assert extract_context_from_url("repo:unstable") == "unstable"
        assert extract_context_from_url("repo:latest") == "latest"

        # Test with non-context
        assert extract_context_from_url("repo:v1.0") is None
        assert extract_context_from_url("repo") is None

    @pytest.mark.parametrize(
        "url,expected_result",
        [
            # Already has ostree prefix
            (
                "ostree-image-signed:docker://example.com/repo:tag",
                "ostree-image-signed:docker://example.com/repo:tag",
            ),
            (
                "ostree-image-unsigned:docker://example.com/repo:tag",
                "ostree-image-unsigned:docker://example.com/repo:tag",
            ),
            # Already has docker prefix
            (
                "docker://example.com/repo:tag",
                "ostree-image-signed:docker://example.com/repo:tag",
            ),
            # No prefix - should add ostree signed prefix
            (
                "example.com/repo:tag",
                "ostree-image-signed:docker://example.com/repo:tag",
            ),
            (
                "ghcr.io/user/repo:latest",
                "ostree-image-signed:docker://ghcr.io/user/repo:latest",
            ),
            (
                "docker.io/library/nginx:latest",
                "ostree-image-signed:docker://docker.io/library/nginx:latest",
            ),
        ],
    )
    def test_ensure_ostree_prefix(self, url, expected_result):
        """Test ensure_ostree_prefix with various URL formats."""
        result = ensure_ostree_prefix(url)

        assert result == expected_result


class TestSystemErrorPaths:
    """Test error handling paths in system functions."""

    def test_run_command_with_exception(self, mocker):
        """Test run_command when subprocess raises unexpected exception."""
        mocker.patch("subprocess.run", side_effect=Exception("Unexpected error"))
        mock_logger = mocker.patch("src.urh.system.logger")
        mock_print = mocker.patch("builtins.print")

        result = run_command(["echo", "test"])

        # Should return 1 as the error code when an unexpected exception occurs
        assert result == 1
        mock_logger.error.assert_called()
        mock_print.assert_called()

    def test_run_command_safe_with_exception(self, mocker):
        """Test run_command_safe when subprocess raises unexpected exception."""
        mocker.patch("subprocess.run", side_effect=Exception("Unexpected error"))
        mock_logger = mocker.patch("src.urh.system.logger")
        mock_print = mocker.patch("builtins.print")

        result = run_command_safe("echo", "test")

        # Should return 1 as the error code when an unexpected exception occurs
        assert result == 1
        mock_logger.error.assert_called()
        mock_print.assert_called()
