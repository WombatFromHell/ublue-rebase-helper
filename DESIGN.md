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
- **Interactive submenu**: When no `<url>` is specified, provides a submenu of common container URLs with arrow key navigation for selection:
  - `ghcr.io/wombatfromhell/bazzite-nix:testing` (default option - first in list)
  - `ghcr.io/wombatfromhell/bazzite-nix:stable`
  - `ghcr.io/ublue-os/bazzite:stable`
  - `ghcr.io/ublue-os/bazzite:testing`
  - `ghcr.io/ublue-os/bazzite:unstable`
  - `ghcr.io/astrovm/amyos:latest`
- **Usage**: Users can navigate with arrow keys or select directly by number; press ESC to cancel

#### `remote-ls <url>`

- **Function**: List available tags for a container image from a remote registry
- **Uses**: Extracts repository name from URL (e.g., from `ghcr.io/user/repo:tag` extracts `user/repo`) and uses `OCIClient.get_all_tags()` to fetch tags from the public `tags/list` endpoint with pagination support by following Link headers. Tags are filtered using rules defined in the TOML configuration file (`~/.config/urh.toml`) to remove SHA256 references, aliases (latest, testing, stable, unstable), and signature tags (ending in `.sig`). When the URL specifies a context like `:testing`, `:stable`, or `:unstable`, ONLY tags prefixed with that context (e.g., `testing-<tag>`, `stable-<tag>`, `unstable-<tag>`) are shown in the results. For the `astrovm/amyos` repository, the `:latest` context is also recognized and will filter to show only YYYYMMDD format tags (which are the transformed version of the original `latest.YYYYMMDD` tags). Both context-aware and non-context filtering include deduplication to avoid duplicate versions. When no context is specified (e.g., `ghcr.io/user/repo`), both prefixed and non-prefixed tags are shown but duplicates with the same version are deduplicated (preferring prefixed versions when available). Tags following the formats `<XX>.<YYYY><MM><DD>[.<SUBVER>]` or `<YYYY><MM><DD>[.<SUBVER>]` (with optional `testing-`, `stable-`, or `unstable-` prefixes) are sorted by version series and date, with higher subversions taking precedence. Results are limited to a maximum of 30 tags (configurable via TOML settings).
- **Requires sudo**: No
- **Interactive submenu**: When no `<url>` is specified, uses the MenuSystem to display a submenu of container URLs loaded from the TOML configuration file, similar to the rebase command options

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

- **Wraps**: `sudo rpm-ostree cleanup -r <num>`
- **Function**: Remove a specific deployment by number
- **Requires sudo**: Yes
- **Interactive submenu**: When no `<num>` is specified, provides a submenu showing all deployments with their version information that allows users to select which deployment to remove. The selection maps to the appropriate deployment index.

### Menu System

When no command is provided, the utility uses gum to display an interactive menu with available commands. If gum is not available, it falls back to displaying a list of available commands.

The MenuSystem class handles both TTY and non-TTY contexts, with support for gum-based interactive menus and text-based fallback menus. It supports ESC key handling for navigation between menus.

### Menu Navigation Behavior

When using interactive menus, the utility supports intuitive navigation:

- Pressing ESC in the main menu will exit the program
- Pressing ESC in any submenu will return the user to the main menu
- When ESC is pressed in a submenu (gum choose), a `MenuExitException(is_main_menu=False)` is raised
- When ESC is pressed in the main menu (gum choose), a `MenuExitException(is_main_menu=True)` is raised
- These exceptions are caught by the main menu loop, which then either exits the program (main menu) or redisplays the main menu (submenus)
- This provides a consistent user experience where ESC acts as a "back" function in submenus and "exit" in the main menu

### Persistent Header Feature

The utility includes a persistent header that displays current deployment information from `rpm-ostree status`:

