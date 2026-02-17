"""
Integration tests for OCIClient implementation.

Tests the OCI client with mocked subprocess (curl) to verify:
- HTTP response parsing (status, headers, body)
- Header extraction and Link header pagination
- Token validation and retry logic
- Error handling (timeout, auth errors, JSON errors)
- Tag filtering integration with OCITagFilter

Following TEST_DESIGN.md principles:
- Mock only external I/O (subprocess.run for curl)
- Test actual OCIClient logic (never mock the SUT)
- Test through public API methods (fetch_repository_tags, get_all_tags)
"""

import subprocess

import pytest
from pytest_mock import MockerFixture

from src.urh.oci_client import OCIClient


class TestOCIClientHTTPResponseParsing:
    """Test HTTP response parsing in OCIClient."""

    @pytest.fixture
    def oci_client(self, mocker: MockerFixture) -> OCIClient:
        """Create OCIClient with mocked token manager."""
        # Mock token manager to return a test token
        mock_token_manager = mocker.MagicMock()
        mock_token_manager.get_token.return_value = "test_token"
        mock_token_manager.invalidate_cache = mocker.MagicMock()
        mock_token_manager.parse_link_header = mocker.MagicMock()

        client = OCIClient("test/repo")
        client.token_manager = mock_token_manager
        return client

    def test_parse_http_response_with_crlf_separators(
        self, oci_client: OCIClient
    ) -> None:
        """Test parsing HTTP response with CRLF line endings."""
        response = (
            "HTTP/2 200\r\n"
            "Content-Type: application/json\r\n"
            'Link: <next-page>; rel="next"\r\n'
            "\r\n"
            '{"tags": ["v1.0", "v2.0"]}'
        )

        status_line, body, headers = oci_client._parse_http_response(response)

        assert status_line == "HTTP/2 200"
        assert body == '{"tags": ["v1.0", "v2.0"]}'
        assert headers is not None
        assert headers["content-type"] == "application/json"
        assert headers["link"] == '<next-page>; rel="next"'

    def test_parse_http_response_with_lf_separators(
        self, oci_client: OCIClient
    ) -> None:
        """Test parsing HTTP response with LF line endings."""
        response = 'HTTP/2 200\nContent-Type: application/json\n\n{"tags": ["v1.0"]}'

        status_line, body, headers = oci_client._parse_http_response(response)

        assert status_line == "HTTP/2 200"
        assert body == '{"tags": ["v1.0"]}'
        assert headers is not None

    def test_parse_http_response_malformed_returns_none(
        self, oci_client: OCIClient
    ) -> None:
        """Test parsing malformed response returns None."""
        response = "Invalid response without separators"

        result = oci_client._parse_http_response(response)

        assert result == (None, None, None)

    def test_parse_http_response_empty_returns_none(
        self, oci_client: OCIClient
    ) -> None:
        """Test parsing empty response returns None."""
        response = ""

        result = oci_client._parse_http_response(response)

        assert result == (None, None, None)

    def test_validate_parse_result_valid(self, oci_client: OCIClient) -> None:
        """Test validation of valid parse result."""
        parse_result = (
            "HTTP/2 200",
            '{"tags": []}',
            {"content-type": "application/json"},
        )

        assert oci_client._validate_parse_result(parse_result) is True

    def test_validate_parse_result_missing_components(
        self, oci_client: OCIClient
    ) -> None:
        """Test validation fails for missing components."""
        parse_result = (None, '{"tags": []}', {"content-type": "application/json"})

        assert oci_client._validate_parse_result(parse_result) is False


