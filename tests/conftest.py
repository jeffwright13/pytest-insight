import os
from pathlib import Path

import pytest

# Import your new ProfileManager and get_profile_manager from the new codebase
from pytest_insight.storage import get_profile_manager

# Lists to track any profile files created during testing
TEST_PROFILE_FILES = []
TEST_PROFILE_NAMES = []


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_profiles():
    """Clean up test profiles after all tests have run."""
    yield

    # Clean up test profiles
    print(f"\nCleaning up {len(TEST_PROFILE_FILES)} test profile files...")
    profile_manager = get_profile_manager()

    # Delete test profiles from the profile manager
    for name in TEST_PROFILE_NAMES:
        try:
            if hasattr(profile_manager, "profiles") and name in profile_manager.profiles:
                profile_manager.delete_profile(name)
        except Exception as e:
            print(f"Error deleting profile {name}: {e}")

    # Delete any remaining test profile files
    for file_path in TEST_PROFILE_FILES:
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                print(f"Deleted test profile file: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")

    # Also clean up any temporary files in the config directory
    if hasattr(profile_manager, "config_path"):
        config_dir = Path(profile_manager.config_path).parent
        for item in config_dir.glob("tmp*"):
            try:
                if item.is_file():
                    os.unlink(str(item))
                    print(f"Deleted temporary file: {item}")
            except Exception as e:
                print(f"Error deleting temp file {item}: {e}")
