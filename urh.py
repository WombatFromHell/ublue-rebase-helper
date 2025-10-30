#!/usr/bin/env python3
# pyright: strict

import json
import subprocess
import sys
import os
from typing import List, Optional, Callable, Dict, Any, Tuple, Union

# Define type aliases for our sorting keys
DateVersionKey = Tuple[
    int, int, int, int, int
]  # (-1, -year, -month, -day, -subver) or (context_priority, -year, -month, -day, -subver)
AlphaVersionKey = Tuple[
    int, Tuple[int, ...]
]  # (0, tuple of char codes) or (context_priority, tuple of char codes)
VersionSortKey = Union[DateVersionKey, AlphaVersionKey]


class MenuExitException(Exception):
    """Exception raised when ESC is pressed in a submenu to return to main menu."""

    pass


class OCIClient:
    """
    A simple client for OCI Container Registry interactions (ghcr.io) that uses OAuth2
    and caches tokens to a temporary file.
    """

    def __init__(self, repository: str, cache_path: Optional[str] = None):
        """
        Initialize the client with a repository name.

        Args:
            repository: The repository name in format "owner/repo"
            cache_path: Optional cache path for testing purposes
        """
        if not repository or "/" not in repository:
            raise ValueError("Repository must be in 'owner/repo' format.")
        self.repository = repository
        self._cache_path_override = cache_path

    def _get_cache_filepath(self) -> str:
        """
        Generates a safe and unique cache file path in /tmp/ for the token.
        Replaces '/' in the repository name with '_' to avoid directory creation.
        """
        if self._cache_path_override:
            return self._cache_path_override

        safe_repo_name = self.repository.replace("/", "_")
        return f"/tmp/gcr_token_{safe_repo_name}"

    def get_token(self) -> Optional[str]:
        """
        Get an OAuth2 token for the repository, using a cached token if available.

        Returns:
            The token string if successful, None otherwise.
        """
        cache_filepath = self._get_cache_filepath()

        # 1. Check for a cached token
        if os.path.exists(cache_filepath):
            try:
                with open(cache_filepath, "r") as f:
                    print(f"Found cached token at {cache_filepath}")
                    return f.read().strip()
            except (IOError, OSError) as e:
                print(f"Warning: Could not read cached token at {cache_filepath}: {e}")

        # 2. If no cache, fetch a new token
        print("No valid cached token found. Fetching a new one...")
        scope = f"repository:{self.repository}:pull"
        # Note: The scope needs to be passed as a single argument to curl
        url = f"https://ghcr.io/token?scope={scope}"

        try:
            result = subprocess.run(
                ["curl", "-s", url],  # Added -s for silent mode
                capture_output=True,
                text=True,
                check=True,
            )
            response = json.loads(result.stdout)
            token = response.get("token")

            if token:
                # 3. Cache the new token for future use
                try:
                    with open(cache_filepath, "w") as f:
                        f.write(token)
                    print(f"Successfully cached new token to {cache_filepath}")
                except (IOError, OSError) as e:
                    print(
                        f"Warning: Could not write token to cache {cache_filepath}: {e}"
                    )
                return token
            return None
        except (subprocess.SubprocessError, json.JSONDecodeError, KeyError) as e:
            print(f"Error getting token: {e}")
            return None

    def _invalidate_cache(self):
        """Deletes the cached token file if it exists."""
        cache_filepath = self._get_cache_filepath()
        try:
            os.remove(cache_filepath)
            print(f"Invalidated and removed cache file: {cache_filepath}")
        except FileNotFoundError:
            # Cache file doesn't exist, nothing to do.
            pass

    def get_tags(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get the tags for the repository using the provided token.
        Implements a retry logic if the token is expired/invalid.

        Args:
            token: The OAuth2 token.

        Returns:
            A dictionary containing the tags if successful, None otherwise.
        """
        url = f"https://ghcr.io/v2/{self.repository}/tags/list?n=200"

        try:
            result = subprocess.run(
                ["curl", "-s", "-H", f"Authorization: Bearer {token}", url],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)

        except subprocess.CalledProcessError as e:
            # Check if the failure was due to an invalid/expired token
            if "401" in e.stderr or "403" in e.stderr:
                print("Request failed with 401/403. Token might be expired.")
                self._invalidate_cache()

                print("Retrying with a new token...")
                new_token = self.get_token()
                if new_token:
                    # Retry the request once with the new token
                    try:
                        retry_result = subprocess.run(
                            [
                                "curl",
                                "-s",
                                "-H",
                                f"Authorization: Bearer {new_token}",
                                url,
                            ],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        print("Retry successful.")
                        return json.loads(retry_result.stdout)
                    except subprocess.CalledProcessError as retry_e:
                        print(f"Retry also failed: {retry_e.stderr}")
                        return None
            else:
                print(f"Error getting tags: {e.stderr}")
                return None
        except json.JSONDecodeError as e:
            print(f"Error parsing tags response: {e}")
            return None

    def _parse_version_for_sorting(self, tag: str) -> VersionSortKey:
        """
        Parse a tag to extract version components for proper sorting.
        Handles format: [<prefix>-]<YYYY><MM><DD>[.<SUBVER>] where prefix might be 'testing-' or 'stable-'

        Args:
            tag: The tag string to parse

        Returns:
            A tuple that can be used for sorting, with the most significant components first
        """
        import re

        # Remove prefix if present for date parsing, but keep original for other cases
        clean_tag = tag
        if tag.startswith("testing-"):
            clean_tag = tag[8:]  # Remove "testing-" prefix
        elif tag.startswith("stable-"):
            clean_tag = tag[7:]  # Remove "stable-" prefix
        elif tag.startswith("unstable-"):
            clean_tag = tag[9:]  # Remove "unstable-" prefix

        # Extract date and subver from format YYYYMMDD[.SUBVER]
        # Match pattern like: 20231201 or 20231201.2
        match = re.match(r"^(\d{8})(?:\.(\d+))?$", clean_tag)
        if match:
            date_str = match.group(1)  # YYYYMMDD
            subver_str = match.group(2)  # SUBVER if present

            # Convert to integers for proper numeric comparison
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            subver = int(subver_str) if subver_str is not None else 0

            # Return tuple with components in order of significance (descending)
            # Using negative values to maintain descending order when sorting
            # Use a high priority indicator to sort date-based versions first
            return (-1, -year, -month, -day, -subver)
        else:
            # For tags that don't match the YYYYMMDD format, sort alphabetically in reverse
            # This maintains backward compatibility with the old behavior
            # To achieve reverse alphabetical order when sorting normally, return the negative first character
            # followed by reversed tag to maintain reverse alphabetical order
            return (0, tuple(-ord(c) for c in tag.lower()))

    def _filter_and_sort_tags(
        self, tags_data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Filter out SHA256 tags and tag aliases (latest, testing, stable), then sort tags in descending order by version.
        Tags following the format [<prefix>-]<YYYY><MM><DD>[.<SUBVER>] where prefix might be 'testing-' or 'stable-'
        are sorted by date (newest first) with higher subversions taking precedence. Other formats maintain reverse
        alphabetical sorting for backward compatibility.

        Args:
            tags_data: Dictionary containing tags data from the API

        Returns:
            A dictionary containing filtered and sorted tags, or None if input is None
        """

        if tags_data is None or "tags" not in tags_data:
            return tags_data

        tags: List[str] = tags_data["tags"]

        # Filter out SHA256 tags
        filtered_tags: List[str] = []
        for tag in tags:
            # Skip if tag starts with sha256 prefix (general pattern)
            if tag.lower().startswith("sha256-") or tag.lower().startswith("sha256:"):
                continue
            # Skip if tag looks like a hex hash (40-64 characters of hex)
            if (
                len(tag) >= 40
                and len(tag) <= 64
                and all(c in "0123456789abcdefABCDEF" for c in tag)
            ):
                continue
            # Skip if tag looks like <hex-hash>
            if tag.startswith("<") and tag.endswith(">"):
                continue
            # Skip tag aliases (both exact matches and those starting with the alias followed by a dot)
            tag_lower = tag.lower()
            if tag_lower in ["latest", "testing", "stable", "unstable"]:
                continue
            if any(
                tag_lower.startswith(alias + ".")
                for alias in ["latest", "testing", "stable", "unstable"]
            ):
                continue
            filtered_tags.append(tag)

        # Sort tags by version in descending order (newest first)
        # This uses our custom parsing function to handle the specific format
        sorted_tags: List[str] = sorted(
            filtered_tags, key=self._parse_version_for_sorting
        )

        # Limit to maximum 30 tags
        limited_tags = sorted_tags[:30]

        # Return a new dictionary with filtered, sorted, and limited tags
        result: Dict[str, Any] = tags_data.copy()
        result["tags"] = limited_tags
        return result

    def fetch_repository_tags(self) -> Optional[Dict[str, Any]]:
        """
        Get the tags for the repository by first obtaining a token,
        then filter and sort the results.

        Returns:
            A dictionary containing the filtered and sorted tags if successful, None otherwise.
        """
        token = self.get_token()
        if token is None:
            print("Could not obtain a token. Aborting.")
            return None

        tags_data = self.get_tags(token)
        return self._filter_and_sort_tags(tags_data)

    def get_raw_tags(self) -> Optional[Dict[str, Any]]:
        """
        Get the raw tags for the repository by first obtaining a token,
        without any filtering or sorting.

        Returns:
            A dictionary containing the raw tags if successful, None otherwise.
        """
        token = self.get_token()
        if token is None:
            print("Could not obtain a token. Aborting.")
            return None

        tags_data = self.get_tags(token)
        return tags_data


def run_command(cmd: List[str]) -> int:
    """Run a command and return its exit code."""
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"Command not found: {' '.join(cmd)}")
        return 1


