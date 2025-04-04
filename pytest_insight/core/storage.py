import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pytest_insight.core.models import TestSession
from pytest_insight.utils.constants import DEFAULT_STORAGE_PATH


class StorageProfile:
    """Represents a storage configuration profile, which is a named storage configuration used to differentiate between different storage backends, different file paths, different SUTs/setups/environments, etc."""

    def __init__(
        self, name: str, storage_type: str = "json", file_path: Optional[str] = None
    ):
        """Initialize a storage profile.

        Args:
            name: Unique name for the profile
            storage_type: Type of storage (json, memory, etc.)
            file_path: Optional custom path for storage. If None, a default path will be generated based on the profile name.
        """
        self.name = name
        self.storage_type = storage_type

        # Generate default file path based on profile name if none provided
        if file_path is None:
            default_dir = Path.home() / ".pytest_insight"
            self.file_path = str(default_dir / f"{name}.json")
        else:
            self.file_path = file_path

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "storage_type": self.storage_type,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StorageProfile":
        """Create profile from dictionary."""
        return cls(
            name=data["name"],
            storage_type=data.get("storage_type", "json"),
            file_path=data.get("file_path"),
        )


class ProfileManager:
    """Manages storage profiles for pytest-insight. Profiles are used to differentiate between different storage
    backends, different file paths, different SUTs/setups/environments, etc."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize profile manager.

        Args:
            config_path: Optional custom path for profile configuration
        """
        self.config_path = (
            config_path or Path.home() / ".pytest_insight" / "profiles.json"
        )
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.profiles = {}
        self.active_profile_name = None
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load profiles from configuration file."""
        if not self.config_path.exists():
            # Create default profile
            default_profile = StorageProfile("default", "json")
            self.profiles = {"default": default_profile}
            self.active_profile_name = "default"
            self._save_profiles()
            return

        try:
            data = json.loads(self.config_path.read_text())
            self.profiles = {
                name: StorageProfile.from_dict(profile_data)
                for name, profile_data in data.get("profiles", {}).items()
            }
            self.active_profile_name = data.get("active_profile", "default")

            # Ensure default profile exists
            if "default" not in self.profiles:
                self.profiles["default"] = StorageProfile("default", "json")

            # Ensure active profile exists
            if self.active_profile_name not in self.profiles:
                self.active_profile_name = "default"
        except Exception as e:
            print(f"Warning: Failed to load profiles from {self.config_path}: {e}")
            # Create default profile
            self.profiles = {"default": StorageProfile("default", "json")}
            self.active_profile_name = "default"
            self._save_profiles()

    # def _save_profiles(self) -> None:
    #     """Save profiles to configuration file."""
    #     data = {
    #         "profiles": {name: profile.to_dict() for name, profile in self.profiles.items()},
    #         "active_profile": self.active_profile_name,
    #     }

    #     # Create a temporary file in the same directory
    #     temp_dir = self.config_path.parent
    #     temp_dir.mkdir(parents=True, exist_ok=True)

    #     with tempfile.NamedTemporaryFile(mode="w", dir=temp_dir, delete=False) as temp_file:
    #         # Write data to the temporary file
    #         json.dump(data, temp_file, indent=2)
    #         temp_path = Path(temp_file.name)

    #     try:
    #         # Rename is atomic on POSIX systems
    #         temp_path.replace(self.config_path)
    #     except Exception as e:
    #         print(f"Warning: Failed to save profiles to {self.config_path}: {e}")
    #         if temp_path.exists():
    #             temp_path.unlink()  # Clean up temp file
    #         raise

    def _save_profiles(self) -> None:
        """Save profiles to configuration file."""
        # Create a backup before saving
        if self.config_path.exists():
            self.backup_profiles()

        data = {
            "profiles": {
                name: profile.to_dict() for name, profile in self.profiles.items()
            },
            "active_profile": self.active_profile_name,
        }

        # Create a temporary file in the same directory
        temp_dir = self.config_path.parent
        temp_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w", dir=temp_dir, delete=False
        ) as temp_file:
            # Write data to the temporary file
            json.dump(data, temp_file, indent=2)
            temp_path = Path(temp_file.name)

        try:
            # Rename is atomic on POSIX systems
            temp_path.replace(self.config_path)
        except Exception as e:
            print(f"Warning: Failed to save profiles to {self.config_path}: {e}")
            if temp_path.exists():
                temp_path.unlink()  # Clean up temp file
            raise

    def _create_profile(
        self, name: str, storage_type: str = "json", file_path: Optional[str] = None
    ) -> StorageProfile:
        """Create a new storage profile.

        Args:
            name: Unique name for the profile
            storage_type: Type of storage (json, memory, etc.)
            file_path: Optional custom path for storage

        Returns:
            The created profile
        """
        if name in self.profiles:
            raise ValueError(f"Profile '{name}' already exists")

        profile = StorageProfile(name, storage_type, file_path)
        self.profiles[name] = profile
        self._save_profiles()
        return profile

    def get_profile(self, name: Optional[str] = None) -> StorageProfile:
        """Get a profile by name.

        Args:
            name: Name of the profile to get, or None for active profile

        Returns:
            The requested profile

        Raises:
            ValueError: If profile does not exist
        """
        profile_name = name or self.active_profile_name or "default"

        # Check environment variable override
        env_profile = os.environ.get("PYTEST_INSIGHT_PROFILE")
        if env_profile and not name:
            profile_name = env_profile

        if profile_name not in self.profiles:
            raise ValueError(f"Profile '{profile_name}' does not exist")

        return self.profiles[profile_name]

    def switch_profile(self, name: str) -> StorageProfile:
        """Switch to a different profile.

        Args:
            name: Name of the profile to switch to

        Returns:
            The activated profile

        Raises:
            ValueError: If profile does not exist
        """
        if name not in self.profiles:
            raise ValueError(f"Profile '{name}' does not exist")

        self.active_profile_name = name
        self._save_profiles()
        return self.profiles[name]

    def delete_profile(self, name: str) -> None:
        """Delete a profile.

        Args:
            name: Name of the profile to delete

        Raises:
            ValueError: If profile does not exist or is the active profile
        """
        if name not in self.profiles:
            raise ValueError(f"Profile '{name}' does not exist")

        if name == "default":
            raise ValueError("Cannot delete the default profile")

        if name == self.active_profile_name:
            raise ValueError("Cannot delete the active profile")

        del self.profiles[name]
        self._save_profiles()

    def list_profiles(self) -> Dict[str, StorageProfile]:
        """List all available profiles.

        Returns:
            Dictionary of profile names to profile objects
        """
        return self.profiles

    def get_active_profile(self) -> StorageProfile:
        """Get the currently active profile.

        Returns:
            The active profile
        """
        return self.get_profile(self.active_profile_name)

    def backup_profiles(self) -> Optional[Path]:
        """Create a timestamped backup of the profiles file.

        Returns:
            Path to the created backup file, or None if backup couldn't be created
        """
        if not self.config_path.exists():
            print("No profiles file to backup")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.config_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Add a unique identifier to ensure uniqueness even when backups are created in rapid succession
        unique_id = str(uuid.uuid4())[:8]

        backup_path = backup_dir / f"profiles_backup_{timestamp}_{unique_id}.json"
        try:
            shutil.copy2(self.config_path, backup_path)
            print(f"Created profiles backup: {backup_path}")

            # Keep only the 10 most recent backups
            self._cleanup_old_backups(max_backups=10)

            return backup_path
        except Exception as e:
            print(f"Failed to create backup: {e}")
            return None

    def _cleanup_old_backups(self, max_backups: int = 10) -> None:
        """Remove old backups, keeping only the most recent ones.

        Args:
            max_backups: Maximum number of backups to keep
        """
        backup_dir = self.config_path.parent / "backups"
        if not backup_dir.exists():
            return

        backups = sorted(
            backup_dir.glob("profiles_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Remove older backups beyond the max limit
        for old_backup in backups[max_backups:]:
            try:
                old_backup.unlink()
                print(f"Removed old backup: {old_backup}")
            except Exception as e:
                print(f"Failed to remove old backup {old_backup}: {e}")

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backup files with metadata.

        Returns:
            List of dictionaries with backup metadata
        """
        backup_dir = self.config_path.parent / "backups"
        if not backup_dir.exists():
            return []

        backups = []
        for backup_file in backup_dir.glob("profiles_backup_*.json"):
            try:
                # Extract timestamp from filename
                # Handle both old format (profiles_backup_YYYYMMDD_HHMMSS.json)
                # and new format (profiles_backup_YYYYMMDD_HHMMSS_uniqueid.json)
                filename = backup_file.name
                # Extract the timestamp part (after profiles_backup_ and before .json or _uniqueid)
                timestamp_str = filename.replace("profiles_backup_", "").replace(
                    ".json", ""
                )

                # If there's an underscore after the timestamp, it's the new format with a unique ID
                if "_" in timestamp_str:
                    # Split by the last underscore to get the timestamp part
                    timestamp_str = timestamp_str.rsplit("_", 1)[0]

                # Parse the timestamp
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                # Get file stats
                stats = backup_file.stat()

                backups.append(
                    {
                        "path": str(backup_file),
                        "filename": backup_file.name,
                        "timestamp": timestamp,
                        "size": stats.st_size,
                        "created": datetime.fromtimestamp(stats.st_ctime),
                    }
                )
            except Exception as e:
                print(f"Error processing backup {backup_file}: {e}")

        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    def restore_from_backup(self, backup_path: Union[str, Path]) -> bool:
        """Restore profiles from a backup file.

        Args:
            backup_path: Path to the backup file to restore from

        Returns:
            True if restore was successful, False otherwise
        """
        backup_path = Path(backup_path) if isinstance(backup_path, str) else backup_path

        if not backup_path.exists():
            print(f"Backup file not found: {backup_path}")
            return False

        try:
            # Create a backup of the current state before restoring
            if self.config_path.exists():
                self.backup_profiles()

            # Copy the backup to the profiles location
            shutil.copy2(backup_path, self.config_path)

            # Reload the profiles
            self._load_profiles()

            print(f"Successfully restored profiles from {backup_path}")
            return True
        except Exception as e:
            print(f"Failed to restore from backup {backup_path}: {e}")
            return False


