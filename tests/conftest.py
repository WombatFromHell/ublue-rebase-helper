import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from urh import (  # noqa: E402
    CommandType,
    ContainerURLsConfig,
    DeploymentInfo,
    ListItem,
    MenuItem,
    RepositoryConfig,
    SettingsConfig,
    TagContext,
    URHConfig,
)

# ============================================================================
# COMMON TEST DATA
# ============================================================================

SAMPLE_STATUS_OUTPUT = """State: idle
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
"""

SAMPLE_STATUS_OUTPUT_WITH_PINNED = """State: idle
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

SAMPLE_TAGS_DATA = {
    "tags": [
        "latest",
        "testing",
        "stable",
        "unstable",
        "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890.sig",
        "testing-42.20231115.0",
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

SAMPLE_CONFIG_DATA = {
    "repository": [
        {
            "name": "ublue-os/bazzite",
            "include_sha256_tags": False,
            "filter_patterns": [
                r"^sha256-.*\.sig$",
                r"^sha256-.*",
                r"^sha256:.*",
                r"^[0-9a-fA-F]{40,64}$",
                r"^<.*>$",
                r"^(latest|testing|stable|unstable)$",
                r"^testing\..*",
                r"^stable\..*",
                r"^unstable\..*",
                r"^\d{1,2}$",
                r"^(latest|testing|stable|unstable)-\d{1,2}$",
                r"^\d{1,2}-(testing|stable|unstable)$",
            ],
            "ignore_tags": ["latest", "testing", "stable", "unstable"],
        },
        {
            "name": "wombatfromhell/bazzite-nix",
            "include_sha256_tags": False,
            "filter_patterns": [
                r"^sha256-.*\.sig$",
                r"^sha256-.*",
                r"^sha256:.*",
                r"^[0-9a-fA-F]{40,64}$",
                r"^<.*>$",
                r"^(latest|testing|stable|unstable)$",
                r"^testing\..*",
                r"^stable\..*",
                r"^unstable\..*",
                r"^\d{1,2}$",
                r"^(latest|testing|stable|unstable)-\d{1,2}$",
                r"^\d{1,2}-(testing|stable|unstable)$",
            ],
            "ignore_tags": ["latest", "testing", "stable", "unstable"],
        },
        {
            "name": "astrovm/amyos",
            "include_sha256_tags": False,
            "filter_patterns": [
                r"^sha256-.*\.sig$",
                r"^<.*>$",
                r"^(testing|stable|unstable)$",
                r"^testing\..*",
                r"^stable\..*",
                r"^unstable\..*",
                r"^\d{1,2}$",
                r"^(latest|testing|stable|unstable)-\d{1,2}$",
                r"^\d{1,2}-(testing|stable|unstable)$",
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
            "ghcr.io/ublue-os/bazzite:testing",
            "ghcr.io/ublue-os/bazzite:unstable",
            "ghcr.io/astrovm/amyos:latest",
        ],
    },
    "settings": {
        "max_tags_display": 30,
        "debug_mode": False,
    },
}

# ============================================================================
# BASIC MOCKING FIXTURES
# ============================================================================


@pytest.fixture
def mock_is_tty_true(mocker):
    """Mock os.isatty to return True."""
    return mocker.patch("os.isatty", return_value=True)


@pytest.fixture
def mock_is_tty_false(mocker):
    """Mock os.isatty to return False."""
    return mocker.patch("os.isatty", return_value=False)


@pytest.fixture
def mock_subprocess_result():
    """Factory fixture for creating mock subprocess results."""

    def _factory(returncode=0, stdout="", stderr=""):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        mock_result.stderr = stderr
        return mock_result

    return _factory


@pytest.fixture
def mock_subprocess_run_success(mocker, mock_subprocess_result):
    """Mock subprocess.run to return a successful result."""
    mock_result = mock_subprocess_result(returncode=0)
    return mocker.patch("subprocess.run", return_value=mock_result)


@pytest.fixture
def mock_subprocess_run_failure(mocker, mock_subprocess_result):
    """Mock subprocess.run to return a failure result."""
    mock_result = mock_subprocess_result(returncode=1)
    return mocker.patch("subprocess.run", return_value=mock_result)


@pytest.fixture
def mock_subprocess_run_not_found(mocker):
    """Mock subprocess.run to raise FileNotFoundError."""
    return mocker.patch("subprocess.run", side_effect=FileNotFoundError)


@pytest.fixture
def mock_print(mocker):
    """Mock the print function."""
    return mocker.patch("builtins.print")


@pytest.fixture
def mock_sys_exit(mocker):
    """Mock sys.exit to prevent actual exit."""
    return mocker.patch("sys.exit")


@pytest.fixture
def mock_sys_argv(mocker):
    """Factory fixture for mocking sys.argv."""

    def _factory(args=None):
        if args is None:
            args = ["urh.py"]
        return mocker.patch("sys.argv", args)

    return _factory


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================


@pytest.fixture
def sample_config():
    """Provide a sample URHConfig object."""
    config = URHConfig()

    # Add repository configurations
    config.repositories["ublue-os/bazzite"] = RepositoryConfig(
        include_sha256_tags=False,
        filter_patterns=[
            r"^sha256-.*\.sig$",
            r"^sha256-.*",
            r"^sha256:.*",
            r"^[0-9a-fA-F]{40,64}$",
            r"^<.*>$",
            r"^(latest|testing|stable|unstable)$",
            r"^testing\..*",
            r"^stable\..*",
            r"^unstable\..*",
            r"^\d{1,2}$",
            r"^(latest|testing|stable|unstable)-\d{1,2}$",
            r"^\d{1,2}-(testing|stable|unstable)$",
        ],
        ignore_tags=["latest", "testing", "stable", "unstable"],
    )

    config.repositories["wombatfromhell/bazzite-nix"] = RepositoryConfig(
        include_sha256_tags=False,
        filter_patterns=[
            r"^sha256-.*\.sig$",
            r"^sha256-.*",
            r"^sha256:.*",
            r"^[0-9a-fA-F]{40,64}$",
            r"^<.*>$",
            r"^(latest|testing|stable|unstable)$",
            r"^testing\..*",
            r"^stable\..*",
            r"^unstable\..*",
            r"^\d{1,2}$",
            r"^(latest|testing|stable|unstable)-\d{1,2}$",
            r"^\d{1,2}-(testing|stable|unstable)$",
        ],
        ignore_tags=["latest", "testing", "stable", "unstable"],
    )

    config.repositories["astrovm/amyos"] = RepositoryConfig(
        include_sha256_tags=False,
        filter_patterns=[
            r"^sha256-.*\.sig$",
            r"^<.*>$",
            r"^(testing|stable|unstable)$",
            r"^testing\..*",
            r"^stable\..*",
            r"^unstable\..*",
            r"^\d{1,2}$",
            r"^(latest|testing|stable|unstable)-\d{1,2}$",
            r"^\d{1,2}-(testing|stable|unstable)$",
        ],
        ignore_tags=["testing", "stable", "unstable"],
        transform_patterns=[{"pattern": r"^latest\.(\d{8})$", "replacement": r"\1"}],
        latest_dot_handling="transform_dates_only",
    )

    # Set container URLs
    config.container_urls = ContainerURLsConfig(
        default="ghcr.io/wombatfromhell/bazzite-nix:testing",
        options=[
            "ghcr.io/wombatfromhell/bazzite-nix:testing",
            "ghcr.io/wombatfromhell/bazzite-nix:stable",
            "ghcr.io/ublue-os/bazzite:stable",
            "ghcr.io/ublue-os/bazzite:testing",
            "ghcr.io/ublue-os/bazzite:unstable",
            "ghcr.io/astrovm/amyos:latest",
        ],
    )

    # Set settings
    config.settings = SettingsConfig(
        max_tags_display=30,
        debug_mode=False,
    )

    return config


@pytest.fixture
def mock_config_manager(mocker):
    """Mock ConfigManager for testing."""
    mock_manager = MagicMock()
    mock_config = MagicMock()
    mock_manager.load_config.return_value = mock_config
    return mocker.patch("urh._config_manager", mock_manager)


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""

    # Create TOML content manually since we don't want to add tomli_w as dependency just for tests
    toml_content = "# Test configuration file\n"

    # Add repositories section
    for repo_data in SAMPLE_CONFIG_DATA["repository"]:
        toml_content += "[[repository]]\n"
        toml_content += f'name = "{repo_data["name"]}"\n'
        toml_content += (
            f"include_sha256_tags = {str(repo_data['include_sha256_tags']).lower()}\n"
        )

        # Add filter_patterns
        toml_content += "filter_patterns = [\n"
        for pattern in repo_data["filter_patterns"]:
            toml_content += f'    "{pattern}",\n'
        toml_content += "]\n"

        # Add ignore_tags
        toml_content += "ignore_tags = [\n"
        for tag in repo_data["ignore_tags"]:
            toml_content += f'    "{tag}",\n'
        toml_content += "]\n"

        # Add transform_patterns if present
        if "transform_patterns" in repo_data and repo_data["transform_patterns"]:
            toml_content += "transform_patterns = [\n"
            for transform in repo_data["transform_patterns"]:
                toml_content += f'    {{ pattern = "{transform["pattern"]}", replacement = "{transform["replacement"]}" }},\n'
            toml_content += "]\n"

        # Add latest_dot_handling if present
        if "latest_dot_handling" in repo_data and repo_data["latest_dot_handling"]:
            toml_content += (
                f'latest_dot_handling = "{repo_data["latest_dot_handling"]}"\n'
            )

        toml_content += "\n"

    # Add container_urls section
    toml_content += "[container_urls]\n"
    toml_content += f'default = "{SAMPLE_CONFIG_DATA["container_urls"]["default"]}"\n'
    toml_content += "options = [\n"
    for option in SAMPLE_CONFIG_DATA["container_urls"]["options"]:
        toml_content += f'    "{option}",\n'
    toml_content += "]\n\n"

    # Add settings section
    toml_content += "[settings]\n"
    toml_content += (
        f"max_tags_display = {SAMPLE_CONFIG_DATA['settings']['max_tags_display']}\n"
    )
    toml_content += (
        f"debug_mode = {str(SAMPLE_CONFIG_DATA['settings']['debug_mode']).lower()}\n"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        config_path = f.name

    yield Path(config_path)

    # Cleanup
    try:
        os.unlink(config_path)
    except FileNotFoundError:
        pass


# ============================================================================
# DEPLOYMENT FIXTURES
# ============================================================================


@pytest.fixture
def sample_deployment_info():
    """Provide sample deployment information."""
    return [
        DeploymentInfo(
            deployment_index=0,
            is_current=True,
            repository="bazzite-nix",
            version="42.20231115.0",
            is_pinned=False,
        ),
        DeploymentInfo(
            deployment_index=1,
            is_current=False,
            repository="bazzite-nix",
            version="41.20231110.0",
            is_pinned=False,
        ),
    ]


@pytest.fixture
def sample_deployment_info_with_pinned():
    """Provide sample deployment information with pinned deployment."""
    return [
        DeploymentInfo(
            deployment_index=0,
            is_current=True,
            repository="bazzite-nix",
            version="42.20231115.0",
            is_pinned=False,
        ),
        DeploymentInfo(
            deployment_index=1,
            is_current=False,
            repository="bazzite-nix",
            version="41.20231110.0",
            is_pinned=True,
        ),
    ]


@pytest.fixture
def mock_get_deployment_info(mocker):
    """Mock get_deployment_info function."""
    return mocker.patch("urh.get_deployment_info")


@pytest.fixture
def mock_get_current_deployment_info(mocker):
    """Mock get_current_deployment_info function."""
    return mocker.patch("urh.get_current_deployment_info")


@pytest.fixture
def mock_get_status_output(mocker):
    """Mock get_status_output function."""
    return mocker.patch("urh.get_status_output")


# ============================================================================
# MENU SYSTEM FIXTURES
# ============================================================================


@pytest.fixture
def sample_menu_items():
    """Provide sample menu items."""
    return [
        MenuItem("1", "Option 1", "value1"),
        MenuItem("2", "Option 2", "value2"),
        MenuItem("3", "Option 3", "value3"),
    ]


@pytest.fixture
def sample_list_items():
    """Provide sample list items."""
    return [
        ListItem("", "Item 1", "item1"),
        ListItem("", "Item 2", "item2"),
        ListItem("", "Item 3", "item3"),
    ]


@pytest.fixture
def mock_menu_system(mocker):
    """Mock MenuSystem for testing."""
    mock_system = MagicMock()
    return mocker.patch("urh._menu_system", mock_system)


@pytest.fixture
def mock_menu_system_show_menu(mocker):
    """Mock MenuSystem.show_menu method."""
    return mocker.patch("urh.MenuSystem.show_menu")


# ============================================================================
# OCI CLIENT FIXTURES
# ============================================================================


@pytest.fixture
def mock_oci_token_manager(mocker):
    """Mock OCITokenManager for testing."""
    mock_manager = MagicMock()
    mock_manager.get_token.return_value = "test_token"
    return mocker.patch("urh.OCITokenManager", return_value=mock_manager)


@pytest.fixture
def mock_oci_client(mocker):
    """Mock OCIClient for testing."""
    mock_client = MagicMock()
    mock_client.get_all_tags.return_value = SAMPLE_TAGS_DATA
    mock_client.fetch_repository_tags.return_value = {"tags": ["tag1", "tag2"]}
    return mocker.patch("urh.OCIClient", return_value=mock_client)


@pytest.fixture
def mock_urlopen(mocker):
    """Mock urllib.request.urlopen for testing."""
    mock_response = MagicMock()
    mock_response.read.return_value.decode.return_value = json.dumps(
        {"token": "test_token"}
    )
    mock_response.headers = {}
    return mocker.patch("urllib.request.urlopen", return_value=mock_response)


@pytest.fixture
def mock_urlopen_with_pagination(mocker):
    """Mock urllib.request.urlopen with pagination for testing."""
    # First response
    mock_response1 = MagicMock()
    mock_response1.read.return_value.decode.return_value = json.dumps(
        {"tags": ["tag1", "tag2"]}
    )
    mock_response1.headers = {
        "Link": '</v2/test/repo/tags/list?last=tag2&n=200>; rel="next"'
    }

    # Second response
    mock_response2 = MagicMock()
    mock_response2.read.return_value.decode.return_value = json.dumps(
        {"tags": ["tag3", "tag4"]}
    )
    mock_response2.headers = {}

    return mocker.patch(
        "urllib.request.urlopen", side_effect=[mock_response1, mock_response2]
    )


# ============================================================================
# COMMAND REGISTRY FIXTURES
# ============================================================================


@pytest.fixture
def mock_command_registry(mocker):
    """Mock CommandRegistry for testing."""
    mock_registry = MagicMock()
    mock_command = MagicMock()
    mock_registry.get_command.return_value = mock_command
    return mocker.patch("urh.CommandRegistry", return_value=mock_registry)


@pytest.fixture
def mock_run_command(mocker):
    """Mock run_command function."""
    return mocker.patch("urh.run_command")


# ============================================================================
# UTILITY FIXTURES
# ============================================================================


@pytest.fixture
def mock_extract_repository_from_url(mocker):
    """Mock extract_repository_from_url function."""
    return mocker.patch("urh.extract_repository_from_url")


@pytest.fixture
def mock_extract_context_from_url(mocker):
    """Mock extract_context_from_url function."""
    return mocker.patch("urh.extract_context_from_url")


@pytest.fixture
def temp_cache_file():
    """Create a temporary cache file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        cache_path = f.name

    yield cache_path

    # Cleanup
    try:
        os.unlink(cache_path)
    except FileNotFoundError:
        pass


