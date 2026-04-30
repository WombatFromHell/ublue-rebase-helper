"""
Rebase command handler with tag resolution.

Supports:
- Direct URL rebase
- Menu-driven selection
- Short tag resolution (e.g., 'unstable' -> latest unstable tag)
- Repository suffix syntax (e.g., 'bazzite-nix-nvidia-open:testing')
"""

import re
from typing import List, Optional, Tuple

from ..commands.deployment_helpers import MenuSystemProtocol
from ..constants import REGISTRY_PREFIXES
from ..deployment import build_persistent_header
from ..oci_client import OCIClient
from ..system import _run_command, build_command


class TagResolutionError(Exception):
    """Raised when tag resolution fails."""

    pass


def parse_repo_and_tag(tag_or_url: str, base_repository: str) -> tuple[str, str, bool]:
    """Parse repository and tag from a tag_or_url string.

    Returns:
        Tuple of (repository, tag, repo_explicitly_specified).
    """
    repository = base_repository
    tag_part = tag_or_url
    repo_explicitly_specified = False

    if ":" in tag_or_url:
        parts = tag_or_url.split(":", 1)
        repo_suffix = parts[0]
        tag_part = parts[1]

        if "/" in repo_suffix:
            repository = repo_suffix
            repo_explicitly_specified = True
        elif "/" in base_repository:
            owner, _ = base_repository.split("/", 1)
            repository = f"{owner}/{repo_suffix}"
            repo_explicitly_specified = True
        else:
            repository = repo_suffix
            repo_explicitly_specified = True

    return repository, tag_part, repo_explicitly_specified


def resolve_short_tag(tag_part: str, repository: str, all_tags: list[str]) -> str:
    """Resolve a short tag to the latest matching tag.

    Returns the latest matching tag or raises TagResolutionError if no matches.
    """
    matching_tags = [
        t for t in all_tags if t == tag_part or t.startswith(f"{tag_part}-")
    ]

    if not matching_tags:
        print(f"Error: No tags found matching '{tag_part}'")
        raise TagResolutionError(f"No tags found matching '{tag_part}'")

    matching_tags.sort(key=extract_version_for_sort, reverse=True)
    return matching_tags[0]


def build_full_url(repository: str, tag: str) -> str:
    """Build a full ghcr.io URL from repository and tag."""
    return f"ghcr.io/{repository}:{tag}"


def _strip_version_prefix(tag: str) -> str:
    """Strip series prefix from a version tag."""
    for prefix in ["unstable-", "stable-", "testing-", "latest."]:
        if tag.startswith(prefix):
            return tag[len(prefix) :]
    return tag


def _parse_numeric_parts(parts: list[str]) -> Tuple[int, int, int]:
    """Parse numeric version parts into (series, date, subver)."""
    try:
        if len(parts) >= 3:
            return (
                int(parts[0]),
                int(parts[1]),
                int(parts[2]) if parts[2].isdigit() else 0,
            )
        if len(parts) == 2:
            if len(parts[0]) == 8 and parts[0].isdigit():
                return (
                    0,
                    int(parts[0]),
                    int(parts[1]) if parts[1].isdigit() else 0,
                )
            return (int(parts[0]), int(parts[1]), 0)
        if len(parts) == 1 and parts[0].isdigit():
            return (0, int(parts[0]), 0)
    except (ValueError, IndexError):
        pass
    return (0, 0, 0)


def extract_version_for_sort(tag: str) -> Tuple[int, int, int]:
    """Extract version tuple for sorting tags (series, date, subver)."""
    return _parse_numeric_parts(_strip_version_prefix(tag).split("."))


def _find_matching_tags(tag_part: str, all_tags: list[str]) -> list[str]:
    """Find all tags matching a short tag pattern."""
    return [t for t in all_tags if t == tag_part or t.startswith(f"{tag_part}-")]


def _confirm_rebase(target: str) -> bool:
    """Confirm rebase with user. Returns True if confirmed, False otherwise."""
    from ..menu import get_user_input

    try:
        response = get_user_input(f'Confirm rebase to "{target}"? [y/N]: ')
        if response.lower() != "y":
            print("Rebase cancelled.")
            return False
        return True
    except KeyboardInterrupt:
        print("\nRebase cancelled.")
        return False


def _maybe_confirm(
    full_url: str,
    tag_or_target: str,
    tag_part: str,
    repo_explicitly_specified: bool,
    skip_confirmation: bool,
    is_resolved: bool,
) -> bool:
    """Show confirmation when appropriate. Returns True if should proceed."""
    if repo_explicitly_specified or skip_confirmation:
        return True

    if is_resolved:
        print(f"Resolving '{tag_part}' to: {tag_or_target}")
    else:
        print(f"Using target: {full_url}")

    return _confirm_rebase(tag_or_target)