class BaseStorage:
    """Abstract interface for persisting test session data."""

    def save_session(self, test_session: TestSession) -> None:
        """Persist a test session."""
        raise NotImplementedError

    def load_sessions(self) -> List[TestSession]:
        """Retrieve past test sessions."""
        raise NotImplementedError

    def clear_sessions(
        self, sessions_to_clear: Optional[List[TestSession]] = None
    ) -> int:
        """Remove stored sessions.

        Args:
            sessions_to_clear: Optional list of TestSession objects to remove.
                              If None, removes all sessions.

        Returns:
            Number of sessions removed
        """
        raise NotImplementedError

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        """Retrieve a test session by its unique identifier."""
        sessions = self.load_sessions()
        return next((s for s in sessions if s.session_id == session_id), None)


class InMemoryStorage(BaseStorage):
    """In-memory storage implementation."""

    def __init__(self, sessions: Optional[List[TestSession]] = None):
        """Initialize storage with optional sessions."""
        super().__init__()
        self._sessions = sessions if sessions is not None else []

    def load_sessions(self) -> List[TestSession]:
        """Get all stored sessions."""
        return self._sessions

    def save_session(self, session: TestSession) -> None:
        """Save a test session."""
        self._sessions.append(session)

    def clear_sessions(
        self, sessions_to_clear: Optional[List[TestSession]] = None
    ) -> int:
        """Clear all sessions or specific sessions from storage.

        Args:
            sessions_to_clear: Optional list of session IDs to clear.
                               If None, all sessions are cleared.

        Returns:
            Number of sessions removed
        """
        # Get current sessions count
        initial_count = len(self._sessions)

        if sessions_to_clear is None:
            # Clear all sessions
            self._sessions.clear()
            return initial_count
        else:
            # Clear specific sessions
            session_ids_to_clear = {session.session_id for session in sessions_to_clear}
            self._sessions = [
                session
                for session in self._sessions
                if session.session_id not in session_ids_to_clear
            ]
            return initial_count - len(self._sessions)


