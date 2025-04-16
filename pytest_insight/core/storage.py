import getpass
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import filelock

from pytest_insight.core.models import TestSession
from pytest_insight.utils.constants import DEFAULT_STORAGE_PATH


class StorageProfile:
    """Represents a storage configuration profile, which is a named storage configuration used to differentiate between different storage backends, different file paths, different SUTs/setups/environments, etc."""

    def __init__(
        self,
        name: str,
        storage_type: str = "json",
        file_path: Optional[str] = None,
        created: Optional[datetime] = None,
        last_modified: Optional[datetime] = None,
        created_by: Optional[str] = None,
        last_modified_by: Optional[str] = None,
    ):
        """Initialize a storage profile.

        Args:
            name: Unique name for the profile
            storage_type: Type of storage (json, memory, etc.)
            file_path: Optional custom path for storage. If None, a default path will be generated based on the profile name.
            created: Timestamp when the profile was created
            last_modified: Timestamp when the profile was last modified
            created_by: Username of the person who created the profile
            last_modified_by: Username of the person who last modified the profile
        """
        self.name = name
        self.storage_type = storage_type

        # Set timestamps and user info
        current_time = datetime.now()
        current_user = getpass.getuser() if hasattr(getpass, "getuser") else "unknown"

        self.created = created or current_time
        self.last_modified = last_modified or current_time
        self.created_by = created_by or current_user
        self.last_modified_by = last_modified_by or current_user

        # Generate default file path based on profile name if none provided
        if file_path is None:
            default_dir = Path.home() / ".pytest_insight" / "profiles"
            default_dir.mkdir(parents=True, exist_ok=True)
            self.file_path = str(default_dir / f"{name}.json")
        else:
            self.file_path = file_path

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        return {
            "name": self.name,
            "storage_type": self.storage_type,
            "file_path": self.file_path,
            "created": self.created.isoformat() if self.created else None,
            "last_modified": (
                self.last_modified.isoformat() if self.last_modified else None
            ),
            "created_by": self.created_by,
            "last_modified_by": self.last_modified_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StorageProfile":
        """Create profile from dictionary."""
        # Handle backward compatibility for profiles with old field names
        created_str = data.get("created") or data.get("created_at")
        last_modified_str = data.get("last_modified") or data.get("last_modified_at")

        # Convert string timestamps to datetime objects if they exist
        created = None
        if created_str:
            try:
                created = datetime.fromisoformat(created_str)
            except (ValueError, TypeError):
                # If conversion fails, use the string as-is for logging but set to current time
                print(
                    f"Warning: Invalid created format: {created_str}. Using current time."
                )
                created = datetime.now()

        last_modified = None
        if last_modified_str:
            try:
                last_modified = datetime.fromisoformat(last_modified_str)
            except (ValueError, TypeError):
                # If conversion fails, use the string as-is for logging but set to current time
                print(
                    f"Warning: Invalid last_modified format: {last_modified_str}. Using current time."
                )
                last_modified = datetime.now()

        return cls(
            name=data["name"],
            storage_type=data.get("storage_type", "json"),
            file_path=data.get("file_path"),
            created=created,
            last_modified=last_modified,
            created_by=data.get("created_by"),
            last_modified_by=data.get("last_modified_by"),
        )


class ProfileManager:
    """Manages storage profiles for pytest-insight. Profiles are used to differentiate between different storage
    backends, different file paths, different SUTs/setups/environments, etc."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize profile manager.

        Args:
            config_path: Optional custom path for profile configuration
        """
        # Create the main directory structure
        base_dir = Path.home() / ".pytest_insight"
        config_dir = base_dir / "config"
        profiles_dir = base_dir / "profiles"
        history_dir = base_dir / "history"

        # Ensure all directories exist
        for directory in [base_dir, config_dir, profiles_dir, history_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.config_path = config_path or config_dir / "profiles.json"
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

            # Log metadata if available
            if "last_modified" in data and "modified_by" in data:
                print(
                    f"Profiles last modified at {data['last_modified']} by {data['modified_by']}"
                )

        except Exception as e:
            print(f"Warning: Failed to load profiles from {self.config_path}: {e}")
            # Create default profile
            self.profiles = {"default": StorageProfile("default", "json")}
            self.active_profile_name = "default"
            self._save_profiles()

    def _save_profiles(self) -> None:
        """Save profiles to disk."""
        # Don't save if we're in memory-only mode
        if hasattr(self, "memory_only") and self.memory_only:
            return

        # Create a backup before saving
        if self.config_path.exists():
            self.backup_profiles()

        # Create parent directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Update last_modified timestamp for all profiles
        current_time = datetime.now()
        current_user = getpass.getuser() if hasattr(getpass, "getuser") else "unknown"

        for profile in self.profiles.values():
            profile.last_modified = current_time
            profile.last_modified_by = current_user

        # Only include non-memory profiles for persistence
        persistent_profiles = {
            name: profile.to_dict()
            for name, profile in self.profiles.items()
            if profile.storage_type != "memory"
        }

        # Write to a temporary file first to avoid corruption
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=str(self.config_path.parent)
        ) as tmp:
            json.dump(
                {
                    "active_profile": self.active_profile_name,
                    "profiles": persistent_profiles,
                    "last_modified": current_time.isoformat(),
                    "modified_by": current_user,
                },
                tmp,
                indent=2,
            )

        # Use atomic replace to avoid corruption
        shutil.move(tmp.name, str(self.config_path))

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

    def list_profiles(
        self, storage_type: Optional[str] = None, pattern: Optional[str] = None
    ) -> Dict[str, StorageProfile]:
        """List available profiles, optionally filtered by storage type and/or name pattern.

        Args:
            storage_type: Optional filter by storage type ('json' or 'memory')
            pattern: Optional glob pattern to filter profile names

        Returns:
            Dictionary of profile names to profile objects that match the filters
        """
        result = self.profiles.copy()

        # Filter by storage type if specified
        if storage_type:
            result = {
                name: profile
                for name, profile in result.items()
                if profile.storage_type == storage_type
            }

        # Filter by pattern if specified
        if pattern:
            import fnmatch

            result = {
                name: profile
                for name, profile in result.items()
                if fnmatch.fnmatch(name, pattern)
            }

        return result

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
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the save_session method...did you mean to call it on the {self.__class__.__name__} class?"
        )

    def load_sessions(
        self,
        chunk_size: int = 1000,
        **kwargs,
    ) -> List[TestSession]:
        """Retrieve past test sessions.

        This base implementation provides a common interface for all storage types.
        Subclasses can implement additional parameters via **kwargs.

        Common parameters that may be supported by subclasses:
            chunk_size: Number of sessions to load at once (for large files)

        Returns:
            List of TestSession objects
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the load_sessions method...did you mean to call it on the {self.__class__.__name__} class?"
        )

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
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the clear_sessions method...did you mean to call it on the {self.__class__.__name__} class?"
        )

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        """Retrieve a test session by its unique identifier."""
        sessions = self.load_sessions()
        return next((s for s in sessions if s.session_id == session_id), None)

    def get_last_session(self) -> Optional[TestSession]:
        """Get the most recent test session.

        Returns:
            The most recent session, or None if no sessions exist
        """
        sessions = self.load_sessions()
        return max(sessions, key=lambda s: s.session_start_time) if sessions else None


class InMemoryStorage(BaseStorage):
    """In-memory storage implementation."""

    def __init__(self, sessions: Optional[List[TestSession]] = None):
        """Initialize storage with optional sessions."""
        super().__init__()
        self._sessions = sessions if sessions is not None else []

    def load_sessions(self, **kwargs) -> List[TestSession]:
        """Get all stored sessions.

        Args:
            **kwargs: Additional parameters (ignored in memory storage)

        Returns:
            List of TestSession objects
        """
        return self._sessions.copy()

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

    def __init__(
        self, file_path: Optional[Path] = None, profile_name: Optional[str] = None
    ):
        """Initialize storage with optional custom file path.

        Args:
            file_path: Optional custom path for session storage.
                      If not provided, uses ~/.pytest_insight/sessions.json
            profile_name: Optional profile name for this storage instance.
        """
        super().__init__()
        self.file_path = Path(file_path) if file_path else DEFAULT_STORAGE_PATH
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize file if it doesn't exist
        if not self.file_path.exists():
            self._write_json_safely([])

    def load_sessions(
        self,
        chunk_size: int = 1000,
        use_streaming: bool = False,
        **kwargs,
    ) -> List[TestSession]:
        """Load all test sessions from storage.

        Args:
            chunk_size: Number of sessions to load at once (for large files)
            use_streaming: Whether to use streaming parser for large files (requires ijson)

        Returns:
            List of TestSession objects
        """
        # Use streaming parser for large files if requested
        if use_streaming:
            try:
                # Try to import ijson only when needed
                import importlib.util

                if importlib.util.find_spec("ijson") is not None:
                    return self._load_sessions_streaming(chunk_size)
                else:
                    print(
                        "Warning: ijson not installed. Falling back to standard JSON loading."
                    )
            except ImportError:
                print(
                    "Warning: Could not check for ijson. Falling back to standard JSON loading."
                )
                # Fall back to regular loading if import check fails

        try:
            # Use _read_json_safely to get data from storage file
            data = self._read_json_safely()

            if not data:
                return []
        except json.JSONDecodeError:
            # Create backup of corrupted file
            backup_path = self.file_path.with_suffix(".bak")
            shutil.copy2(self.file_path, backup_path)
            print(
                f"Warning: JSON decode error in {self.file_path}. Backup created at {backup_path}"
            )
            return []

        # Handle both formats: {"sessions": [...]} and directly [...]
        sessions_data = data.get("sessions", []) if isinstance(data, dict) else data

        # Ensure sessions_data is a list
        if not isinstance(sessions_data, list):
            print(
                f"Warning: Invalid sessions data format. Expected list, got {type(sessions_data).__name__}"
            )
            return []

        total_sessions = len(sessions_data)

        # Process sessions in chunks to avoid memory issues with large files
        sessions = []
        for i in range(0, total_sessions, chunk_size):
            chunk = sessions_data[i : i + chunk_size]
            for j, session_data in enumerate(chunk):
                try:
                    # Handle both dictionary and TestSession objects
                    if isinstance(session_data, dict):
                        session = TestSession.from_dict(session_data)
                        sessions.append(session)
                    elif isinstance(session_data, TestSession):
                        sessions.append(session_data)
                    else:
                        print(
                            f"Warning: Invalid session data type: {type(session_data).__name__}"
                        )
                except Exception as e:
                    print(f"Failed to load session: {e}")

        return sessions

    def _load_sessions_streaming(self, chunk_size: int = 1000) -> List[TestSession]:
        """Load sessions using a streaming JSON parser for large files.

        Args:
            chunk_size: Number of sessions to process at once

        Returns:
            List of TestSession objects
        """
        try:
            import ijson
        except ImportError:
            print(
                "Error: ijson package is required for streaming. Install with: pip install ijson"
            )
            return []

        sessions = []

        try:
            with open(self.file_path, "rb") as f:
                # Determine if we're parsing a list or a dict with "sessions" key
                # Read a small chunk to check format
                first_bytes = f.read(100)
                f.seek(0)  # Reset position

                # Check if file starts with an array or object
                is_array = first_bytes.lstrip().startswith(b"[")

                # Set the appropriate path prefix for ijson
                prefix = "item" if is_array else "sessions.item"

                # Parse the file
                current_chunk = []

                for session_data in ijson.items(f, prefix):
                    try:
                        # Create session object
                        session = TestSession.from_dict(session_data)
                        current_chunk.append(session)

                        # Process in chunks
                        if len(current_chunk) >= chunk_size:
                            sessions.extend(current_chunk)
                            current_chunk = []

                    except Exception as e:
                        print(f"Error parsing session: {e}")

                # Add any remaining sessions
                if current_chunk:
                    sessions.extend(current_chunk)

            return sessions

        except Exception as e:
            print(f"Error streaming sessions: {e}")
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

    def _write_json_safely(self, sessions_data: List[Dict]) -> None:
        """Write JSON data safely to avoid corruption.

        Uses file locking to prevent concurrent writes from multiple processes.

        Args:
            sessions_data: List of session data dictionaries
        """
        # Create a lock file path
        lock_file = f"{self.file_path}.lock"

        # Acquire a lock before writing
        lock = filelock.FileLock(lock_file, timeout=30)
        try:
            with lock:
                # Create a temporary file
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, mode="w", suffix=".json"
                )
                try:
                    # Write data to temp file
                    json.dump({"sessions": sessions_data}, temp_file, indent=2)
                    temp_file.close()

                    # Ensure directory exists
                    os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

                    # Move temp file to target location
                    shutil.move(temp_file.name, self.file_path)
                except Exception as e:
                    # Clean up temp file on error
                    os.unlink(temp_file.name)
                    raise e
        finally:
            # Clean up the lock file after use
            try:
                if os.path.exists(lock_file):
                    os.unlink(lock_file)
            except OSError:
                # If we can't delete the lock file, log a warning but don't fail
                print(f"Warning: Could not delete lock file {lock_file}")

    def _read_json_safely(self) -> Any:
        """Read JSON data from storage file. Creates a backup if the file is corrupted, then returns empty list. Also returns empty list if file doesn't exist or is invalid.

        Returns:
            Parsed JSON data, or empty list if file was corrupted, doesn't exist or is invalid
        """
        if not self.file_path.exists():
            return []

        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError:
            # Create backup of corrupted file
            backup_path = self.file_path.with_suffix(".bak")
            shutil.copy2(self.file_path, backup_path)
            print(
                f"Warning: JSON decode error in {self.file_path}. Backup created at {backup_path}"
            )
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
        except ValueError:
            # Create the profile if it doesn't exist and ensure it's saved
            print(f"Creating new profile: '{profile_name}'")
            # Create the profile using the profile manager directly to avoid circular imports
            new_profile = profile_manager._create_profile(profile_name)
            profile_manager._save_profiles()  # Explicitly save the profiles to disk

            if new_profile.storage_type.lower() == "json":
                return JSONStorage(new_profile.file_path)
            elif new_profile.storage_type.lower() == "memory":
                return InMemoryStorage()
            else:
                raise ValueError(
                    f"Unsupported storage type in new profile '{profile_name}': {new_profile.storage_type}"
                )
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

    Raises:
        ValueError: If profile already exists
    """
    profile_manager = get_profile_manager()

    # Create timestamp information
    current_time = datetime.now()
    creator = getpass.getuser() if hasattr(getpass, "getuser") else "unknown"

    # Print creation information
    print(f"Creating profile '{name}' at {current_time.isoformat()} by {creator}")

    profile = profile_manager._create_profile(name, storage_type, file_path)
    return profile


