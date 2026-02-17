"""
Configuration management for ublue-rebase-helper.
"""

import logging
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Self, cast

from .constants import MAX_TAGS_DISPLAY

# Set up logging
logger = logging.getLogger(__name__)


# Single source of truth for standard repositories
# Format: (repo_name, default_tag)
_STANDARD_REPOSITORIES: tuple[tuple[str, str], ...] = (
    ("wombatfromhell/bazzite-nix", "testing"),
    ("wombatfromhell/bazzite-nix", "stable"),
    ("wombatfromhell/bazzite-nix-cachyos", "testing"),
    ("wombatfromhell/bazzite-nvidia-open-nix", "stable"),
    ("ublue-os/bazzite", "testing"),
    ("ublue-os/bazzite", "stable"),
    ("ublue-os/bazzite-nvidia-open", "stable"),
)

# Special repositories with custom configurations
_SPECIAL_REPOSITORIES: tuple[tuple[str, str], ...] = (("astrovm/amyos", "latest"),)

# All repositories combined for container URL generation
_ALL_REPOSITORIES: tuple[tuple[str, str], ...] = (
    *_STANDARD_REPOSITORIES,
    *_SPECIAL_REPOSITORIES,
)


@dataclass(slots=True, kw_only=True)
class RepositoryConfig:
    """Configuration for a specific repository."""

    include_sha256_tags: bool = False
    filter_patterns: List[str] = field(default_factory=lambda: cast(List[str], []))
    ignore_tags: List[str] = field(default_factory=lambda: cast(List[str], []))
    transform_patterns: List[Dict[str, str]] = field(
        default_factory=lambda: cast(List[Dict[str, str]], [])
    )
    latest_dot_handling: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Validate filter patterns are valid regex
        for pattern in self.filter_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}")

        # Validate transform patterns
        for transform in self.transform_patterns:
            if not all(key in transform for key in ["pattern", "replacement"]):
                raise ValueError(
                    f"Transform pattern must have 'pattern' and 'replacement' keys: {transform}"
                )
            try:
                re.compile(transform["pattern"])
            except re.error as e:
                raise ValueError(
                    f"Invalid regex in transform pattern '{transform['pattern']}': {e}"
                )

        # Validate latest_dot_handling
        valid_handlers = {None, "transform_dates_only"}
        if self.latest_dot_handling not in valid_handlers:
            raise ValueError(
                f"latest_dot_handling must be one of {valid_handlers}, "
                f"got '{self.latest_dot_handling}'"
            )


@dataclass(slots=True, kw_only=True)
class ContainerURLsConfig:
    """Configuration for container URLs."""

    default: str = "ghcr.io/wombatfromhell/bazzite-nix:testing"
    options: List[str] = field(
        default_factory=lambda: [
            f"ghcr.io/{repo}:{tag}" for repo, tag in _ALL_REPOSITORIES
        ]
    )


@dataclass(slots=True, kw_only=True)
class SettingsConfig:
    """Global settings configuration."""

    max_tags_display: int = MAX_TAGS_DISPLAY
    debug_mode: bool = False

    def __post_init__(self):
        """Validate settings configuration."""
        if self.max_tags_display <= 0:
            raise ValueError(
                f"max_tags_display must be positive, got {self.max_tags_display}"
            )
        if self.max_tags_display > 1000:
            raise ValueError(
                f"max_tags_display too large (max 1000), got {self.max_tags_display}"
            )


