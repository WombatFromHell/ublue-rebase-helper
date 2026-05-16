"""
Tests for privilege escalation command selection (sudo).

Covers the get_elevation_command function that determines whether to use
sudo, and build_command which prepends it when elevation is required.
"""

from pytest_mock import MockerFixture

from src.urh.system import build_command, get_elevation_command


def _reset_system_cache():
    """Reset the cached values in system module."""
    import src.urh.system as system_mod

    system_mod._cache_is_root = None


class TestGetElevationCommand:
    """Tests for get_elevation_command function."""

    def test_running_as_root_returns_none(self, mocker: MockerFixture):
        """When already running as root, return None (no elevation needed)."""
        _reset_system_cache()
        mocker.patch("src.urh.system.is_running_as_root", return_value=True)

        result = get_elevation_command()
        assert result is None

    def test_not_running_as_root_returns_sudo(self, mocker: MockerFixture):
        """When not running as root, return 'sudo'."""
        _reset_system_cache()
        mocker.patch("src.urh.system.is_running_as_root", return_value=False)

        result = get_elevation_command()
        assert result == "sudo"


class TestBuildCommand:
    """Tests for build_command function with sudo."""

    def test_build_command_uses_sudo_when_not_root(self, mocker: MockerFixture):
        """build_command should use sudo when not root and elevation required."""
        _reset_system_cache()
        mocker.patch("src.urh.system.is_running_as_root", return_value=False)

        result = build_command(True, ["rpm-ostree", "rebase"])
        assert result == ["sudo", "rpm-ostree", "rebase"]

    def test_build_command_no_elevation_when_root(self, mocker: MockerFixture):
        """build_command should not add elevation when already root."""
        _reset_system_cache()
        mocker.patch("src.urh.system.is_running_as_root", return_value=True)

        result = build_command(True, ["rpm-ostree", "rebase"])
        assert result == ["rpm-ostree", "rebase"]

    def test_build_command_no_elevation_when_not_required(self, mocker: MockerFixture):
        """build_command should not add elevation when requires_sudo is False."""
        _reset_system_cache()
        mocker.patch("src.urh.system.is_running_as_root", return_value=False)

        result = build_command(False, ["rpm-ostree", "status"])
        assert result == ["rpm-ostree", "status"]
