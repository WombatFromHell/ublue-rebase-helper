"""Unit tests for the token manager module."""

import json
import tempfile

import pytest

from src.urh.token_manager import OCITokenManager


class TestOCITokenManager:
    """Test OCI token management."""

    @pytest.fixture
    def temp_cache_file(self):
        """Create a temporary cache file for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        yield tmp_path
        # Cleanup after test
        import os

        os.unlink(tmp_path)

    def test_get_token_from_cache(self, mocker):
        """Test getting token from cache."""
        # Mock os.path.exists to return True
        mocker.patch("os.path.exists", return_value=True)

        # Use mock_open correctly - patch directly without storing in a variable
        mocker.patch("builtins.open", mocker.mock_open(read_data="cached_token"))

        token_manager = OCITokenManager("test/repo")
        token = token_manager.get_token()

        assert token == "cached_token"

    def test_get_token_invalid_cache_file(self, mocker):
        """Test getting token when cache file has invalid content (empty content)."""
        # Mock file operations with empty content - when cache exists but is empty,
        # it returns the empty string, it doesn't fetch a new token
        mocker.patch("builtins.open", mocker.mock_open(read_data=""))
        mocker.patch("os.path.exists", return_value=True)

        # Mock the network request (should not be called since cache exists)
        mock_response = mocker.MagicMock()
        mock_response.read.return_value.decode.return_value = json.dumps(
            {"token": "new_token"}
        )
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None

        # Mock subprocess.run instead of urlopen
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = json.dumps({"token": "new_token"})

        token_manager = OCITokenManager("test/repo")
        token = token_manager.get_token()

        # When cache file exists but is empty, it returns the empty string content
        assert token == ""
        # subprocess should not be called since cache exists and is read successfully (even if empty)
        mock_subprocess.assert_not_called()

    def test_get_token_cache_error(self, mocker):
        """Test getting token when cache read fails."""
        # Mock file operations to raise IOError
        mocker.patch("builtins.open", side_effect=IOError("Cache error"))

        # Mock the network request response properly with context manager protocol
        mock_response = mocker.MagicMock()
        mock_response.read.return_value.decode.return_value = json.dumps(
            {"token": "new_token"}
        )
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None

        # Mock subprocess.run instead of urlopen
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = json.dumps({"token": "new_token"})

        token_manager = OCITokenManager("test/repo")
        token = token_manager.get_token()

        assert token == "new_token"
        mock_subprocess.assert_called_once()

    def test_get_token_fetch_new(self, mocker):
        """Test fetching new token when cache doesn't exist."""
        # Mock file existence check
        mocker.patch("os.path.exists", return_value=False)

        # Mock the cache method
        mock_cache = mocker.patch.object(OCITokenManager, "_cache_token")

        # Mock the network request response properly with context manager protocol
        mock_response = mocker.MagicMock()
        mock_response.read.return_value.decode.return_value = json.dumps(
            {"token": "new_token"}
        )
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None

        # Mock subprocess.run instead of urlopen
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = json.dumps({"token": "new_token"})

        token_manager = OCITokenManager("test/repo")
        token = token_manager.get_token()

        assert token == "new_token"
        mock_subprocess.assert_called_once()
        mock_cache.assert_called_once_with("new_token")

    def test_fetch_new_token(self, mocker):
        """Test successfully fetching a new token."""
        # Mock file existence
        mocker.patch("os.path.exists", return_value=False)

        # Mock the network request response properly with context manager protocol
        mock_response = mocker.MagicMock()
        mock_response.read.return_value.decode.return_value = json.dumps(
            {"token": "test_token"}
        )
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None

        # Mock subprocess.run instead of urlopen
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = json.dumps({"token": "test_token"})

        token_manager = OCITokenManager("test/repo")
        token = token_manager.get_token()

        assert token == "test_token"

    def test_fetch_new_token_error(self, mocker):
        """Test error when fetching a new token."""
        # Mock file existence
        mocker.patch("os.path.exists", return_value=False)

        # Mock subprocess.run to raise an exception
        mock_subprocess = mocker.patch(
            "subprocess.run", side_effect=Exception("Network error")
        )

        # Mock print to capture the error message
        mock_print = mocker.patch("builtins.print")

        token_manager = OCITokenManager("test/repo")
        token = token_manager.get_token()

        # Should return None when an exception occurs
        assert token is None
        mock_subprocess.assert_called_once()
        # Verify that the error message was printed
        mock_print.assert_any_call("Error getting token: Network error")

    def test_cache_token(self, mocker):
        """Test caching a token."""
        # Use mock_open correctly - patch directly without storing in a variable
        mock_open = mocker.patch("builtins.open", mocker.mock_open())

        token_manager = OCITokenManager("test/repo")
        token_manager._cache_token("test_token")

        mock_open.assert_called_once_with(token_manager.cache_path, "w")
        handle = mock_open.return_value
        handle.write.assert_called_once_with("test_token")

    def test_cache_token_error(self, mocker):
        """Test error when caching a token."""
        mocker.patch("builtins.open", side_effect=IOError("Cache error"))

        token_manager = OCITokenManager("test/repo")
        # Should not raise an exception
        token_manager._cache_token("test_token")

    def test_invalidate_cache(self, mocker):
        """Test invalidating token cache."""
        mock_remove = mocker.patch("os.remove")
        token_manager = OCITokenManager("test/repo")
        token_manager.invalidate_cache()

        mock_remove.assert_called_once_with(token_manager.cache_path)

    def test_invalidate_cache_not_exists(self, mocker):
        """Test invalidating token cache when file doesn't exist."""
        mocker.patch("os.remove", side_effect=FileNotFoundError)

        token_manager = OCITokenManager("test/repo")
        # Should not raise an exception
        token_manager.invalidate_cache()

    def test_get_token_exception_handling(self, mocker):
        """Test exception handling in get_token method (line 83)."""
        # Mock file existence to False to trigger token fetching
        mocker.patch("os.path.exists", return_value=False)

        # Mock subprocess.run to raise an exception
        mock_subprocess = mocker.patch(
            "subprocess.run", side_effect=Exception("Network error")
        )

        # Mock logger.error to verify it's called
        mock_logger_error = mocker.patch("src.urh.token_manager.logger.error")

        # Mock print to capture the error message
        mock_print = mocker.patch("builtins.print")

        token_manager = OCITokenManager("test/repo")
        token = token_manager.get_token()

        # Should return None when an exception occurs
        assert token is None
        mock_subprocess.assert_called_once()
        mock_logger_error.assert_called_once_with("Error getting token: Network error")
        mock_print.assert_called_once_with("Error getting token: Network error")

    def test_parse_link_header_various_formats(self):
        """Test parse_link_header with various Link header formats (lines 110-122)."""
        token_manager = OCITokenManager("test/repo")

        # Test with None input
        result = token_manager.parse_link_header(None)
        assert result is None

        # Test with empty string
        result = token_manager.parse_link_header("")
        assert result is None

        # Test standard format
        link_header = '</v2/user/repo/tags/list?last=tag1&n=200>; rel="next"'
        result = token_manager.parse_link_header(link_header)
        assert result == "/v2/user/repo/tags/list?last=tag1&n=200"

        # Test with spaces around the entire link (valid format)
        link_header = ' < /v2/user/repo/tags/list?last=tag2&n=200 > ; rel = "next" '
        result = token_manager.parse_link_header(link_header)
        assert result == "/v2/user/repo/tags/list?last=tag2&n=200"

        # Test with single quotes
        link_header = "</v2/user/repo/tags/list?last=tag3&n=200>; rel='next'"
        result = token_manager.parse_link_header(link_header)
        assert result == "/v2/user/repo/tags/list?last=tag3&n=200"

        # Test with spaces around rel attribute
        link_header = '</v2/user/repo/tags/list?last=tag4&n=200>; rel = "next"'
        result = token_manager.parse_link_header(link_header)
        assert result == "/v2/user/repo/tags/list?last=tag4&n=200"

        # Test with multiple links (should return first next link)
        link_header = '</v2/user/repo/tags/list?last=tag5&n=200>; rel="next", </v2/user/repo/tags/list?last=tag6&n=200>; rel="prev"'
        result = token_manager.parse_link_header(link_header)
        assert result == "/v2/user/repo/tags/list?last=tag5&n=200"

        # Test with no next link
        link_header = '</v2/user/repo/tags/list?last=tag7&n=200>; rel="prev"'
        result = token_manager.parse_link_header(link_header)
        assert result is None

        # Test with malformed link header
        link_header = "malformed header"
        result = token_manager.parse_link_header(link_header)
        assert result is None