@dataclass(slots=True, kw_only=True)
class URHConfig:
    """Main configuration class."""

    repositories: Dict[str, RepositoryConfig] = field(
        default_factory=lambda: cast(Dict[str, RepositoryConfig], {})
    )
    container_urls: ContainerURLsConfig = field(
        default_factory=lambda: ContainerURLsConfig()
    )
    settings: SettingsConfig = field(default_factory=lambda: SettingsConfig())

    @classmethod
    def _get_standard_filter_patterns(cls) -> List[str]:
        """Get standard filter patterns for most repositories."""
        return [
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
        ]

    @classmethod
    def _get_amyos_filter_patterns(cls) -> List[str]:
        """Get filter patterns for astrovm/amyos repository."""
        return [
            r"^sha256-.*\.sig$",
            r"^<.*>$",
            r"^(testing|stable|unstable)$",
            r"^testing\..*",
            r"^stable\..*",
            r"^unstable\..*",
            r"^\d{1,2}$",
            r"^(latest|testing|stable|unstable)-\d{1,2}$",
            r"^\d{1,2}-(testing|stable|unstable)$",
        ]

    @classmethod
    def _create_standard_repository_config(cls) -> RepositoryConfig:
        """Create standard repository configuration."""
        return RepositoryConfig(
            include_sha256_tags=False,
            filter_patterns=cls._get_standard_filter_patterns(),
            ignore_tags=["latest", "testing", "stable", "unstable"],
        )

    @classmethod
    def _create_amyos_repository_config(cls) -> RepositoryConfig:
        """Create astrovm/amyos repository configuration."""
        return RepositoryConfig(
            include_sha256_tags=False,
            filter_patterns=cls._get_amyos_filter_patterns(),
            ignore_tags=["testing", "stable", "unstable"],
            transform_patterns=[
                {"pattern": r"^latest\.(\d{8})$", "replacement": r"\1"}
            ],
            latest_dot_handling="transform_dates_only",
        )

    @classmethod
    def get_default(cls) -> Self:
        """Get default configuration."""
        config = cls()

        # Standard repositories with identical configuration
        for repo_name, _ in _STANDARD_REPOSITORIES:
            config.repositories[repo_name] = cls._create_standard_repository_config()

        # Special repositories with custom configurations
        for repo_name, _ in _SPECIAL_REPOSITORIES:
            if repo_name == "astrovm/amyos":
                config.repositories[repo_name] = cls._create_amyos_repository_config()

        return config