class JSONStorage(BaseStorage):
    """Storage for test sessions using JSON files."""

    def __init__(self, file_path: Optional[Path] = None):
        """Initialize storage with optional custom file path.

        Args:
            file_path: Optional custom path for session storage.
                      If not provided, uses ~/.pytest_insight/sessions.json
        """
        self.file_path = Path(file_path) if file_path else DEFAULT_STORAGE_PATH
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if it doesn't exist
        if not self.file_path.exists():
            self._write_json_safely([])

    def load_sessions(self) -> List[TestSession]:
        """Load all test sessions from storage."""
        if not self.file_path.exists():
            return []
        try:
            data = self._read_json_safely()
            sessions = []
            for idx, session_data in enumerate(data):
                try:
                    sessions.append(TestSession.from_dict(session_data))
                except Exception as e:
                    print(f"Warning: Failed to deserialize session at index {idx}: {e}")
            return sessions
        except Exception as e:
            print(f"Warning: Failed to load sessions from {self.file_path}: {e}")
            return []

    def save_session(self, session: TestSession) -> None:
        """Save a single test session to storage.

        Args:
            session: Test session to save
        """

        try:
            # Load existing sessions
            sessions = self.load_sessions()

            # Add new session
            sessions.append(session)

            # Save all sessions
            self._write_json_safely([s.to_dict() for s in sessions])
        except Exception as e:
            print(f"Warning: Failed to save session to {self.file_path}: {e}")

    def save_sessions(self, sessions: List[TestSession]) -> None:
        """Save multiple test sessions to storage.

        Args:
            sessions: List of test sessions to save
        """

        try:
            self._write_json_safely([s.to_dict() for s in sessions])
        except Exception as e:
            print(f"Warning: Failed to save sessions to {self.file_path}: {e}")

    def clear_sessions(
        self, sessions_to_clear: Optional[List[TestSession]] = None
    ) -> int:
        """Remove stored sessions.

        Args:
            sessions_to_clear: Optional list of TestSession objects to remove.
                              If None, removes all sessions.

        Returns:
            Number of sessions removed
        """
        if sessions_to_clear is None:
            # Clear all sessions
            current_sessions = self.load_sessions()
            count = len(current_sessions)
            self._write_json_safely([])
            return count
        else:
            # Get current sessions
            current_sessions = self.load_sessions()
            initial_count = len(current_sessions)

            # Create a set of session IDs to clear
            session_ids_to_clear = {session.session_id for session in sessions_to_clear}

            # Keep only sessions not in the clear list
            remaining_sessions = [
                session
                for session in current_sessions
                if session.session_id not in session_ids_to_clear
            ]

            # Save the filtered sessions
            self._write_json_safely([s.to_dict() for s in remaining_sessions])

            # Return number of sessions removed
            return initial_count - len(remaining_sessions)

    def clear(self) -> None:
        """Clear all sessions from storage."""
        self._write_json_safely([])

    def get_last_session(self) -> Optional[TestSession]:
        """Get the most recent test session.

        Returns:
            The most recent TestSession or None if no sessions exist
        """
        sessions = self.load_sessions()
        if not sessions:
            return None

        # Sort sessions by start time (newest first) and return the first one
        return sorted(sessions, key=lambda s: s.session_start_time, reverse=True)[0]

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        """Get a test session by its ID.

        Args:
            session_id: The ID of the session to retrieve

        Returns:
            The TestSession with the matching ID or None if not found
        """
        sessions = self.load_sessions()
        for session in sessions:
            if session.session_id == session_id:
                return session
        return None

    def export_sessions(
        self, export_path: str, days: Optional[int] = None, output_format: str = "json"
    ):
        """Export test sessions to a file.

        Args:
            export_path: Path to export file
            days: Optional number of days to include in export
            output_format: Optional output format (json or csv)
        """
        # Get sessions
        sessions = self.load_sessions()

        # Filter by days if specified
        if days is not None:
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=days)
            sessions = [s for s in sessions if s.session_start_time > cutoff_date]

        # Export to file
        if output_format.lower() == "json":
            with open(export_path, "w") as f:
                json.dump([s.to_dict() for s in sessions], f, indent=2)
        elif output_format.lower() == "csv":
            import csv

            with open(export_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=TestSession.csv_fields())
                writer.writeheader()
                for session in sessions:
                    writer.writerow(session.to_dict())
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def import_sessions(
        self, import_path: str, merge_strategy: str = "skip_existing"
    ) -> Dict[str, int]:
        """Import sessions from a file exported by another instance.

        Args:
            import_path: Path to the file containing exported sessions
            merge_strategy: How to handle duplicate session IDs:
                - "skip_existing": Skip sessions that already exist (default)
                - "replace_existing": Replace existing sessions with imported ones
                - "keep_both": Keep both versions, appending a suffix to imported IDs

        Returns:
            Dictionary with import statistics:
                - total: Total number of sessions in the import file
                - imported: Number of sessions successfully imported
                - skipped: Number of sessions skipped
                - errors: Number of sessions with errors during import
        """
        # Initialize stats
        stats = {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

        # Check if file exists
        import_path = Path(import_path)
        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")

        # Load existing sessions
        existing_sessions = self.load_sessions()
        existing_ids = {session.session_id for session in existing_sessions}

        # Load imported data
        try:
            with open(import_path, "r") as f:
                imported_data = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in import file")

        # Update stats
        stats["total"] = len(imported_data)

        # Process imported sessions
        imported_sessions = []
        for session_data in imported_data:
            try:
                # Create TestSession from dict
                session = TestSession.from_dict(session_data)

                # Check for duplicate ID
                if session.session_id in existing_ids:
                    if merge_strategy == "skip_existing":
                        stats["skipped"] += 1
                        continue
                    elif merge_strategy == "replace_existing":
                        # Will be replaced, so count as imported
                        stats["imported"] += 1
                        imported_sessions.append(session)
                    elif merge_strategy == "keep_both":
                        # Modify ID to avoid collision
                        suffix = 1
                        new_id = f"{session.session_id}_imported_{suffix}"
                        while new_id in existing_ids:
                            suffix += 1
                            new_id = f"{session.session_id}_imported_{suffix}"

                        session.session_id = new_id
                        stats["imported"] += 1
                        imported_sessions.append(session)
                    else:
                        raise ValueError(f"Invalid merge strategy: {merge_strategy}")
                else:
                    # New session, import it
                    stats["imported"] += 1
                    imported_sessions.append(session)
            except Exception as e:
                stats["errors"] += 1
                print(f"Error importing session: {e}")

        # Apply the changes based on merge strategy
        if merge_strategy == "replace_existing":
            # Remove existing sessions that will be replaced
            imported_ids = {session.session_id for session in imported_sessions}
            existing_sessions = [
                s for s in existing_sessions if s.session_id not in imported_ids
            ]

        # Combine existing and imported sessions
        all_sessions = existing_sessions + imported_sessions

        # Save to storage
        self._write_json_safely([s.to_dict() for s in all_sessions])

        return stats

    def _write_json_safely(self, data):
        """Write JSON data to file using atomic operations."""
        # Create a temporary file in the same directory
        temp_dir = self.file_path.parent
        temp_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w", dir=temp_dir, delete=False
        ) as temp_file:
            # Write data to the temporary file
            json.dump(data, temp_file, indent=2)
            temp_path = Path(temp_file.name)

        try:
            # Rename is atomic on POSIX systems
            temp_path.replace(self.file_path)
        except Exception as e:
            print(f"Warning: Failed to save data to {self.file_path}: {e}")
            if temp_path.exists():
                temp_path.unlink()  # Clean up temp file
            raise

    def _read_json_safely(self):
        """Read JSON data from file with error handling."""
        try:
            data = json.loads(self.file_path.read_text())
            if not isinstance(data, list):
                print(
                    f"Warning: Invalid data format in {self.file_path}, expected list"
                )
                return []
            return data
        except json.JSONDecodeError as e:
            print(f"Warning: JSON decode error in {self.file_path}: {e}")
            # Try to recover by creating a backup of the corrupted file
            backup_path = self.file_path.with_suffix(".bak")
            print(f"Creating backup of corrupted file at {backup_path}")
            self.file_path.rename(backup_path)
            return []