# ============================================================================
# PARAMETRIZED TEST DATA
# ============================================================================


@pytest.fixture(
    params=[
        ("ghcr.io/user/repo:tag", "user/repo"),
        ("docker.io/user/repo:tag", "user/repo"),
        ("quay.io/user/repo:tag", "user/repo"),
        ("gcr.io/user/repo:tag", "user/repo"),
        ("user/repo:tag", "user/repo"),
        ("ghcr.io/user/repo", "user/repo"),
        ("user/repo", "user/repo"),
    ]
)
def repository_url_params(request):
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
def context_url_params(request):
    """Parametrized fixture for context URL extraction tests."""
    return request.param


@pytest.fixture(
    params=[
        CommandType.CHECK,
        CommandType.LS,
        CommandType.PIN,
        CommandType.REBASE,
        CommandType.REMOTE_LS,
        CommandType.RM,
        CommandType.ROLLBACK,
        CommandType.UNPIN,
        CommandType.UPGRADE,
    ]
)
def command_type_params(request):
    """Parametrized fixture for command type tests."""
    return request.param


@pytest.fixture(
    params=[
        TagContext.TESTING,
        TagContext.STABLE,
        TagContext.UNSTABLE,
        TagContext.LATEST,
    ]
)
def tag_context_params(request):
    """Parametrized fixture for tag context tests."""
    return request.param


