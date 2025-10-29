# ublue-rebase-helper (urh.py) Design Document

## Overview

The ublue-rebase-helper (urh.py) is a wrapper utility that provides a simplified interface for rpm-ostree and ostree commands. It leverages the gum utility to provide interactive menus and user-friendly prompts when needed.

## Purpose

This utility is designed to:
- Simplify common rpm-ostree and ostree operations
- Provide an alternative to memorizing complex commands
- Offer interactive prompts for command selection using gum
- Ensure proper privilege escalation with sudo for system modification commands

## Command Structure

### Primary Commands

#### `rebase <url>`
- **Wraps**: `sudo rpm-ostree rebase <url>`
- **Function**: Rebase the system to a specified container image URL
- **Requires sudo**: Yes

#### `check`
- **Wraps**: `sudo rpm-ostree upgrade --check`
- **Function**: Check for available updates without applying them
- **Requires sudo**: Yes

#### `ls`
- **Wraps**: `rpm-ostree status -v`
- **Function**: List deployments with detailed information
- **Requires sudo**: No

#### `rollback`
- **Wraps**: `sudo rpm-ostree rollback`
- **Function**: Roll back to the previous deployment
- **Requires sudo**: Yes

### Deployment Management Commands

#### `pin <num>`
- **Wraps**: `sudo ostree admin pin <num>`
- **Function**: Pin a specific deployment by number to prevent automatic cleanup
- **Requires sudo**: Yes

#### `unpin <num>`
- **Wraps**: `sudo ostree admin pin -u <num>`
- **Function**: Unpin a specific deployment by number
- **Requires sudo**: Yes

#### `rm <num>`
- **Wraps**: `sudo ostree cleanup -r <num>`
- **Function**: Remove a specific deployment by number
- **Requires sudo**: Yes

### Menu System

When no command is provided, the utility uses gum to display an interactive menu with available commands. If gum is not available, it falls back to displaying a list of available commands.

## Implementation Details

### Command Execution

All commands are executed using `subprocess.run()` with proper error handling. The utility returns the exit code from the underlying commands to maintain proper exit status behavior.

### Privilege Escalation

Commands that modify the system state require elevated privileges using `sudo`. The utility automatically prepends `sudo` to these commands.

### Error Handling

- Invalid deployment numbers are caught and reported with user-friendly error messages
- Missing arguments result in usage information being displayed
- Command not found errors are caught and reported appropriately

## Dependencies

- `rpm-ostree`: Core system for ostree-based updates
- `ostree`: Core ostree functionality
- `gum`: For interactive UI elements and menus
- `python3.13+`: Minimum Python version requirement

## Security Considerations

- All system modification commands run with appropriate elevated privileges via sudo
- Input validation is performed on numeric arguments to prevent command injection
- The utility operates within the established rpm-ostree/ostree security model

## Testing Strategy

The project follows a comprehensive testing strategy with three distinct test categories:

### Unit Tests (`test_units.py`)
- Test individual functions in isolation
- Use mocking to isolate the function under test
- Focus on pure logic and error handling within each function
- Fast execution with no external dependencies
- Located in `tests/test_units.py`

### Integration Tests (`test_integrations.py`)
- Test how different functions work together
- Validate interactions between modules/components
- May involve testing integration with external tools like `gum`
- Located in `tests/test_integrations.py`

### End-to-End Tests (`test_e2e.py`)
- Test complete workflows and user journeys
- Validate the main entry point and command flow
- Simulate real usage scenarios from user input to function calls
- Located in `tests/test_e2e.py`