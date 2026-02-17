"""
Integration tests for configuration system.

Tests the ConfigManager and URHConfig classes, including:
- TOML loading and validation
- Default config generation
- Repository-specific filter rules
- Settings validation
- Container URLs configuration

These tests focus on module-level integration between ConfigManager,
URHConfig, and their dependencies (file I/O, TOML parsing).
"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from src.urh.config import (
    ConfigManager,
    ContainerURLsConfig,
    RepositoryConfig,
    SettingsConfig,
    URHConfig,
    get_config,
)


class TestURHConfigDefaults:
    """Test URHConfig default configuration."""

    def test_get_default_creates_valid_config(self) -> None:
        """Test that get_default returns a properly initialized config."""
        config = URHConfig.get_default()

        assert isinstance(config, URHConfig)
        assert len(config.repositories) > 0
        assert isinstance(config.container_urls, ContainerURLsConfig)
        assert isinstance(config.settings, SettingsConfig)

    def test_default_has_standard_repositories(self) -> None:
        """Test that default config includes standard repositories."""
        config = URHConfig.get_default()

        standard_repos = [
            "ublue-os/bazzite",
            "ublue-os/bazzite-nvidia-open",
            "wombatfromhell/bazzite-nix",
            "wombatfromhell/bazzite-nvidia-open-nix",
        ]

        for repo_name in standard_repos:
            assert repo_name in config.repositories
            repo_config = config.repositories[repo_name]
            assert isinstance(repo_config, RepositoryConfig)
            assert not repo_config.include_sha256_tags

    def test_default_has_amyos_repository(self) -> None:
        """Test that default config includes astrovm/amyos with special config."""
        config = URHConfig.get_default()

        assert "astrovm/amyos" in config.repositories
        amyos_config = config.repositories["astrovm/amyos"]

        assert not amyos_config.include_sha256_tags
        assert amyos_config.latest_dot_handling == "transform_dates_only"
        assert len(amyos_config.transform_patterns) > 0

    def test_default_container_urls(self) -> None:
        """Test that default config has container URLs configured."""
        config = URHConfig.get_default()

        assert config.container_urls.default.startswith("ghcr.io/")
        assert len(config.container_urls.options) > 0
        assert config.container_urls.default in config.container_urls.options

    def test_default_settings(self) -> None:
        """Test that default settings are properly initialized."""
        config = URHConfig.get_default()

        assert config.settings.max_tags_display > 0
        assert config.settings.max_tags_display <= 1000
        assert isinstance(config.settings.debug_mode, bool)


class TestRepositoryConfigValidation:
    """Test RepositoryConfig validation logic."""

    def test_valid_filter_patterns(self) -> None:
        """Test that valid regex patterns are accepted."""
        config = RepositoryConfig(
            filter_patterns=[r"^test.*", r"^[0-9]+$", r"^(foo|bar)$"]
        )
        assert len(config.filter_patterns) == 3

    def test_invalid_filter_pattern_raises_error(self) -> None:
        """Test that invalid regex patterns raise ValueError."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            RepositoryConfig(filter_patterns=[r"[invalid(regex"])

    def test_valid_transform_patterns(self) -> None:
        """Test that valid transform patterns are accepted."""
        config = RepositoryConfig(
            transform_patterns=[{"pattern": r"^latest\.(\d+)$", "replacement": r"\1"}]
        )
        assert len(config.transform_patterns) == 1

    def test_invalid_transform_pattern_missing_keys(self) -> None:
        """Test that transform patterns with missing keys raise ValueError."""
        with pytest.raises(
            ValueError, match="must have 'pattern' and 'replacement' keys"
        ):
            RepositoryConfig(transform_patterns=[{"pattern": r"test"}])

    def test_invalid_transform_pattern_regex(self) -> None:
        """Test that invalid regex in transform patterns raises ValueError."""
        with pytest.raises(ValueError, match="Invalid regex in transform pattern"):
            RepositoryConfig(
                transform_patterns=[{"pattern": r"[invalid", "replacement": "test"}]
            )

    def test_valid_latest_dot_handling(self) -> None:
        """Test that valid latest_dot_handling values are accepted."""
        config_none = RepositoryConfig(latest_dot_handling=None)
        assert config_none.latest_dot_handling is None

        config_transform = RepositoryConfig(latest_dot_handling="transform_dates_only")
        assert config_transform.latest_dot_handling == "transform_dates_only"

    def test_invalid_latest_dot_handling_raises_error(self) -> None:
        """Test that invalid latest_dot_handling raises ValueError."""
        with pytest.raises(ValueError, match="latest_dot_handling must be one of"):
            RepositoryConfig(latest_dot_handling="invalid_value")


class TestSettingsConfigValidation:
    """Test SettingsConfig validation logic."""

    def test_valid_max_tags_display(self) -> None:
        """Test that valid max_tags_display values are accepted."""
        config = SettingsConfig(max_tags_display=50)
        assert config.max_tags_display == 50

    def test_max_tags_display_too_low(self) -> None:
        """Test that max_tags_display <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="max_tags_display must be positive"):
            SettingsConfig(max_tags_display=0)

        with pytest.raises(ValueError, match="max_tags_display must be positive"):
            SettingsConfig(max_tags_display=-1)

    def test_max_tags_display_too_high(self) -> None:
        """Test that max_tags_display > 1000 raises ValueError."""
        with pytest.raises(ValueError, match="max_tags_display too large"):
            SettingsConfig(max_tags_display=1001)

    def test_default_max_tags_display(self) -> None:
        """Test that default max_tags_display is reasonable."""
        config = SettingsConfig()
        assert 0 < config.max_tags_display <= 1000


class TestConfigManagerLoading:
    """Test ConfigManager config loading functionality."""

    def test_load_config_creates_default_if_missing(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that missing config file triggers default config creation."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        # Mock get_config_path to return temp path
        mocker.patch.object(manager, "get_config_path", return_value=config_path)
        mocker.patch.object(manager, "create_default_config")

        config = manager.load_config()

        assert isinstance(config, URHConfig)
        assert len(config.repositories) > 0

    def test_load_config_parses_valid_toml(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that valid TOML is parsed correctly."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        config_content = """
[container_urls]
default = "ghcr.io/custom/repo:testing"
options = ["ghcr.io/custom/repo:testing", "ghcr.io/custom/repo:stable"]

[settings]
max_tags_display = 50
debug_mode = true
"""
        config_path.write_text(config_content)
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        config = manager.load_config()

        assert config.container_urls.default == "ghcr.io/custom/repo:testing"
        assert len(config.container_urls.options) == 2
        assert config.settings.max_tags_display == 50
        assert config.settings.debug_mode is True

    def test_load_config_handles_invalid_toml_gracefully(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that invalid TOML falls back to default config."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        config_path.write_text("invalid toml content [[[")
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        config = manager.load_config()

        # Should return default config, not raise
        assert isinstance(config, URHConfig)
        assert len(config.repositories) > 0

    def test_load_config_caches_result(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that config is cached after first load."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        config_path.write_text("""
[container_urls]
default = "ghcr.io/test/repo:testing"
""")
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        # First load
        config1 = manager.load_config()

        # Modify file - should still return cached config
        config_path.write_text("""
[container_urls]
default = "ghcr.io/different/repo:stable"
""")

        config2 = manager.load_config()

        # Should be the same cached object
        assert config1 is config2
        assert config1.container_urls.default == "ghcr.io/test/repo:testing"

    def test_get_config_path_uses_xdg_env(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that config path respects XDG_CONFIG_HOME environment variable."""
        manager = ConfigManager()
        xdg_config = tmp_path / "xdg_config"
        xdg_config.mkdir()

        mocker.patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg_config)})

        config_path = manager.get_config_path()

        assert config_path.parent == xdg_config
        assert config_path.name == "urh.toml"

    def test_get_config_path_uses_home_fallback(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that config path falls back to ~/.config when XDG not set."""
        manager = ConfigManager()

        # Remove XDG_CONFIG_HOME if present
        env = {"HOME": str(tmp_path)}
        mocker.patch.dict("os.environ", env, clear=True)

        config_path = manager.get_config_path()

        assert config_path.parent == tmp_path / ".config"
        assert config_path.name == "urh.toml"


class TestConfigParsing:
    """Test config parsing from TOML data."""

    def test_parse_repositories_section(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test parsing repository configurations."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        config_content = """
[[repository]]
name = "custom/repo"
include_sha256_tags = true
filter_patterns = ["^custom.*"]
ignore_tags = ["custom-ignore"]

[[repository]]
name = "another/repo"
include_sha256_tags = false
"""
        config_path.write_text(config_content)
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        config = manager.load_config()

        assert "custom/repo" in config.repositories
        assert "another/repo" in config.repositories

        custom_config = config.repositories["custom/repo"]
        assert custom_config.include_sha256_tags is True
        assert custom_config.filter_patterns == ["^custom.*"]
        assert custom_config.ignore_tags == ["custom-ignore"]

    def test_parse_transform_patterns(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test parsing transform patterns."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        # Note: TOML requires double backslashes for regex patterns
        config_content = """
[[repository]]
name = "transform/repo"
transform_patterns = [
    { pattern = "^v(\\\\d+)$", replacement = "\\\\1" },
    { pattern = "^release-(.*)$", replacement = "\\\\1" }
]
"""
        config_path.write_text(config_content)
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        config = manager.load_config()

        repo_config = config.repositories["transform/repo"]
        assert len(repo_config.transform_patterns) == 2
        assert repo_config.transform_patterns[0]["pattern"] == r"^v(\d+)$"
        assert repo_config.transform_patterns[0]["replacement"] == r"\1"

    def test_parse_container_urls_section(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test parsing container URLs section."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        config_content = """
[container_urls]
default = "ghcr.io/my/repo:custom"
options = [
    "ghcr.io/my/repo:custom",
    "ghcr.io/my/repo:alt"
]
"""
        config_path.write_text(config_content)
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        config = manager.load_config()

        assert config.container_urls.default == "ghcr.io/my/repo:custom"
        assert len(config.container_urls.options) == 2

    def test_parse_settings_section(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test parsing settings section."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        config_content = """
[settings]
max_tags_display = 75
debug_mode = true
"""
        config_path.write_text(config_content)
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        config = manager.load_config()

        assert config.settings.max_tags_display == 75
        assert config.settings.debug_mode is True

    def test_parse_handles_missing_sections(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that missing sections use defaults."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        # Empty config - all sections should use defaults
        config_path.write_text("")
        mocker.patch.object(manager, "get_config_path", return_value=config_path)

        config = manager.load_config()

        # Empty config means no custom repositories (defaults not auto-added)
        # But container_urls and settings should have defaults
        assert isinstance(config.repositories, dict)
        assert isinstance(config.container_urls, ContainerURLsConfig)
        assert isinstance(config.settings, SettingsConfig)
        assert config.settings.max_tags_display == 30


class TestConfigSerialization:
    """Test config serialization to TOML format."""

    def test_serialize_boolean_values(self) -> None:
        """Test boolean serialization."""
        manager = ConfigManager()

        assert manager._serialize_value(True) == "true"
        assert manager._serialize_value(False) == "false"

    def test_serialize_integer_values(self) -> None:
        """Test integer serialization."""
        manager = ConfigManager()

        assert manager._serialize_value(42) == "42"
        assert manager._serialize_value(0) == "0"
        assert manager._serialize_value(-10) == "-10"

    def test_serialize_string_values(self) -> None:
        """Test string serialization with escaping."""
        manager = ConfigManager()

        assert manager._serialize_value("test") == '"test"'
        assert (
            manager._serialize_value("test\\with\\backslash")
            == '"test\\\\with\\\\backslash"'
        )

    def test_serialize_empty_list(self) -> None:
        """Test empty list serialization."""
        manager = ConfigManager()

        assert manager._serialize_value([]) == "[]"

    def test_serialize_list_of_strings(self) -> None:
        """Test list of strings serialization."""
        manager = ConfigManager()

        result = manager._serialize_value(["a", "b", "c"], indent=0)
        assert '"a"' in result
        assert '"b"' in result
        assert '"c"' in result

    def test_serialize_list_of_dicts(self) -> None:
        """Test list of dicts serialization (transform patterns)."""
        manager = ConfigManager()

        data = [{"pattern": "test", "replacement": "repl"}]
        result = manager._serialize_value(data, indent=0)
        assert "pattern" in result
        assert "replacement" in result

    def test_serialize_dict(self) -> None:
        """Test dict serialization."""
        manager = ConfigManager()

        data = {"key1": "value1", "key2": 42}
        result = manager._serialize_value(data, indent=0)
        assert "key1" in result
        assert "key2" in result


class TestCreateDefaultConfig:
    """Test default config file creation."""

    def test_create_default_config_writes_file(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that create_default_config creates a TOML file."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        mocker.patch.object(manager, "get_config_path", return_value=config_path)
        manager.create_default_config()

        assert config_path.exists()
        content = config_path.read_text()
        assert "[container_urls]" in content
        assert "[settings]" in content

    def test_create_default_config_has_standard_repos(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that default config includes standard repositories."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        mocker.patch.object(manager, "get_config_path", return_value=config_path)
        manager.create_default_config()

        content = config_path.read_text()
        assert "ublue-os/bazzite" in content
        assert "wombatfromhell/bazzite-nix" in content

    def test_create_default_config_has_amyos_transform(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that default config includes amyos transform patterns."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        mocker.patch.object(manager, "get_config_path", return_value=config_path)
        manager.create_default_config()

        content = config_path.read_text()
        assert "astrovm/amyos" in content
        assert "transform_patterns" in content
        assert "latest_dot_handling" in content

    def test_created_config_is_loadable(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that created config can be loaded."""
        manager = ConfigManager()
        config_path = tmp_path / "urh.toml"

        mocker.patch.object(manager, "get_config_path", return_value=config_path)
        manager.create_default_config()

        # Clear cache and reload
        manager._config = None
        config = manager.load_config()

        assert isinstance(config, URHConfig)
        assert len(config.repositories) > 0


class TestGlobalGetConfig:
    """Test the global get_config function."""

    def test_get_config_returns_loaded_config(
        self, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Test that get_config uses the global config manager."""
        config_path = tmp_path / "urh.toml"
        config_path.write_text("""
[container_urls]
default = "ghcr.io/global/test:config"
""")

        # Patch the global config manager's get_config_path
        from src.urh import config as config_module

        mocker.patch.object(
            config_module._config_manager, "get_config_path", return_value=config_path
        )

        # Clear any cached config
        config_module._config_manager._config = None

        config = get_config()

        assert isinstance(config, URHConfig)
        assert config.container_urls.default == "ghcr.io/global/test:config"