class ConfigManager:
    """Manages configuration loading and saving."""

    def __init__(self):
        self._config: Optional[URHConfig] = None
        self._config_path: Optional[Path] = None

    def _get_standard_filter_patterns(self) -> List[str]:
        """Get standard filter patterns for most repositories."""
        return [
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
        ]

    def get_config_path(self) -> Path:
        """Get the path to the configuration file with caching."""
        if self._config_path is None:
            xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config_home:
                config_file = Path(xdg_config_home) / "urh.toml"
            else:
                config_file = Path.home() / ".config" / "urh.toml"

            config_file.parent.mkdir(parents=True, exist_ok=True)
            self._config_path = config_file
        return self._config_path

    def load_config(self) -> URHConfig:
        """Load configuration from file."""
        if self._config is not None:
            return self._config

        config_path = self.get_config_path()

        if not config_path.exists():
            self.create_default_config()
            logger.info(f"Created default config file at {config_path}")
            self._config = URHConfig.get_default()
            return self._config

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
                self._config = self._parse_config(data)
                return self._config
        except tomllib.TOMLDecodeError as e:
            logger.error(f"Error parsing TOML config file: {e}")
            logger.info("Using default configuration instead.")
            self._config = URHConfig.get_default()
            return self._config
        except Exception as e:
            logger.error(f"Error reading config file: {e}")
            logger.info("Using default configuration instead.")
            self._config = URHConfig.get_default()
            return self._config

    def _parse_config(self, data: Dict[str, Any]) -> URHConfig:
        """Parse configuration data from TOML."""
        config = URHConfig()

        # Parse repositories
        if "repository" in data:
            self._parse_repositories(data["repository"], config)

        # Parse container URLs
        if "container_urls" in data:
            self._parse_container_urls(data["container_urls"], config)

        # Parse settings
        if "settings" in data:
            self._parse_settings(data["settings"], config)

        return config

    def _parse_repositories(
        self, repositories_list: List[Dict[str, Any]], config: URHConfig
    ) -> None:
        """Parse repository configurations."""

        for repo_data in repositories_list:
            repo_name = repo_data.get("name")
            if not repo_name:
                continue

            repo_config = self._create_repository_config(repo_data)
            config.repositories[repo_name] = repo_config

    def _create_repository_config(self, repo_data: Dict[str, Any]) -> RepositoryConfig:
        """Create a RepositoryConfig from parsed data with DRY optimizations."""

        include_sha256_tags = repo_data.get("include_sha256_tags", False)

        # Use standard defaults for filter_patterns and ignore_tags if not specified
        # This enables DRY TOML files where standard repos don't need to repeat common settings
        if "filter_patterns" in repo_data:
            filter_patterns = self._extract_string_list(repo_data, "filter_patterns")
        else:
            # Use standard filter patterns as default
            filter_patterns = self._get_standard_filter_patterns()

        if "ignore_tags" in repo_data:
            ignore_tags = self._extract_string_list(repo_data, "ignore_tags")
        else:
            # Use standard ignore tags as default
            ignore_tags = ["latest", "testing", "stable", "unstable"]

        transform_patterns = self._extract_transform_patterns(repo_data)
        latest_dot_handling = self._extract_optional_string(
            repo_data, "latest_dot_handling"
        )

        return RepositoryConfig(
            include_sha256_tags=include_sha256_tags,
            filter_patterns=filter_patterns,
            ignore_tags=ignore_tags,
            transform_patterns=transform_patterns,
            latest_dot_handling=latest_dot_handling,
        )

    def _extract_string_list(self, data: Dict[str, Any], key: str) -> List[str]:
        """Extract and validate a list of strings from configuration data."""
        from typing import cast

        raw_list = data.get(key, [])
        return [item for item in cast(List[Any], raw_list) if isinstance(item, str)]

    def _extract_transform_patterns(self, data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract and validate transform patterns from configuration data."""
        from typing import cast

        patterns: List[Dict[str, str]] = []
        raw_patterns = data.get("transform_patterns", [])

        for item in cast(List[Any], raw_patterns):
            if isinstance(item, dict):
                item_dict = cast(Dict[str, Any], item)
                pattern = item_dict.get("pattern")
                replacement = item_dict.get("replacement")
                if isinstance(pattern, str) and isinstance(replacement, str):
                    patterns.append({"pattern": pattern, "replacement": replacement})

        return patterns

    def _extract_optional_string(self, data: Dict[str, Any], key: str) -> Optional[str]:
        """Extract an optional string value from configuration data."""
        value = data.get(key)
        return value if isinstance(value, str) else None

    def _parse_container_urls(
        self, urls_data: Dict[str, Any], config: URHConfig
    ) -> None:
        """Parse container URL configurations."""

        default = self._extract_string_with_default(
            urls_data, "default", config.container_urls.default
        )
        options = self._extract_string_list(urls_data, "options")

        config.container_urls = ContainerURLsConfig(
            default=default,
            options=options,
        )

    def _extract_string_with_default(
        self, data: Dict[str, Any], key: str, default_value: str
    ) -> str:
        """Extract a string value with a default fallback."""
        value = data.get(key, default_value)
        return value if isinstance(value, str) else default_value

    def _parse_settings(self, settings_data: Dict[str, Any], config: URHConfig) -> None:
        """Parse settings configurations."""
        max_tags_display = self._extract_int_with_default(
            settings_data, "max_tags_display", MAX_TAGS_DISPLAY
        )
        debug_mode = self._extract_bool_with_default(settings_data, "debug_mode", False)

        config.settings = SettingsConfig(
            max_tags_display=max_tags_display,
            debug_mode=debug_mode,
        )

    def _extract_int_with_default(
        self, data: Dict[str, Any], key: str, default_value: int
    ) -> int:
        """Extract an integer value with a default fallback."""
        value = data.get(key, default_value)
        return value if isinstance(value, int) else default_value

    def _extract_bool_with_default(
        self, data: Dict[str, Any], key: str, default_value: bool
    ) -> bool:
        """Extract a boolean value with a default fallback."""
        value = data.get(key, default_value)
        return value if isinstance(value, bool) else default_value

    def _serialize_value(self, value: Any, indent: int = 0) -> str:
        """Serialize a value to TOML format with proper escaping using pattern matching."""
        match value:
            case bool():
                return self._serialize_boolean(value)
            case int():
                return self._serialize_integer(value)
            case str():
                return self._serialize_string(value)
            case []:
                return self._serialize_empty_list()
            case _ if isinstance(value, list):
                return self._serialize_list(cast(List[Any], value), indent)
            case _ if isinstance(value, dict):
                return self._serialize_dict(cast(Dict[str, Any], value), indent)
            case _:
                return self._serialize_fallback(value)

    def _serialize_boolean(self, value: bool) -> str:
        """Serialize a boolean value."""
        return str(value).lower()

    def _serialize_integer(self, value: int) -> str:
        """Serialize an integer value."""
        return str(value)

    def _serialize_string(self, value: str) -> str:
        """Serialize a string value with proper escaping."""
        return f'"{value.replace("\\", "\\\\")}"'

    def _serialize_empty_list(self) -> str:
        """Serialize an empty list."""
        return "[]"

    def _serialize_list(self, items: List[Any], indent: int) -> str:
        """Serialize a list with proper formatting and indentation."""
        from typing import cast

        if not items:
            return "[]"

        indent_str = "    " * indent
        serialized_items: List[str] = []

        for item in items:
            if isinstance(item, str):
                serialized_items.append(
                    self._serialize_list_string_item(item, indent_str)
                )
            elif isinstance(item, dict):
                serialized_items.append(
                    self._serialize_list_dict_item(
                        cast(Dict[str, Any], item), indent_str
                    )
                )
            else:
                serialized_items.append(
                    self._serialize_list_other_item(item, indent_str)
                )

        return "[\n" + ",\n".join(serialized_items) + "\n" + indent_str + "]"

    def _serialize_list_string_item(self, item: str, indent_str: str) -> str:
        """Serialize a string item within a list."""
        return f'{indent_str}    "{item.replace("\\", "\\\\")}"'

    def _serialize_list_dict_item(
        self, item_dict: Dict[str, Any], indent_str: str
    ) -> str:
        """Serialize a dictionary item within a list as an inline table."""
        table_items: List[str] = []
        for k, v in item_dict.items():
            if isinstance(v, str):
                table_items.append(f'{k} = "{v.replace("\\", "\\\\")}"')
            else:
                table_items.append(f"{k} = {self._serialize_value(v, 0)}")
        return f"{indent_str}    {{ {', '.join(table_items)} }}"

    def _serialize_list_other_item(self, item: Any, indent_str: str) -> str:
        """Serialize a non-string, non-dict item within a list."""
        return f"{indent_str}    {self._serialize_value(item, 0)}"

    def _serialize_dict(self, d: Dict[str, Any], indent: int) -> str:
        """Serialize a dictionary as TOML key-value pairs."""
        indent_str = "    " * indent
        lines: List[str] = []
        for k, v in d.items():
            lines.append(f"{indent_str}{k} = {self._serialize_value(v, 0)}")
        return "\n".join(lines)

    def _serialize_fallback(self, value: Any) -> str:
        """Fallback serialization for unknown types."""
        return str(value)

    def create_default_config(self) -> None:
        """Create default configuration file with DRY optimizations."""
        config_path = self.get_config_path()
        default_config = URHConfig.get_default()

        with open(config_path, "w") as f:
            f.write("# ublue-rebase-helper (urh) configuration file\n")
            f.write(f"# Default location: {config_path}\n")
            f.write("#\n")
            f.write("# For documentation about the format, see DESIGN.md\n")
            f.write("#\n")
            f.write(
                "# This file uses DRY principles - common settings are inherited from defaults\n"
            )
            f.write("# Only overrides and special cases are explicitly specified\n")
            f.write("\n")

            # Write standard repositories with shared configuration
            # Write comment explaining the standard configuration
            f.write(
                "# Standard repositories share the same filter patterns and ignore tags\n"
            )
            f.write("# Defaults: include_sha256_tags = false\n")
            f.write(
                "# Standard filter patterns: SHA256 hashes, latest/testing/stable/unstable tags, etc.\n"
            )
            f.write("# Standard ignore tags: latest, testing, stable, unstable\n")
            f.write("\n")

            # Write standard repositories using defaults
            for repo_name, _ in _STANDARD_REPOSITORIES:
                f.write("[[repository]]\n")
                f.write(f'name = "{repo_name}"\n')
                # Only specify overrides if they differ from defaults
                # include_sha256_tags defaults to false, so we don't need to specify it
                f.write("\n")

            # Write special astrovm/amyos repository with explicit configuration
            f.write("# Special repository with custom configuration\n")
            f.write("[[repository]]\n")
            f.write('name = "astrovm/amyos"\n')
            f.write("include_sha256_tags = false\n")

            # Write filter_patterns (different from standard)
            amyos_config = default_config.repositories["astrovm/amyos"]
            f.write("filter_patterns = ")
            f.write(self._serialize_value(amyos_config.filter_patterns, 0) + "\n")

            # Write ignore_tags (different from standard - no "latest")
            f.write("ignore_tags = ")
            f.write(self._serialize_value(amyos_config.ignore_tags, 0) + "\n")

            # Write transform_patterns
            f.write("transform_patterns = ")
            f.write(self._serialize_value(amyos_config.transform_patterns, 0) + "\n")

            # Write latest_dot_handling
            f.write(f'latest_dot_handling = "{amyos_config.latest_dot_handling}"\n')

            f.write("\n")

            # Write container URLs section
            f.write("[container_urls]\n")
            f.write(f'default = "{default_config.container_urls.default}"\n')
            f.write("options = [\n")
            for url in default_config.container_urls.options:
                f.write(f'    "{url}",\n')
            f.write("]\n")
            f.write("\n")

            # Write settings section
            f.write("[settings]\n")
            f.write("# Default: max_tags_display = 30\n")
            f.write("# Default: debug_mode = false\n")
            f.write(
                "# Settings are commented out to show defaults - uncomment to override\n"
            )
            f.write("\n")


# Global config manager instance
_config_manager = ConfigManager()


def get_config() -> URHConfig:
    """Get the current configuration."""
    return _config_manager.load_config()