def switch_profile(name: str) -> StorageProfile:
    """Switch to a different profile.

    Args:
        name: Name of the profile to switch to

    Returns:
        The activated profile
    """
    return get_profile_manager().switch_profile(name)


def list_profiles(
    storage_type: Optional[str] = None, pattern: Optional[str] = None
) -> Dict[str, StorageProfile]:
    """List available profiles, optionally filtered by storage type and/or name pattern.

    Args:
        storage_type: Optional filter by storage type ('json' or 'memory')
        pattern: Optional glob pattern to filter profile names

    Returns:
        Dictionary of profile names to profile objects that match the filters
    """
    return get_profile_manager().list_profiles(storage_type, pattern)


def get_active_profile() -> StorageProfile:
    """Get the currently active profile.

    Returns:
        The active profile
    """
    return get_profile_manager().get_active_profile()


def get_profile_metadata(name: Optional[str] = None) -> Dict[str, Any]:
    """Get metadata about a profile or all profiles.

    Args:
        name: Optional name of the profile to get metadata for. If None, returns metadata for all profiles.

    Returns:
        Dictionary containing metadata about the profile(s)
    """
    profile_manager = get_profile_manager()

    # Load the profiles.json file directly to get the metadata
    if not profile_manager.config_path.exists():
        return {"error": "No profiles configuration found"}

    try:
        data = json.loads(profile_manager.config_path.read_text())

        # Extract global metadata
        metadata = {
            "last_modified": data.get("last_modified", "unknown"),
            "modified_by": data.get("modified_by", "unknown"),
            "active_profile": data.get("active_profile", "default"),
            "profiles_count": len(data.get("profiles", {})),
        }

        # Helper function to safely convert timestamp strings to datetime
        def safe_parse_datetime(dt_str):
            if not dt_str or dt_str == "unknown":
                return "unknown"
            try:
                return datetime.fromisoformat(dt_str)
            except (ValueError, TypeError):
                return "unknown"

        # If a specific profile is requested, add its metadata
        if name:
            if name in data.get("profiles", {}):
                profile_data = data["profiles"][name]
                metadata["profile"] = {
                    "name": name,
                    "storage_type": profile_data.get("storage_type", "unknown"),
                    "file_path": profile_data.get("file_path", "unknown"),
                    "created": safe_parse_datetime(profile_data.get("created")),
                    "last_modified": safe_parse_datetime(
                        profile_data.get("last_modified")
                    ),
                    "created_by": profile_data.get("created_by", "unknown"),
                    "last_modified_by": profile_data.get("last_modified_by", "unknown"),
                }
            else:
                metadata["error"] = f"Profile '{name}' not found"
        else:
            # Add summary of all profiles
            metadata["profiles"] = {
                name: {
                    "storage_type": profile_data.get("storage_type", "unknown"),
                    "created": safe_parse_datetime(profile_data.get("created")),
                    "last_modified": safe_parse_datetime(
                        profile_data.get("last_modified")
                    ),
                    "created_by": profile_data.get("created_by", "unknown"),
                    "last_modified_by": profile_data.get("last_modified_by", "unknown"),
                }
                for name, profile_data in data.get("profiles", {}).items()
            }

        return metadata
    except Exception as e:
        return {"error": f"Failed to load profile metadata: {str(e)}"}


# Main entry point for loading sessions
def load_sessions(
    profile_name: Optional[str] = None,
    chunk_size: int = 1000,
    use_streaming: bool = False,
) -> List[TestSession]:
    """Load sessions from the specified storage profile.

    Args:
        profile_name: Storage profile name to use
        chunk_size: Number of sessions to load at once (for large files)
        use_streaming: Whether to use streaming parser for large files (requires ijson)

    Returns:
        List of TestSession objects
    """
    storage_instance = get_storage_instance(profile_name=profile_name)

    # All storage classes now support the same parameters via **kwargs
    return storage_instance.load_sessions(
        chunk_size=chunk_size, use_streaming=use_streaming
    )


# Main entry point
if __name__ == "__main__":
    # Example usage
    pass
