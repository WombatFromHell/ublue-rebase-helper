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

    default: str
    options: List[str] = field(default_factory=lambda: cast(List[str], []))


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
        default_factory=lambda: ContainerURLsConfig(
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
    )
    settings: SettingsConfig = field(default_factory=lambda: SettingsConfig())

    @classmethod
    def get_default(cls) -> Self:
        """Get default configuration."""
        config = cls()

        # Add default repository configurations
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
            transform_patterns=[
                {"pattern": r"^latest\.(\d{8})$", "replacement": r"\1"}
            ],
            latest_dot_handling="transform_dates_only",
        )

        return config


class ConfigManager:
    """Manages configuration loading and saving."""

    def __init__(self):
        self._config: Optional[URHConfig] = None
        self._config_path: Optional[Path] = None

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
        from typing import cast

        config = URHConfig()

        # Parse repositories (now as array of tables)
        if "repository" in data:
            repositories_list = cast(List[Dict[str, Any]], data["repository"])
            for repo_data in repositories_list:
                # Get the repository name from the 'name' field
                repo_name = repo_data.get("name")
                if not repo_name:
                    continue

                # Extract with explicit type annotations and validation
                include_sha256_tags: bool = repo_data.get("include_sha256_tags", False)

                # Type-safe extraction of list fields
                filter_patterns_raw = repo_data.get("filter_patterns", [])
                filter_patterns: List[str] = [
                    p
                    for p in cast(List[Any], filter_patterns_raw)
                    if isinstance(p, str)
                ]

                ignore_tags_raw = repo_data.get("ignore_tags", [])
                ignore_tags: List[str] = [
                    t for t in cast(List[Any], ignore_tags_raw) if isinstance(t, str)
                ]

                transform_patterns_raw = repo_data.get("transform_patterns", [])
                transform_patterns: List[Dict[str, str]] = []
                for item in cast(List[Any], transform_patterns_raw):
                    if isinstance(item, dict):
                        item_dict = cast(Dict[str, Any], item)
                        # Ensure both 'pattern' and 'replacement' exist and are strings
                        pattern = item_dict.get("pattern")
                        replacement = item_dict.get("replacement")
                        if isinstance(pattern, str) and isinstance(replacement, str):
                            transform_patterns.append(
                                {"pattern": pattern, "replacement": replacement}
                            )

                latest_dot_handling_raw = repo_data.get("latest_dot_handling")
                latest_dot_handling: Optional[str] = (
                    latest_dot_handling_raw
                    if isinstance(latest_dot_handling_raw, str)
                    else None
                )

                repo_config = RepositoryConfig(
                    include_sha256_tags=include_sha256_tags,
                    filter_patterns=filter_patterns,
                    ignore_tags=ignore_tags,
                    transform_patterns=transform_patterns,
                    latest_dot_handling=latest_dot_handling,
                )
                config.repositories[repo_name] = repo_config

        # Parse container URLs
        if "container_urls" in data:
            urls_data = cast(Dict[str, Any], data["container_urls"])

            default_raw = urls_data.get("default", config.container_urls.default)
            default: str = (
                default_raw
                if isinstance(default_raw, str)
                else config.container_urls.default
            )

            options_raw = urls_data.get("options", config.container_urls.options)
            options: List[str] = [
                o for o in cast(List[Any], options_raw) if isinstance(o, str)
            ]

            config.container_urls = ContainerURLsConfig(
                default=default,
                options=options,
            )

        # Parse settings
        if "settings" in data:
            settings_data = cast(Dict[str, Any], data["settings"])

            max_tags_display_raw = settings_data.get(
                "max_tags_display", MAX_TAGS_DISPLAY
            )
            max_tags_display: int = (
                max_tags_display_raw
                if isinstance(max_tags_display_raw, int)
                else MAX_TAGS_DISPLAY
            )

            debug_mode_raw = settings_data.get("debug_mode", False)
            debug_mode: bool = (
                debug_mode_raw if isinstance(debug_mode_raw, bool) else False
            )

            config.settings = SettingsConfig(
                max_tags_display=max_tags_display,
                debug_mode=debug_mode,
            )

        return config

    def _serialize_value(self, value: Any, indent: int = 0) -> str:
        """Serialize a value to TOML format with proper escaping using pattern matching."""
        indent_str = "    " * indent
        match value:
            case bool():
                return str(value).lower()
            case int():
                return str(value)
            case str():
                # Escape backslashes for TOML
                return f'"{value.replace("\\", "\\\\")}"'
            case []:
                return "[]"
            case _ if isinstance(value, list):
                items = cast(List[Any], value)
                if not items:
                    return "[]"
                serialized_items: List[str] = []
                for item in items:
                    if isinstance(item, str):
                        # Escape backslashes for TOML
                        serialized_items.append(
                            f'{indent_str}    "{item.replace("\\", "\\\\")}"'
                        )
                    elif isinstance(item, dict):
                        # Handle inline tables
                        table_items: List[str] = []
                        item_dict = cast(Dict[str, Any], item)
                        for k, v in item_dict.items():
                            if isinstance(v, str):
                                table_items.append(f'{k} = "{v.replace("\\", "\\\\")}"')
                            else:
                                table_items.append(
                                    f"{k} = {self._serialize_value(v, 0)}"
                                )
                        serialized_items.append(
                            f"{indent_str}    {{ {', '.join(table_items)} }}"
                        )
                    else:
                        serialized_items.append(
                            f"{indent_str}    {self._serialize_value(item, 0)}"
                        )
                return "[\n" + ",\n".join(serialized_items) + "\n" + indent_str + "]"
            case _ if isinstance(value, dict):
                d = cast(Dict[str, Any], value)
                # Handle regular tables
                lines: List[str] = []
                for k, v in d.items():
                    lines.append(f"{indent_str}{k} = {self._serialize_value(v, 0)}")
                return "\n".join(lines)
            case _:
                return str(value)

    def create_default_config(self) -> None:
        """Create default configuration file."""
        config_path = self.get_config_path()
        default_config = URHConfig.get_default()

        with open(config_path, "w") as f:
            f.write("# ublue-rebase-helper (urh) configuration file\n")
            f.write(f"# Default location: {config_path}\n")
            f.write("#\n")
            f.write("# For documentation about the format, see DESIGN.md\n")
            f.write("\n")

            # Write repositories section as an array of tables
            for repo_name, repo_config in default_config.repositories.items():
                f.write("[[repository]]\n")
                f.write(f'name = "{repo_name}"\n')
                f.write(
                    f"include_sha256_tags = {self._serialize_value(repo_config.include_sha256_tags)}\n"
                )

                # Write filter_patterns
                f.write("filter_patterns = ")
                f.write(self._serialize_value(repo_config.filter_patterns, 0) + "\n")

                # Write ignore_tags
                f.write("ignore_tags = ")
                f.write(self._serialize_value(repo_config.ignore_tags, 0) + "\n")

                # Write transform_patterns if present
                if repo_config.transform_patterns:
                    f.write("transform_patterns = ")
                    f.write(
                        self._serialize_value(repo_config.transform_patterns, 0) + "\n"
                    )

                # Write latest_dot_handling if present
                if repo_config.latest_dot_handling:
                    f.write(
                        f'latest_dot_handling = "{repo_config.latest_dot_handling}"\n'
                    )

                f.write("\n")

            # Write container URLs section
            f.write("[container_urls]\n")
            f.write(f'default = "{default_config.container_urls.default}"\n')
            f.write("options = ")
            f.write(
                self._serialize_value(default_config.container_urls.options, 0) + "\n"
            )
            f.write("\n")

            # Write settings section
            f.write("[settings]\n")
            f.write(f"max_tags_display = {default_config.settings.max_tags_display}\n")
            f.write(
                f"debug_mode = {self._serialize_value(default_config.settings.debug_mode)}\n"
            )


# Global config manager instance
_config_manager = ConfigManager()


def get_config() -> URHConfig:
    """Get the current configuration."""
    return _config_manager.load_config()
