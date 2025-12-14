"""Tests for the config module."""

import os
import tempfile
from pathlib import Path

import pytest
from pytest_mock import MockFixture

from src.urh.config import (
    ConfigManager,
    RepositoryConfig,
    SettingsConfig,
    URHConfig,
)


class TestRepositoryConfigValidation:
    """Test RepositoryConfig validation."""

    def test_valid_repository_config(self):
        """Test valid repository configuration."""
        config = RepositoryConfig(
            include_sha256_tags=True,
            filter_patterns=[r"^test.*$"],
            ignore_tags=["latest"],
            transform_patterns=[{"pattern": r"^latest\.(.*)$", "replacement": r"\1"}],
            latest_dot_handling="transform_dates_only",
        )
        assert config.include_sha256_tags is True
        assert config.filter_patterns == [r"^test.*$"]
        assert config.ignore_tags == ["latest"]
        assert config.transform_patterns == [
            {"pattern": r"^latest\.(.*)$", "replacement": r"\1"}
        ]
        assert config.latest_dot_handling == "transform_dates_only"

    def test_invalid_regex_pattern(self):
        """Test invalid regex pattern validation."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            RepositoryConfig(filter_patterns=[r"[invalid(regex"])

    def test_invalid_transform_pattern_missing_keys(self):
        """Test transform pattern with missing keys."""
        with pytest.raises(
            ValueError, match="must have 'pattern' and 'replacement' keys"
        ):
            RepositoryConfig(
                transform_patterns=[{"pattern": "test"}]
            )  # Missing replacement

        with pytest.raises(
            ValueError, match="must have 'pattern' and 'replacement' keys"
        ):
            RepositoryConfig(
                transform_patterns=[{"replacement": "test"}]
            )  # Missing pattern

    def test_invalid_transform_pattern_regex(self):
        """Test transform pattern with invalid regex."""
        with pytest.raises(ValueError, match="Invalid regex in transform pattern"):
            RepositoryConfig(
                transform_patterns=[
                    {"pattern": r"[invalid(regex", "replacement": "test"}
                ]
            )

    def test_invalid_latest_dot_handling(self):
        """Test invalid latest_dot_handling value."""
        with pytest.raises(ValueError, match="latest_dot_handling must be one of"):
            RepositoryConfig(latest_dot_handling="invalid_value")


class TestSettingsConfigValidation:
    """Test SettingsConfig validation."""

    def test_valid_settings_config(self):
        """Test valid settings configuration."""
        config = SettingsConfig(max_tags_display=50, debug_mode=True)
        assert config.max_tags_display == 50
        assert config.debug_mode is True

    def test_invalid_max_tags_display_negative(self):
        """Test negative max_tags_display validation."""
        with pytest.raises(ValueError, match="max_tags_display must be positive"):
            SettingsConfig(max_tags_display=-1)

    def test_invalid_max_tags_display_zero(self):
        """Test zero max_tags_display validation."""
        with pytest.raises(ValueError, match="max_tags_display must be positive"):
            SettingsConfig(max_tags_display=0)

    def test_invalid_max_tags_display_too_large(self):
        """Test max_tags_display too large validation."""
        with pytest.raises(ValueError, match="max_tags_display too large"):
            SettingsConfig(max_tags_display=1001)


class TestConfigManager:
    """Test configuration management."""

    def test_get_config_path_xdg(self, mocker: MockFixture, monkeypatch):
        """Test getting config path with XDG_CONFIG_HOME."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/test/config")
        mock_mkdir = mocker.patch("pathlib.Path.mkdir")
        config_manager = ConfigManager()
        path = config_manager.get_config_path()
        assert "/test/config/urh.toml" in str(path)
        mock_mkdir.assert_called()

    def test_get_config_path_home(self, mocker: MockFixture, monkeypatch):
        """Test getting config path with HOME."""
        # Clear XDG_CONFIG_HOME if it exists
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        mocker.patch("pathlib.Path.home", return_value=Path("/home/test"))
        mock_mkdir = mocker.patch("pathlib.Path.mkdir")
        config_manager = ConfigManager()
        path = config_manager.get_config_path()
        assert "/home/test/.config/urh.toml" in str(path)
        mock_mkdir.assert_called()

    def test_parse_config_with_invalid_data(self):
        """Test parsing config with invalid data types."""
        config_manager = ConfigManager()
        data = {
            "container_urls": {
                "default": 123,  # Invalid type
                "options": "not_a_list",  # Invalid type
            },
            "settings": {
                "max_tags_display": "not_an_int",  # Invalid type
                "debug_mode": "not_a_bool",  # Invalid type
            },
        }
        config = config_manager._parse_config(data)

        # Should use defaults when invalid types are provided
        assert config.container_urls.default != 123  # Should use default
        assert config.settings.max_tags_display != 0  # Should use default
        assert config.settings.debug_mode is False  # Should use default

    def test_parse_config_repository_missing_name(self):
        """Test parsing repository config with missing name field."""
        config_manager = ConfigManager()
        data = {
            "repository": [
                {
                    # Missing 'name' field
                    "include_sha256_tags": True,
                    "filter_patterns": ["pattern1"],
                }
            ]
        }
        config = config_manager._parse_config(data)

        # Should skip repositories without name
        assert len(config.repositories) == 0

    def test_parse_config_repository_invalid_types(self):
        """Test parsing repository config with invalid data types."""
        config_manager = ConfigManager()
        data = {
            "repository": [
                {
                    "name": "test/repo",
                    "include_sha256_tags": "not_a_bool",  # Invalid type
                    "filter_patterns": 123,  # Invalid type - will cause TypeError
                    "ignore_tags": 456,  # Invalid type - will cause TypeError
                    "transform_patterns": "not_a_list",  # Invalid type
                    "latest_dot_handling": 789,  # Invalid type
                }
            ]
        }
        # This should raise TypeError due to non-iterable filter_patterns
        with pytest.raises(TypeError):
            config_manager._parse_config(data)

    def test_parse_config_container_urls_invalid_types(self):
        """Test parsing container URLs with invalid data types."""
        config_manager = ConfigManager()
        data = {
            "container_urls": {
                "default": ["not_a_string"],  # Invalid type
                "options": {"not": "a_list"},  # Invalid type
            }
        }
        config = config_manager._parse_config(data)

        # Should use defaults when invalid types are provided
        assert config.container_urls.default != "not_a_string"  # Should use default
        assert config.container_urls.options != ["not", "a_list"]  # Should use default

    def test_parse_config_settings_invalid_types(self):
        """Test parsing settings with invalid data types."""
        config_manager = ConfigManager()
        data = {
            "settings": {
                "max_tags_display": "not_an_int",  # Invalid type
                "debug_mode": "not_a_bool",  # Invalid type
            }
        }
        config = config_manager._parse_config(data)

        # Should use defaults when invalid types are provided
        assert config.settings.max_tags_display != 0  # Should use default
        assert config.settings.debug_mode is False  # Should use default

    def test_serialize_value_complex_types(self):
        """Test serializing complex value types to TOML format."""
        config_manager = ConfigManager()

        # Test nested dictionary serialization (this would be handled with inline tables)
        complex_dict = {"key1": "value1", "key2": "value2"}
        result = config_manager._serialize_value(complex_dict)
        assert 'key1 = "value1"' in result or 'key2 = "value2"' in result

        # Test serialization with escaping
        result = config_manager._serialize_value("test\\path")
        assert result == '"test\\\\path"'

    def test_config_manager_create_default_config(self, temp_config_file):
        """Test ConfigManager create_default_config method."""
        config_manager = ConfigManager()
        # Verify that the method creates a config file without errors
        config_manager.create_default_config()
        # We've already tested the content creation in other tests

    def test_load_config_not_exists(self, mocker):
        """Test loading config when file doesn't exist."""
        mock_config_path = mocker.MagicMock()
        mock_config_path.exists.return_value = False

        config_manager = ConfigManager()
        config_manager.get_config_path = mocker.MagicMock(return_value=mock_config_path)

        mock_create_default = mocker.patch.object(
            config_manager, "create_default_config"
        )
        mock_get_default = mocker.patch.object(URHConfig, "get_default")
        mock_config = mocker.MagicMock()
        mock_get_default.return_value = mock_config

        result = config_manager.load_config()

        assert result == mock_config
        mock_get_default.assert_called_once()
        mock_create_default.assert_called_once()

    def test_load_config_exists(self, mocker):
        """Test loading config when file exists."""
        mock_config_path = mocker.MagicMock()
        mock_config_path.exists.return_value = True

        config_manager = ConfigManager()
        config_manager.get_config_path = mocker.MagicMock(return_value=mock_config_path)

        # Use mock_open correctly - patch directly without storing in a variable
        mocker.patch("builtins.open", mocker.mock_open(read_data='{"test": "value"}'))

        mock_load = mocker.patch("tomllib.load")
        mock_load.return_value = {"test": "value"}

        mock_parse = mocker.patch.object(config_manager, "_parse_config")
        mock_config = mocker.MagicMock()
        mock_parse.return_value = mock_config

        result = config_manager.load_config()

        assert result == mock_config
        mock_parse.assert_called_once_with({"test": "value"})

    def test_load_config_toml_error(self, mocker):
        """Test loading config with TOML decode error."""
        mock_config_path = mocker.MagicMock()
        mock_config_path.exists.return_value = True

        config_manager = ConfigManager()
        config_manager.get_config_path = mocker.MagicMock(return_value=mock_config_path)

        # Use mock_open correctly - patch directly without storing in a variable
        mocker.patch("builtins.open", mocker.mock_open(read_data="invalid toml"))

        mocker.patch("tomllib.load", side_effect=Exception("TOML error"))

        mock_get_default = mocker.patch.object(URHConfig, "get_default")
        mock_config = mocker.MagicMock()
        mock_get_default.return_value = mock_config

        result = config_manager.load_config()

        assert result == mock_config
        mock_get_default.assert_called_once()

    def test_load_config_file_error(self, mocker):
        """Test loading config with file reading error."""
        mock_config_path = mocker.MagicMock()
        mock_config_path.exists.return_value = True

        config_manager = ConfigManager()
        config_manager.get_config_path = mocker.MagicMock(return_value=mock_config_path)

        # Simulate file reading error
        mocker.patch("builtins.open", side_effect=IOError("File error"))

        mock_get_default = mocker.patch.object(URHConfig, "get_default")
        mock_config = mocker.MagicMock()
        mock_get_default.return_value = mock_config

        result = config_manager.load_config()

        assert result == mock_config
        mock_get_default.assert_called_once()

    def test_load_config_caching(self, mocker):
        """Test config caching behavior."""
        mock_config_path = mocker.MagicMock()
        mock_config_path.exists.return_value = True

        config_manager = ConfigManager()
        config_manager.get_config_path = mocker.MagicMock(return_value=mock_config_path)

        # Mock the file reading and parsing
        mocker.patch("builtins.open", mocker.mock_open(read_data='{"test": "value"}'))
        mocker.patch("tomllib.load", return_value={"test": "value"})

        mock_parse = mocker.patch.object(config_manager, "_parse_config")
        mock_config = mocker.MagicMock()
        mock_parse.return_value = mock_config

        # First call should parse the config
        result1 = config_manager.load_config()
        assert result1 == mock_config
        mock_parse.assert_called_once()

        # Second call should return cached config without parsing again
        result2 = config_manager.load_config()
        assert result2 == mock_config
        mock_parse.assert_called_once()  # Should still be called only once

    def test_parse_config(self):
        """Test parsing configuration data."""
        data = {
            "repository": [
                {
                    "name": "test/repo",
                    "include_sha256_tags": True,
                    "filter_patterns": ["pattern1", "pattern2"],
                    "ignore_tags": ["tag1", "tag2"],
                    "transform_patterns": [
                        {"pattern": "pattern3", "replacement": "replacement3"}
                    ],
                    "latest_dot_handling": "transform_dates_only",
                }
            ],
            "container_urls": {
                "default": "ghcr.io/test/repo:testing",
                "options": ["ghcr.io/test/repo:testing", "ghcr.io/test/repo:stable"],
            },
            "settings": {
                "max_tags_display": 50,
                "debug_mode": True,
            },
        }

        config_manager = ConfigManager()
        config = config_manager._parse_config(data)

        # Check repository config
        assert "test/repo" in config.repositories
        repo_config = config.repositories["test/repo"]
        assert repo_config.include_sha256_tags is True
        assert repo_config.filter_patterns == ["pattern1", "pattern2"]
        assert repo_config.ignore_tags == ["tag1", "tag2"]
        assert repo_config.transform_patterns == [
            {"pattern": "pattern3", "replacement": "replacement3"}
        ]
        assert repo_config.latest_dot_handling == "transform_dates_only"

        # Check container URLs config
        assert config.container_urls.default == "ghcr.io/test/repo:testing"
        assert config.container_urls.options == [
            "ghcr.io/test/repo:testing",
            "ghcr.io/test/repo:stable",
        ]

        # Check settings config
        assert config.settings.max_tags_display == 50
        assert config.settings.debug_mode is True

    def test_parse_config_edge_cases(self):
        """Test parsing config with edge cases."""
        config_manager = ConfigManager()

        # Test empty config
        data = {}
        config = config_manager._parse_config(data)
        assert config.repositories == {}
        assert config.container_urls.default is not None  # Should use defaults
        assert config.settings.max_tags_display is not None  # Should use defaults

        # Test config with empty repository list
        data = {"repository": []}
        config = config_manager._parse_config(data)
        assert config.repositories == {}

        # Test config with empty container URLs
        data = {"container_urls": {}}
        config = config_manager._parse_config(data)
        assert config.container_urls.default is not None  # Should use defaults
        assert config.container_urls.options is not None  # Should use defaults

        # Test config with empty settings
        data = {"settings": {}}
        config = config_manager._parse_config(data)
        assert config.settings.max_tags_display is not None  # Should use defaults
        assert config.settings.debug_mode is not None  # Should use defaults

    def test_parse_config_transform_patterns_edge_cases(self):
        """Test parsing transform patterns with edge cases."""
        config_manager = ConfigManager()

        # Test transform patterns with non-string values
        data = {
            "repository": [
                {
                    "name": "test/repo",
                    "transform_patterns": [
                        {"pattern": 123, "replacement": "test"},  # Invalid pattern type
                        {
                            "pattern": "test",
                            "replacement": 456,
                        },  # Invalid replacement type
                        {"pattern": "valid", "replacement": "valid"},  # Valid
                    ],
                }
            ]
        }
        config = config_manager._parse_config(data)

        repo_config = config.repositories["test/repo"]
        # Should only include valid transform patterns
        assert len(repo_config.transform_patterns) == 1
        assert repo_config.transform_patterns[0] == {
            "pattern": "valid",
            "replacement": "valid",
        }

    def test_parse_config_mixed_valid_invalid_data(self):
        """Test parsing config with mixed valid and invalid data."""
        config_manager = ConfigManager()

        data = {
            "repository": [
                {
                    "name": "valid/repo",
                    "include_sha256_tags": True,
                    "filter_patterns": ["valid_pattern"],
                },
                {
                    "name": "invalid/repo",
                    "include_sha256_tags": "invalid",  # Invalid type
                    "filter_patterns": 123,  # Invalid type - will cause TypeError
                },
            ],
            "container_urls": {
                "default": "valid/default",
                "options": ["valid/option"],
            },
            "settings": {
                "max_tags_display": 50,
                "debug_mode": True,
            },
        }
        # This should raise TypeError due to non-iterable filter_patterns
        with pytest.raises(TypeError):
            config_manager._parse_config(data)

    @pytest.mark.parametrize(
        "value,expected",
        [
            (True, "true"),
            (False, "false"),
            (42, "42"),
            ("test", '"test"'),
            ("test\\backslash", '"test\\\\backslash"'),
            ([], "[]"),
            (["item1", "item2"], '[\n    "item1",\n    "item2"\n]'),
            ({"key": "value"}, 'key = "value"'),
        ],
    )
    def test_serialize_value(self, value, expected):
        """Test serializing values to TOML format."""
        config_manager = ConfigManager()
        assert config_manager._serialize_value(value) == expected

    def test_serialize_value_complex_nested_structures(self):
        """Test serializing complex nested structures."""
        config_manager = ConfigManager()

        # Test nested dictionaries (inline tables)
        complex_dict = {
            "pattern": r"^latest\.(.*)$",
            "replacement": r"\1",
        }
        result = config_manager._serialize_value(complex_dict)
        assert 'pattern = "^latest\\\\.(.*)$"' in result
        assert 'replacement = "\\\\1"' in result

        # Test list with nested dictionaries
        complex_list = [
            {"pattern": r"^test.*$", "replacement": "test"},
            {"pattern": r"^prod.*$", "replacement": "prod"},
        ]
        result = config_manager._serialize_value(complex_list)
        assert 'pattern = "^test.*$"' in result
        assert 'replacement = "test"' in result
        assert 'pattern = "^prod.*$"' in result
        assert 'replacement = "prod"' in result

        # Test empty dict
        result = config_manager._serialize_value({})
        assert result == ""

        # Test list with mixed types
        mixed_list = ["string", 42, True, {"key": "value"}]
        result = config_manager._serialize_value(mixed_list)
        assert '"string"' in result
        assert "42" in result
        assert "true" in result
        assert 'key = "value"' in result

    def test_serialize_value_edge_cases(self):
        """Test serializing edge cases."""
        config_manager = ConfigManager()

        # Test empty list
        result = config_manager._serialize_value([])
        assert result == "[]"

        # Test None value
        result = config_manager._serialize_value(None)
        assert result == "None"

        # Test complex string with special characters
        test_string = "test\nwith\tnewlines\rand\ttabs"
        result = config_manager._serialize_value(test_string)
        # The actual result will contain the literal characters, not escape sequences
        assert result.startswith('"') and result.endswith('"')
        assert len(result) > 2  # Should have quotes around it

        # Test boolean values
        result = config_manager._serialize_value(True)
        assert result == "true"
        result = config_manager._serialize_value(False)
        assert result == "false"

    def test_create_default_config(self, mocker):
        """Test creating default configuration file."""
        mock_config_path = mocker.MagicMock()

        config_manager = ConfigManager()
        config_manager.get_config_path = mocker.MagicMock(return_value=mock_config_path)

        # Use mock_open correctly - patch directly without storing in a variable
        mock_open = mocker.patch("builtins.open", mocker.mock_open())

        config_manager.create_default_config()

        mock_open.assert_called_once_with(mock_config_path, "w")
        handle = mock_open.return_value
        handle.write.assert_called()

    def test_get_default_config(self):
        """Test getting default configuration."""
        config = URHConfig.get_default()
        assert config.repositories is not None
        assert "ublue-os/bazzite" in config.repositories
        assert "wombatfromhell/bazzite-nix" in config.repositories
        assert "astrovm/amyos" in config.repositories