class TestOCIClientPagination:
    """Test pagination logic in OCIClient."""

    @pytest.fixture
    def oci_client_with_mocks(self, mocker: MockerFixture) -> OCIClient:
        """Create OCIClient with mocked dependencies for pagination tests."""
        mock_token_manager = mocker.MagicMock()
        mock_token_manager.get_token.return_value = "test_token"
        mock_token_manager.invalidate_cache = mocker.MagicMock()
        mock_token_manager.parse_link_header = mocker.MagicMock()

        client = OCIClient("test/repo")
        client.token_manager = mock_token_manager
        return client

    def test_extract_next_url_from_link_header(
        self, oci_client_with_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test extracting next URL from Link header."""
        # Setup mock to return next URL
        oci_client_with_mocks.token_manager.parse_link_header.return_value = (  # type: ignore[assignment]
            "https://ghcr.io/v2/test/repo/tags/list?last=tag2&n=200"
        )

        headers = {"link": '<next-page>; rel="next"'}
        next_url = oci_client_with_mocks._extract_next_url(headers)

        assert next_url == "https://ghcr.io/v2/test/repo/tags/list?last=tag2&n=200"
        oci_client_with_mocks.token_manager.parse_link_header.assert_called_once_with(  # type: ignore[attr-defined]
            '<next-page>; rel="next"'
        )

    def test_extract_next_url_no_link_header(
        self, oci_client_with_mocks: OCIClient
    ) -> None:
        """Test extracting next URL when no Link header present."""
        headers = {"content-type": "application/json"}

        next_url = oci_client_with_mocks._extract_next_url(headers)

        assert next_url is None

    def test_fetch_page_with_headers_success(
        self, oci_client_with_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test successful page fetch with headers."""
        # Mock subprocess.run to return valid response
        mock_response = (
            "HTTP/2 200\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            '{"tags": ["v1.0", "v2.0"]}'
        )
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_response, stderr=""
        )

        data, next_url = oci_client_with_mocks._fetch_page_with_headers(
            "https://ghcr.io/v2/test/repo/tags/list", "test_token"
        )

        assert data is not None
        assert data["tags"] == ["v1.0", "v2.0"]
        assert next_url is None  # No Link header in response

    def test_fetch_page_with_headers_with_pagination(
        self, oci_client_with_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test page fetch with Link header for pagination."""
        mock_response = (
            "HTTP/2 200\r\n"
            "Content-Type: application/json\r\n"
            'Link: </v2/test/repo/tags/list?last=tag2&n=200>; rel="next"\r\n'
            "\r\n"
            '{"tags": ["v1.0", "v2.0"]}'
        )
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_response, stderr=""
        )

        # Mock parse_link_header to return next URL
        oci_client_with_mocks.token_manager.parse_link_header.return_value = (  # type: ignore[assignment]
            "https://ghcr.io/v2/test/repo/tags/list?last=tag2&n=200"
        )

        data, next_url = oci_client_with_mocks._fetch_page_with_headers(
            "https://ghcr.io/v2/test/repo/tags/list", "test_token"
        )

        assert data is not None
        assert next_url == "https://ghcr.io/v2/test/repo/tags/list?last=tag2&n=200"

    def test_fetch_page_timeout_returns_none(
        self, oci_client_with_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test timeout during page fetch returns None."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["curl"], timeout=30)

        data, next_url = oci_client_with_mocks._fetch_page_with_headers(
            "https://ghcr.io/v2/test/repo/tags/list", "test_token"
        )

        assert data is None
        assert next_url is None

    def test_get_all_tags_single_page(
        self, oci_client_with_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test get_all_tags with single page response."""
        mock_response = (
            "HTTP/2 200\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            '{"tags": ["v1.0", "v2.0", "v3.0"]}'
        )
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=mock_response, stderr=""
        )

        result = oci_client_with_mocks.get_all_tags()

        assert result is not None
        assert result["tags"] == ["v1.0", "v2.0", "v3.0"]

    def test_get_all_tags_multiple_pages(
        self, oci_client_with_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test get_all_tags follows pagination."""
        # First page with Link header
        response1 = (
            "HTTP/2 200\r\n"
            "Content-Type: application/json\r\n"
            'Link: </v2/test/repo/tags/list?last=tag2&n=200>; rel="next"\r\n'
            "\r\n"
            '{"tags": ["v1.0", "v2.0"]}'
        )
        # Second page without Link header (last page)
        response2 = (
            "HTTP/2 200\r\n"
            "Content-Type: application/json\r\n"
            "\r\n"
            '{"tags": ["v3.0", "v4.0"]}'
        )

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=response1, stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=response2, stderr=""
            ),
        ]

        # Mock parse_link_header to return next URL first time, None second
        oci_client_with_mocks.token_manager.parse_link_header.side_effect = [  # type: ignore[assignment]
            "https://ghcr.io/v2/test/repo/tags/list?last=tag2&n=200",
            None,
        ]

        result = oci_client_with_mocks.get_all_tags()

        assert result is not None
        assert len(result["tags"]) == 4
        assert "v1.0" in result["tags"]
        assert "v4.0" in result["tags"]


class TestOCIClientAuthHandling:
    """Test authentication error handling in OCIClient."""

    @pytest.fixture
    def oci_client_auth_mocks(self, mocker: MockerFixture) -> OCIClient:
        """Create OCIClient with mocked token manager for auth tests."""
        mock_token_manager = mocker.MagicMock()
        mock_token_manager.get_token.return_value = "test_token"
        mock_token_manager.invalidate_cache = mocker.MagicMock()
        mock_token_manager.parse_link_header = mocker.MagicMock()

        client = OCIClient("test/repo")
        client.token_manager = mock_token_manager
        return client

    def test_auth_error_401_invalidates_token_and_retries(
        self, oci_client_auth_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test 401 auth error invalidates token and retries."""
        # First response: 401 Unauthorized
        response1 = "HTTP/1.1 401 Unauthorized\r\n\r\n"
        # Second response (after retry): 200 OK
        response2 = (
            'HTTP/2 200\r\nContent-Type: application/json\r\n\r\n{"tags": ["v1.0"]}'
        )

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=response1, stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=response2, stderr=""
            ),
        ]

        # Mock new token after invalidation
        oci_client_auth_mocks.token_manager.get_token.return_value = "new_token"  # type: ignore[assignment]

        data, next_url = oci_client_auth_mocks._fetch_page_with_headers(
            "https://ghcr.io/v2/test/repo/tags/list", "test_token"
        )

        # Verify token was invalidated
        oci_client_auth_mocks.token_manager.invalidate_cache.assert_called_once()  # type: ignore[attr-defined]
        # Verify new token was requested
        assert oci_client_auth_mocks.token_manager.get_token.call_count >= 1  # type: ignore[attr-defined]
        # Verify data was fetched on retry
        assert data is not None
        assert data["tags"] == ["v1.0"]

    def test_auth_error_403_invalidates_token_and_retries(
        self, oci_client_auth_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test 403 auth error invalidates token and retries."""
        response1 = "HTTP/1.1 403 Forbidden\r\n\r\n"
        response2 = (
            'HTTP/2 200\r\nContent-Type: application/json\r\n\r\n{"tags": ["v1.0"]}'
        )

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=response1, stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=response2, stderr=""
            ),
        ]

        oci_client_auth_mocks.token_manager.get_token.return_value = "new_token"  # type: ignore[assignment]

        data, next_url = oci_client_auth_mocks._fetch_page_with_headers(
            "https://ghcr.io/v2/test/repo/tags/list", "test_token"
        )

        assert oci_client_auth_mocks.token_manager.invalidate_cache.called  # type: ignore[attr-defined]
        assert data is not None

    def test_auth_error_retry_fails_returns_none(
        self, oci_client_auth_mocks: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test auth error retry fails when new token unavailable."""
        response1 = "HTTP/1.1 401 Unauthorized\r\n\r\n"

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=response1, stderr=""
        )

        # Mock token manager to return None (no new token)
        oci_client_auth_mocks.token_manager.get_token.return_value = None  # type: ignore[assignment]

        data, next_url = oci_client_auth_mocks._fetch_page_with_headers(
            "https://ghcr.io/v2/test/repo/tags/list", "test_token"
        )

        assert data is None
        assert next_url is None


