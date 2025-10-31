"""Shared fixtures and test configuration for ublue-rebase-helper tests."""

import os
import sys

import pytest

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from urh import OCIClient


# Common fixtures for dependency injection tests
@pytest.fixture
def mock_is_tty_true(mocker):
    """Fixture that mocks is_tty to return True."""
    return mocker.Mock(return_value=True)


@pytest.fixture
def mock_is_tty_false(mocker):
    """Fixture that mocks is_tty to return False."""
    return mocker.Mock(return_value=False)


@pytest.fixture
def mock_subprocess_result(mocker):
    """Fixture that creates a mock subprocess result."""

    def _create_result(returncode=0, stdout=""):
        mock_result = mocker.Mock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        return mock_result

    return _create_result


@pytest.fixture
def mock_subprocess_run_success(mocker, mock_subprocess_result):
    """Fixture that mocks subprocess.run to return success."""
    mock_run = mocker.Mock(return_value=mock_subprocess_result(0, "success"))
    return mock_run


@pytest.fixture
def mock_subprocess_run_failure(mocker, mock_subprocess_result):
    """Fixture that mocks subprocess.run to return failure."""
    mock_run = mocker.Mock(return_value=mock_subprocess_result(1, ""))
    return mock_run


@pytest.fixture
def mock_print(mocker):
    """Fixture that mocks the print function."""
    return mocker.Mock()


@pytest.fixture
def mock_client() -> OCIClient:
    """Provides a OCIClient instance for testing."""
    repo = "test/test-repo"
    instance = OCIClient(repo, cache_path="/tmp/oci_ghcr_token")
    return instance