- The header is displayed above the main command menu and in all submenus
- It shows the current repository and version in the format: `{repository} ({version})`
- The information is parsed from the output of `rpm-ostree status` command
- Functions involved: `get_current_deployment_info()` and `format_deployment_header()`
- The header persists when navigating between menus (e.g., when returning from a submenu to the main menu)
- The header is displayed using the `persistent_header` parameter in the `MenuSystem.show_menu()` function

- **Header Parsing Process**: The header information is extracted by first calling `get_status_output()` to get the raw output of `rpm-ostree status -v`, then parsing that output with `parse_deployment_info()` to extract all deployments, and finally filtering to find the current deployment (marked with ● symbol)
- **Repository Extraction**: The repository name is extracted from the `ostree-image-signed:docker://` line in the rpm-ostree status output, taking everything after the registry URL (e.g., from `ostree-image-signed:docker://ghcr.io/user/repo:tag`, it extracts `user/repo:tag`)
- **Version Extraction**: The version information is extracted from the Version line in the deployment details, with special handling for metadata that may appear in parentheses
- **Current Deployment Detection**: The current deployment is identified by looking for the ● symbol that rpm-ostree uses to mark the currently booted deployment
- **Error Handling**: If deployment information cannot be retrieved, a default message "Current deployment: System Information: Unable to retrieve deployment info" is displayed
- **Header Formatting**: The `format_deployment_header()` function formats the repository and version into a user-friendly string that shows the repository name (without the tag) and the version in parentheses
- **Persistent Display**: The header is passed as the `persistent_header` parameter to all menu system calls, ensuring it appears consistently across main menu and all submenus

## Configuration System

The ublue-rebase-helper uses a TOML-based configuration system for customizable filter rules and options.

### Configuration File Location

The configuration file is located at:

- `$XDG_CONFIG_HOME/urh.toml` (if XDG_CONFIG_HOME is set)
- `$HOME/.config/urh.toml` (fallback location)

The application automatically creates a default configuration file if one doesn't exist.

### Configuration Classes

The configuration system is implemented using dataclasses:

- `URHConfig`: Main configuration class
- `RepositoryConfig`: Configuration for a specific repository
- `ContainerURLsConfig`: Configuration for container URLs
- `SettingsConfig`: Global settings configuration
- `ConfigManager`: Manages configuration loading and saving

### Repository Filter Rules Configuration

Repository-specific filter rules are defined in the `[[repository]]` section of the TOML file as an array of tables. Each repository can have:

- `name`: The repository name (required field)
- `include_sha256_tags`: Whether to include SHA256 hash tags (default: false)
- `filter_patterns`: List of regex patterns for tags to be filtered out
- `ignore_tags`: List of exact tag names to be filtered out
- `transform_patterns`: List of pattern/replacement pairs for tag transformations (e.g., for astrovm/amyos)
- `latest_dot_handling`: Optional handling for latest. tags

### Container URL Configuration

The container URLs available in the rebase and remote-ls submenus are defined in the `[container_urls]` section:

- `default`: The default container URL to use
- `options`: List of available container URLs in the submenu

### Settings Configuration

Global settings are defined in the `[settings]` section:

- `max_tags_display`: Maximum number of tags to display (default: 30)
- `debug_mode`: Enable debug output (default: false)

## Implementation Details

### Command Registry

Commands are defined using a centralized command registry (`CommandRegistry`) which maps command names to their definitions (including description, sudo requirement, and handler function). This approach reduces duplication and makes it easier to add new commands.

The `CommandDefinition` dataclass defines command properties and behavior, enabling centralized command registration. Each command is registered with its name, description, handler function, sudo requirement, and whether it has a submenu.

- **Command Definition**: Uses `CommandDefinition` dataclass to define command properties (name, description, handler, requires_sudo, has_submenu)
- **Centralized Registration**: All commands are registered in `CommandRegistry._register_commands()` method
- **Handler Functions**: Each command has a dedicated handler function (e.g., `_handle_rebase`, `_handle_pin`) that implements the command-specific logic
- **Sudo Integration**: Automatically prepends `sudo` to commands that require elevated privileges
- **Submenu Integration**: Commands with submenus (like rebase, pin, unpin, rm) provide interactive menu options when no arguments are provided
- **Argument Parsing**: Supports both direct command execution with arguments and interactive menu selection
- **Exit Code Handling**: Properly handles exit codes from underlying system commands using `sys.exit()`
- **Error Handling**: Includes validation for numeric arguments to prevent command injection and provides user-friendly error messages

