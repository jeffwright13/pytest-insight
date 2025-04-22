"""
Unit tests for core storage: StorageProfile and ProfileManager.
Covers profile creation, serialization, profile switching, error handling, and backup logic.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pytest_insight.core.storage import ProfileManager, StorageProfile


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


def test_profilemanager_create_and_switch(tmp_path):
    config_path = tmp_path / "profiles.json"
    mgr = ProfileManager(config_path=config_path)
    mgr._create_profile(
        "prof1", storage_type="json", file_path=str(tmp_path / "prof1.json")
    )
    mgr._save_profiles()
    assert mgr.get_profile("prof1").name == "prof1"
    mgr.switch_profile("prof1")
    assert mgr.get_active_profile().name == "prof1"
    with pytest.raises(ValueError):
        mgr.get_profile("does_not_exist")
    with pytest.raises(ValueError):
        mgr.switch_profile("does_not_exist")


def test_profilemanager_delete_and_list(tmp_path):
    config_path = tmp_path / "profiles.json"
    mgr = ProfileManager(config_path=config_path)
    mgr._create_profile("prof1")
    mgr._create_profile("prof2")
    mgr._save_profiles()
    mgr.switch_profile("prof1")
    mgr.delete_profile("prof2")
    assert "prof2" not in mgr.list_profiles()
    with pytest.raises(ValueError):
        mgr.delete_profile("prof1")  # Can't delete active
    mgr.switch_profile("default")
    mgr.delete_profile("prof1")
    assert "prof1" not in mgr.list_profiles()


def test_profilemanager_backup_and_cleanup(tmp_path):
    config_path = tmp_path / "profiles.json"
    mgr = ProfileManager(config_path=config_path)
    mgr._create_profile("prof1")
    mgr._save_profiles()
    backup_path = mgr.backup_profiles()
    assert backup_path.exists()
    # Create extra backups to trigger cleanup
    for _ in range(12):
        mgr.backup_profiles()
    mgr._cleanup_old_backups(max_backups=5)
    backups = mgr.list_backups()
    assert len(backups) <= 5


def test_profilemanager_load_and_save(tmp_path):
    config_path = tmp_path / "profiles.json"
    mgr = ProfileManager(config_path=config_path)
    mgr._create_profile("profA")
    mgr._save_profiles()
    # Simulate a new manager loading from disk
    mgr2 = ProfileManager(config_path=config_path)
    assert "profA" in mgr2.list_profiles()
    assert mgr2.get_profile("profA").name == "profA"


def test_profilemanager_error_on_duplicate(tmp_path):
    config_path = tmp_path / "profiles.json"
    mgr = ProfileManager(config_path=config_path)
    mgr._create_profile("profA")
    with pytest.raises(ValueError):
        mgr._create_profile("profA")


def test_profilemanager_fileio_edge_cases(tmp_path, mocker):
    config_path = tmp_path / "profiles.json"
    mgr = ProfileManager(config_path=config_path)
    mgr._create_profile("profA")
    mgr._save_profiles()
    # Simulate filelock failure (should not raise)
    mocker.patch("filelock.FileLock.acquire", side_effect=Exception("fail lock"))
    mgr._save_profiles()  # Should not raise
    # Simulate read error
    config_path.write_text("not-json")
    mgr._load_profiles()  # Should not raise
    # Only the default profile should remain after failed load
    assert set(mgr.profiles.keys()) == {"default"}


def test_storageprofile_default_path(monkeypatch, tmp_path):
    # Patch Path.home to tmp_path to avoid polluting real home
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    prof = StorageProfile(name="profX")
    assert Path(prof.file_path).parent.exists()
    assert prof.file_path.endswith("profX.json")


def test_profilemanager_list_profiles_pattern(tmp_path):
    config_path = tmp_path / "profiles.json"
    mgr = ProfileManager(config_path=config_path)
    mgr._create_profile("alpha")
    mgr._create_profile("beta")
    mgr._save_profiles()
    filtered = mgr.list_profiles(pattern="alpha*")
    assert "alpha" in filtered
    assert "beta" not in filtered
