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
        """Check if tag should be filtered as a signature/attestation tag.

        Handles cosign v2.x and v3.x signature and attestation tags:
        - sha256-<hash>.sig (v2.x legacy signatures)
        - sha256-<hash>.att (v3.x attestations)
        - sha256-<hash>.sbom (v3.x SBOMs)
        - sha256-<hash> (v3.x bundles without suffix)
        """
        if not tag_lower.startswith("sha256-"):
            return False
        # Filter all sha256- prefixed tags (covers v2.x .sig and v3.x bundles)
        return True

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

        def _extract_date_parts(
            match, date_group: int, subver_group: Optional[int] = None
        ) -> tuple[int, int, int, int]:
            """Extract (year, month, day, subver) from a regex match."""
            date_str = match.group(date_group)
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            subver = (
                int(match.group(subver_group))
                if subver_group and match.group(subver_group)
                else 0
            )
            return (year, month, day, subver)

        def version_key(tag: str) -> VersionSortKey:
            # Context-prefixed version tags (testing-XX.YYYYMMDD.SUBVER)
            m = re.match(
                r"^(testing|stable|unstable)-(\d{2})\.(\d{8})(?:\.(\d+))?$", tag
            )
            if m:
                year, month, day, subver = _extract_date_parts(m, 3, 4)
                series = int(m.group(2))
                return (year, month, day, subver, 10000 + series)

            # Context-prefixed date-only tags (testing-YYYYMMDD.SUBVER)
            m = re.match(r"^(testing|stable|unstable)-(\d{8})(?:\.(\d+))?$", tag)
            if m:
                year, month, day, subver = _extract_date_parts(m, 2, 3)
                return (year, month, day, subver, 10000)

            # Version format tags (XX.YYYYMMDD.SUBVER)
            m = re.match(r"^(\d{2})\.(\d{8})(?:\.(\d+))?$", tag)
            if m:
                year, month, day, subver = _extract_date_parts(m, 2, 3)
                series = int(m.group(1))
                return (year, month, day, subver, series)

            # Date format tags (YYYYMMDD.SUBVER)
            m = re.match(r"^(\d{8})(?:\.(\d+))?$", tag)
            if m:
                year, month, day, subver = _extract_date_parts(m, 1, 2)
                return (year, month, day, subver, 0)

            # Alphabetical sorting for other tags
            return (-1, tuple(ord(c) for c in tag))

        return sorted(tags, key=version_key, reverse=True)
