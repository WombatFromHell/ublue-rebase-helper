"""
Deployment information management for ublue-rebase-helper.
"""

import logging
import re
import subprocess
from dataclasses import dataclass
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


def get_status_output() -> Optional[str]:
    """Get the raw output from rpm-ostree status -v."""
    try:
        result = subprocess.run(
            ["rpm-ostree", "status", "-v"], capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting status: {e}")
        return None


def parse_deployment_info(status_output: str) -> List[DeploymentInfo]:
    """Parse deployment information from rpm-ostree status -v output."""
    lines = status_output.split("\n")
    deployments: List[DeploymentInfo] = []

    i = 0
    deployment_index_counter = 0  # Use counter to assign index based on order in output

    while i < len(lines):
        line = lines[i]

        # Look for deployment lines (with ●, *, or space at the start of the line, possibly with indentation)
        if _is_deployment_line(line):
            deployment_index = deployment_index_counter
            deployment_index_counter += 1  # Increment for next deployment

            # Parse the deployment information
            deployment_data = _parse_single_deployment(line, lines, i)

            deployments.append(
                DeploymentInfo(
                    deployment_index=deployment_index,
                    is_current=deployment_data["is_current"],
                    repository=deployment_data["repository"],
                    version=deployment_data["version"],
                    is_pinned=deployment_data["is_pinned"],
                )
            )

            i = deployment_data["next_line_index"]  # Continue from where we left off
        else:
            i += 1

    return deployments


def _is_deployment_line(line: str) -> bool:
    """Check if the line is a deployment line."""
    return bool(re.match(r"^\s*[●* ]\s*ostree-image-signed:", line))


def _parse_single_deployment(line: str, lines: List[str], start_index: int) -> Dict:
    """Parse a single deployment from the start line and following lines."""
    # Check if this is the current deployment
    is_current = "●" in line

    # Initialize values
    repository = "Unknown"
    version = "Unknown"
    is_pinned = False

    # Extract repository and tag from the ostree-image-signed line
    if "ostree-image-signed:docker://" in line:
        repository = _extract_repository_from_line(line)

    # Look ahead for more information
    j = start_index + 1
    while j < len(lines):
        next_line = lines[j]

        # Stop when we reach the next deployment or a major section
        if _should_stop_parsing(next_line):
            break

        # Extract version
        if next_line.strip().startswith("Version:"):
            version = _extract_version_from_line(next_line.strip())

        # Check for pinned status
        if "Pinned: yes" in next_line:
            is_pinned = True

        j += 1

    return {
        "is_current": is_current,
        "repository": repository,
        "version": version,
        "is_pinned": is_pinned,
        "next_line_index": j - 1,
    }


def _extract_repository_from_line(line: str) -> str:
    """Extract repository from the ostree-image-signed line."""
    # Extract the full image URL
    url_match = re.search(r"docker://([^\s)]+)", line)
    if url_match:
        full_url = url_match.group(1)
        # Extract the full image reference: {owner}/{repo}:{tag}
        # e.g., "ghcr.io/wombatfromhell/bazzite-nix:testing" -> "wombatfromhell/bazzite-nix:testing"
        if "/" in full_url:
            # Take everything after the registry: "wombatfromhell/bazzite-nix:testing"
            return full_url.split("/", 1)[1]
        else:
            return full_url
    return "Unknown"


def _should_stop_parsing(next_line: str) -> bool:
    """Check if we should stop parsing the current deployment."""
    return (
        bool(re.match(r"^\s*[●* ]\s+ostree-image-signed:", next_line))
        or next_line.startswith("State:")
        or next_line.startswith("AutomaticUpdates:")
        or next_line.startswith("Deployments:")
    )


def _extract_version_from_line(version_line: str) -> str:
    """Extract version from the version line."""
    # Extract just the version part after "Version:" but keep date-version format
    version_part = version_line.replace("Version:", "").strip()
    # Extract the main version part before any additional metadata in parentheses
    if " (" in version_part:
        # Look for the pattern like "testing-XX.YYYYMMDD.N (timestamp)"
        # We want to keep "testing-XX.YYYYMMDD.N" part
        main_part = version_part.split(" (")[0].strip()
        return main_part
    else:
        return version_part


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