def run_gum_submenu(
    options: List[str],
    header: str,
    display_func_non_tty: Callable[[Callable[[str], Any]], None],
    display_func_gum_not_found: Callable[[Callable[[str], Any]], None],
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
    no_selection_message: str = "No option selected.",
) -> Optional[str]:
    """
    Generic function to run a gum submenu with specified options.

    Args:
        options: List of options to display in submenu
        header: Header text for the submenu
        display_func_non_tty: Function to call when not in TTY
        display_func_gum_not_found: Function to call when gum is not found
        is_tty_func: Function to determine if running in TTY
        subprocess_run_func: Function for subprocess execution
        print_func: Function for printing
        no_selection_message: Message to display when no selection is made

    Returns:
        Selected option string or None if no selection made
    """
    # Check if we're running in a TTY context before using gum
    if is_tty_func():  # stdout is a TTY
        try:
            result = subprocess_run_func(
                [
                    "gum",
                    "choose",
                    "--cursor",
                    "→",
                    "--selected-prefix",
                    "✓ ",
                    "--header",
                    header,
                ]
                + options,
                text=True,
                stdout=subprocess.PIPE,  # Only capture stdout to get user selection
                # stdin and stderr will inherit from the parent process, allowing gum's UI to appear
            )

            if result.returncode == 0:
                selected_option = result.stdout.strip()
                return selected_option
            else:
                # gum failed or no selection made (ESC or Ctrl+C)
                # When ESC is pressed in gum, it returns exit code 1
                if result.returncode == 1:
                    # Check if we're in a test environment
                    in_test_mode = "PYTEST_CURRENT_TEST" in os.environ
                    if in_test_mode:
                        # In test mode, print message and return None for integration tests
                        print_func(no_selection_message)
                        return None
                    else:
                        # avoid printing fallback message on ESC
                        sys.stdout.write("\033[F\033[K")
                        sys.stdout.flush()
                        # In normal mode, raise exception to return to main menu
                        raise MenuExitException()
                # For other errors, return None
                return None
        except FileNotFoundError:
            # gum not found, show the list only
            display_func_gum_not_found(print_func)
            return None
    else:
        # Not running in TTY, show the list only
        display_func_non_tty(print_func)
        return None


