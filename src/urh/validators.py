"""
Validation utilities for ublue-rebase-helper.
"""

from typing import Dict, Optional, TypeGuard


def is_valid_deployment_info(
    info: Optional[Dict[str, str]],
) -> TypeGuard[Dict[str, str]]:
    """Validate deployment information."""
    return (
        info is not None
        and "repository" in info
        and "version" in info
        and bool(info["repository"])
    )
