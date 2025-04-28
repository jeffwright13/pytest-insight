"""
Unit tests for core storage: StorageProfile and ProfileManager.
Covers profile creation, serialization, profile switching, error handling, and backup logic.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pytest_insight.core.storage import ProfileManager, StorageProfile

# @pytest.fixture
# def temp_profile_manager():
#     with tempfile.TemporaryDirectory() as tmpdir:
#         path = Path(tmpdir) / "profiles.json"
#         pm = ProfileManager(profiles_path=path)
#         yield pm


def test_storageprofile_to_from_dict():
    now = datetime(2025, 4, 21, 10, 0, 0)
    prof = StorageProfile(
        name="test_prof",
        storage_type="json",
        file_path="/tmp/test_prof.json",
        created=now,
        last_modified=now + timedelta(minutes=1),
        created_by="alice",
        last_modified_by="bob",
    )
    d = prof.to_dict()
    prof2 = StorageProfile.from_dict(d)
    assert prof2.name == "test_prof"
    assert prof2.storage_type == "json"
    assert prof2.file_path == "/tmp/test_prof.json"
    assert prof2.created_by == "alice"
    assert prof2.last_modified_by == "bob"
    assert isinstance(prof2.created, datetime)
    assert isinstance(prof2.last_modified, datetime)


def test_profilemanager_create_and_switch(temp_profile_manager):
    pm = temp_profile_manager
    profile1 = pm.create_profile("test1", "json")
    assert profile1.name == "test1"
    pm.active_profile_name = "test1"
    assert pm.active_profile_name == "test1"


def test_profilemanager_delete_and_list(temp_profile_manager):
    pm = temp_profile_manager
    pm.create_profile("test2", "json")
    pm.create_profile("test3", "json")
    pm.delete_profile("test2")
    assert "test2" not in pm.profiles
    assert "test3" in pm.profiles


def test_profilemanager_backup_and_cleanup(temp_profile_manager):
    pm = temp_profile_manager
    pm.create_profile("test4", "json")
    backup_path = pm.backup_profiles()
    assert backup_path is not None
    # Cleanup backups
    pm.cleanup_backups()
    # Should not raise


def test_profilemanager_load_and_save(temp_profile_manager):
    pm = temp_profile_manager
    pm.create_profile("profA")
    # Simulate a new manager loading from disk
    pm2 = ProfileManager(profiles_path=pm.profiles_path)
    pm2._load_profiles_from_disk()
    assert "profA" in pm2.profiles


def test_profilemanager_error_on_duplicate(temp_profile_manager):
    pm = temp_profile_manager
    pm.create_profile("profA")
    with pytest.raises(ValueError):
        pm.create_profile("profA")


def test_profilemanager_fileio_edge_cases(temp_profile_manager, mocker):
    pm = temp_profile_manager
    pm.create_profile("profA")
    # Simulate filelock failure (should not raise)
    mocker.patch("filelock.FileLock.acquire", side_effect=Exception("fail lock"))
    try:
        pm._save_profiles_to_disk()
    except Exception as e:
        # Should handle lock failure gracefully, not raise
        pytest.fail(f"ProfileManager did not handle filelock failure: {e}")
    # Simulate read error
    pm.profiles_path.write_text("not-json")
    try:
        pm._load_profiles_from_disk()
    except Exception as e:
        pytest.fail(f"ProfileManager did not handle read error: {e}")
    # Only the default profile should remain after failed load
    assert set(pm.profiles.keys()) == {"default"}


def test_storageprofile_default_path(monkeypatch, temp_profile_manager):
    # Patch Path.home to tmp_path to avoid polluting real home
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_profile_manager.profiles_path.parent)
    prof = StorageProfile(name="profX")
    assert Path(prof.file_path).parent.exists()
    assert prof.file_path.endswith("profX.json")


def test_profilemanager_list_profiles_pattern(temp_profile_manager):
    pm = temp_profile_manager
    pm.create_profile("alpha")
    pm.create_profile("beta")
    filtered = pm.list_profiles(pattern="alpha*")
    assert "alpha" in filtered
    assert "beta" not in filtered


def test_profilemanager_create_when_no_profiles_exist(tmp_path):
    """Test creating a profile when no profiles.json exists; file and profile are created."""
    profiles_path = tmp_path / "profiles.json"
    pm = ProfileManager(profiles_path=profiles_path)
    assert not profiles_path.exists(), "profiles.json should not exist initially"
    profile = pm.create_profile("new_profile", "json")
    assert profile.name == "new_profile"
    assert profiles_path.exists(), "profiles.json should be created after profile creation"
    # Reload and check profile presence
    pm2 = ProfileManager(profiles_path=profiles_path)
    pm2._load_profiles_from_disk()
    assert "new_profile" in pm2.profiles