class TestOCIClientJSONParsing:
    """Test JSON response parsing in OCIClient."""

    @pytest.fixture
    def oci_client_json_mocks(self, mocker: MockerFixture) -> OCIClient:
        """Create OCIClient for JSON parsing tests."""
        mock_token_manager = mocker.MagicMock()
        mock_token_manager.get_token.return_value = "test_token"
        mock_token_manager.invalidate_cache = mocker.MagicMock()
        mock_token_manager.parse_link_header = mocker.MagicMock()

        client = OCIClient("test/repo")
        client.token_manager = mock_token_manager
        return client

    def test_parse_response_body_valid_json(
        self, oci_client_json_mocks: OCIClient
    ) -> None:
        """Test parsing valid JSON response body."""
        body = '{"tags": ["v1.0", "v2.0", "v3.0"]}'

        data = oci_client_json_mocks._parse_response_body(body)

        assert data is not None
        assert data["tags"] == ["v1.0", "v2.0", "v3.0"]

    def test_parse_response_body_empty_returns_none(
        self, oci_client_json_mocks: OCIClient
    ) -> None:
        """Test parsing empty body returns None."""
        body = ""

        data = oci_client_json_mocks._parse_response_body(body)

        assert data is None

    def test_parse_response_body_invalid_json_returns_none(
        self, oci_client_json_mocks: OCIClient
    ) -> None:
        """Test parsing invalid JSON returns None."""
        body = "Not valid JSON {broken"

        data = oci_client_json_mocks._parse_response_body(body)

        assert data is None

    def test_parse_response_body_ghcr_error_returns_none(
        self, oci_client_json_mocks: OCIClient
    ) -> None:
        """Test parsing GHCR error response returns None."""
        body = (
            '{"errors":[{"code":"UNAUTHORIZED","message":"authentication required"}]}'
        )

        data = oci_client_json_mocks._parse_response_body(body)

        assert data is None


