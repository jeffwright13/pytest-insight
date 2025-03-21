import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from pytest_insight.constants import DEFAULT_STORAGE_PATH
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

    def clear_sessions(self) -> None:
        """Remove all stored test sessions."""
        self._sessions.clear()


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

    def clear(self) -> None:
        """Clear all sessions from storage."""
        self._write_json_safely([])

    def clear_sessions(self) -> None:
        """Remove all stored sessions."""
        self.clear()

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
    storage_type: str = None, file_path: str = None
) -> BaseStorage:
    """Get storage instance based on configuration."""
    # Get storage type from args, env, or default
    storage_type = storage_type or os.environ.get("PYTEST_INSIGHT_STORAGE_TYPE", "json")

    # Get file path from args, env, or default
    if not file_path:
        file_path = os.environ.get("PYTEST_INSIGHT_DB_PATH")

    # Create appropriate storage instance
    if storage_type.lower() == "json":
        return JSONStorage(file_path)
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