def get_storage_instance(
    profile_name: Optional[str] = None,
) -> BaseStorage:
    """Get a storage instance configured according to the specified profile.

    This function returns a storage instance configured according to the specified profile.
    If no profile is specified, it will try to use the profile from the PYTEST_INSIGHT_PROFILE
    environment variable. If that's not set, it will use the active profile from the profile manager.

    Args:
        profile_name: Optional profile name to use

    Returns:
        Configured storage instance
    """
    profile_manager = get_profile_manager()

    # Step 1: Use explicitly provided profile name
    if profile_name is not None:
        try:
            profile = profile_manager.get_profile(profile_name)
            if profile.storage_type.lower() == "json":
                return JSONStorage(profile.file_path)
            elif profile.storage_type.lower() == "memory":
                return InMemoryStorage()
            else:
                raise ValueError(
                    f"Unsupported storage type in profile '{profile_name}': {profile.storage_type}"
                )
        except ValueError as e:
            print(f"Warning: Profile '{profile_name}' not found: {e}")
            print("Falling back to environment or active profile")

    # Step 2: Check environment variable for profile
    env_profile = os.environ.get("PYTEST_INSIGHT_PROFILE")
    if env_profile and env_profile != "":
        try:
            profile = profile_manager.get_profile(env_profile)
            if profile.storage_type.lower() == "json":
                return JSONStorage(profile.file_path)
            elif profile.storage_type.lower() == "memory":
                return InMemoryStorage()
            else:
                raise ValueError(
                    f"Unsupported storage type in environment profile '{env_profile}': {profile.storage_type}"
                )
        except ValueError as e:
            print(f"Warning: Environment profile '{env_profile}' not found: {e}")
            print("Falling back to active profile")

    # Step 3: Use active profile
    profile = profile_manager.get_active_profile()
    if profile.storage_type.lower() == "json":
        return JSONStorage(profile.file_path)
    elif profile.storage_type.lower() == "memory":
        return InMemoryStorage()
    else:
        raise ValueError(
            f"Unsupported storage type in active profile '{profile.name}': {profile.storage_type}"
        )


# Global profile manager instance
_profile_manager = None


def get_profile_manager() -> ProfileManager:
    """Get the global profile manager instance.

    Returns:
        ProfileManager instance
    """
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager


def create_profile(
    name: str, storage_type: str = "json", file_path: Optional[str] = None
) -> StorageProfile:
    """Create a new storage profile.

    Args:
        name: Unique name for the profile
        storage_type: Type of storage (json, memory, etc.)
        file_path: Optional custom path for storage

    Returns:
        The created profile
    """
    # For backward compatibility, we still accept storage_type and file_path
    # but in the future, we'll encourage users to just use profiles
    return get_profile_manager()._create_profile(name, storage_type, file_path)


def switch_profile(name: str) -> StorageProfile:
    """Switch to a different profile.

    Args:
        name: Name of the profile to switch to

    Returns:
        The activated profile
    """
    return get_profile_manager().switch_profile(name)


def list_profiles() -> Dict[str, StorageProfile]:
    """List all available profiles.

    Returns:
        Dictionary of profile names to profile objects
    """
    return get_profile_manager().list_profiles()


def get_active_profile() -> StorageProfile:
    """Get the currently active profile.

    Returns:
        The active profile
    """
    return get_profile_manager().get_active_profile()