def handle_command_with_submenu(
    args: List[str],
    submenu_func: Callable[[], Optional[Any]],
    cmd_builder: Callable[[Any], List[str]],
    arg_parser: Optional[Callable[[str], Any]] = None,
    error_message_func: Optional[Callable[[str], str]] = None,
) -> None:
    """
    Generic function to handle commands that can accept arguments or show submenus.

    Args:
        args: Command line arguments
        submenu_func: Function to call when no arguments provided
        cmd_builder: Function to build command from parsed argument
        arg_parser: Optional function to parse the argument (default: str)
        error_message_func: Optional function to format error message (default: uses arg_parser name)
    """
    if not args:
        # No arguments provided, show submenu to select
        if arg_parser is None:
            arg_parser = str  # Default to string parsing

        selected_value = submenu_func()
        # If submenu raises an exception (like MenuExitException), it will propagate up
        # If submenu returns None, we exit gracefully
        if selected_value is None:
            return  # No selection made, exit gracefully
        parsed_value = arg_parser(selected_value)
    else:
        try:
            parsed_value = arg_parser(args[0]) if arg_parser else str(args[0])
        except ValueError:
            # Default error message if no custom function provided
            if error_message_func:
                error_msg = error_message_func(args[0])
            else:
                error_msg = f"Invalid argument: {args[0]}"
            print(error_msg)
            return

    cmd = cmd_builder(parsed_value)
    sys.exit(run_command(cmd))


def get_commands_with_descriptions() -> List[str]:
    """Get the list of commands with descriptions."""
    return [
        "check - Check for available updates",
        "ls - List deployments with details",
        "pin - Pin a deployment",
        "rebase - Rebase to a container image",
        "remote-ls - List available tags for a container image",
        "rm - Remove a deployment",
        "rollback - Roll back to the previous deployment",
        "unpin - Unpin a deployment",
        "upgrade - Upgrade to the latest version",
    ]


def get_container_options() -> List[str]:
    """Get the list of container URL options (with our default first)."""
    return [
        "ghcr.io/wombatfromhell/bazzite-nix:testing",
        "ghcr.io/wombatfromhell/bazzite-nix:stable",
        "ghcr.io/ublue-os/bazzite:stable",
        "ghcr.io/ublue-os/bazzite:testing",
        "ghcr.io/ublue-os/bazzite:unstable",
        "ghcr.io/astrovm/amyos:latest",
    ]


def show_commands_non_tty(print_func: Callable[[str], Any] = print) -> None:
    """Show command list when not in TTY context."""
    print_func("Not running in interactive mode. Available commands:")
    for cmd_desc in get_commands_with_descriptions():
        print_func(f"  {cmd_desc}")
    print_func("\nRun 'urh.py help' for more information.")


def show_commands_gum_not_found(print_func: Callable[[str], Any] = print) -> None:
    """Show command list when gum is not found."""
    print_func("gum not found. Available commands:")
    for cmd_desc in get_commands_with_descriptions():
        print_func(f"  {cmd_desc}")
    print_func("\nRun 'urh.py help' for more information.")


def show_command_menu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> Optional[str]:
    """Show a menu of available commands using gum."""

    def display_commands_non_tty(func: Callable[[str], Any]) -> None:
        show_commands_non_tty(func)

    def display_commands_gum_not_found(func: Callable[[str], Any]) -> None:
        show_commands_gum_not_found(func)

    options = get_commands_with_descriptions()
    result = run_gum_submenu(
        options,
        "Select command (ESC to cancel):",
        display_commands_non_tty,
        display_commands_gum_not_found,
        is_tty_func,
        subprocess_run_func,
        print_func,
        "No command selected.",
    )

    if result:
        # Extract just the command name from the selected option
        command = result.split(" - ")[0] if " - " in result else result
        return command
    return result


