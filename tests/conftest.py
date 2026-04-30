"""
Centralized fixtures and dependency injection helpers for test suite.

This module provides session, module, and function-scoped fixtures for:
- Precomputed test data (config, tags, deployments)
- Mocked external dependencies (subprocess, network, file I/O)
- Dependency injection helpers for testable source code
"""

import sys
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional

import pytest
from pytest_mock import MockerFixture

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.urh.commands.registry import CommandRegistry  # noqa: E402
from src.urh.config import (  # noqa: E402
    _STANDARD_REPOSITORIES,
    ContainerURLsConfig,
    URHConfig,
)
from src.urh.deployment import DeploymentInfo  # noqa: E402

# =============================================================================
# SHARED TEST UTILITIES
# =============================================================================


def _make_mock_process(mocker: MockerFixture, returncode: int = 0) -> Any:
    """Create a properly configured mock subprocess.Popen process object.

    Usage:
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = _make_mock_process(mocker, returncode=0)
    """
    proc = mocker.MagicMock()
    proc.returncode = returncode
    proc.communicate.return_value = (None, None)
    return proc


@pytest.fixture
def cli_command() -> Generator[Callable[[List[str]], List[str]], None, None]:
    """Fixture that sets sys.argv and restores it after the test.

    Replaces the manual try/finally pattern:
        original_argv = sys.argv
        sys.argv = ["urh", "command", "arg"]
        try:
            # test code
        finally:
            sys.argv = original_argv

    Usage:
        def test_something(cli_command):
            cli_command(["urh", "rebase", "testing"])
            # test code
    """
    original_argv = sys.argv

    def _factory(argv: List[str]) -> List[str]:
        sys.argv = argv
        return argv

    yield _factory

    sys.argv = original_argv


# =============================================================================
# SESSION-SCOPED FIXTURES (expensive, reusable across all tests)
# =============================================================================


@pytest.fixture(scope="session")
def sample_config_data() -> Dict[str, Any]:
    """
    Precomputed sample configuration data.

    Use this fixture when you need consistent config data across tests.
    Avoid modifying the returned data to maintain test isolation.

    Container URLs are generated from _STANDARD_REPOSITORIES to stay in sync
    with the single source of truth in config.py.
    """
    # Generate container URLs from central source of truth
    container_options = [
        f"ghcr.io/{repo}:{tag}" for repo, tag in _STANDARD_REPOSITORIES
    ]

    return {
        "repository": [
            {
                "name": "ublue-os/bazzite",
                "include_sha256_tags": False,
                "filter_patterns": [
                    r"^sha256-.*\.sig$",
                    r"^sha256-.*\.att$",
                    r"^sha256-.*\.sbom$",
                    r"^sha256-.*",
                    r"^(latest|testing|stable|unstable)$",
                ],
                "ignore_tags": ["latest", "testing", "stable", "unstable"],
            },
        ],
        "container_urls": {
            "default": "ghcr.io/wombatfromhell/bazzite-nix:testing",
            "options": container_options,
        },
        "settings": {
            "max_tags_display": 30,
            "debug_mode": False,
        },
    }


@pytest.fixture(scope="session")
def sample_tags_data() -> Dict[str, List[str]]:
    """
    Precomputed sample OCI tags API response.

    Includes various tag formats for comprehensive filtering tests:
    - Context aliases (latest, testing, stable, unstable)
    - SHA256 hashes and signatures
    - Context-prefixed versions (testing-X.X, stable-X.X)
    - Date-based versions (YYYYMMDD)
    - Cosign v2.x signatures (.sig) and v3.x attestations (.att, .sbom)
    """
    return {
        "tags": [
            "latest",
            "testing",
            "stable",
            "unstable",
            "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890.sig",
            "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890.att",
            "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890.sbom",
            "testing-42.20231115.0",
            "testing-41.20231110.0",
            "stable-42.20231115.0",
            "stable-41.20231110.0",
            "unstable-43.20231120.0",
            "42.20231115.0",
            "41.20231110.0",
            "43.20231120.0",
            "latest.20231115",
            "20231115",
            "20231110",
            "20231120",
        ]
    }


@pytest.fixture(scope="session")
def sample_status_output() -> str:
    """
    Precomputed rpm-ostree status -v output.

    Simulates output with multiple deployments, including pinned status.
    """
    return """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
        Pinned: yes
"""


@pytest.fixture(scope="session")
def sample_deployments(sample_status_output: str) -> List[DeploymentInfo]:
    """
    Pre-parsed DeploymentInfo list from sample status output.

    Use this when you need deployment data without parsing.
    """
    from src.urh.deployment import parse_deployment_info

    return parse_deployment_info(sample_status_output)


