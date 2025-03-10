import fcntl
import json
import os
from pathlib import Path
from typing import List, Optional

from pytest_insight.config import get_config
from pytest_insight.constants import StorageType
from pytest_insight.models import TestSession


class BaseStorage:
    """Abstract interface for persisting test session data."""

    def save_session(self, test_session: TestSession) -> None:
        """Persist a test session."""
        raise NotImplementedError

    def load_sessions(self) -> List[TestSession]:
        """Retrieve past test sessions."""
        raise NotImplementedError

    def clear_sessions(self) -> None:
        """Remove all stored sessions."""
        raise NotImplementedError

    def get_last_session(self) -> Optional[TestSession]:
        """Retrieve the most recent test session."""
        sessions = self.load_sessions()
        return max(sessions, key=lambda s: s.session_start_time) if sessions else None

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        """Retrieve a test session by its unique identifier."""
        sessions = self.load_sessions()
        return next((s for s in sessions if s.session_id == session_id), None)

    def get_sessions_summary(self) -> List[str]:
        """Get formatted summary strings for all test sessions."""
        sessions = self.load_sessions()
        if not sessions:
            return ["[pytest-insight] No test sessions found."]

        return [
            (
                f"Session {idx}: {session.session_id}, "
                f"Started: {session.session_start_time}, "
                f"Duration: {session.session_duration}, "
                f"Tests: {len(session.test_results)}\n"
                f"{session.outcome_summary}"
            )
            for idx, session in enumerate(sessions, start=1)
        ]


class InMemoryStorage(BaseStorage):
    """In-memory storage implementation."""

    def __init__(self, sessions=None):
        """Initialize storage with optional sessions."""
        super().__init__()
        self._sessions = sessions if sessions is not None else []

    def load_sessions(self) -> List[TestSession]:
        """Get all stored sessions."""
        return self._sessions

    def save_session(self, session: TestSession) -> None:
        """Save a test session."""
        self._sessions.append(session)

    def clear_sessions(self) -> None:
        """Remove all stored test sessions."""
        self._sessions.clear()


class JSONStorage(BaseStorage):
    """Store test sessions in a JSON file for persistence with safe writes and corruption recovery."""

    FILE_PATH = Path.home() / ".pytest_insight" / "test_sessions.json"

    def __init__(self, file_path: Optional[Path] = None):
        """Initialize storage with optional custom file path."""
        self.file_path = Path(file_path) if file_path else self.FILE_PATH
        self.backup_path = self.file_path.with_suffix(".backup")

        # Create parent directories immediately
        if self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: TestSession) -> None:
        """Save a test session to JSON storage."""
        # Load existing data or create new
        data = []
        if self.file_path.exists():
            with open(self.file_path) as f:
                data = json.load(f)

        # Add new session and save
        data.append(session.to_dict())

        # Ensure parent directories exist before writing
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(self.file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_sessions(self) -> List[TestSession]:
        """Load all test sessions, recovering from backup if needed."""
        if not self.file_path.exists():
            print(f"[INFO] Database file not found: {self.file_path}")
            return []

        # Handle empty file case
        if self.file_path.stat().st_size == 0:
            print(f"[INFO] Empty database file: {self.file_path}")
            self.file_path.unlink()
            return []

        try:
            with self.file_path.open("r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    print(f"[INFO] Loading sessions from {self.file_path}")
                    data = json.load(f)
                    print(f"[INFO] Successfully loaded {len(data)} sessions")
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Failed to parse JSON ({self.file_path}): {e}")
                    print("[INFO] Looking for backup file...")
                    fcntl.flock(f, fcntl.LOCK_UN)
                    return self._recover_from_backup()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

            # Process valid data
            if not isinstance(data, list):
                print("[ERROR] Invalid data format (not a list)")
                return []

            sessions = []
            for item in data:
                if isinstance(item, dict):
                    try:
                        session = TestSession.from_dict(item)
                        sessions.append(session)
                    except (KeyError, ValueError) as e:
                        print(f"[WARN] Skipping invalid session: {e}")
                        continue

            return sessions
        except Exception as e:
            print(f"[ERROR] Failed to load sessions: {e}")
            return []

    def _recover_from_backup(self) -> List[TestSession]:
        """Try to recover from a backup file."""
        backup_path = self.file_path.with_suffix(".json.bak")
        if backup_path.exists():
            print(f"[INFO] Trying to recover from backup: {backup_path}")
            try:
                with backup_path.open("r") as f:
                    data = json.load(f)
                    # Process backup data like normal data
                    if not isinstance(data, list):
                        return []

                    sessions = []
                    for item in data:
                        if isinstance(item, dict):
                            try:
                                session = TestSession.from_dict(item)
                                sessions.append(session)
                            except (KeyError, ValueError):
                                continue

                    print(f"[INFO] Successfully recovered {len(sessions)} sessions from backup")
                    return sessions
            except Exception as e:
                print(f"[ERROR] Backup recovery failed: {e}")
        else:
            print(f"[INFO] No backup file found: {backup_path}")

        return []

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        """Retrieve a test session by ID, ensuring index is populated."""
        sessions = self.load_sessions()
        return next((s for s in sessions if s.session_id == session_id), None)

    def clear_sessions(self) -> None:
        """Delete all stored test sessions safely."""
        if self.file_path.exists():
            self.file_path.unlink()


def get_storage_instance(storage_type: str = None, file_path: str = None) -> BaseStorage:
    """Get storage instance based on configuration."""
    # Check config for file path first
    config = get_config()
    if config.get("db_path"):
        file_path = config["db_path"]
        print(f"[STORAGE] Using DB path from config: {file_path}")
    elif file_path:
        print(f"[STORAGE] Using provided DB path: {file_path}")
    else:
        print("[STORAGE] Using default DB path")

    # Process storage type
    storage_type = storage_type or os.environ.get("PYTEST_INSIGHT_STORAGE_TYPE", StorageType.JSON.value)

    if storage_type.lower() == StorageType.JSON.value:
        return JSONStorage(file_path)
    elif storage_type == StorageType.LOCAL.value:
        return InMemoryStorage()
    elif storage_type == StorageType.REMOTE.value:
        # Future: Return RemoteStorage implementation
        raise NotImplementedError("Remote storage not yet implemented")
    elif storage_type == StorageType.DATABASE.value:
        # Future: Return DatabaseStorage implementation
        raise NotImplementedError("Database storage not yet implemented")
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