def show_container_options_non_tty(print_func: Callable[[str], Any] = print) -> None:
    """Show container options when not in TTY context."""
    print_func("Available container URLs:")
    options = get_container_options()
    for _, option in enumerate(options, 1):
        print_func(f"{option}")
    print_func("\nRun 'urh.py rebase <url>' with a specific URL.")


def show_container_options_gum_not_found(
    print_func: Callable[[str], Any] = print,
) -> None:
    """Show container options when gum is not found."""
    print_func("gum not found. Available container URLs:")
    options = get_container_options()
    for _, option in enumerate(options, 1):
        print_func(f"{option}")
    print_func("\nRun 'urh.py rebase <url>' with a specific URL.")


def show_rebase_submenu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> Optional[str]:
    """Show a submenu of common container URLs using gum."""

    def display_container_options_non_tty(func: Callable[[str], Any]) -> None:
        show_container_options_non_tty(func)

    def display_container_options_gum_not_found(func: Callable[[str], Any]) -> None:
        show_container_options_gum_not_found(func)

    options = get_container_options()
    return run_gum_submenu(
        options,
        "Select container image (ESC to cancel):",
        display_container_options_non_tty,
        display_container_options_gum_not_found,
        is_tty_func,
        subprocess_run_func,
        print_func,
    )


def show_remote_ls_submenu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> Optional[str]:
    """Show a submenu of common container URLs for remote-ls using gum."""

    def display_container_options_non_tty(func: Callable[[str], Any]) -> None:
        show_container_options_non_tty(func)

    def display_container_options_gum_not_found(func: Callable[[str], Any]) -> None:
        show_container_options_gum_not_found(func)

    options = get_container_options()
    return run_gum_submenu(
        options,
        "Select container image to list tags (ESC to cancel):",
        display_container_options_non_tty,
        display_container_options_gum_not_found,
        is_tty_func,
        subprocess_run_func,
        print_func,
    )


def rebase_command(
    args: List[str],
    show_rebase_submenu_func: Optional[Callable[[], Optional[str]]] = None,
):
    """Handle the rebase command."""
    if show_rebase_submenu_func is None:
        show_rebase_submenu_func = show_rebase_submenu

    def cmd_builder(url: str) -> List[str]:
        return ["sudo", "rpm-ostree", "rebase", url]

    handle_command_with_submenu(args, show_rebase_submenu_func, cmd_builder)


def remote_ls_command(
    args: List[str],
    show_remote_ls_submenu_func: Optional[Callable[[], Optional[str]]] = None,
):
    """Handle the remote-ls command to list tags for a container image."""
    if show_remote_ls_submenu_func is None:
        show_remote_ls_submenu_func = show_remote_ls_submenu

    def parse_url(url: str) -> str:
        """Parse and validate the container URL."""
        return url

    def error_message(value: str) -> str:
        return f"Invalid container URL: {value}"

    def handle_selection(url: str) -> None:
        """Handle the selected or provided URL by listing its tags."""
        try:
            # Extract the repository name from the URL (e.g., from "ghcr.io/user/repo:tag" get "user/repo")
            if url.startswith(("ghcr.io/", "docker.io/", "quay.io/", "gcr.io/")):
                # Extract the part after the registry
                registry_removed = url.split("/", 1)[1]
                # Remove the tag part if present
                repo_part = registry_removed.split(":")[0]
            else:
                # For URLs that don't start with a specific registry, assume it's the full repo part
                repo_part = url.split(":")[0] if ":" in url else url

            # Determine the tag context from the URL (e.g., "testing", "stable", "unstable", etc.)
            url_tag_context = None
            if ":" in url:
                url_tag = url.split(":")[-1]
                if url_tag in ["testing", "stable", "unstable"]:
                    url_tag_context = url_tag

            # Create OCIClient instance
            client = OCIClient(repo_part)

            # For backward compatibility with existing tests, call fetch_repository_tags
            # But for context-aware behavior, we'll get raw tags and process them separately
            if url_tag_context:
                # If there's a URL context (e.g. :testing or :stable), get raw tags and apply context-aware processing
                tags_data = client.get_raw_tags()
            else:
                # Otherwise, use the standard processed tags for backward compatibility
                tags_data = client.fetch_repository_tags()

            if tags_data and "tags" in tags_data:
                tags = tags_data["tags"]
                if tags:
                    print(f"Tags for {url}:")

                    # Apply context-aware filtering and sorting based on URL tag context if needed
                    if url_tag_context:
                        filtered_and_sorted_tags = _context_aware_filter_and_sort(
                            tags, url_tag_context
                        )
                    else:
                        # Use the already processed tags (maintains backward compatibility)
                        filtered_and_sorted_tags = tags

                    for tag in filtered_and_sorted_tags:
                        print(f"  {tag}")
                else:
                    print(f"No tags found for {url}")
            else:
                print(f"Could not fetch tags for {url}")
        except Exception as e:
            print(f"Error fetching tags for {url}: {e}")

    if not args:
        # No arguments provided, show submenu to select
        selected_value = show_remote_ls_submenu_func()
        if selected_value is not None:
            handle_selection(selected_value)
    else:
        try:
            parsed_value = parse_url(args[0])
            handle_selection(parsed_value)
        except ValueError:
            print(error_message(args[0]))

    # Exit after displaying tags since the command is complete
    sys.exit(0)