@pytest.fixture(scope="session")
def command_registry() -> CommandRegistry:
    """
    Initialized CommandRegistry instance.

    Session-scoped for performance - command definitions don't change between tests.
    """
    return CommandRegistry()


# =============================================================================
# MODULE-SCOPED FIXTURES (shared within test file)
# =============================================================================


@pytest.fixture(scope="module")
def mock_config_for_module_tests(mocker: MockerFixture) -> URHConfig:
    """
    Create a mock URHConfig for module-level tests.

    Use this when you need a config object but don't want file I/O.
    """
    config = URHConfig()
    config.container_urls = ContainerURLsConfig(
        default="ghcr.io/test/repo:testing",
        options=[
            "ghcr.io/test/repo:testing",
            "ghcr.io/test/repo:stable",
        ],
    )
    return config


@pytest.fixture(scope="module")
def oci_client_with_mocks(mocker: MockerFixture) -> Any:
    """
    OCIClient with mocked token manager and HTTP client.

    Use this for integration tests that need OCIClient without network calls.
    """
    from src.urh.oci_client import OCIClient

    # Mock token manager
    mock_token_manager = mocker.MagicMock()
    mock_token_manager.get_token.return_value = "test_token"
    mock_token_manager.invalidate_cache = mocker.MagicMock()

    # Create client and inject mock
    client = OCIClient("test/repo")
    client.token_manager = mock_token_manager

    # Mock subprocess for curl calls
    mocker.patch(
        "subprocess.run",
        return_value=mocker.MagicMock(
            returncode=0,
            stdout='{"tags": ["tag1", "tag2", "tag3"]}',
        ),
    )

    return client


@pytest.fixture(scope="module")
def menu_system_with_mocks(mocker: MockerFixture) -> Any:
    """
    MenuSystem with mocked gum and subprocess.

    Use this for integration tests that need menu interactions without TTY.
    """
    from src.urh.menu import MenuSystem

    # Force non-TTY mode to avoid gum
    mocker.patch("os.isatty", return_value=False)

    return MenuSystem()


# =============================================================================
# FUNCTION-SCOPED FIXTURES (isolated per-test)
# =============================================================================


@pytest.fixture
def mock_rpm_ostree_commands(mocker: MockerFixture) -> None:
    """
    Mock rpm-ostree, ostree, and curl commands to prevent FileNotFoundError.

    Patches subprocess.run to handle common system commands with sensible
    defaults. Unmocked commands fail with a clear error message.

    Usage:
        def test_with_rpm_ostree(mock_rpm_ostree_commands):
            # rpm-ostree, ostree, and curl commands now return mock results
    """

    def mock_subprocess_handler(cmd: list, **kwargs: Any) -> Any:
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0

        if "curl" in cmd:
            if cmd[0] in ("which", "type", "command"):
                mock_result.stdout = "/usr/bin/curl"
            else:
                mock_result.stdout = ""
        elif "rpm-ostree" in cmd and "status" in cmd:
            mock_result.stdout = """State: idle
Deployments:
● ostree-image-signed:docker://ghcr.io/test/repo:testing
               Version: 1.0.0
                Commit: abc123
"""
        elif "rpm-ostree" in cmd and "kargs" in cmd and "sudo" not in cmd:
            mock_result.stdout = "quiet loglevel=3"
        elif "ostree" in cmd and "admin" in cmd and "pin" in cmd:
            mock_result.stdout = ""
        elif "ostree" in cmd and "admin" in cmd and "undeploy" in cmd:
            mock_result.stdout = ""
        elif "rpm-ostree" in cmd or "ostree" in cmd:
            mock_result.stdout = ""
        else:
            mock_result.returncode = 1
            mock_result.stderr = f"Unmocked command: {' '.join(cmd)}"

        return mock_result

    mocker.patch("subprocess.run", side_effect=mock_subprocess_handler)


class ExecCompleted(Exception):
    """Raised when os.execvp is mocked in tests to simulate process replacement."""

    def __init__(self, cmd: list[str]):
        self.cmd = cmd
        super().__init__(f"execvp: {cmd[0]}")