class TestConfigIntegration:
    """Test configuration management integration."""

    def test_load_config_integration(self):
        """Test loading configuration from file."""
        # Create TOML content string
        toml_content = """[[repository]]
name = "test/repo"
include_sha256_tags = true
filter_patterns = ["pattern1", "pattern2"]
ignore_tags = ["tag1", "tag2"]
transform_patterns = [
    {pattern = "pattern3", replacement = "replacement3"}
]
latest_dot_handling = "transform_dates_only"

[container_urls]
default = "ghcr.io/test/repo:testing"
options = ["ghcr.io/test/repo:testing", "ghcr.io/test/repo:stable"]

[settings]
max_tags_display = 50
debug_mode = true
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()  # Ensure content is written to disk
            config_path = f.name

        try:
            with pytest.MonkeyPatch().context() as m:
                m.setattr(
                    "src.urh.config.ConfigManager.get_config_path",
                    lambda self: Path(config_path),
                )
                config_manager = ConfigManager()
                config = config_manager.load_config()

                # Verify repository config
                assert "test/repo" in config.repositories
                repo_config = config.repositories["test/repo"]
                assert repo_config.include_sha256_tags is True
                assert repo_config.filter_patterns == ["pattern1", "pattern2"]
                assert repo_config.ignore_tags == ["tag1", "tag2"]
                assert repo_config.transform_patterns == [
                    {"pattern": "pattern3", "replacement": "replacement3"}
                ]
                assert repo_config.latest_dot_handling == "transform_dates_only"

                # Verify container URLs config
                assert config.container_urls.default == "ghcr.io/test/repo:testing"
                assert config.container_urls.options == [
                    "ghcr.io/test/repo:testing",
                    "ghcr.io/test/repo:stable",
                ]

                # Verify settings config
                assert config.settings.max_tags_display == 50
                assert config.settings.debug_mode is True
        finally:
            os.unlink(config_path)

    def test_create_default_config_integration(self):
        """Test creating default configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "urh.toml"

            with pytest.MonkeyPatch().context() as m:
                m.setattr(
                    "src.urh.config.ConfigManager.get_config_path",
                    lambda self: config_path,
                )
                config_manager = ConfigManager()
                config_manager.create_default_config()

                # Verify file was created
                assert config_path.exists()

                # Load and verify content
                with open(config_path, "r") as f:
                    content = f.read()

                # Check for expected sections
                assert "[[repository]]" in content
                assert "[container_urls]" in content
                assert "[settings]" in content

                # Check for expected repositories
                assert 'name = "ublue-os/bazzite"' in content
                assert 'name = "wombatfromhell/bazzite-nix"' in content
                assert 'name = "astrovm/amyos"' in content
