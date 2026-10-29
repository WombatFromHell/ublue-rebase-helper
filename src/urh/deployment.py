"""
Deployment information management for ublue-rebase-helper.
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Dict, List, Optional

# Import here to avoid circular import
from .validators import is_valid_deployment_info

# Set up logging
logger = logging.getLogger(__name__)


class TagContext(StrEnum):
    """Enumeration of tag contexts."""

    TESTING = "testing"
    STABLE = "stable"
    UNSTABLE = "unstable"
    LATEST = "latest"


@dataclass(slots=True, frozen=True)
class DeploymentInfo:
    """Information about a deployment."""

    deployment_index: int  # Renamed from 'index' to avoid conflict
    is_current: bool
    repository: str
    version: str
    is_pinned: bool
    # Extra fields only urh ls reads; menus use the five above.
    image_ref: str = ""
    digest: str = ""
    commit: str = ""
    osname: str = ""
    timestamp: str = ""
    staged: bool = False
    requested_packages: List[str] = field(default_factory=list)


def get_status_output() -> Optional[str]:
    """Get rpm-ostree's JSON status, or None if it fails.

    JSON rather than `status -v`: rpm-ostreed aborts (SIGABRT) in the verbose
    text renderer when a deployment has no `timestamp`, which is normal for
    bootc images. The JSON keys are rpm-ostree's scripting interface.
    """
    try:
        result = subprocess.run(
            ["rpm-ostree", "status", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.error(f"Error getting status: {e}")
        return None


def parse_deployment_info(status_json: str) -> List[DeploymentInfo]:
    """Map `rpm-ostree status --json` deployments onto DeploymentInfo.

    deployment_index is the position in the JSON list, which is the bootloader
    order `ostree admin pin|undeploy <index>` counts. Deploy serial is 0 for
    bootc images and is not an index.
    """
    try:
        payload = json.loads(status_json)
    except json.JSONDecodeError, TypeError:
        logger.warning("Could not parse rpm-ostree status JSON.")
        return []

    deployments = payload.get("deployments") if isinstance(payload, dict) else None
    if not deployments:
        return []

    infos = []
    for index, deployment in enumerate(deployments):
        if not isinstance(deployment, dict):
            continue
        origin = deployment.get("container-image-reference") or deployment.get(
            "origin", ""
        )
        infos.append(
            DeploymentInfo(
                deployment_index=index,
                is_current=bool(deployment.get("booted")),
                repository=_repository_from_image_ref(origin),
                version=deployment.get("version") or "Unknown",
                is_pinned=bool(deployment.get("pinned")),
                image_ref=_image_ref(origin),
                digest=deployment.get("container-image-reference-digest") or "",
                commit=deployment.get("checksum") or "",
                osname=deployment.get("osname") or "",
                timestamp=_timestamp(deployment.get("timestamp")),
                staged=bool(deployment.get("staged")),
                requested_packages=list(deployment.get("requested-packages") or []),
            )
        )
    return infos


def _timestamp(value: object) -> str:
    """rpm-ostree reports epoch seconds; render a UTC date. Missing key -> empty."""
    if not isinstance(value, (int, float)):
        return ""
    return datetime.fromtimestamp(value, UTC).strftime("%Y-%m-%d %H:%M UTC")


def _image_ref(origin: str) -> str:
    """Strip transport prefixes, keep the registry host: docker://ghcr.io/o/r:tag -> ghcr.io/o/r:tag."""
    if "://" in origin:
        return origin.rsplit("://", 1)[-1]
    prefix, _, rest = origin.partition(":")
    if rest and "/" in rest and "." not in prefix:
        return rest  # containers-storage:localhost/name:tag
    return origin


def _repository_from_image_ref(origin: str) -> str:
    """Drop the registry host too: ghcr.io/owner/repo:tag -> owner/repo:tag."""
    ref = _image_ref(origin)
    return ref.split("/", 1)[1] if "/" in ref else ref


def get_deployment_info() -> List[DeploymentInfo]:
    """Get information about all deployments."""
    status_output = get_status_output()
    if status_output:
        return parse_deployment_info(status_output)
    return []


def get_current_deployment_info() -> Optional[Dict[str, str]]:
    """Get the current deployment information."""
    deployments = get_deployment_info()
    for deployment in deployments:
        if deployment.is_current:
            return {"repository": deployment.repository, "version": deployment.version}
    return None


def format_deployment_header(deployment_info: Optional[Dict[str, str]]) -> str:
    """Format the deployment information into a header string."""
    if not is_valid_deployment_info(deployment_info):
        return (
            "Current deployment: System Information: Unable to retrieve deployment info"
        )

    # Now type checker knows deployment_info is Dict[str, str]
    # Extract just the repository name without the tag for display
    full_repository = deployment_info["repository"]
    repository = full_repository.split(":")[0]  # Get part before the colon
    version = deployment_info["version"]

    return f"Current deployment: {repository} ({version})"


def format_deployment_summary(deployments: List[DeploymentInfo]) -> str:
    """Render each deployment like bootc status -v does, from status --json.

    Indices are the positions `ostree admin pin|undeploy` counts, so the numbers a
    user reads here are the numbers `pin`/`unpin`/`rm`/`undeploy` take.
    """
    if not deployments:
        return "No deployments found."

    lines = ["Deployments:", ""]
    for deployment in deployments:
        marker = "●" if deployment.is_current else "*" if deployment.is_pinned else " "
        version = deployment.version
        if deployment.timestamp:
            version = f"{version} ({deployment.timestamp})"
        details = [
            ("Version", version),
            ("Digest", deployment.digest),
            ("Commit", deployment.commit),
            # Container images always report osname "default" — not worth a line.
            ("OSName", "" if deployment.osname == "default" else deployment.osname),
            ("Layered", ", ".join(deployment.requested_packages)),
            ("Staged", "yes" if deployment.staged else "no"),
            ("Pinned", "yes" if deployment.is_pinned else "no"),
        ]
        lines.append(f"{marker} {deployment.deployment_index}  {deployment.image_ref}")
        lines.extend(f"    {label:>7}: {value}" for label, value in details if value)
        lines.append("")
    lines.append("Indices match urh pin / unpin / rm / undeploy.")
    return "\n".join(lines)


def format_menu_header(
    version_header: str, deployment_info: Optional[Dict[str, str]]
) -> str:
    """Format a complete menu header with version and deployment info.

    Creates a well-organized header with visual separation:
    - App version at top
    - Separator line
    - Current deployment info
    - Another separator line
    """
    from .constants import format_menu_separator

    deployment_header = format_deployment_header(deployment_info)
    separator = format_menu_separator()

    return f"{version_header}\n{separator}\n{deployment_header}\n{separator}"


def build_persistent_header() -> str:
    """Build a persistent header with version and current deployment info."""
    from .constants import format_version_header

    deployment_info = get_current_deployment_info()
    return format_menu_header(format_version_header(), deployment_info)
