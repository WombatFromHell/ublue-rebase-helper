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

    def _should_filter_latest_tag(self, tag_lower: str) -> bool:
        """Handle filtering of latest. tags."""
        if tag_lower.startswith("latest."):
            suffix = tag_lower[7:]
            if not suffix:
                return True
            if len(suffix) >= 8 and suffix.isdigit():
                return False  # Date format, keep for transformation
            return True  # Non-date format, filter out
        return False

    def _should_filter_ignore_list(self, tag_lower: str) -> bool:
        """Check if tag should be filtered based on ignore list."""
        return tag_lower in [t.lower() for t in self.repo_config.ignore_tags]

    def _should_filter_patterns(self, tag_lower: str) -> bool:
        """Check if tag should be filtered based on filter patterns."""
        for pattern in self.repo_config.filter_patterns:
            compiled_pattern = _get_compiled_pattern(pattern)
            if compiled_pattern.match(tag_lower):
                return True
        return False

    def _should_filter_signature_tags(self, tag_lower: str) -> bool:
        """Check if tag should be filtered as a signature tag."""
        return tag_lower.endswith(".sig") and "sha256-" in tag_lower

    def _should_filter_sha256_hashes(self, tag: str) -> bool:
        """Check if tag should be filtered as a SHA256 hash."""
        if not self.repo_config.include_sha256_tags:
            if len(tag) == 64 and all(c in "0123456789abcdefABCDEF" for c in tag):
                return True
        return False

    def should_filter_tag(self, tag: str) -> bool:
        """Determine if a tag should be filtered out."""
        tag_lower = tag.lower()

        # Check each filter condition in sequence
        if self._should_filter_latest_tag(tag_lower):
            return True
        if self._should_filter_ignore_list(tag_lower):
            return True
        if self._should_filter_patterns(tag_lower):
            return True
        if self._should_filter_signature_tags(tag_lower):
            return True
        if self._should_filter_sha256_hashes(tag):
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

    def _is_prefixed_tag(self, tag: str) -> bool:
        """Check if a tag is prefixed with testing-, stable-, or unstable-."""
        return tag.startswith(("testing-", "stable-", "unstable-"))

    def _create_version_key_from_match(
        self,
        match,
        series_group: int = 1,
        date_group: int = 2,
        subver_group: Optional[int] = 3,
    ) -> Tuple[str, str, str]:
        """Create version key from regex match with flexible group positions."""
        series = match.group(series_group) or ""
        date = match.group(date_group)
        subver = (
            match.group(subver_group) or "0"
            if subver_group and match.group(subver_group)
            else "0"
        )
        return (series, date, subver)

    def _handle_version_tag_deduplication(
        self, tag: str, version_key: Tuple[str, str, str], version_map: Dict
    ) -> None:
        """Handle deduplication logic for version tags."""
        is_prefixed = self._is_prefixed_tag(tag)

        # If this version is not in the map, add it
        # OR if this tag is prefixed and currently stored is not prefixed, replace it
        # But don't replace an existing prefixed tag with another prefixed tag
        if version_key not in version_map:
            version_map[version_key] = tag
        elif is_prefixed and not self._is_prefixed_tag(version_map[version_key]):
            # Replace non-prefixed with prefixed
            version_map[version_key] = tag
        # Otherwise, keep the existing one (whether prefixed or not)

    def _handle_date_only_tag_deduplication(self, tag: str, version_map: Dict) -> bool:
        """Handle deduplication logic for date-only tags."""
        date_only_match = re.match(
            r"^(?:testing-|stable-|unstable-)?(\d{8})(?:\.(\d+))?$", tag
        )
        if date_only_match:
            # Date-only format: no series (empty string), date, subver
            version_key = self._create_version_key_from_match(
                date_only_match, series_group=1, date_group=2, subver_group=2
            )

            is_prefixed = self._is_prefixed_tag(tag)

            # Use the same logic for storing
            if version_key not in version_map:
                version_map[version_key] = tag
            elif is_prefixed and not self._is_prefixed_tag(version_map[version_key]):
                # Replace non-prefixed with prefixed
                version_map[version_key] = tag
            return True  # Tag was handled
        return False  # Tag was not handled

    def _deduplicate_tags_by_version(self, tags: List[str]) -> List[str]:
        """Deduplicate tags by version, preferring prefixed versions when available."""
        version_map: Dict[Union[Tuple[str, str, str], str], str] = {}

        for tag in tags:
            # Try more specific pattern first: prefixed with series number
            version_match = re.match(
                r"^(?:testing-|stable-|unstable-)?(\d{2})\.(\d{8})(?:\.(\d+))?$", tag
            )

            if version_match:
                # Handle version tags
                version_key = self._create_version_key_from_match(version_match)
                self._handle_version_tag_deduplication(tag, version_key, version_map)
            elif self._handle_date_only_tag_deduplication(tag, version_map):
                # Date-only tag was handled, continue to next tag
                continue
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