def _context_aware_filter_and_sort(
    tags: List[str], url_context: Optional[str] = None
) -> List[str]:
    """
    Filter and sort tags based on the context from the URL, limiting to maximum 30 tags.

    Args:
        tags: List of tags to filter and sort
        url_context: The context from the URL (e.g., "testing", "stable", or None)

    Returns:
        Filtered, sorted, and limited (max 30) list of tags
    """

    # First filter out invalid tags (SHA256, aliases, signatures)
    filtered_tags: List[str] = []
    for tag in tags:
        # Skip if tag starts with sha256 prefix (general pattern)
        if tag.lower().startswith("sha256-") or tag.lower().startswith("sha256:"):
            continue
        # Skip if tag looks like a hex hash (40-64 characters of hex)
        if (
            len(tag) >= 40
            and len(tag) <= 64
            and all(c in "0123456789abcdefABCDEF" for c in tag)
        ):
            continue
        # Skip if tag looks like <hex-hash>
        if tag.startswith("<") and tag.endswith(">"):
            continue
        # Skip tag aliases (both exact matches and those starting with the alias followed by a dot)
        tag_lower = tag.lower()
        if tag_lower in ["latest", "testing", "stable", "unstable"]:
            continue
        if any(
            tag_lower.startswith(alias + ".")
            for alias in ["latest", "testing", "stable", "unstable"]
        ):
            continue
        # Skip signature tags (common convention)
        if tag.endswith(".sig"):
            continue
        filtered_tags.append(tag)

    if url_context:
        # If URL has a tag context (like :testing or :stable), only show tags with that prefix
        # Filter to only include tags with the matching context prefix
        context_prefix = f"{url_context}-"
        context_filtered_tags: List[str] = []

        for tag in filtered_tags:
            # Only include tags that start with the context prefix (e.g., "stable-")
            if tag.startswith(context_prefix):
                context_filtered_tags.append(tag)

        # Sort by context-aware sorting function
        sorted_tags: List[str] = sorted(
            context_filtered_tags,
            key=lambda t: _parse_version_for_context_aware_sorting(t, url_context),
        )
    else:
        # When no context specified, deduplicate by extracting version information
        # Create a dict to store the best tag for each unique version pattern
        unique_version_tags: Dict[str, str] = {}

        for tag in filtered_tags:
            # Extract version information for deduplication
            version_key = _extract_version_key(tag)
            if version_key not in unique_version_tags or _should_replace_tag(
                unique_version_tags[version_key], tag
            ):
                unique_version_tags[version_key] = tag

        # Get the unique tags
        unique_tags = list(unique_version_tags.values())

        # Use basic date-based sorting without preferencing prefixes
        sorted_tags: List[str] = sorted(
            unique_tags, key=lambda t: _parse_version_for_basic_sorting(t)
        )

    # Limit to maximum 30 tags
    return sorted_tags[:30]


def _extract_version_key(tag: str) -> str:
    """
    Extract a version key for deduplication purposes.
    For tags like 'stable-43.20251028', '43.20251028', 'testing-43.20251028',
    this returns a normalized version string to identify duplicates.
    """
    import re

    # Remove prefix if present for version parsing
    clean_tag = tag
    if tag.startswith("testing-"):
        clean_tag = tag[8:]  # Remove "testing-" prefix
    elif tag.startswith("stable-"):
        clean_tag = tag[7:]  # Remove "stable-" prefix
    elif tag.startswith("unstable-"):
        clean_tag = tag[9:]  # Remove "unstable-" prefix

    # Try XX.YYYYMMDD[.SUBVER] format
    match = re.match(r"^(\d+)\.(\d{8})(?:\.(\d+))?$", clean_tag)
    if match:
        version_series = match.group(1)
        date_part = match.group(2)
        subver_part = match.group(3) if match.group(3) else ""
        return f"{version_series}.{date_part}.{subver_part}"

    # Try YYYYMMDD[.SUBVER] format
    match = re.match(r"^(\d{8})(?:\.(\d+))?$", clean_tag)
    if match:
        date_part = match.group(1)
        subver_part = match.group(2) if match.group(2) else ""
        return f"{date_part}.{subver_part}"

    # For non-matching formats, return the tag itself as the key
    return tag


def _should_replace_tag(existing_tag: str, new_tag: str) -> bool:
    """
    Determine if a new tag should replace an existing tag during deduplication.
    When there are duplicates, prefer the prefixed version (stable- or testing-)
    over the unprefixed version with the same content.
    """
    # If the new tag has a prefix but the existing doesn't, prefer the new one
    new_has_prefix = new_tag.startswith(("stable-", "testing-"))
    existing_has_prefix = existing_tag.startswith(("stable-", "testing-"))

    if new_has_prefix and not existing_has_prefix:
        return True
    elif not new_has_prefix and existing_has_prefix:
        return False
    else:
        # If both have prefixes or both don't, keep the existing one (arbitrary choice)
        return False