# ============================================================================
# PYTEST HOOKS AND CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test file location."""
    for item in items:
        # Add markers based on file location
        if "test_units.py" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "test_integrations.py" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "test_e2e.py" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Add markers based on test names
        if "slow" in item.name.lower():
            item.add_marker(pytest.mark.slow)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


@pytest.fixture
def create_mock_deployment_info():
    """Factory fixture for creating mock deployment info."""

    def _factory(
        deployment_index: int = 0,
        is_current: bool = False,
        repository: str = "test-repo",
        version: str = "v1.0.0",
        is_pinned: bool = False,
    ) -> DeploymentInfo:
        return DeploymentInfo(
            deployment_index=deployment_index,
            is_current=is_current,
            repository=repository,
            version=version,
            is_pinned=is_pinned,
        )

    return _factory


@pytest.fixture
def create_mock_menu_item():
    """Factory fixture for creating mock menu items."""

    def _factory(
        key: str = "1",
        description: str = "Test Item",
        value: Any = "test_value",
    ) -> MenuItem:
        return MenuItem(key=key, description=description, value=value)

    return _factory


@pytest.fixture
def create_mock_list_item():
    """Factory fixture for creating mock list items."""

    def _factory(
        key: str = "",
        description: str = "Test Item",
        value: Any = "test_value",
    ) -> ListItem:
        return ListItem(key=key, description=description, value=value)

    return _factory


@pytest.fixture
def create_mock_repository_config():
    """Factory fixture for creating mock repository configs."""

    def _factory(
        name: str = "test/repo",
        include_sha256_tags: bool = False,
        filter_patterns: Optional[List[str]] = None,
        ignore_tags: Optional[List[str]] = None,
        transform_patterns: Optional[List[Dict[str, str]]] = None,
        latest_dot_handling: Optional[str] = None,
    ) -> RepositoryConfig:
        actual_filter_patterns = filter_patterns if filter_patterns is not None else []
        actual_ignore_tags = ignore_tags if ignore_tags is not None else []
        actual_transform_patterns = (
            transform_patterns if transform_patterns is not None else []
        )

        return RepositoryConfig(
            include_sha256_tags=include_sha256_tags,
            filter_patterns=actual_filter_patterns,
            ignore_tags=actual_ignore_tags,
            transform_patterns=actual_transform_patterns,
            latest_dot_handling=latest_dot_handling,
        )

    return _factory