def _resolve_short_tag_with_confirmation(
    tag_part: str,
    repository: str,
    tags_data: dict,
    skip_confirmation: bool,
) -> Optional[str]:
    """Resolve a short tag and handle confirmation with match display."""
    latest_tag = resolve_short_tag(tag_part, repository, tags_data["tags"])
    matching = _find_matching_tags(tag_part, tags_data["tags"])

    if len(tags_data["tags"]) > 1 and len(matching) > 1 and not skip_confirmation:
        print(f"Tag '{tag_part}' matches {len(matching)} available tags:")
        for t in matching[:10]:
            print(f"  - {t}")
        if len(matching) > 10:
            print(f"  ... and {len(matching) - 10} more")
        print(f"\nResolving to: {latest_tag}")

        if not _confirm_rebase(latest_tag):
            return None
    elif not skip_confirmation:
        print(f"Resolving '{tag_part}' to: {latest_tag}")
        if not _confirm_rebase(latest_tag):
            return None

    return latest_tag


def _resolve_and_build_url(
    repository: str,
    tag_part: str,
    skip_confirmation: bool,
) -> Optional[str]:
    """Fetch tags, resolve short tag, and build full URL."""
    client = OCIClient(repository)
    tags_data = client.fetch_repository_tags(f"ghcr.io/{repository}")

    if not tags_data or "tags" not in tags_data:
        print(f"Error: Could not fetch tags for {repository}")
        raise TagResolutionError(f"Could not fetch tags for {repository}")

    latest_tag = _resolve_short_tag_with_confirmation(
        tag_part, repository, tags_data, skip_confirmation
    )
    if latest_tag is None:
        return None

    return build_full_url(repository, latest_tag)


def resolve_tag_to_full_url(
    tag_or_url: str, skip_confirmation: bool = False, menu_system=None
) -> Optional[str]:
    """Resolve a short tag to a full URL.

    Supports syntax:
    - 'unstable' -> resolves to latest unstable tag from default repo
    - 'unstable-43.20260326.1' -> resolves to full URL with default repo
    - 'bazzite-nix-nvidia-open:testing' -> resolves to latest testing tag from specified repo variant
    - 'bazzite-nix-nvidia-open:unstable-43.20260326.1' -> full URL with specified repo
    - Full URLs (with ://) are returned as-is

    Shows confirmation prompt unless skip_confirmation is True.

    Args:
        tag_or_url: The tag or URL to resolve
        skip_confirmation: If True, skip the confirmation prompt
        menu_system: MenuSystem instance (unused but kept for interface consistency)

    Returns:
        The resolved full URL, or None if resolution failed/cancelled
    """
    from ..config import get_config
    from ..system import extract_repository_from_url

    config = get_config()
    default_url = config.container_urls.default
    base_repository = extract_repository_from_url(default_url)

    if "://" in tag_or_url or tag_or_url.startswith(REGISTRY_PREFIXES):
        return tag_or_url

    repository, tag_part, repo_explicitly_specified = parse_repo_and_tag(
        tag_or_url, base_repository
    )

    is_primary_alias = (
        not repo_explicitly_specified
        and repository == base_repository
        and tag_part in ("testing", "unstable", "stable", "latest")
    )

    needs_resolution = not re.search(r"-\d+\.\d+", tag_part)

    if is_primary_alias or not needs_resolution:
        full_url = build_full_url(repository, tag_part)

        if not _maybe_confirm(
            full_url,
            tag_part,
            tag_part,
            repo_explicitly_specified,
            skip_confirmation,
            is_resolved=False,
        ):
            return None

        return full_url

    return _resolve_and_build_url(repository, tag_part, skip_confirmation)


def _show_rebase_menu(menu_system: MenuSystemProtocol, config: object) -> Optional[str]:
    """Show rebase submenu and return selected URL."""
    from ..models import ListItem

    options = list(config.container_urls.options)  # type: ignore[attr-defined]
    items = [ListItem("", url, url) for url in options]
    persistent_header = build_persistent_header()

    selected = menu_system.show_menu(
        items,
        "Select container image (ESC to cancel):",
        persistent_header=persistent_header,
        is_main_menu=False,
    )
    return selected


def handle_rebase(
    args: List[str],
    skip_confirmation: bool = False,
    menu_system: Optional[MenuSystemProtocol] = None,
) -> int:
    """Handle the rebase command.

    Args:
        args: Command line arguments (empty for menu mode).
        skip_confirmation: If True, skip confirmation prompts.
        menu_system: MenuSystem instance for interactive selection.
    """
    from ..config import get_config
    from ..system import ensure_ostree_prefix

    config = get_config()

    if not args:
        if menu_system is None:
            return 0

        url = _show_rebase_menu(menu_system, config)
        if url is None:
            return 0
    else:
        try:
            resolved_url = resolve_tag_to_full_url(args[0], skip_confirmation)
        except TagResolutionError:
            return 1
        if resolved_url is None:
            return 0
        url = resolved_url

    prefixed_url = ensure_ostree_prefix(url)
    cmd = build_command(True, ["rpm-ostree", "rebase", prefixed_url])
    return _run_command(cmd)
