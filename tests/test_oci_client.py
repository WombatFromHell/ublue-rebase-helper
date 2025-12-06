"""Tests for the OCI client module."""

import tempfile

import pytest

from src.urh.oci_client import OCIClient


class TestOCIClient:
    """Test OCI client functionality."""

    def test_oci_client_module_exists(self):
        """Test that the OCI client module can be imported."""
        from src.urh.oci_client import OCIClient

        assert OCIClient is not None


class TestOCIIntegration:
    """Test OCI components integration."""

    @pytest.fixture
    def temp_cache_file(self):
        """Create a temporary cache file for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        yield tmp_path
        # Cleanup after test
        import os

        os.unlink(tmp_path)

    def test_token_manager_with_client(self, mocker, temp_cache_file):
        """Test OCITokenManager integration with OCIClient."""
        mock_token = "test_token"
        mock_tags_data = {"tags": ["tag1", "tag2", "tag3"]}

        # Write the token to the cache manually to simulate a pre-cached token
        with open(temp_cache_file, "w") as f:
            f.write(mock_token)

        # Mock the internal methods that make curl calls for tag fetching
        # Use the new optimized single-request method
        mocker.patch.object(
            OCIClient, "_fetch_page_with_headers", return_value=(mock_tags_data, None)
        )
        # Mock the token validation to return the same token
        mocker.patch.object(
            OCIClient, "_validate_token_and_retry", return_value=mock_token
        )

        client = OCIClient("test/repo", cache_path=temp_cache_file)
        result = client.get_all_tags()

        assert result == mock_tags_data

        # Verify token exists in cache (since we wrote it manually)
        with open(temp_cache_file, "r") as f:
            cached_token = f.read().strip()
        assert cached_token == mock_token

    def test_tag_filter_with_client(self, mocker):
        """Test OCITagFilter integration with OCIClient."""
        mock_tags_data = {
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
            ]
        }

        # Ensure that the client's get_all_tags method returns the mock data
        mock_get_all_tags = mocker.patch.object(OCIClient, "get_all_tags")
        mock_get_all_tags.return_value = mock_tags_data
        client = OCIClient("test/repo")
        result = client.fetch_repository_tags("ghcr.io/test/repo:testing")

        # Should filter out ignored tags and pattern matches
        assert result is not None
        assert "latest" not in result["tags"]
        assert "testing" not in result["tags"]
        assert (
            "sha256-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
            not in result["tags"]
        )

        # Should keep context-specific tags
        assert "testing-42.20231115.0" in result["tags"]

        # Should be sorted by version (newest first)
        assert result["tags"][0] == "testing-42.20231115.0"

    @pytest.mark.parametrize(
        "context,expected_tags,unexpected_tags",
        [
            (
                "testing",
                ["testing-42.20231115.0", "testing-41.20231110.0"],
                ["stable-42.20231115.0", "stable-41.20231110.0"],
            ),
            (
                "stable",
                ["stable-42.20231115.0", "stable-41.20231110.0"],
                ["testing-42.20231115.0", "testing-41.20231110.0"],
            ),
            (
                "unstable",
                ["unstable-43.20231120.0"],
                ["testing-42.20231115.0", "stable-41.20231110.0"],
            ),
        ],
    )
    def test_oci_client_with_context_filtering(
        self, mocker, context, expected_tags, unexpected_tags
    ):
        """Test OCIClient with context-aware tag filtering."""
        mock_tags_data = {
            "tags": [
                "testing-42.20231115.0",
                "testing-41.20231110.0",
                "stable-42.20231115.0",
                "stable-41.20231110.0",
                "unstable-43.20231120.0",
                "42.20231115.0",
                "41.20231110.0",
            ]
        }

        mock_get_all_tags = mocker.patch.object(OCIClient, "get_all_tags")
        mock_get_all_tags.return_value = mock_tags_data
        client = OCIClient("test/repo")

        # Test with specified context
        result = client.fetch_repository_tags(f"ghcr.io/test/repo:{context}")
        assert result is not None

        # Should only include tags with the specified context
        for tag in expected_tags:
            assert tag in result["tags"], f"Expected tag {tag} not found in results"

        # Should not include tags with other contexts
        for tag in unexpected_tags:
            assert tag not in result["tags"], f"Unexpected tag {tag} found in results"

        # All returned tags should start with the specified context
        for tag in result["tags"]:
            assert tag.startswith(context), (
                f"Tag {tag} does not start with context {context}"
            )

    def test_oci_client_amyos_latest_context(self, mocker):
        """Test OCIClient with amyos repository and latest context."""
        mock_tags_data = {
            "tags": [
                "latest.20231115",
                "20231115",
                "20231110",
                "testing-20231115",
                "stable-20231110",
            ]
        }

        mock_get_all_tags = mocker.patch.object(OCIClient, "get_all_tags")
        mock_get_all_tags.return_value = mock_tags_data
        client = OCIClient("astrovm/amyos")

        # Test with latest context (special handling for amyos)
        result = client.fetch_repository_tags("ghcr.io/astrovm/amyos:latest")
        assert result is not None
        assert "20231115" in result["tags"]
        assert "20231110" in result["tags"]
        assert "latest.20231115" not in result["tags"]
        assert "testing-20231115" not in result["tags"]
        assert "stable-20231110" not in result["tags"]