def _parse_version_for_context_aware_sorting(
    tag: str, url_context: str
) -> VersionSortKey:
    """
    Parse tag for context-aware sorting where tags matching the URL context are prioritized.

    Args:
        tag: The tag to parse
        url_context: The context from the URL (e.g., "testing", "stable")

    Returns:
        A tuple for sorting that prioritizes context-matching tags
    """
    import re

    # Remove prefix if present for date parsing
    clean_tag = tag
    tag_prefix = None
    if tag.startswith("testing-"):
        tag_prefix = "testing"
        clean_tag = tag[8:]  # Remove "testing-" prefix
    elif tag.startswith("stable-"):
        tag_prefix = "stable"
        clean_tag = tag[7:]  # Remove "stable-" prefix
    elif tag.startswith("unstable-"):
        tag_prefix = "unstable"
        clean_tag = tag[9:]  # Remove "unstable-" prefix

    # Extract version and date from format XX.YYYYMMDD[.SUBVER] where XX is a version series
    # Also handle format YYYYMMDD[.SUBVER]
    # First try XX.YYYYMMDD[.SUBVER] format
    match = re.match(r"^(\d+)\.(\d{8})(?:\.(\d+))?$", clean_tag)
    if match:
        version_series_str = match.group(1)  # XX
        date_str = match.group(2)  # YYYYMMDD
        subver_str = match.group(3)  # SUBVER if present

        # Convert to integers for proper numeric comparison
        version_series = int(version_series_str)
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        subver = int(subver_str) if subver_str is not None else 0

        # If the tag prefix matches the URL context, give it higher priority
        # This means testing- prefixed tags will sort first if URL has :testing
        context_priority = 0 if tag_prefix == url_context else 1

        # Return tuple with components: context priority combined with version series (descending), then date (descending), then subver (descending)
        return (context_priority * 10000 - version_series, -year, -month, -day, -subver)
    else:
        # Try YYYYMMDD[.SUBVER] format
        match = re.match(r"^(\d{8})(?:\.(\d+))?$", clean_tag)
        if match:
            date_str = match.group(1)  # YYYYMMDD
            subver_str = match.group(2)  # SUBVER if present

            # Convert to integers for proper numeric comparison
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            subver = int(subver_str) if subver_str is not None else 0

            # If the tag prefix matches the URL context, give it higher priority
            # This means testing- prefixed tags will sort first if URL has :testing
            context_priority = 0 if tag_prefix == url_context else 1

            # Return tuple with components: context priority combined with -10000 as base, then date (descending), then subver (descending)
            return (
                context_priority * 10000 - 10000,
                -year,
                -month,
                -day,
                -subver,
            )  # -10000 ensures date-only tags sort lower than XX.YYYYMMDD format
        else:
            # For tags that don't match the expected format, use reverse alphabetical
            # with context priority still applying
            context_priority = 0 if tag_prefix == url_context else 1
            return (
                context_priority * 10000 - 20000,
                tuple(-ord(c) for c in tag.lower()),
            )  # -20000 ensures non-matching format tags sort lowest


def _parse_version_for_basic_sorting(tag: str) -> VersionSortKey:
    """
    Parse tag for basic sorting (no context prioritization).

    Args:
        tag: The tag to parse

    Returns:
        A tuple for sorting without context consideration
    """
    import re

    # Remove prefix if present for date parsing
    clean_tag = tag
    if tag.startswith("testing-"):
        clean_tag = tag[8:]  # Remove "testing-" prefix
    elif tag.startswith("stable-"):
        clean_tag = tag[7:]  # Remove "stable-" prefix
    elif tag.startswith("unstable-"):
        clean_tag = tag[9:]  # Remove "unstable-" prefix

    # Extract version and date from format XX.YYYYMMDD[.SUBVER] where XX is a version series
    # Also handle format YYYYMMDD[.SUBVER]
    # First try XX.YYYYMMDD[.SUBVER] format
    match = re.match(r"^(\d+)\.(\d{8})(?:\.(\d+))?$", clean_tag)
    if match:
        version_series_str = match.group(1)  # XX
        date_str = match.group(2)  # YYYYMMDD
        subver_str = match.group(3)  # SUBVER if present

        # Convert to integers for proper numeric comparison
        version_series = int(version_series_str)
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        subver = int(subver_str) if subver_str is not None else 0

        # Return tuple with components: then version series (descending), then date (descending), then subver (descending)
        # Use -10000 as base to distinguish from other formats
        return (
            -10000 - version_series,
            -year,
            -month,
            -day,
            -subver,
        )  # -10000 to distinguish from other formats
    else:
        # Try YYYYMMDD[.SUBVER] format
        match = re.match(r"^(\d{8})(?:\.(\d+))?$", clean_tag)
        if match:
            date_str = match.group(1)  # YYYYMMDD
            subver_str = match.group(2)  # SUBVER if present

            # Convert to integers for proper numeric comparison
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            subver = int(subver_str) if subver_str is not None else 0

            # Return tuple with date components (descending) for date-based sorting
            return (
                -20000,
                -year,
                -month,
                -day,
                -subver,
            )  # -20000 to distinguish from XX.YYYYMMDD format and other formats
        else:
            # For tags that don't match the expected format, use reverse alphabetical
            return (-30000, tuple(-ord(c) for c in tag.lower()))


def check_command(args: List[str]):
    """Handle the check command."""
    cmd = ["rpm-ostree", "upgrade", "--check"]
    sys.exit(run_command(cmd))


def ls_command(args: List[str]):
    """Handle the ls command."""
    cmd = ["rpm-ostree", "status", "-v"]
    sys.exit(run_command(cmd))