### Command Execution

All commands are executed using `run_command()` with proper error handling. The utility returns the exit code from the underlying commands to maintain proper exit status behavior.

### Type Safety Requirements

The codebase follows strict typing requirements to improve maintainability and reduce bugs:

- Functions that perform UI display operations should return `None` rather than empty strings
- Functions that return data should have consistent return types (e.g., `Optional[str]`, `Optional[int]`) rather than mixing types
- Functions should return a single valid type or `None` and never return blank strings as a form of "no value"
- Avoid union return types like `Union[str, None]` where possible in favor of proper `Optional[T]` annotations
- Separate business logic from UI presentation by having distinct functions for data processing and display

The implementation uses several type aliases for better type safety:

- `DateVersionKey`: Type alias for date-based version sorting keys
- `AlphaVersionKey`: Type alias for alphanumeric version sorting keys
- `VersionSortKey`: Union type for version sorting keys
- `TagFilterFunc`: Type alias for tag filtering functions
- `TagTransformFunc`: Type alias for tag transformation functions

### OCIClient Implementation Details

The `OCIClient` class provides functionality for interacting with OCI Container Registries such as ghcr.io:

- **Token Management**: Uses `OCITokenManager` for OAuth2 authentication with token caching to `/tmp/` using a single shared filename (`/tmp/oci_ghcr_token`) for all GHCR requests
- **Pagination Support**: Implements Link header following to retrieve all tags beyond the initial 200 limit by parsing Link headers like `Link: </v2/user/repo/tags/list?last=tag_value&n=200>; rel="next"` and continuing until no more next links are present
- **Tag Processing**: Includes filtering, sorting, and deduplication logic for container image tags through the `OCITagFilter` class
- **Error Handling**: Includes retry mechanisms for expired/invalid tokens, with validation of token before use and automatic refresh when needed
- **HTTP Headers**: Uses curl to fetch headers and process Link headers for pagination
- **Caching Mechanism**: Implements token caching with `OCITokenManager` that caches tokens to a shared file for reuse across sessions
- **Token Validation**: Performs proactive token validation and refresh when a 403 (Forbidden) error is encountered
- **Header Processing**: Manages HTTP headers using temporary files to fetch and parse Link headers for pagination
- **Page Fetching**: Uses curl with proper authorization headers to fetch individual pages of tags
- **URL Handling**: Properly handles relative and absolute URLs when following pagination links

### OCITagFilter Implementation

The `OCITagFilter` class handles tag filtering and sorting logic:

- `should_filter_tag()`: Determines if a tag should be filtered out based on repository configuration
- `transform_tag()`: Transforms a tag based on repository rules (e.g., converting latest.YYYYMMDD to YYYYMMDD)
- `filter_and_sort_tags()`: Filters and sorts tags according to repository configuration
- `_context_filter_tags()`: Filters tags based on context (testing, stable, unstable, latest)
- `_deduplicate_tags_by_version()`: Deduplicates tags by version, preferring prefixed versions when available
- `_sort_tags()`: Sorts tags based on version patterns with special handling for different tag formats
- **Version Key Creation**: Creates proper version keys for sorting different tag formats (context-prefixed, date-only, version formats)
- **Context-aware Sorting**: Prioritizes context-prefixed tags (testing-, stable-, unstable-) over non-prefixed tags during sorting
- **Date-based Sorting**: Handles YYYYMMDD date formats and XX.YYYYMMDD version formats with subversion support
- **Alphabetical Fallback**: Provides alphabetical sorting for unrecognized tag formats

