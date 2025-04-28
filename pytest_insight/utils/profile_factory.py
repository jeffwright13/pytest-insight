"""
Centralized helper for creating, switching, and cleaning up test profiles using the real ProfileManager API.
Use this everywhere in tests and scripts to ensure realistic and consistent profile management.
"""
from pathlib import Path
from typing import Optional

from pytest_insight.core.storage import ProfileManager, StorageProfile


def create_test_profile(
    name: str = "test",
    storage_type: str = "json",
    file_path: Optional[str] = None,
    profiles_path: Optional[Path] = None,
) -> StorageProfile:
    """
    Create a test profile using ProfileManager. Switches to the created profile.
    Args:
        name: Profile name
        storage_type: Storage type (default: json)
        file_path: Optional path for storage file
        profiles_path: Optional path for profiles.json (for test isolation)
    Returns:
        The created or existing StorageProfile.
    """
    pm = ProfileManager(profiles_path=profiles_path)
    if name not in pm.profiles:
        pm.create_profile(name, storage_type, file_path)
    pm.switch_profile(name)
    return pm.get_profile(name)


def cleanup_test_profiles(profiles_path: Optional[Path] = None):
    """
    Delete all non-default test profiles using ProfileManager.
    Args:
        profiles_path: Optional path for profiles.json (for test isolation)
    """
    pm = ProfileManager(profiles_path=profiles_path)
    for name in list(pm.profiles.keys()):
        if name != "default":
            try:
                pm.delete_profile(name)
            except Exception:
                pass
