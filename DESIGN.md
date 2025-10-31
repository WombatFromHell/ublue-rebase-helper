# ublue-rebase-helper (urh.py) Design Document

## Overview

The ublue-rebase-helper (urh.py) is a wrapper utility that provides a simplified interface for rpm-ostree and ostree commands. It leverages the gum utility to provide interactive menus and user-friendly prompts when needed.

## Planning and Change Management

All modifications to this project, whether they involve code changes, feature additions, or refactoring, must follow a structured planning process:

- Any significant changes to the codebase must be planned with clear implementation steps before execution
- All plans must be presented to and approved by the user before implementation begins
- No destructive changes may be applied without explicit user consent
- Design documents (including this one) must be updated when implementation decisions change

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
- **Interactive submenu**: When no `<url>` is specified, provides a submenu of common container URLs with number prefixes for direct selection:
  - `1: ghcr.io/ublue-os/bazzite:stable`
  - `2: ghcr.io/ublue-os/bazzite:testing`
  - `3: ghcr.io/ublue-os/bazzite:unstable`
  - `*4: ghcr.io/wombatfromhell/bazzite-nix:testing` (default option marked with *)
  - `5: ghcr.io/wombatfromhell/bazzite-nix:stable`
  - `6: ghcr.io/astrovm/amyos:latest`
- **Usage**: Users can navigate with arrow keys or select directly by number; press ESC to cancel

#### `remote-ls <url>`
- **Function**: List available tags for a container image from a remote registry
- **Uses**: Extracts repository name from URL (e.g., from `ghcr.io/user/repo:tag` extracts `user/repo`) and uses `OCIClient.get_all_tags()` to fetch tags from the public `tags/list` endpoint with pagination support by following Link headers. Tags are filtered to remove SHA256 references, aliases (latest, testing, stable, unstable), and signature tags (ending in `.sig`). When the URL specifies a context like `:testing`, `:stable`, or `:unstable`, ONLY tags prefixed with that context (e.g., `testing-<tag>`, `stable-<tag>`, `unstable-<tag>`) are shown in the results. When no context is specified (e.g., `ghcr.io/user/repo`), both prefixed and non-prefixed tags are shown but duplicates with the same version are deduplicated (preferring prefixed versions when available). Tags following the formats `<XX>.<YYYY><MM><DD>[.<SUBVER>]` or `<YYYY><MM><DD>[.<SUBVER>]` (with optional `testing-`, `stable-`, or `unstable-` prefixes) are sorted by version series and date, with higher subversions taking precedence. Results are limited to a maximum of 30 tags.
- **Requires sudo**: No
- **Interactive submenu**: When no `<url>` is specified, uses `show_remote_ls_submenu()` to display a submenu of common container URLs for tag listing, similar to the rebase command options

#### `check`
- **Wraps**: `rpm-ostree upgrade --check`
- **Function**: Check for available updates without applying them
- **Requires sudo**: No

#### `upgrade`
- **Wraps**: `sudo rpm-ostree upgrade`
- **Function**: Upgrade the system to the latest available version
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
- **Interactive submenu**: When no `<num>` is specified, provides a submenu showing deployments with their version information (excluding already pinned deployments) that allows users to select which deployment to pin. The selection maps to the appropriate deployment index.

#### `unpin <num>`
- **Wraps**: `sudo ostree admin pin -u <num>`
- **Function**: Unpin a specific deployment by number
- **Requires sudo**: Yes
- **Interactive submenu**: When no `<num>` is specified, provides a submenu showing deployments with their version information (only showing already pinned deployments) that allows users to select which deployment to unpin. The selection maps to the appropriate deployment index.

#### `rm <num>`
- **Wraps**: `sudo ostree cleanup -r <num>`
- **Function**: Remove a specific deployment by number
- **Requires sudo**: Yes
- **Interactive submenu**: When no `<num>` is specified, provides a submenu showing all deployments with their version information that allows users to select which deployment to remove. The selection maps to the appropriate deployment index.

### Menu System

When no command is provided, the utility uses gum to display an interactive menu with available commands. If gum is not available, it falls back to displaying a list of available commands.

### Submenu Implementation Details

For commands that require submenu functionality (like `rebase`), the utility uses gum with proper subprocess configuration to ensure the interactive UI is displayed correctly. The subprocess must capture stdout to receive user selections, but stderr must not be captured to allow the gum interface to be visible in TTY contexts.

The submenu display functions (for non-TTY and gum-not-found scenarios) are now created using the `create_submenu_display_functions()` factory function, which reduces code duplication across different submenu types (command menu, container URL selection, deployment selection).

### Menu Navigation Behavior

When using interactive menus, the utility supports intuitive navigation:
- Pressing ESC in the main menu will exit the program
- Pressing ESC in any submenu will return the user to the main menu
- When ESC is pressed in a submenu (gum choose), a `MenuExitException(is_main_menu=False)` is raised
- When ESC is pressed in the main menu (gum choose), a `MenuExitException(is_main_menu=True)` is raised
- These exceptions are caught by the main menu loop, which then either exits the program (main menu) or redisplays the main menu (submenus)
- This provides a consistent user experience where ESC acts as a "back" function in submenus and "exit" in the main menu

## Implementation Details

### Command Execution

All commands are executed using `subprocess.run()` with proper error handling. The utility returns the exit code from the underlying commands to maintain proper exit status behavior.