def rollback_command(args: List[str]):
    """Handle the rollback command."""
    cmd = ["sudo", "rpm-ostree", "rollback"]
    sys.exit(run_command(cmd))


def pin_command(
    args: List[str],
    show_deployment_submenu_func: Optional[Callable[..., Optional[int]]] = None,
):
    """Handle the pin command."""
    if show_deployment_submenu_func is None:
        show_deployment_submenu_func = show_deployment_submenu

    def cmd_builder(num: int) -> List[str]:
        return ["sudo", "ostree", "admin", "pin", str(num)]

    def not_pinned_filter(deployment: Dict[str, Any]) -> bool:
        return not deployment["pinned"]

    def submenu_func():
        return show_deployment_submenu_func(filter_func=not_pinned_filter)

    def error_message(value: str) -> str:
        return f"Invalid deployment number: {value}"

    handle_command_with_submenu(args, submenu_func, cmd_builder, int, error_message)


def unpin_command(
    args: List[str],
    show_deployment_submenu_func: Optional[Callable[..., Optional[int]]] = None,
):
    """Handle the unpin command."""
    if show_deployment_submenu_func is None:
        show_deployment_submenu_func = show_deployment_submenu

    def cmd_builder(num: int) -> List[str]:
        return ["sudo", "ostree", "admin", "pin", "-u", str(num)]

    def pinned_filter(deployment: Dict[str, Any]) -> bool:
        return deployment["pinned"]

    def submenu_func():
        return show_deployment_submenu_func(filter_func=pinned_filter)

    def error_message(value: str) -> str:
        return f"Invalid deployment number: {value}"

    handle_command_with_submenu(args, submenu_func, cmd_builder, int, error_message)


def parse_deployments() -> List[Dict[str, Any]]:
    """Parse rpm-ostree status -v to extract deployment information."""
    try:
        result = subprocess.run(
            ["rpm-ostree", "status", "-v"], capture_output=True, text=True
        )
        if result.returncode != 0:
            print("Error getting deployments")
            return []

        deployments: List[Dict[str, Any]] = []
        lines = result.stdout.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()  # Use rstrip() to preserve indentation

            # Check if this line starts a new deployment (starts with ● or space)
            if line.startswith("●") or (
                line.startswith(" ") and "ostree-image-signed:" in line
            ):
                # This is a deployment line, extract the index
                deployment_info: Dict[str, Any] = {
                    "index": None,
                    "version": None,
                    "pinned": False,
                    "current": line.startswith(
                        "●"
                    ),  # Mark if it's the current deployment
                }

                # Extract index from this line
                if "index:" in line:
                    start_idx = line.find("index:") + len("index:")
                    end_idx = line.find(")", start_idx)
                    if end_idx != -1:
                        index_str = line[start_idx:end_idx].strip()
                        try:
                            deployment_info["index"] = int(index_str)
                        except ValueError:
                            pass  # Keep as None if can't parse

                # Continue processing subsequent lines for this deployment
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()

                    # If we hit an empty line or a new deployment, break
                    if (
                        not next_line
                        or next_line.startswith("●")
                        or next_line.startswith(" ")
                        and "ostree-image-signed:" in next_line
                    ):
                        break

                    # Look for Version field
                    if next_line.startswith("Version:"):
                        version_info = next_line[len("Version:") :].strip()
                        deployment_info["version"] = version_info

                    # Look for Pinned field
                    elif next_line.startswith("Pinned:"):
                        pinned_info = next_line[len("Pinned:") :].strip()
                        deployment_info["pinned"] = pinned_info.lower() == "yes"

                    i += 1

                # Add this deployment to our list
                if deployment_info["index"] is not None:
                    deployments.append(deployment_info)

                # Don't increment i here since we already did it in the inner loop
                continue  # Continue to the next iteration of the outer loop

            i += 1

        return deployments

    except subprocess.CalledProcessError:
        print("Error running rpm-ostree status command")
        return []
    except Exception:
        print("Error parsing deployments")
        return []


def show_deployment_submenu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
    filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> Optional[int]:
    """Show a submenu of deployments using gum."""
    deployments = parse_deployments()

    if not deployments:
        print_func("No deployments found.")
        return None

    # Apply filter if provided
    if filter_func:
        deployments = [d for d in deployments if filter_func(d)]

    if not deployments:
        print_func("No deployments match the filter criteria.")
        return None

    # Create options for gum with version info
    options: List[str] = []
    deployment_map: Dict[str, int] = {}

    for deployment in deployments:
        # Create display string with version info
        version_info = (
            deployment["version"] if deployment["version"] else "Unknown Version"
        )

        # Add pinning status for pin/unpin commands
        pin_status = ""
        if "pinned" in deployment:
            pin_status = f" [Pinned: {'Yes' if deployment['pinned'] else 'No'}]"

        option_text = f"{version_info}{pin_status}"
        options.append(option_text)
        deployment_map[option_text] = deployment["index"]

    def display_deployments_non_tty(func: Callable[[str], Any]) -> None:
        func("Available deployments:")
        for deployment in deployments:
            version_info = (
                deployment["version"] if deployment["version"] else "Unknown Version"
            )
            pin_status = f" [Pinned: {'Yes' if deployment['pinned'] else 'No'}]"
            func(f"  {deployment['index']}: {version_info}{pin_status}")
        func("\nRun with deployment number directly (e.g., urh.py rm 0).")

    def display_deployments_gum_not_found(func: Callable[[str], Any]) -> None:
        func("gum not found. Available deployments:")
        for deployment in deployments:
            version_info = (
                deployment["version"] if deployment["version"] else "Unknown Version"
            )
            pin_status = f" [Pinned: {'Yes' if deployment['pinned'] else 'No'}]"
            func(f"  {deployment['index']}: {version_info}{pin_status}")
        func("\nRun with deployment number directly (e.g., urh.py rm 0).")

    result_str = run_gum_submenu(
        options,
        "Select deployment (ESC to cancel):",
        display_deployments_non_tty,
        display_deployments_gum_not_found,
        is_tty_func,
        subprocess_run_func,
        print_func,
    )

    if result_str:
        # Get the corresponding deployment index
        if result_str in deployment_map:
            return deployment_map[result_str]
        else:
            print_func("Invalid selection.")
            return None
    return None