def apply_e2e_test_environment(
    mocker: MockerFixture,
    tty: bool = False,
    deployment_info: Optional[Dict[str, str]] = None,
    deployment_header: Optional[str] = None,
    mock_execvp: bool = False,
    mock_sys_exit: bool = False,
    execvp_cmd: Optional[List[str]] = None,
) -> None:
    """
    Apply common E2E test environment setup.

    This function consolidates the near-identical setup code that appears
    in every E2E test class's autouse fixture. Call it from your fixture
    with the parameters that match your test class's needs.

    Parameters
    ----------
    mocker : MockerFixture
        pytest-mock fixture instance.
    tty : bool, default False
        If True, mock os.isatty to return True (menu mode).
        If False, mock os.isatty to return False (direct CLI mode).
    deployment_info : dict, optional
        Return value for get_current_deployment_info. Defaults to
        {"repository": "test-repo", "version": "1.0.0"}.
    deployment_header : str, optional
        Return value for format_deployment_header. Auto-generated from
        deployment_info if not provided.
    mock_execvp : bool, default False
        If True, patch os.execvp to raise ExecCompleted(execvp_cmd).
        Tests that need custom execvp behavior should set this to False
        and patch os.execvp themselves.
    mock_sys_exit : bool, default False
        If True, patch sys.exit to prevent actual exits.
    execvp_cmd : list[str], optional
        Command to use in ExecCompleted exception. Defaults to
        ["sudo", "rpm-ostree", "upgrade"] if mock_execvp is True.
    """

    def _mock_subprocess(cmd: list, **kwargs: Any) -> Any:
        result = mocker.MagicMock()
        result.returncode = 0
        if "curl" in cmd:
            result.stdout = (
                "/usr/bin/curl" if cmd[0] in ("which", "type", "command") else ""
            )
        elif "rpm-ostree" in cmd and "status" in cmd:
            result.stdout = """State: idle
Deployments:
● ostree-image-signed:docker://ghcr.io/test/repo:testing
               Version: 1.0.0
                Commit: abc123
"""
        elif "rpm-ostree" in cmd and "kargs" in cmd and "sudo" not in cmd:
            result.stdout = "quiet loglevel=3"
        elif "ostree" in cmd and "admin" in cmd and "pin" in cmd:
            result.stdout = ""
        elif "ostree" in cmd and "admin" in cmd and "undeploy" in cmd:
            result.stdout = ""
        elif "rpm-ostree" in cmd or "ostree" in cmd:
            result.stdout = ""
        else:
            result.returncode = 1
            result.stderr = f"Unmocked command: {' '.join(cmd)}"
        return result

    mocker.patch("subprocess.run", side_effect=_mock_subprocess)

    # Mock TTY mode
    mocker.patch("os.isatty", return_value=tty)

    # Mock curl check to always succeed
    mocker.patch("src.urh.system.check_curl_presence", return_value=True)

    # Mock deployment info
    if deployment_info is None:
        deployment_info = {"repository": "test-repo", "version": "1.0.0"}
    if deployment_header is None:
        deployment_header = (
            f"Current deployment: {deployment_info['repository']} "
            f"({deployment_info['version']})"
        )
    mocker.patch(
        "src.urh.deployment.get_current_deployment_info",
        return_value=deployment_info,
    )
    mocker.patch(
        "src.urh.deployment.format_deployment_header",
        return_value=deployment_header,
    )

    # Optionally mock os.execvp
    if mock_execvp:
        cmd = execvp_cmd or ["sudo", "rpm-ostree", "upgrade"]
        mocker.patch("os.execvp", side_effect=ExecCompleted(cmd))

    # Optionally mock sys.exit
    if mock_sys_exit:
        mocker.patch("sys.exit")


def mock_execvp_command(
    mocker: MockerFixture,
    expected_cmd: List[str],
) -> List[str]:
    """
    Mock os.execvp, run cli_main(), and return the captured command.

    This helper consolidates the common pattern:

        mock_execvp = mocker.patch("os.execvp", side_effect=ExecCompleted(cmd))
        with pytest.raises(ExecCompleted):
            cli_main()
        assert mock_execvp.call_count >= 1
        last_call = mock_execvp.call_args_list[-1][0][1]

    Parameters
    ----------
    mocker : MockerFixture
        pytest-mock fixture instance.
    expected_cmd : list[str]
        The command list to raise in ExecCompleted.

    Returns
    -------
    list[str]
        The command list actually passed to os.execvp (last call).

    Example
    -------
        def test_rebase_executes_command(mocker, cli_command):
            cli_command(["urh", "rebase", "tag"])
            cmd = mock_execvp_command(mocker, ["sudo", "rpm-ostree", "rebase", "tag"])
            assert "rpm-ostree" in cmd
    """
    mock_execvp = mocker.patch("os.execvp", side_effect=ExecCompleted(expected_cmd))

    with pytest.raises(ExecCompleted):
        from src.urh.cli import main as cli_main

        cli_main()

    assert mock_execvp.call_count >= 1
    return mock_execvp.call_args_list[-1][0][1]


# =============================================================================
# PARAMETRIZED TEST DATA FIXTURES
# =============================================================================


@pytest.fixture(
    params=[
        ("check", False),
        ("ls", False),
        ("upgrade", True),
        ("rollback", True),
        ("pin", True),
        ("unpin", True),
    ]
)
def command_sudo_params(request: Any) -> tuple:
    """Parametrized fixture for command sudo requirement tests."""
    return request.param