class TestOCIClientTagFiltering:
    """Test tag filtering integration in OCIClient."""

    @pytest.fixture
    def oci_client_with_config(self, mocker: MockerFixture) -> OCIClient:
        """Create OCIClient with test config for filtering tests."""
        # Mock config with filter rules
        from src.urh.config import (
            ContainerURLsConfig,
            RepositoryConfig,
            SettingsConfig,
            URHConfig,
        )

        mock_config = URHConfig()
        mock_config.settings = SettingsConfig(max_tags_display=30, debug_mode=False)
        mock_config.container_urls = ContainerURLsConfig(
            default="ghcr.io/test/repo:testing", options=["ghcr.io/test/repo:testing"]
        )
        # Add repository config with filter patterns
        mock_config.repositories["test/repo"] = RepositoryConfig(
            include_sha256_tags=False,
            filter_patterns=[
                r"^(latest|testing|stable|unstable)$",
            ],
            ignore_tags=["latest", "testing", "stable", "unstable"],
        )

        mock_token_manager = mocker.MagicMock()
        mock_token_manager.get_token.return_value = "test_token"
        mock_token_manager.invalidate_cache = mocker.MagicMock()
        mock_token_manager.parse_link_header = mocker.MagicMock()

        client = OCIClient("test/repo")
        client.config = mock_config
        client.token_manager = mock_token_manager
        return client

    def test_fetch_repository_tags_filters_and_sorts(
        self, oci_client_with_config: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test fetch_repository_tags applies filtering and sorting."""
        # Mock get_all_tags to return unfiltered tags
        raw_tags = [
            "latest",
            "testing",
            "stable",
            "v1.0.0",
            "v2.0.0",
            "v1.5.0",
        ]
        mocker.patch.object(
            oci_client_with_config, "get_all_tags", return_value={"tags": raw_tags}
        )

        result = oci_client_with_config.fetch_repository_tags()

        assert result is not None
        # Context aliases should be filtered out
        assert "latest" not in result["tags"]
        assert "testing" not in result["tags"]
        assert "stable" not in result["tags"]
        # Version tags should remain and be sorted
        assert "v2.0.0" in result["tags"]
        assert "v1.5.0" in result["tags"]
        assert "v1.0.0" in result["tags"]

    def test_fetch_repository_tags_with_context_filtering(
        self, oci_client_with_config: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test fetch_repository_tags with context-aware filtering."""
        raw_tags = [
            "testing-42.20231115.0",
            "testing-41.20231110.0",
            "stable-42.20231115.0",
            "v1.0.0",
        ]
        mocker.patch.object(
            oci_client_with_config, "get_all_tags", return_value={"tags": raw_tags}
        )

        # Test with testing context
        result = oci_client_with_config.fetch_repository_tags(
            "ghcr.io/test/repo:testing"
        )

        assert result is not None
        # Should only show testing-prefixed tags
        assert all(tag.startswith("testing-") for tag in result["tags"])

    def test_fetch_repository_tags_limits_display_count(
        self, oci_client_with_config: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test fetch_repository_tags respects max_tags_display limit."""
        # Generate many tags
        raw_tags = [f"v{i}.0.0" for i in range(1, 101)]  # 100 tags
        mocker.patch.object(
            oci_client_with_config, "get_all_tags", return_value={"tags": raw_tags}
        )

        # Set max display to 10
        oci_client_with_config.config.settings.max_tags_display = 10

        result = oci_client_with_config.fetch_repository_tags()

        assert result is not None
        assert len(result["tags"]) <= 10

    def test_fetch_repository_tags_get_all_tags_failure(
        self, oci_client_with_config: OCIClient, mocker: MockerFixture
    ) -> None:
        """Test fetch_repository_tags handles get_all_tags failure."""
        mocker.patch.object(oci_client_with_config, "get_all_tags", return_value=None)

        result = oci_client_with_config.fetch_repository_tags()

        assert result is None


class TestOCIClientCurlCommandBuilding:
    """Test curl command building in OCIClient."""

    @pytest.fixture
    def oci_client_curl_mocks(self, mocker: MockerFixture) -> OCIClient:
        """Create OCIClient for curl command building tests."""
        mock_token_manager = mocker.MagicMock()
        mock_token_manager.get_token.return_value = "test_token"
        mock_token_manager.invalidate_cache = mocker.MagicMock()
        mock_token_manager.parse_link_header = mocker.MagicMock()

        client = OCIClient("test/repo")
        client.token_manager = mock_token_manager
        return client

    def test_build_curl_command_with_options(
        self, oci_client_curl_mocks: OCIClient
    ) -> None:
        """Test building curl command with various options."""
        cmd = oci_client_curl_mocks._build_curl_command_with_options(
            url="https://ghcr.io/v2/test/repo/tags/list",
            token="test_token",
            capture_headers=True,
            capture_body=True,
            capture_status_code=False,
            timeout=30,
        )

        assert "curl" in cmd
        assert "-s" in cmd
        assert "--http2" in cmd
        assert "--max-time" in cmd
        assert "30" in cmd
        assert "--globoff" in cmd
        assert "--compressed" in cmd
        assert "-i" in cmd  # capture_headers
        assert "-H" in cmd
        assert "Authorization: Bearer test_token" in cmd
        assert "https://ghcr.io/v2/test/repo/tags/list" in cmd

    def test_build_curl_command_without_headers(
        self, oci_client_curl_mocks: OCIClient
    ) -> None:
        """Test building curl command without header capture."""
        cmd = oci_client_curl_mocks._build_curl_command_with_options(
            url="https://ghcr.io/v2/test/repo/tags/list",
            token="test_token",
            capture_headers=False,
            capture_body=True,
            capture_status_code=False,
            timeout=30,
        )

        assert "-i" not in cmd  # No header capture
        # -o /dev/null only added when both capture_body=False AND capture_status_code=False
        assert "-o" not in cmd  # Body capture enabled

    def test_build_curl_command_with_status_code(
        self, oci_client_curl_mocks: OCIClient
    ) -> None:
        """Test building curl command with status code capture."""
        cmd = oci_client_curl_mocks._build_curl_command_with_options(
            url="https://ghcr.io/v2/test/repo/tags/list",
            token="test_token",
            capture_headers=False,
            capture_body=False,
            capture_status_code=True,
            timeout=30,
        )

        assert "-w" in cmd
        assert "%{http_code}" in cmd
