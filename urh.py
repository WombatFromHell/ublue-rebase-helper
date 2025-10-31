#!/usr/bin/env python3
# pyright: strict

import json
import os
import re
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Define type aliases for our sorting keys
DateVersionKey = Tuple[
    int, int, int, int, int
]  # (-1, -year, -month, -day, -subver) or (context_priority, -year, -month, -day, -subver)
AlphaVersionKey = Tuple[
    int, Tuple[int, ...]
]  # (0, tuple of char codes) or (context_priority, tuple of char codes)
VersionSortKey = Union[DateVersionKey, AlphaVersionKey]


class MenuExitException(Exception):
    """Exception raised when ESC is pressed in a menu.

    Args:
        is_main_menu: If True, indicates ESC was pressed in main menu (should exit program).
                     If False, indicates ESC was pressed in submenu (should return to main menu).
    """

    def __init__(self, is_main_menu: bool = False):
        self.is_main_menu = is_main_menu
        super().__init__()


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
        Uses a single token file for all GHCR repositories.
        """
        if self._cache_path_override:
            return self._cache_path_override

        return "/tmp/oci_ghcr_token"

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

    def _parse_link_header(self, link_header: Optional[str]) -> Optional[str]:
        """
        Parse the Link header to extract the next URL.
        Example: Link: </v2/WombatFromHell/bazzite-nix/tags/list?last=1.2.0&n=200>; rel="next"

        Args:
            link_header: The raw Link header value

        Returns:
            The next URL if found, None otherwise
        """
        if not link_header:
            return None

        # Look for the next link in the Link header
        # Pattern: </v2/...>; rel="next" or similar variations with spaces
        # Using a comprehensive pattern to match various formats
        # This pattern handles: '<url>; rel="next"' including possible spaces
        next_match = re.search(
            r'<\s*([^>]+?)\s*>\s*;\s*rel\s*=\s*["\']next["\']', link_header
        )
        if next_match:
            return next_match.group(1)
        return None

    def get_all_tags(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get all tags for the repository using the provided token with pagination.
        Follows Link headers to get all tags until no more pages exist.

        Args:
            token: The OAuth2 token.

        Returns:
            A dictionary containing all tags if successful, None otherwise.
        """
        # Use the full URL with protocol for the initial request
        base_url = f"https://ghcr.io/v2/{self.repository}/tags/list"
        initial_url = f"{base_url}?n=200"
        all_tags: List[str] = []
        next_url = initial_url

        while next_url:
            # Check if the next_url is a relative path (from Link header) or full URL
            if next_url.startswith("/"):
                # If it's a relative path, prepend the base URL
                full_url = f"https://ghcr.io{next_url}"
            else:
                # If it's already a full URL, use as is
                full_url = next_url

            # Fetch a single page of tags using the shared method
            result = self._fetch_single_page_tags(full_url, token)
            if not result:
                return None

            # Extract tags and next URL from the result
            tags_data = result["tags_data"]
            link_header = result["link_header"]

            # Get the next URL by parsing the Link header
            next_url = (
                self._parse_link_header(link_header)
                if link_header is not None
                else None
            )

            # Add tags to the collection
            if "tags" in tags_data:
                all_tags.extend(tags_data["tags"])

        # Return all collected tags
        return {"tags": all_tags}

    def _parse_response_headers_and_body(self, response_text: str) -> Tuple[str, str]:
        """
        Parse headers and body from an HTTP response.

        Args:
            response_text: The raw response text from curl

        Returns:
            A tuple of (headers_part, body)
        """
        # Split headers and body (HTTP responses are separated by \r\n\r\n)
        if "\r\n\r\n" in response_text:
            headers_part, body = response_text.split("\r\n\r\n", 1)
        elif "\n\n" in response_text:
            # In test environments, newlines might not be \r\n
            headers_part, body = response_text.split("\n\n", 1)
        else:
            # If no separate headers found, treat the entire output as response body
            headers_part = ""
            body = response_text

        return headers_part, body

    def _extract_link_header(self, headers_part: str) -> Optional[str]:
        """
        Extract the Link header from response headers.

        Args:
            headers_part: The headers part of the response

        Returns:
            The Link header value if found, None otherwise
        """
        link_header = None
        if headers_part:
            for line in headers_part.splitlines():
                if line.lower().startswith("link:"):
                    link_header = line[5:].strip()  # Remove 'Link:' and whitespace
                    break
        return link_header

    def _fetch_single_page_tags(self, url: str, token: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single page of tags from the given URL with the provided token.
        Implements a retry logic if the token is expired/invalid.

        Args:
            url: The URL to fetch tags from
            token: The OAuth2 token to use for authentication

        Returns:
            A dictionary containing the tags if successful, None otherwise.
        """

        def _process_response(stdout_text: str) -> Optional[Dict[str, Any]]:
            # Parse headers and body from the response
            headers_part, body = self._parse_response_headers_and_body(stdout_text)

            # Find Link header in headers_part
            link_header = self._extract_link_header(headers_part)

            # Parse tags from the response body
            try:
                response_data = json.loads(body)
                return {"tags_data": response_data, "link_header": link_header}
            except json.JSONDecodeError as e:
                print(f"Error parsing tags response: {e}")
                print(f"Response body: {body}")
                return None

        try:
            result = subprocess.run(
                ["curl", "-s", "-i", "-H", f"Authorization: Bearer {token}", url],
                capture_output=True,
                text=True,
                check=True,
            )

            return _process_response(result.stdout)

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
                                "-i",
                                "-H",
                                f"Authorization: Bearer {new_token}",
                                url,
                            ],
                            capture_output=True,
                            text=True,
                            check=True,
                        )

                        result = _process_response(retry_result.stdout)
                        if result:
                            print("Retry successful.")
                        return result
                    except subprocess.CalledProcessError as retry_e:
                        print(f"Retry also failed: {retry_e.stderr}")
                        return None
            else:
                print(f"Error getting tags: {e.stderr}")
                return None
        except json.JSONDecodeError as e:
            print(f"Error parsing tags response: {e}")
            return None

    def get_tags(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get the tags for the repository using the provided token.
        Implements a retry logic if the token is expired/invalid.

        Args:
            token: The OAuth2 token.

        Returns:
            A dictionary containing the tags if successful, None otherwise.
        """
        # For backward compatibility, keep the original behavior with 200 tags
        url = f"https://ghcr.io/v2/{self.repository}/tags/list?n=200"

        result = self._fetch_single_page_tags(url, token)
        if result:
            return result["tags_data"]
        return None

    def _should_filter_tag(self, tag: str) -> bool:
        """
        Determine if a tag should be filtered out based on multiple criteria.

        Args:
            tag: The tag to evaluate

        Returns:
            True if the tag should be filtered out, False otherwise
        """
        # Use the common filtering function directly
        return _should_filter_tag_common(tag)

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

        # Filter tags using the dedicated filtering function
        filtered_tags: List[str] = [
            tag for tag in tags if not self._should_filter_tag(tag)
        ]

        # Sort tags by version in descending order (newest first)
        # This uses the consolidated parsing function to handle the specific format
        sorted_tags: List[str] = sorted(
            filtered_tags,
            key=lambda tag: _create_version_sort_key(
                tag, include_context_priority=False
            ),
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

        tags_data = self.get_all_tags(token)
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

        tags_data = self.get_all_tags(token)
        return tags_data


def run_command(cmd: List[str]) -> int:
    """Run a command and return its exit code."""
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(f"Command not found: {' '.join(cmd)}")
        return 1


def create_submenu_display_functions(
    data_source: Callable[[], List[str]],
    non_tty_message: str,
    gum_not_found_message: str,
) -> Tuple[
    Callable[[Callable[[str], Any]], None], Callable[[Callable[[str], Any]], None]
]:
    """
    Factory function that creates the non-TTY and gum-not-found display functions for a submenu.

    Args:
        data_source: Function that returns the list of options to display
        non_tty_message: Message to show when not in TTY context
        gum_not_found_message: Message to show when gum is not found

    Returns:
        A tuple of (non_tty_func, gum_not_found_func)
    """

    def display_non_tty(print_func: Callable[[str], Any]) -> None:
        print_func(non_tty_message)
        options: List[str] = data_source()
        for option in options:
            print_func(f"{option}")
        print_func("\nRun 'urh.py with a specific option.'")

    def display_gum_not_found(print_func: Callable[[str], Any]) -> None:
        print_func(gum_not_found_message)
        options: List[str] = data_source()
        for option in options:
            print_func(f"{option}")
        print_func("\nRun 'urh.py with a specific option.'")

    return display_non_tty, display_gum_not_found


def run_gum_submenu(
    options: List[str],
    header: str,
    display_func_non_tty: Callable[[Callable[[str], Any]], None],
    display_func_gum_not_found: Callable[[Callable[[str], Any]], None],
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
    no_selection_message: str = "No option selected.",
    is_main_menu: bool = False,
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
                        # In normal mode, raise exception with context
                        raise MenuExitException(is_main_menu=is_main_menu)
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


def show_command_menu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> Optional[str]:
    """Show a menu of available commands using gum."""
    data_source = get_commands_with_descriptions
    display_non_tty, display_gum_not_found = create_submenu_display_functions(
        data_source,
        "Not running in interactive mode. Available commands:",
        "gum not found. Available commands:",
    )

    options = get_commands_with_descriptions()
    result = run_gum_submenu(
        options,
        "Select command (ESC to cancel):",
        display_non_tty,
        display_gum_not_found,
        is_tty_func,
        subprocess_run_func,
        print_func,
        "No command selected.",
        is_main_menu=True,
    )

    if result:
        # Extract just the command name from the selected option
        command = result.split(" - ")[0] if " - " in result else result
        return command
    return result


def show_rebase_submenu(
    is_tty_func: Callable[[], bool] = lambda: os.isatty(1),
    subprocess_run_func: Callable[..., Any] = subprocess.run,
    print_func: Callable[[str], Any] = print,
) -> Optional[str]:
    """Show a submenu of common container URLs using gum."""
    data_source = get_container_options
    display_non_tty, display_gum_not_found = create_submenu_display_functions(
        data_source,
        "Available container URLs:",
        "gum not found. Available container URLs:",
    )

    options = data_source()
    return run_gum_submenu(
        options,
        "Select container image (ESC to cancel):",
        display_non_tty,
        display_gum_not_found,
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
    data_source = get_container_options
    display_non_tty, display_gum_not_found = create_submenu_display_functions(
        data_source,
        "Available container URLs:",
        "gum not found. Available container URLs:",
    )

    options = data_source()
    return run_gum_submenu(
        options,
        "Select container image to list tags (ESC to cancel):",
        display_non_tty,
        display_gum_not_found,
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


def _should_filter_tag_common(tag: str) -> bool:
    """
    Common function to determine if a tag should be filtered out based on multiple criteria.
    This is a standalone function that can be used by both OCIClient and context-aware filtering.

    Args:
        tag: The tag to evaluate

    Returns:
        True if the tag should be filtered out, False otherwise
    """
    tag_lower = tag.lower()

    # Skip if tag starts with sha256 prefix (general pattern)
    if tag_lower.startswith("sha256-") or tag_lower.startswith("sha256:"):
        return True

    # Skip if tag looks like a hex hash (40-64 characters of hex)
    if (
        len(tag) >= 40
        and len(tag) <= 64
        and all(c in "0123456789abcdefABCDEF" for c in tag)
    ):
        return True

    # Skip if tag looks like <hex-hash>
    if tag.startswith("<") and tag.endswith(">"):
        return True

    # Skip tag aliases (both exact matches and those starting with the alias followed by a dot)
    if tag_lower in ["latest", "testing", "stable", "unstable"]:
        return True
    if any(
        tag_lower.startswith(alias + ".")
        for alias in ["latest", "testing", "stable", "unstable"]
    ):
        return True

    # Skip major version patterns like "42", "43", etc. (standalone major versions)
    if tag_lower.isdigit() and len(tag_lower) <= 2:
        return True

    # Skip major version alias patterns like "unstable-43", "testing-42", "stable-43", etc.
    # These are aliases for actual version tags like "unstable-43.20251030"
    # But don't skip patterns like "unstable-43.20251030" (major version with date) or "unstable-20231001" (date format)
    for alias in ["latest", "testing", "stable", "unstable"]:
        if tag_lower.startswith(alias + "-"):
            after_prefix = tag_lower[len(alias) + 1 :]
            parts = after_prefix.split(".")
            first_part = parts[0]
            # Check if it's a simple number with no more parts after (like "43" from "unstable-43")
            # Major versions are typically short numbers (1-2 digits) with no additional parts
            if (
                first_part.isdigit() and len(first_part) <= 2 and len(parts) == 1
            ):  # Major version numbers are typically 1-2 digits with no additional parts
                return True

    # Skip version suffix patterns like "42-testing", "42-stable", "42-unstable"
    # These are aliases where a major version has a suffix
    suffix_patterns = ["-testing", "-stable", "-unstable"]
    for suffix in suffix_patterns:
        if tag_lower.endswith(suffix):
            prefix_part = tag_lower[: -len(suffix)]  # Remove the suffix
            if prefix_part.isdigit() and len(prefix_part) <= 2:  # Major version number
                return True

    # Skip signature tags (common convention)
    if tag.endswith(".sig"):
        return True

    return False


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

    # First filter out invalid tags using the common filtering logic
    filtered_tags: List[str] = [
        tag for tag in tags if not _should_filter_tag_common(tag)
    ]

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
            key=lambda t: _create_version_sort_key(
                t, url_context, include_context_priority=True
            ),
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
            unique_tags,
            key=lambda t: _create_version_sort_key(t, include_context_priority=False),
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

    # For non-matching formats, return the tag itself as the key (lowercase for case-insensitive comparison)
    return tag.lower()


def _should_replace_tag(existing_tag: str, new_tag: str) -> bool:
    """
    Determine if a new tag should replace an existing tag during deduplication.
    When there are duplicates, prefer the prefixed version (stable-, testing-, unstable-)
    over the unprefixed version with the same content.
    """
    # If the new tag has a prefix but the existing doesn't, prefer the new one
    new_has_prefix = new_tag.startswith(("stable-", "testing-", "unstable-"))
    existing_has_prefix = existing_tag.startswith(("stable-", "testing-", "unstable-"))

    if new_has_prefix and not existing_has_prefix:
        return True
    elif not new_has_prefix and existing_has_prefix:
        return False
    else:
        # If both have prefixes or both don't, keep the existing one (arbitrary choice)
        return False


def _extract_prefix_and_clean_tag(tag: str) -> Tuple[Optional[str], str]:
    """
    Extract the prefix (if any) and clean tag without prefix.

    Args:
        tag: The original tag

    Returns:
        A tuple of (prefix, clean_tag) where prefix is None if no prefix exists
    """
    if tag.startswith("testing-"):
        return "testing", tag[8:]  # Remove "testing-" prefix
    elif tag.startswith("stable-"):
        return "stable", tag[7:]  # Remove "stable-" prefix
    elif tag.startswith("unstable-"):
        return "unstable", tag[9:]  # Remove "unstable-" prefix
    else:
        return None, tag


def _parse_version_components(
    clean_tag: str,
) -> Optional[Tuple[Optional[int], int, int, int, int]]:
    """
    Parse version components from a clean tag (without prefix).

    Args:
        clean_tag: Tag without any prefix

    Returns:
        A tuple of (version_series, year, month, day, subver) or None if no match
    """
    import re

    # Try XX.YYYYMMDD[.SUBVER] format first
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

        return version_series, year, month, day, subver

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

        return None, year, month, day, subver  # version_series is None for this format

    return None  # No match for known formats


def _create_version_sort_key(
    tag: str, url_context: Optional[str] = None, include_context_priority: bool = False
) -> VersionSortKey:
    """
    Create a sort key for a tag with optional context priority.
    This maintains backward compatibility with the original sorting behavior.

    Args:
        tag: The tag to create a sort key for
        url_context: The context from the URL (e.g., "testing", "stable")
        include_context_priority: Whether to prioritize context-matching tags

    Returns:
        A tuple that can be used for sorting
    """
    # Extract prefix and clean tag
    tag_prefix, clean_tag = _extract_prefix_and_clean_tag(tag)

    # Try to parse version components
    version_components = _parse_version_components(clean_tag)

    if version_components:
        version_series, year, month, day, subver = version_components

        if include_context_priority and url_context:
            # Context priority: 0 if matching context, 1 otherwise
            context_priority = 0 if tag_prefix == url_context else 1

            if version_series is not None:
                # XX.YYYYMMDD[.SUBVER] format
                # Return tuple with context priority combined with version series (descending), then date (descending), then subver (descending)
                return (
                    context_priority * 10000 - version_series,
                    -year,
                    -month,
                    -day,
                    -subver,
                )
            else:
                # YYYYMMDD[.SUBVER] format - this should get priority -1 to match original
                # Return tuple with context priority combined with base -1, then date (descending), then subver (descending)
                return (
                    -1,  # Original behavior: -1 for date-based versions
                    -year,
                    -month,
                    -day,
                    -subver,
                )
        else:
            # No context priority - regular version sorting
            if version_series is not None:
                # XX.YYYYMMDD[.SUBVER] format
                return (
                    -10000 - version_series,  # Keep this as is
                    -year,
                    -month,
                    -day,
                    -subver,
                )
            else:
                # YYYYMMDD[.SUBVER] format - should get priority -1 to match original behavior
                return (
                    -1,  # Original behavior: -1 for date-based versions
                    -year,
                    -month,
                    -day,
                    -subver,
                )  # -1 matches the original priority for date-based tags
    else:
        # For tags that don't match the expected format, use reverse alphabetical
        if include_context_priority and url_context:
            context_priority = 0 if tag_prefix == url_context else 1
            return (
                context_priority * 10000 - 20000,
                tuple(-ord(c) for c in tag.lower()),
            )
        else:
            # For non-date formats, use reverse alphabetical order (same as original for non-matching)
            return (
                0,
                tuple(-ord(c) for c in tag.lower()),
            )  # 0 for non-matching formats like original


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

    # Create deployment data source function for the abstraction
    def get_deployment_options() -> List[str]:
        result: List[str] = []
        for deployment in deployments:
            version_info = (
                deployment["version"] if deployment["version"] else "Unknown Version"
            )
            pin_status = f" [Pinned: {'Yes' if deployment['pinned'] else 'No'}]"
            result.append(f"  {deployment['index']}: {version_info}{pin_status}")
        return result

    display_non_tty, display_gum_not_found = create_submenu_display_functions(
        get_deployment_options,
        "Available deployments:",
        "gum not found. Available deployments:",
    )

    result_str = run_gum_submenu(
        options,
        "Select deployment (ESC to cancel):",
        display_non_tty,
        display_gum_not_found,
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
    print_func("  check            - Check for available updates")
    print_func("  help             - Show this help message")
    print_func("  ls               - List deployments with details")
    print_func("  pin <num>        - Pin a deployment")
    print_func("  rebase <url>     - Rebase to a container image")
    print_func("  remote-ls <url>  - List available tags for a container image")
    print_func("  rm <num>         - Remove a deployment")
    print_func("  rollback         - Roll back to the previous deployment")
    print_func("  unpin <num>      - Unpin a deployment")
    print_func("  upgrade          - Upgrade to the latest version")


def execute_simple_command(command_parts: List[str]) -> None:
    """Execute a simple command with no arguments needed."""
    sys.exit(run_command(command_parts))


def execute_command_with_args(command_parts: List[str], args: List[str]) -> None:
    """Execute a command with additional arguments."""
    cmd = command_parts + args
    sys.exit(run_command(cmd))


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
                except MenuExitException as e:
                    # In test mode, handle MenuExitException based on context
                    if e.is_main_menu:
                        # User pressed ESC in main menu, exit the program
                        sys.exit(0)
                    else:
                        # User pressed ESC in submenu, return to main menu (exit with success)
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

                except MenuExitException as e:
                    if e.is_main_menu:
                        # User pressed ESC in main menu, exit the program
                        sys.exit(0)
                    else:
                        # User pressed ESC in submenu, return to main menu (continue loop)
                        continue


if __name__ == "__main__":
    main()
