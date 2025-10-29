"""Unit tests for ublue-rebase-helper (urh.py)."""

import pytest
import sys
import os
from pytest_mock import MockerFixture

# Add the parent directory to sys.path so we can import urh
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from urh import (
    run_command,
    rebase_command,
    check_command,
    ls_command,
    rollback_command,
    pin_command,
    unpin_command,
    rm_command,
    help_command
)


class TestRunCommand:
    """Unit tests for the run_command function."""

    def test_run_command_success(self, mocker: MockerFixture):
        """Test run_command returns correct exit code when command succeeds."""
        mock_subprocess_run = mocker.patch('urh.subprocess.run')
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result

        result = run_command(['echo', 'hello'])
        assert result == 0
        mock_subprocess_run.assert_called_once_with(['echo', 'hello'], check=False)

    def test_run_command_failure(self, mocker: MockerFixture):
        """Test run_command returns correct exit code when command fails."""
        mock_subprocess_run = mocker.patch('urh.subprocess.run')
        mock_result = mocker.Mock()
        mock_result.returncode = 1
        mock_subprocess_run.return_value = mock_result

        result = run_command(['false'])
        assert result == 1

    def test_run_command_file_not_found(self, mocker: MockerFixture):
        """Test run_command handles FileNotFoundError."""
        mock_subprocess_run = mocker.patch('urh.subprocess.run', side_effect=FileNotFoundError)
        mock_print = mocker.patch('urh.print')

        result = run_command(['nonexistent-command'])
        assert result == 1
        mock_print.assert_called_once_with("Command not found: nonexistent-command")


class TestRebaseCommand:
    """Unit tests for the rebase_command function."""

    def test_rebase_command_with_url(self, mocker: MockerFixture):
        """Test rebase_command with valid URL."""
        mock_run_command = mocker.patch('urh.run_command', return_value=0)
        mock_sys_exit = mocker.patch('urh.sys.exit')

        rebase_command(['some-url'])
        mock_run_command.assert_called_once_with(['sudo', 'rpm-ostree', 'rebase', 'some-url'])
        mock_sys_exit.assert_called_once_with(0)

    def test_rebase_command_no_args(self, mocker: MockerFixture):
        """Test rebase_command prints usage when no args provided."""
        mock_print = mocker.patch('urh.print')

        rebase_command([])
        mock_print.assert_called_once_with("Usage: urh.py rebase <url>")


class TestCheckCommand:
    """Unit tests for the check_command function."""

    def test_check_command(self, mocker: MockerFixture):
        """Test check_command executes correct command."""
        mock_run_command = mocker.patch('urh.run_command', return_value=0)
        mock_sys_exit = mocker.patch('urh.sys.exit')

        check_command([])
        mock_run_command.assert_called_once_with(['sudo', 'rpm-ostree', 'upgrade', '--check'])
        mock_sys_exit.assert_called_once_with(0)


class TestLsCommand:
    """Unit tests for the ls_command function."""

    def test_ls_command(self, mocker: MockerFixture):
        """Test ls_command executes correct command."""
        mock_run_command = mocker.patch('urh.run_command', return_value=0)
        mock_sys_exit = mocker.patch('urh.sys.exit')

        ls_command([])
        mock_run_command.assert_called_once_with(['rpm-ostree', 'status', '-v'])
        mock_sys_exit.assert_called_once_with(0)


class TestRollbackCommand:
    """Unit tests for the rollback_command function."""

    def test_rollback_command(self, mocker: MockerFixture):
        """Test rollback_command executes correct command."""
        mock_run_command = mocker.patch('urh.run_command', return_value=0)
        mock_sys_exit = mocker.patch('urh.sys.exit')

        rollback_command([])
        mock_run_command.assert_called_once_with(['sudo', 'rpm-ostree', 'rollback'])
        mock_sys_exit.assert_called_once_with(0)


class TestPinCommand:
    """Unit tests for the pin_command function."""

    def test_pin_command_with_number(self, mocker: MockerFixture):
        """Test pin_command with valid number."""
        mock_run_command = mocker.patch('urh.run_command', return_value=0)
        mock_sys_exit = mocker.patch('urh.sys.exit')

        pin_command(['1'])
        mock_run_command.assert_called_once_with(['sudo', 'ostree', 'admin', 'pin', '1'])
        mock_sys_exit.assert_called_once_with(0)

    def test_pin_command_no_args(self, mocker: MockerFixture):
        """Test pin_command prints usage when no args provided."""
        mock_print = mocker.patch('urh.print')

        pin_command([])
        mock_print.assert_called_once_with("Usage: urh.py pin <num>")

    def test_pin_command_invalid_number(self, mocker: MockerFixture):
        """Test pin_command handles invalid number."""
        mock_print = mocker.patch('urh.print')

        pin_command(['invalid'])
        mock_print.assert_called_once_with("Invalid deployment number: invalid")


class TestUnpinCommand:
    """Unit tests for the unpin_command function."""

    def test_unpin_command_with_number(self, mocker: MockerFixture):
        """Test unpin_command with valid number."""
        mock_run_command = mocker.patch('urh.run_command', return_value=0)
        mock_sys_exit = mocker.patch('urh.sys.exit')

        unpin_command(['2'])
        mock_run_command.assert_called_once_with(['sudo', 'ostree', 'admin', 'pin', '-u', '2'])
        mock_sys_exit.assert_called_once_with(0)

    def test_unpin_command_no_args(self, mocker: MockerFixture):
        """Test unpin_command prints usage when no args provided."""
        mock_print = mocker.patch('urh.print')

        unpin_command([])
        mock_print.assert_called_once_with("Usage: urh.py unpin <num>")

    def test_unpin_command_invalid_number(self, mocker: MockerFixture):
        """Test unpin_command handles invalid number."""
        mock_print = mocker.patch('urh.print')

        unpin_command(['invalid'])
        mock_print.assert_called_once_with("Invalid deployment number: invalid")


class TestRmCommand:
    """Unit tests for the rm_command function."""

    def test_rm_command_with_number(self, mocker: MockerFixture):
        """Test rm_command with valid number."""
        mock_run_command = mocker.patch('urh.run_command', return_value=0)
        mock_sys_exit = mocker.patch('urh.sys.exit')

        rm_command(['3'])
        mock_run_command.assert_called_once_with(['sudo', 'ostree', 'cleanup', '-r', '3'])
        mock_sys_exit.assert_called_once_with(0)

    def test_rm_command_no_args(self, mocker: MockerFixture):
        """Test rm_command prints usage when no args provided."""
        mock_print = mocker.patch('urh.print')

        rm_command([])
        mock_print.assert_called_once_with("Usage: urh.py rm <num>")

    def test_rm_command_invalid_number(self, mocker: MockerFixture):
        """Test rm_command handles invalid number."""
        mock_print = mocker.patch('urh.print')

        rm_command(['invalid'])
        mock_print.assert_called_once_with("Invalid deployment number: invalid")


class TestHelpCommand:
    """Unit tests for the help_command function."""

    def test_help_command(self, mocker: MockerFixture):
        """Test help_command prints help information."""
        mock_print = mocker.patch('urh.print')

        help_command([])
        # Check that print was called at least once
        assert mock_print.called