"""Unit tests for the tag filter module."""

from src.urh.config import RepositoryConfig, URHConfig
from src.urh.tag_filter import OCITagFilter


class TestTagFilter:
    """Test tag filter functionality."""

    def test_filter_tag_sha256_prefix(self):
        """Test filtering tags that start with sha256-."""
        config = URHConfig.get_default()

        # By default, sha256 tags should be filtered out because they are in the default filter patterns
        tag_filter = OCITagFilter("test/repo", config)
        # Check if this tag is in the filter patterns by testing the configuration
        # Since it's the default repository configuration, it should filter out SHA256 tags
        # Let's test with a configuration that explicitly includes them
        custom_config = URHConfig()
        custom_config.repositories["test/repo"] = RepositoryConfig(
            include_sha256_tags=False,  # Default behavior
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
        )
        tag_filter = OCITagFilter("test/repo", custom_config)
        assert tag_filter.should_filter_tag("sha256-abc123def456") is True

        # With include_sha256_tags=True, they should not be filtered by the default patterns
        custom_config = URHConfig()
        custom_config.repositories["test/repo"] = RepositoryConfig(
            include_sha256_tags=True,
            filter_patterns=[r"^sha256-.*\.sig$"],  # Only filter signatures
        )
        tag_filter = OCITagFilter("test/repo", custom_config)
        assert tag_filter.should_filter_tag("sha256-abc123def456") is False

    def test_filter_tag_latest_dot_dates(self):
        """Test filtering latest. tags with date transformation."""
        config = URHConfig.get_default()

        # Test with latest_dot_handling set to transform dates only
        repo_config = RepositoryConfig(latest_dot_handling="transform_dates_only")
        config.repositories["test/repo"] = repo_config
        tag_filter = OCITagFilter("test/repo", config)

        # latest.YYYYMMDD should be kept for transformation (not filtered)
        assert tag_filter.should_filter_tag("latest.20231115") is False
        # Other latest. tags should be filtered
        assert tag_filter.should_filter_tag("latest.feature") is True
        assert tag_filter.should_filter_tag("latest.") is True

    def test_filter_tag_ignore_list(self):
        """Test filtering tags from the ignore list."""
        config = URHConfig.get_default()

        repo_config = RepositoryConfig(ignore_tags=["latest", "testing", "unstable"])
        config.repositories["test/repo"] = repo_config
        tag_filter = OCITagFilter("test/repo", config)

        assert tag_filter.should_filter_tag("latest") is True
        assert tag_filter.should_filter_tag("testing") is True
        assert tag_filter.should_filter_tag("unstable") is True
        assert tag_filter.should_filter_tag("stable") is False  # Not in ignore list

    def test_filter_tag_pattern_matching(self):
        """Test filtering tags using regex patterns."""
        config = URHConfig.get_default()

        repo_config = RepositoryConfig(filter_patterns=[r".*\.sig$", r"dev-.*"])
        config.repositories["test/repo"] = repo_config
        tag_filter = OCITagFilter("test/repo", config)

        # Tags matching patterns should be filtered
        assert tag_filter.should_filter_tag("v1.0.0.sig") is True  # Ends with .sig
        assert tag_filter.should_filter_tag("dev-feature") is True  # Starts with dev-

        # Tags not matching patterns should not be filtered
        assert tag_filter.should_filter_tag("v1.0.0") is False
        assert tag_filter.should_filter_tag("release-1.0") is False
