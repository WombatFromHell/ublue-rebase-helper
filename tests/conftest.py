"""
Centralized fixtures and dependency injection helpers for test suite.

This module provides session, module, and function-scoped fixtures for:
- Precomputed test data (config, tags, deployments)
- Mocked external dependencies (subprocess, network, file I/O)
- Dependency injection helpers for testable source code
"""

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest
from pytest_mock import MockerFixture

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.urh.commands import CommandRegistry  # noqa: E402
from src.urh.config import ContainerURLsConfig, URHConfig  # noqa: E402
from src.urh.deployment import DeploymentInfo  # noqa: E402

# =============================================================================
# SESSION-SCOPED FIXTURES (expensive, reusable across all tests)
# =============================================================================


@pytest.fixture(scope="session")
def sample_config_data() -> Dict[str, Any]:
    """
    Precomputed sample configuration data.

    Use this fixture when you need consistent config data across tests.
    Avoid modifying the returned data to maintain test isolation.
    """
    return {
        "repository": [
            {
                "name": "ublue-os/bazzite",
                "include_sha256_tags": False,
                "filter_patterns": [
                    r"^sha256-.*\.sig$",
                    r"^sha256-.*",
                    r"^(latest|testing|stable|unstable)$",
                ],
                "ignore_tags": ["latest", "testing", "stable", "unstable"],
            },
            {
                "name": "astrovm/amyos",
                "include_sha256_tags": False,
                "filter_patterns": [
                    r"^sha256-.*\.sig$",
                    r"^(testing|stable|unstable)$",
                ],
                "ignore_tags": ["testing", "stable", "unstable"],
                "transform_patterns": [
                    {"pattern": r"^latest\.(\d{8})$", "replacement": r"\1"}
                ],
                "latest_dot_handling": "transform_dates_only",
            },
        ],
        "container_urls": {
            "default": "ghcr.io/wombatfromhell/bazzite-nix:testing",
            "options": [
                "ghcr.io/wombatfromhell/bazzite-nix:testing",
                "ghcr.io/wombatfromhell/bazzite-nix:stable",
                "ghcr.io/ublue-os/bazzite:stable",
                "ghcr.io/astrovm/amyos:latest",
            ],
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
    """
    return {
        "tags": [
            "latest",
            "testing",
            "stable",
            "unstable",
            "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890.sig",
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
def mock_subprocess_run(mocker: MockerFixture) -> Any:
    """
    Mock subprocess.run with configurable return value.

    Usage:
        def test_something(mock_subprocess_run):
            mock_subprocess_run(returncode=0, stdout="output")
    """

    def _factory(returncode: int = 0, stdout: str = "", stderr: str = "") -> Any:
        mock_result = mocker.MagicMock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        mock_result.stderr = stderr
        return mocker.patch("subprocess.run", return_value=mock_result)

    return _factory


@pytest.fixture
def mock_curl_response(mocker: MockerFixture) -> Any:
    """
    Mock curl response for OCI registry calls.

    Usage:
        def test_fetch_tags(mock_curl_response):
            mock_curl_response(tags=["v1.0", "v2.0"])
    """

    def _factory(
        tags: Optional[List[str]] = None,
        link_header: Optional[str] = None,
        status_code: int = 200,
    ) -> Any:
        tags = tags or []
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0

        # Build response with optional headers
        response_body = json.dumps({"tags": tags})
        if link_header:
            mock_result.stdout = (
                f"HTTP/2 {status_code}\r\nLink: {link_header}\r\n\r\n{response_body}"
            )
        else:
            mock_result.stdout = response_body

        return mocker.patch("subprocess.run", return_value=mock_result)

    return _factory


@pytest.fixture
def mock_get_config(mocker: MockerFixture) -> Any:
    """
    Mock get_config to return a test configuration.

    Usage:
        def test_command(mock_get_config):
            config = mock_get_config(options=["ghcr.io/test/repo:tag"])
    """

    def _factory(
        options: Optional[List[str]] = None,
        default: str = "ghcr.io/test/repo:testing",
    ) -> URHConfig:
        config = URHConfig()
        config.container_urls = ContainerURLsConfig(
            default=default,
            options=options or ["ghcr.io/test/repo:testing"],
        )
        return mocker.patch("src.urh.config.get_config", return_value=config)

    return _factory


@pytest.fixture
def mock_menu_show(mocker: MockerFixture) -> Any:
    """
    Mock MenuSystem.show_menu to return a predefined selection.

    Usage:
        def test_submenu(mock_menu_show):
            mock_menu_show(return_value="ghcr.io/test/repo:stable")
    """

    def _factory(return_value: Any = "test_selection") -> Any:
        return mocker.patch(
            "src.urh.menu.MenuSystem.show_menu", return_value=return_value
        )

    return _factory


@pytest.fixture
def mock_deployment_info(mocker: MockerFixture) -> Any:
    """
    Mock deployment info functions.

    Usage:
        def test_pin_command(mock_deployment_info):
            mock_deployment_info(
                current={"repository": "test", "version": "1.0"},
                deployments=[DeploymentInfo(...)]
            )
    """

    def _factory(
        current: Optional[Dict[str, str]] = None,
        deployments: Optional[List[DeploymentInfo]] = None,
    ) -> Dict[str, Any]:
        current = current or {"repository": "test-repo", "version": "1.0.0"}
        deployments = deployments or []

        mocks = {
            "get_current": mocker.patch(
                "src.urh.deployment.get_current_deployment_info", return_value=current
            ),
            "get_deployments": mocker.patch(
                "src.urh.deployment.get_deployment_info", return_value=deployments
            ),
            "format_header": mocker.patch(
                "src.urh.deployment.format_deployment_header",
                return_value=f"Current deployment: {current['repository']} ({current['version']})",
            ),
        }
        return mocks

    return _factory


@pytest.fixture
def mock_sys_exit(mocker: MockerFixture) -> Any:
    """
    Mock sys.exit to prevent actual exit during tests.

    Usage:
        def test_exits_on_error(mock_sys_exit):
            # Test code that calls sys.exit()
            mock_sys_exit.assert_called_once_with(1)
    """
    return mocker.patch("sys.exit")


@pytest.fixture
def mock_print(mocker: MockerFixture) -> Any:
    """
    Mock print to capture output during tests.

    Usage:
        def test_prints_message(mock_print):
            # Test code that calls print()
            mock_print.assert_called_once_with("expected message")
    """
    return mocker.patch("builtins.print")


@pytest.fixture
def temp_config_file(
    mocker: MockerFixture, tmp_path: Path
) -> Callable[[Optional[str]], Path]:
    """
    Create a temporary config file for testing.

    Usage:
        def test_load_config(temp_config_file):
            config_path = temp_config_file(content="[settings]\nmax_tags_display = 50")
    """

    def _factory(content: Optional[str] = None) -> Path:
        content = (
            content
            or """
[container_urls]
default = "ghcr.io/test/repo:testing"
options = ["ghcr.io/test/repo:testing"]

[settings]
max_tags_display = 30
debug_mode = false
"""
        )
        config_path = tmp_path / "urh.toml"
        config_path.write_text(content)
        return config_path

    return _factory


# =============================================================================
# DEPENDENCY INJECTION HELPERS (Protocol classes and factories)
# =============================================================================


# Protocol definitions for type hints (Python 3.11+ uses typing.Protocol)
try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol


class TokenProvider(Protocol):
    """Protocol for injectable token providers."""

    def get_token(self) -> Optional[str]: ...

    def invalidate_cache(self) -> None: ...


class HTTPClient(Protocol):
    """Protocol for injectable HTTP clients."""

    def get(self, url: str, headers: Dict[str, str]) -> Any: ...


class MenuProvider(Protocol):
    """Protocol for injectable menu providers."""

    def show_menu(
        self,
        items: Any,
        header: str,
        persistent_header: Optional[str] = None,
        is_main_menu: bool = False,
    ) -> Optional[Any]: ...


class FileReader(Protocol):
    """Protocol for injectable file readers."""

    def read_toml(self, path: Path) -> Dict[str, Any]: ...

    def write_toml(self, path: Path, data: Dict[str, Any]) -> None: ...


@pytest.fixture
def mock_token_provider(mocker: MockerFixture) -> TokenProvider:
    """
    Create a mock TokenProvider for dependency injection.

    Usage:
        def test_with_injected_token(mock_token_provider):
            mock_token_provider.get_token.return_value = "injected_token"
            client = OCIClient("test/repo", token_manager=mock_token_provider)
    """
    mock = mocker.MagicMock()
    mock.get_token.return_value = "injected_test_token"
    mock.invalidate_cache = mocker.MagicMock()
    return mock


@pytest.fixture
def mock_http_client(mocker: MockerFixture) -> HTTPClient:
    """
    Create a mock HTTPClient for dependency injection.

    Usage:
        def test_with_injected_http(mock_http_client):
            mock_http_client.get.return_value = {"tags": [...]}
            # Use with refactored OCIClient that accepts http_client
    """
    mock = mocker.MagicMock()
    mock.get.return_value = {"tags": ["tag1", "tag2"]}
    return mock


@pytest.fixture
def mock_menu_provider(mocker: MockerFixture) -> MenuProvider:
    """
    Create a mock MenuProvider for dependency injection.

    Usage:
        def test_with_injected_menu(mock_menu_provider):
            mock_menu_provider.show_menu.return_value = "selected"
            registry = CommandRegistry(menu_system=mock_menu_provider)
    """
    mock = mocker.MagicMock()
    mock.show_menu.return_value = "injected_selection"
    return mock


@pytest.fixture
def mock_file_reader(mocker: MockerFixture) -> FileReader:
    """
    Create a mock FileReader for dependency injection.

    Usage:
        def test_with_injected_file_reader(mock_file_reader):
            mock_file_reader.read_toml.return_value = {...}
            manager = ConfigManager(file_reader=mock_file_reader)
    """
    mock = mocker.MagicMock()

    def _read_toml(path: Path) -> Dict[str, Any]:
        # For testing, just return predefined data
        return {
            "container_urls": {
                "default": "ghcr.io/test/repo:testing",
                "options": ["ghcr.io/test/repo:testing"],
            },
            "settings": {"max_tags_display": 30, "debug_mode": False},
        }

    mock.read_toml.side_effect = _read_toml
    mock.write_toml = mocker.MagicMock()
    return mock


# =============================================================================
# PARAMETRIZED TEST DATA FIXTURES
# =============================================================================


@pytest.fixture(
    params=[
        ("ghcr.io/user/repo:tag", "user/repo"),
        ("docker.io/user/repo:tag", "user/repo"),
        ("quay.io/user/repo:tag", "user/repo"),
        ("user/repo:tag", "user/repo"),
        ("ghcr.io/user/repo", "user/repo"),
    ]
)
def repository_url_params(request: Any) -> tuple:
    """Parametrized fixture for repository URL extraction tests."""
    return request.param


@pytest.fixture(
    params=[
        ("ghcr.io/user/repo:testing", "testing"),
        ("ghcr.io/user/repo:stable", "stable"),
        ("ghcr.io/user/repo:unstable", "unstable"),
        ("ghcr.io/user/repo:latest", "latest"),
        ("ghcr.io/user/repo:v1.0.0", None),
        ("ghcr.io/user/repo", None),
    ]
)
def context_url_params(request: Any) -> tuple:
    """Parametrized fixture for context URL extraction tests."""
    return request.param


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