Commands are now defined using a centralized command registry (`get_command_registry()`) which maps command names to their definitions (including description, sudo requirement, argument parser, submenu function, and command builder). This approach reduces duplication and makes it easier to add new commands.

### Type Safety Requirements

The codebase follows strict typing requirements to improve maintainability and reduce bugs:

- Functions that perform UI display operations should return `None` rather than empty strings
- Functions that return data should have consistent return types (e.g., `Optional[str]`, `Optional[int]`) rather than mixing types
- Functions should return a single valid type or `None` and never return blank strings as a form of "no value"
- Avoid union return types like `Union[str, None]` where possible in favor of proper `Optional[T]` annotations
- Separate business logic from UI presentation by having distinct functions for data processing and display

### Code Reusability

To reduce code duplication and improve maintainability, the codebase uses common utility functions:

- `run_gum_submenu()` - A generic function for displaying interactive menus with gum that handles both TTY and non-TTY contexts, as well as "gum not found" scenarios
- `handle_command_with_submenu()` - A generic function for handling commands that can accept arguments or show submenus, reducing duplication in rebase, pin, unpin, and rm commands
- `create_submenu_display_functions()` - A factory function that creates display functions for non-TTY and gum-not-found scenarios, reducing duplication across various submenu functions
- `CommandDefinition` - A data class that defines command properties and behavior, enabling centralized command registration and reducing duplication in command handling
- `_create_version_sort_key()` - A consolidated function for tag version sorting that handles both basic and context-aware sorting, reducing duplication in OCIClient methods
- `_parse_response_headers_and_body()` and `_extract_link_header()` - Utility functions in OCIClient to reduce duplication in HTTP response parsing

### Privilege Escalation

Commands that modify the system state require elevated privileges using `sudo`. The utility automatically prepends `sudo` to these commands.

### Error Handling

- Invalid deployment numbers are caught and reported with user-friendly error messages
- Missing arguments result in usage information being displayed
- Command not found errors are caught and reported appropriately

### OCIClient Implementation Details

The `OCIClient` class provides functionality for interacting with OCI Container Registries such as ghcr.io:

- **Token Management**: Uses OAuth2 authentication with token caching to `/tmp/` using a single shared filename (`/tmp/oci_ghcr_token`) for all GHCR requests
- **Pagination Support**: Implements Link header following to retrieve all tags beyond the initial 200 limit by parsing Link headers like `Link: </v2/user/repo/tags/list?last=tag_value&n=200>; rel="next"` and continuing until no more next links are present
- **Tag Processing**: Includes filtering, sorting, and deduplication logic for container image tags
- **Error Handling**: Includes retry mechanisms for expired/invalid tokens
- **Code Reusability**: Implements the DRY principle through shared methods:
  - `_fetch_single_page_tags()`: Handles authenticated requests, response parsing, and token refresh retry logic for both single-page requests (`get_tags`) and paginated requests (`get_all_tags`)
  - Shared version parsing helper functions: `_extract_prefix_and_clean_tag()` and `_parse_version_components()` to avoid duplication in sorting functions
  - Consolidated version sorting with `_create_version_sort_key()` function that handles both basic and context-aware sorting
  - Response parsing utilities `_parse_response_headers_and_body()` and `_extract_link_header()` to eliminate duplication in HTTP response processing
- **Architecture**: Uses a shared private method to eliminate code duplication between `get_tags()` and `get_all_tags()` methods, with `get_tags()` handling single-page requests and `get_all_tags()` using the shared method in its pagination loop

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

### Shared Test Configuration (`conftest.py`)

To reduce code duplication and improve maintainability, the project uses a `conftest.py` file in the tests directory that contains:

- Common path setup for all test files (sys.path manipulation)
- Shared fixtures for common mocking patterns
- Standardized test utilities and helper functions
- Dependency injection fixtures for testing functions with external dependencies

#### Conftest.py Structure

The `conftest.py` file includes the following shared fixtures:

- `mock_is_tty_true` and `mock_is_tty_false`: Pre-configured fixtures for mocking TTY detection
- `mock_subprocess_result`: Factory fixture for creating mock subprocess results
- `mock_subprocess_run_success` and `mock_subprocess_run_failure`: Standardized subprocess run mocks
- `mock_print`: Pre-configured mock for the print function

Each test file still needs to import the necessary functions from the urh module, but they benefit from:
- Centralized path setup (no need to repeat sys.path manipulation in each file)
- Access to standardized fixtures defined in conftest.py
- Cleaner test code with no duplicated fixture definitions

#### Conftest.py Usage Requirement

When modifying or adding tests to this project, developers must leverage the shared fixtures in `tests/conftest.py` whenever appropriate. Any new common fixtures that may benefit multiple test files should be added to `conftest.py` rather than being defined in individual test modules to maintain consistency and reduce code duplication.

### Test Parametrization

When writing tests that cover similar functionality with different input values, prefer pytest's parametrization feature rather than creating multiple discrete test functions. This approach reduces code duplication and makes test maintenance easier. Only create separate tests when the code concerns are fundamentally different.

The test suite should leverage parametrization to consolidate similar test scenarios, such as:
- Testing command functions with different input parameters
- Testing error handling for various error conditions
- Testing submenu functionality with different return values
- Testing commands that follow similar patterns (like pin, unpin, rm which all take deployment numbers)

### Test Function Naming

When test functions are similarly named yet test different code concerns, each test function name should be changed to concisely reflect what the test's specific code concern is. This prevents tests from shadowing each other and makes it clear what each test is verifying.