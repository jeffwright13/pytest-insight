import os
import json
import fcntl
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pytest_insight.models import TestResult, TestSession
from pytest_insight.constants import DEFAULT_STORAGE_CLASS

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
    """Temporary, in-memory storage for test sessions."""

    def __init__(self):
        self.sessions: List[TestSession] = []

    def save_session(self, test_session: TestSession) -> None:
        """Save a session in memory."""
        self.sessions.append(test_session)

    def load_sessions(self) -> List[TestSession]:
        """Retrieve all stored test sessions."""
        return self.sessions

    def clear_sessions(self) -> None:
        """Remove all stored test sessions."""
        self.sessions.clear()

class JSONStorage(BaseStorage):
    """Store test sessions in a JSON file for persistence with safe writes and corruption recovery."""

    FILE_PATH = Path.home() / ".pytest_insight" / "test_sessions.json"
    BACKUP_PATH = FILE_PATH.with_suffix('.backup')

    def __init__(self):
        super().__init__()
        self._session_index = {}

    def save_session(self, test_session: TestSession) -> None:
        """Save a test session to storage."""
        temp_path = self.FILE_PATH.with_suffix('.tmp')

        try:
            # Ensure parent directory exists
            self.FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Load existing sessions
            sessions = []
            if self.FILE_PATH.exists():
                try:
                    with self.FILE_PATH.open('r') as f:
                        fcntl.flock(f, fcntl.LOCK_SH)
                        data = json.load(f)
                        fcntl.flock(f, fcntl.LOCK_UN)
                        if isinstance(data, list):
                            sessions = data
                except json.JSONDecodeError:
                    # Create backup of corrupt file
                    if self.FILE_PATH.exists():
                        shutil.copy(self.FILE_PATH, self.BACKUP_PATH)

            # Add new session and write to temp file
            sessions.append(test_session.to_dict())
            with temp_path.open('w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(sessions, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f, fcntl.LOCK_UN)

            # Atomically replace original file
            temp_path.rename(self.FILE_PATH)

        except Exception as e:
            print(f"[pytest-insight] ERROR: Failed to write session data - {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load_sessions(self) -> List[TestSession]:
        """Load all test sessions, recovering from backup if needed."""
        if not self.FILE_PATH.exists():
            return []

        try:
            # Handle empty file case
            if self.FILE_PATH.stat().st_size == 0:
                self.FILE_PATH.unlink()
                return []

            with self.FILE_PATH.open('r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)

            if not isinstance(data, list):
                return []

            sessions = []
            for item in data:
                if isinstance(item, dict):
                    try:
                        session = TestSession.from_dict(item)
                        sessions.append(session)
                        self._session_index[session.session_id] = session
                    except (KeyError, ValueError):
                        continue

            return sessions

        except json.JSONDecodeError:
            return self._recover_from_backup()

    def _recover_from_backup(self) -> List[TestSession]:
        """Recover data from backup file and replace main file if possible."""
        try:
            if not self.BACKUP_PATH.exists():
                print("[pytest-insight] No backup found. Recovery failed.")
                return []

            with self.BACKUP_PATH.open('r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                raw_data = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)

            if not isinstance(raw_data, list):
                print("[pytest-insight] Backup file is not in the correct format.")
                return []

            valid_sessions = [TestSession.from_dict(item) for item in raw_data if isinstance(item, dict)]

            if valid_sessions:
                print("[pytest-insight] Restoring from backup...")
                shutil.copy(self.BACKUP_PATH, self.FILE_PATH)  # ✅ Replace corrupted file
                return valid_sessions

        except (json.JSONDecodeError, OSError) as e:
            print(f"[pytest-insight] ERROR: Could not recover from backup: {e}")

        print("[pytest-insight] Both primary and backup JSON files are corrupt. Starting fresh.")
        return []

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        """Retrieve a test session by ID, ensuring index is populated."""
        if not self._session_index:
            self.load_sessions()
        return self._session_index.get(session_id)

    def clear_sessions(self) -> None:
        """Delete all stored test sessions safely."""
        try:
            if self.FILE_PATH.exists():
                self.FILE_PATH.unlink()
            self._session_index.clear()
        except Exception as e:
            print(f"[pytest-insight] ERROR: Failed to clear session storage - {e}")

def get_storage_instance() -> "BaseStorage":
    """Get configured storage instance."""
    storage_classes = {
        "JSONStorage": JSONStorage,
        "InMemoryStorage": InMemoryStorage,
    }
    return storage_classes.get(DEFAULT_STORAGE_CLASS, JSONStorage)()