### Context-Aware Tag Filtering

The implementation supports context-aware tag filtering for different repositories:

- For standard repositories, when a context like `:testing`, `:stable`, or `:unstable` is specified, only tags prefixed with that context are shown
- For the `astrovm/amyos` repository, the `:latest` context is recognized and filters to show only YYYYMMDD format tags
- The `latest_dot_handling` configuration option can be set to "transform_dates_only" for special handling of latest. tags

### Exception Handling

The implementation defines several custom exception classes:

- `URHError`: Base exception for urh errors
- `ConfigurationError`: Raised when configuration is invalid
- `OCIError`: Raised when OCI operations fail
- `MenuExitException`: Exception raised when ESC is pressed in a menu, with an `is_main_menu` flag to distinguish between main menu and submenu exits

### Privilege Escalation

Commands that modify the system state require elevated privileges using `sudo`. The utility automatically prepends `sudo` to these commands.

### Error Handling

- Invalid deployment numbers are caught and reported with user-friendly error messages
- Missing arguments result in usage information being displayed
- Command not found errors are caught and reported appropriately

### Deployment Information Parsing

The utility parses deployment information from `rpm-ostree status -v` output using regex patterns to extract:

- Deployment index based on order in the output
- Current deployment status (marked with ●)
- Repository name from the `ostree-image-signed:docker://` line
- Version information from the Version line
- Pinned status from Pinned: yes flag

- **DeploymentInfo Class**: Uses `DeploymentInfo` NamedTuple to structure deployment data (deployment_index, is_current, repository, version, is_pinned)
- **Index Assignment**: Assigns deployment index based on order in the output, with the most recent deployment getting the highest index
- **Current Status Detection**: Identifies current deployment using the ● character in the rpm-ostree status output
- **Repository Extraction**: Extracts repository name by parsing the `ostree-image-signed:docker://` line
- **Version Parsing**: Parses version information and handles various version formats including context-prefixed versions
- **Pinned Status**: Detects pinned status by looking for "Pinned: yes" in the deployment details
- **Deployment Filtering**: Commands like `pin` show only unpinned deployments, while `unpin` shows only pinned deployments in their menus
- **Display Ordering**: Deploys are displayed in reverse chronological order (newest first) in the rm command menu
- **Metadata Handling**: Properly handles additional metadata in parentheses that may appear after version information

### Menu System Architecture

The MenuSystem supports multiple interface modes:

- **Gum Mode**: Uses gum choose for interactive menus when gum is available
- **Text Mode**: Provides numbered list selection when gum is not available or in non-TTY environments
- **TTY Detection**: Uses `os.isatty()` to determine whether to use interactive or text mode
- **MenuItem Classes**: Uses `MenuItem` and `ListItem` classes to format display options differently
- **Exception Handling**: Uses `MenuExitException` to handle ESC key presses with `is_main_menu` flag to distinguish between main menu and submenu exits
- **Persistent Headers**: Supports persistent headers using the `persistent_header` parameter that displays current deployment information above menus
- **Menu Navigation**: Implements ESC key handling for navigation between menus with consistent user experience
- **Item Selection**: Supports both key-based and value-based return from menu items using the item's meaningful key or value
- **Fallback Mechanism**: Provides seamless fallback from gum to text mode when gum is not available or when running in automated environments

## Dependencies

- `rpm-ostree`: Core system for ostree-based updates
- `ostree`: Core ostree functionality
- `gum`: For interactive UI elements and menus
- `python3.13+`: Minimum Python version requirement
- `curl`: Required for OCI registry interactions (used by OCIClient)
- `tomllib`: For TOML configuration parsing (built-in in Python 3.11+)

## Security Considerations

- All system modification commands run with appropriate elevated privileges via sudo
- Input validation is performed on numeric arguments to prevent command injection
- The utility operates within the established rpm-ostree/ostree security model
- Token caching is done to `/tmp/` with appropriate error handling
- Commands are executed through subprocess with proper argument separation

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
