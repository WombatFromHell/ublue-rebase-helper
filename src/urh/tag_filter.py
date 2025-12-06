"""
Tag filtering and sorting for ublue-rebase-helper.
"""

import functools
import re
from typing import Dict, List, Optional, Tuple, Union

from .config import RepositoryConfig, URHConfig
from .constants import MAX_TAGS_DISPLAY

# Type aliases for better type safety
DateVersionKey = Tuple[int, int, int, int, int]
AlphaVersionKey = Tuple[int, Tuple[int, ...]]
VersionSortKey = Union[DateVersionKey, AlphaVersionKey]


@functools.lru_cache(maxsize=128)
def _get_compiled_pattern(pattern: str) -> re.Pattern[str]:
    """Get a cached compiled regex pattern."""
    return re.compile(pattern)


class OCITagFilter:
    """Handles tag filtering and sorting logic."""

    def __init__(
        self, repository: str, config: URHConfig, context: Optional[str] = None
    ):
        self.repository = repository
        self.config = config
        self.repo_config = config.repositories.get(repository, RepositoryConfig())
        self.context = context

    def should_filter_tag(self, tag: str) -> bool:
        """Determine if a tag should be filtered out."""
        tag_lower = tag.lower()

        # Handle latest. tags
        if tag_lower.startswith("latest."):
            suffix = tag_lower[7:]
            if not suffix:
                return True
            if len(suffix) >= 8 and suffix.isdigit():
                return False  # Date format, keep for transformation
            return True  # Non-date format, filter out

        # Check ignore list
        if tag_lower in [t.lower() for t in self.repo_config.ignore_tags]:
            return True

        # Check filter patterns using cached patterns
        for pattern in self.repo_config.filter_patterns:
            compiled_pattern = _get_compiled_pattern(pattern)
            if compiled_pattern.match(tag_lower):
                return True

        # Filter signature tags
        if tag_lower.endswith(".sig") and "sha256-" in tag_lower:
            return True

        # Filter SHA256 hashes
        if not self.repo_config.include_sha256_tags:
            if len(tag) == 64 and all(c in "0123456789abcdefABCDEF" for c in tag):
                return True

        return False

    def transform_tag(self, tag: str) -> str:
        """Transform a tag based on repository rules."""
        for transform in self.repo_config.transform_patterns:
            pattern = transform["pattern"]
            replacement = transform["replacement"]
            compiled_pattern = _get_compiled_pattern(pattern)
            if compiled_pattern.match(tag):
                return re.sub(compiled_pattern, replacement, tag)
        return tag

    def filter_and_sort_tags(
        self, tags: List[str], limit: int = MAX_TAGS_DISPLAY
    ) -> List[str]:
        """Filter and sort tags."""
        # Filter out unwanted tags
        filtered_tags = [tag for tag in tags if not self.should_filter_tag(tag)]

        # Apply context-based filtering if a context is specified
        if self.context:
            filtered_tags = self._context_filter_tags(filtered_tags, self.context)

        # Transform tags
        transformed_tags = [self.transform_tag(tag) for tag in filtered_tags]

        # Deduplicate tags
        deduplicated_tags = self._deduplicate_tags_by_version(transformed_tags)

        # Sort tags based on version patterns
        sorted_tags = self._sort_tags(deduplicated_tags)

        # Return the first N tags
        return sorted_tags[:limit]

    def _context_filter_tags(self, tags: List[str], context: str) -> List[str]:
        """Filter tags based on context."""
        context_prefix = f"{context}-"
        context_tags = [tag for tag in tags if tag.startswith(context_prefix)]

        # Special handling for astrovm/amyos with latest context
        if self.repository == "astrovm/amyos" and context == "latest":
            # For amyos with latest context, we want YYYYMMDD format tags
            # which are the transformed version of latest.YYYYMMDD tags
            date_pattern = r"^\d{8}$"
            context_tags = [tag for tag in tags if re.match(date_pattern, tag)]

        return context_tags

    def _deduplicate_tags_by_version(self, tags: List[str]) -> List[str]:
        """Deduplicate tags by version, preferring prefixed versions when available."""
        version_map: Dict[Union[Tuple[str, str, str], str], str] = {}

        for tag in tags:
            # Extract version components - handle different formats
            # Format 1: [prefix-][XX.]YYYYMMDD[.N] where XX is optional series number
            # Format 2: [prefix-]XX.YYYYYYYY[.N] where XX is required series number
            # Try more specific pattern first: prefixed with series number
            version_match = re.match(
                r"^(?:testing-|stable-|unstable-)?(\d{2})\.(\d{8})(?:\.(\d+))?$", tag
            )

            if not version_match:
                # Try date-only format (like YYYYMMDD)
                date_only_match = re.match(
                    r"^(?:testing-|stable-|unstable-)?(\d{8})(?:\.(\d+))?$", tag
                )
                if date_only_match:
                    # Date-only format: no series (empty string), date, subver
                    date = date_only_match.group(1)
                    subver = date_only_match.group(2) or "0"
                    version_key = ("", date, subver)

                    # Check if this is a prefixed tag
                    is_prefixed = any(
                        tag.startswith(prefix)
                        for prefix in ["testing-", "stable-", "unstable-"]
                    )

                    # Use the same logic for storing
                    if version_key not in version_map:
                        version_map[version_key] = tag
                    elif is_prefixed and not any(
                        version_map[version_key].startswith(prefix)
                        for prefix in ["testing-", "stable-", "unstable-"]
                    ):
                        # Replace non-prefixed with prefixed
                        version_map[version_key] = tag
                    continue  # Continue to next tag since we handled this one

            if version_match:
                series = version_match.group(1)
                date = version_match.group(2)
                subver = version_match.group(3) or "0"

                # Create a version key
                version_key = (series, date, subver)

                # Check if this is a prefixed tag
                is_prefixed = tag.startswith(("testing-", "stable-", "unstable-"))

                # If this version is not in the map, add it
                # OR if this tag is prefixed and currently stored is not prefixed, replace it
                # But don't replace an existing prefixed tag with another prefixed tag
                if version_key not in version_map:
                    version_map[version_key] = tag
                elif is_prefixed and not version_map[version_key].startswith(
                    ("testing-", "stable-", "unstable-")
                ):
                    # Replace non-prefixed with prefixed
                    version_map[version_key] = tag
                # Otherwise, keep the existing one (whether prefixed or not)
            else:
                # For non-version tags, just add them directly
                version_map[tag] = tag

        return list(version_map.values())

    def _sort_tags(self, tags: List[str]) -> List[str]:
        """Sort tags based on version patterns."""

        def version_key(tag: str) -> VersionSortKey:
            # Handle context-prefixed version tags (testing-XX.YYYYMMDD, etc.)
            context_version_match = re.match(
                r"^(testing|stable|unstable)-(\d{2})\.(\d{8})(?:\.(\d+))?$", tag
            )
            if context_version_match:
                series = int(context_version_match.group(2))
                year, month, day = (
                    int(context_version_match.group(3)[:4]),
                    int(context_version_match.group(3)[4:6]),
                    int(context_version_match.group(3)[6:8]),
                )
                subver = (
                    int(context_version_match.group(4))
                    if context_version_match.group(4)
                    else 0
                )
                # Prefixed tags get priority over non-prefixed for same date
                # Using tuple of 5 elements: (year, month, day, subver, priority * 10000 + series)
                return (year, month, day, subver, 10000 + series)

            # Handle context-prefixed date-only tags (testing-YYYYMMDD, etc.)
            context_date_match = re.match(
                r"^(testing|stable|unstable)-(\d{8})(?:\.(\d+))?$", tag
            )
            if context_date_match:
                year, month, day = (
                    int(context_date_match.group(2)[:4]),
                    int(context_date_match.group(2)[4:6]),
                    int(context_date_match.group(2)[6:8]),
                )
                subver = (
                    int(context_date_match.group(3))
                    if context_date_match.group(3)
                    else 0
                )
                # Prefixed date-only tags get priority
                # Using tuple of 5 elements: (year, month, day, subver, priority)
                return (year, month, day, subver, 10000)

            # Handle version format tags (XX.YYYYMMDD.SUBVER)
            version_match = re.match(r"^(\d{2})\.(\d{8})(?:\.(\d+))?$", tag)
            if version_match:
                series = int(version_match.group(1))
                year, month, day = (
                    int(version_match.group(2)[:4]),
                    int(version_match.group(2)[4:6]),
                    int(version_match.group(2)[6:8]),
                )
                subver = int(version_match.group(3)) if version_match.group(3) else 0
                # Non-prefixed tags get lower priority
                # Using tuple of 5 elements: (year, month, day, subver, priority * 10000 + series)
                return (year, month, day, subver, series)  # priority 0, so just series

            # Handle date format tags (YYYYMMDD)
            date_match = re.match(r"^(\d{8})(?:\.(\d+))?$", tag)
            if date_match:
                year, month, day = (
                    int(date_match.group(1)[:4]),
                    int(date_match.group(1)[4:6]),
                    int(date_match.group(1)[6:8]),
                )
                subver = int(date_match.group(2)) if date_match.group(2) else 0
                # Non-prefixed date tags get lower priority
                # Using tuple of 5 elements: (year, month, day, subver, priority)
                return (year, month, day, subver, 0)

            # For all other tags, use alphabetical sorting
            # Using AlphaVersionKey format: (priority, tuple of character codes)
            return (-1, tuple(ord(c) for c in tag))

        return sorted(tags, key=version_key, reverse=True)