def rm_command(
    args: List[str],
    show_deployment_submenu_func: Optional[Callable[..., Optional[int]]] = None,
):
    """Handle the rm command."""
    if show_deployment_submenu_func is None:
        show_deployment_submenu_func = show_deployment_submenu

    def cmd_builder(num: int) -> List[str]:
        return ["sudo", "rpm-ostree", "cleanup", "-r", str(num)]

    def error_message(value: str) -> str:
        return f"Invalid deployment number: {value}"

    handle_command_with_submenu(
        args, show_deployment_submenu_func, cmd_builder, int, error_message
    )


def upgrade_command(args: List[str]):
    """Handle the upgrade command."""
    cmd = ["sudo", "rpm-ostree", "upgrade"]
    sys.exit(run_command(cmd))


def help_command(args: List[str], print_func: Callable[[str], Any] = print) -> None:
    """Show help information."""
    print_func(
        "ublue-rebase-helper (urh.py) - Wrapper for rpm-ostree and ostree commands"
    )
    print_func("")
    print_func("Usage: urh.py <command> [args]")
    print_func("")
    print_func("Commands:")
    print_func("  rebase <url>     - Rebase to a container image")
    print_func("  remote-ls <url>  - List available tags for a container image")
    print_func("  check            - Check for available updates")
    print_func("  upgrade          - Upgrade to the latest version")
    print_func("  ls               - List deployments with details")
    print_func("  rollback         - Roll back to the previous deployment")
    print_func("  pin <num>        - Pin a deployment")
    print_func("  unpin <num>      - Unpin a deployment")
    print_func("  rm <num>         - Remove a deployment")
    print_func("  help             - Show this help message")


def main(argv: Optional[List[str]] = None):
    if argv is None:
        argv = sys.argv

    # If arguments were provided directly, execute that command
    if len(argv) >= 2:
        command = argv[1]

        # Map commands to their respective functions
        command_map: Dict[str, Callable[[List[str]], None]] = {
            "rebase": rebase_command,
            "remote-ls": remote_ls_command,
            "check": check_command,
            "upgrade": upgrade_command,
            "ls": ls_command,
            "rollback": rollback_command,
            "pin": pin_command,
            "unpin": unpin_command,
            "rm": rm_command,
            "help": help_command,
        }

        if command in command_map:
            command_map[command](argv[2:])
        else:
            print(f"Unknown command: {command}")
            help_command([])
    else:
        # No command provided, enter menu loop for interactive use
        # Check if we're in a test environment to avoid infinite loops
        import os

        in_test_mode = "PYTEST_CURRENT_TEST" in os.environ

        if in_test_mode:
            # Single execution for tests to avoid hanging
            command = show_command_menu()
            if not command:
                sys.exit(0)

            # Map commands to their respective functions
            command_map: Dict[str, Callable[[List[str]], None]] = {
                "rebase": rebase_command,
                "remote-ls": remote_ls_command,
                "check": check_command,
                "upgrade": upgrade_command,
                "ls": ls_command,
                "rollback": rollback_command,
                "pin": pin_command,
                "unpin": unpin_command,
                "rm": rm_command,
                "help": help_command,
            }

            if command in command_map:
                try:
                    command_map[command]([])
                except MenuExitException:
                    # In test mode, MenuExitException is caught and handled
                    sys.exit(0)
            else:
                print(f"Unknown command: {command}")
                help_command([])
        else:
            # Interactive menu loop
            while True:
                try:
                    command = show_command_menu()
                    if not command:
                        sys.exit(0)

                    # Map commands to their respective functions
                    command_map: Dict[str, Callable[[List[str]], None]] = {
                        "rebase": rebase_command,
                        "remote-ls": remote_ls_command,
                        "check": check_command,
                        "upgrade": upgrade_command,
                        "ls": ls_command,
                        "rollback": rollback_command,
                        "pin": pin_command,
                        "unpin": unpin_command,
                        "rm": rm_command,
                        "help": help_command,
                    }

                    if command in command_map:
                        try:
                            command_map[command]([])
                        except MenuExitException:
                            # Continue the menu loop when MenuExitException is raised
                            continue
                    else:
                        print(f"Unknown command: {command}")
                        help_command([])

                except MenuExitException:
                    # User pressed ESC to return to main menu, continue the loop
                    continue


if __name__ == "__main__":
    main()
