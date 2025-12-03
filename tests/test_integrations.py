import json
import os
import tempfile
from pathlib import Path

import pytest

from urh import (
    CommandRegistry,
    ConfigManager,
    MenuSystem,
    OCIClient,
    extract_context_from_url,
    extract_repository_from_url,
    format_deployment_header,
    parse_deployment_info,
    run_command,
)


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
                    "urh.ConfigManager.get_config_path", lambda self: Path(config_path)
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
                m.setattr("urh.ConfigManager.get_config_path", lambda self: config_path)
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


class TestOCIIntegration:
    """Test OCI components integration."""

    def test_token_manager_with_client(self, mocker, temp_cache_file):
        """Test OCITokenManager integration with OCIClient."""
        mock_token = "test_token"
        mock_tags_data = {"tags": ["tag1", "tag2", "tag3"]}

        # Write the token to the cache manually to simulate a pre-cached token
        with open(temp_cache_file, "w") as f:
            f.write(mock_token)

        # Mock the internal methods that make curl calls for tag fetching
        # Use the new optimized single-request method
        mock_fetch_page_with_headers = mocker.patch.object(
            OCIClient, "_fetch_page_with_headers", return_value=(mock_tags_data, None)
        )
        # Mock the token validation to return the same token
        mock_validate_token = mocker.patch.object(
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


class TestMenuIntegration:
    """Test menu system integration."""

    def test_menu_system_with_subprocess(self, mocker, sample_menu_items):
        """Test MenuSystem integration with subprocess."""
        mocker.patch("os.isatty", return_value=True)
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = "1 - Option 1"

        menu_system = MenuSystem()
        result = menu_system.show_menu(sample_menu_items, "Test Header")

        assert result == "1"
        mock_subprocess.assert_called_once()

    def test_menu_system_with_persistent_header(self, mocker, sample_menu_items):
        """Test MenuSystem with persistent header."""
        mocker.patch("os.isatty", return_value=True)
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.stdout = "1 - Option 1"

        menu_system = MenuSystem()
        result = menu_system.show_menu(
            items=sample_menu_items,
            header="Test Header",
            persistent_header="Current deployment: test-repo (v1.0.0)",
        )

        assert result == "1"

        # Verify persistent header was included in the command
        call_args = mock_subprocess.call_args[0][0]
        header_index = call_args.index("--header") + 1
        header_value = call_args[header_index]
        assert "Current deployment: test-repo (v1.0.0)" in header_value
        assert "Test Header" in header_value

    def test_menu_system_fallback_to_text(self, mocker, sample_menu_items):
        """Test MenuSystem fallback to text menu when gum is not available."""
        mocker.patch("os.isatty", return_value=True)
        mocker.patch("subprocess.run", side_effect=FileNotFoundError)
        mock_input = mocker.patch("builtins.input", return_value="1")

        menu_system = MenuSystem()
        result = menu_system.show_menu(sample_menu_items, "Test Header")

        assert result == "1"
        mock_input.assert_called_once_with("\nEnter choice (number): ")


class TestCommandIntegration:
    """Test command registry integration."""

    def test_command_registry_with_menu_system(self, mocker):
        """Test CommandRegistry integration with MenuSystem."""
        mock_get_config = mocker.patch("urh.get_config")
        mock_menu_system = mocker.patch("urh._menu_system")
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        config = mocker.MagicMock()
        config.container_urls.options = [
            "ghcr.io/test/repo:testing",
            "ghcr.io/test/repo:stable",
        ]
        mock_get_config.return_value = config

        mock_menu_system.show_menu.return_value = "ghcr.io/test/repo:stable"

        registry = CommandRegistry()
        registry._handle_rebase([])

        mock_menu_system.show_menu.assert_called_once()
        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "rebase", "ghcr.io/test/repo:stable"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_deployment_info(
        self, mocker, sample_deployment_info
    ):
        """Test CommandRegistry integration with deployment info."""
        mock_get_deployment_info = mocker.patch("urh.get_deployment_info")
        mock_get_current_deployment_info = mocker.patch(
            "urh.get_current_deployment_info"
        )
        mock_format_deployment_header = mocker.patch("urh.format_deployment_header")
        mock_menu_system = mocker.patch("urh._menu_system")
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        current_deployment_info = {
            "repository": "bazzite-nix",
            "version": "42.20231115.0",
        }

        mock_get_deployment_info.return_value = sample_deployment_info
        mock_get_current_deployment_info.return_value = current_deployment_info
        mock_format_deployment_header.return_value = (
            "Current deployment: bazzite-nix (42.20231115.0)"
        )
        mock_menu_system.show_menu.return_value = 1

        registry = CommandRegistry()
        registry._handle_pin([])

        mock_get_deployment_info.assert_called_once()
        mock_get_current_deployment_info.assert_called_once()
        mock_format_deployment_header.assert_called_once_with(current_deployment_info)
        mock_menu_system.show_menu.assert_called_once()
        mock_run_command.assert_called_once_with(
            ["sudo", "ostree", "admin", "pin", "1"]
        )
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_oci_client(self, mocker):
        """Test CommandRegistry integration with OCIClient."""
        mock_extract_repository = mocker.patch(
            "urh.extract_repository_from_url", return_value="test/repo"
        )
        mock_client_class = mocker.patch("urh.OCIClient")
        mock_sys_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")

        mock_instance = mocker.MagicMock()
        mock_instance.fetch_repository_tags.return_value = {"tags": ["tag1", "tag2"]}
        mock_client_class.return_value = mock_instance

        registry = CommandRegistry()
        registry._handle_remote_ls(["ghcr.io/test/repo:testing"])

        mock_extract_repository.assert_called_once_with("ghcr.io/test/repo:testing")
        mock_client_class.assert_called_once_with("test/repo")
        mock_instance.fetch_repository_tags.assert_called_once_with(
            "ghcr.io/test/repo:testing"
        )
        mock_print.assert_any_call("Tags for ghcr.io/test/repo:testing:")
        mock_print.assert_any_call("  tag1")
        mock_print.assert_any_call("  tag2")
        mock_sys_exit.assert_called_once_with(0)

    def test_command_registry_with_kargs_command(self, mocker):
        """Test CommandRegistry integration with kargs command."""
        mock_run_command = mocker.patch("urh.run_command", return_value=0)
        mock_sys_exit = mocker.patch("sys.exit")

        registry = CommandRegistry()
        registry._handle_kargs(["--append=console=ttyS0", "--delete=quiet"])

        mock_run_command.assert_called_once_with(
            ["sudo", "rpm-ostree", "kargs", "--append=console=ttyS0", "--delete=quiet"]
        )
        mock_sys_exit.assert_called_once_with(0)


class TestDeploymentIntegration:
    """Test deployment management integration."""

    def test_deployment_parsing_workflow(self):
        """Test complete deployment parsing workflow."""
        status_output = """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
"""

        # Parse deployment info
        deployments = parse_deployment_info(status_output)
        assert len(deployments) == 2

        # Get current deployment info
        current_deployment = None
        for deployment in deployments:
            if deployment.is_current:
                current_deployment = {
                    "repository": deployment.repository,
                    "version": deployment.version,
                }
                break

        assert current_deployment == {
            "repository": "wombatfromhell/bazzite-nix:testing",
            "version": "42.20231115.0",
        }

        # Format deployment header
        header = format_deployment_header(current_deployment)
        assert (
            header == "Current deployment: wombatfromhell/bazzite-nix (42.20231115.0)"
        )

    def test_deployment_info_with_pinned(self):
        """Test deployment parsing with pinned deployments."""
        status_output = """State: idle
AutomaticUpdates: disabled
Deployments:
● ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:testing
                   Digest: sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890
                  Version: 42.20231115.0 (2023-11-15T12:34:56Z)
                   Commit: abcdef1234567890abcdef1234567890abcdef12
                    OSName: bazzite
  ostree-image-signed:docker://ghcr.io/wombatfromhell/bazzite-nix:stable
                   Digest: sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
                  Version: 41.20231110.0 (2023-11-10T12:34:56Z)
                   Commit: 1234567890abcdef1234567890abcdef12345678
                    OSName: bazzite
        Pinned: yes
"""

        # Parse deployment info
        deployments = parse_deployment_info(status_output)
        assert len(deployments) == 2

        # Check first deployment (current, not pinned)
        assert deployments[0].deployment_index == 0
        assert deployments[0].is_current is True
        assert deployments[0].repository == "wombatfromhell/bazzite-nix:testing"
        assert deployments[0].version == "42.20231115.0"
        assert deployments[0].is_pinned is False

        # Check second deployment (not current, pinned)
        assert deployments[1].deployment_index == 1
        assert deployments[1].is_current is False
        assert deployments[1].repository == "wombatfromhell/bazzite-nix:stable"
        assert deployments[1].version == "41.20231110.0"
        assert deployments[1].is_pinned is True


class TestUtilityIntegration:
    """Test utility function integration."""

    def test_extract_functions_integration(self):
        """Test integration between extract functions."""
        url = "ghcr.io/wombatfromhell/bazzite-nix:testing"

        repository = extract_repository_from_url(url)
        context = extract_context_from_url(url)

        assert repository == "wombatfromhell/bazzite-nix"
        assert context == "testing"

    def test_run_command_integration(self, mocker):
        """Test run_command integration with subprocess."""
        mock_subprocess = mocker.patch("subprocess.run")
        mock_subprocess.return_value.returncode = 0

        cmd = ["echo", "hello"]
        result = run_command(cmd)

        assert result == 0
        mock_subprocess.assert_called_once_with(cmd, check=False)
