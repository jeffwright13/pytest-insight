import os
import fcntl  # Only works on Unix-like systems. Windows alternative: `msvcrt.locking`
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pytest_insight import constants
from pytest_insight.models import TestResult, TestSession


def get_storage_instance() -> "TestResultStorage":
    """Get configured storage instance dynamically, either from env var PYTEST_INSIGHT_STORAGE or from constants.py."""
    storage_map = {
        "json": JSONTestResultStorage,
        "memory": InMemoryTestResultStorage,
        # Future: "sql": SQLTestResultStorage
    }
    storage_type = os.getenv("PYTEST_INSIGHT_STORAGE", constants.DEFAULT_STORAGE_CLASS).lower()
    return storage_map.get(storage_type, JSONTestResultStorage)()

class StorageManager:
    """Manages selection and delegation to the appropriate storage backend."""

    def __init__(self):
        """Initialize the storage backend based on configuration."""
        self.storage = get_storage_instance()

    def save_session(self, test_session: TestSession) -> None:
        self.storage.save_session(test_session)

    def load_sessions(self) -> List[TestSession]:
        return self.storage.load_sessions()

    def clear_sessions(self) -> None:
        self.storage.clear_sessions()

    def get_last_session(self) -> Optional[TestSession]:
        return self.storage.get_last_session()

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        return self.storage.get_session_by_id(session_id)

    def get_sessions_summary(self) -> List[str]:
        return self.storage.get_sessions_summary()

class TestResultStorage:
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


class InMemoryTestResultStorage(TestResultStorage):
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


class JSONTestResultStorage(TestResultStorage):
    """Store test sessions in a JSON file for persistence."""

    FILE_PATH = Path("test_sessions.json")

    def __init__(self):
        self._session_index = {}  # Dictionary for fast lookups

    def save_session(self, test_session: TestSession) -> None:
        """Append a new session to the JSON file safely."""
        existing_sessions = self.load_sessions()

        session_dicts = [s.to_dict() for s in existing_sessions]
        session_dicts.append(test_session.to_dict())

        try:
            with self.FILE_PATH.open("w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(session_dicts, f, indent=4)
                fcntl.flock(f, fcntl.LOCK_UN)
        except PermissionError:
            print(f"[pytest-insight] ERROR: Permission denied. Check write access to {self.FILE_PATH}")
        except Exception as e:
            print(f"[pytest-insight] ERROR: Failed to write session data - {e}")

    def load_sessions(self) -> List[TestSession]:
        """Retrieve all stored test sessions, handling corruption gracefully."""
        if not self.FILE_PATH.exists():
            return []

        try:
            with self.FILE_PATH.open("r") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, list):
                print(
                    f"[pytest-insight] WARNING: Invalid JSON format in {self.FILE_PATH}. Skipping load."
                )
                return []

            self._session_index = {}
            sessions = []
            for d in raw_data:
                if not isinstance(d, dict):
                    continue

                try:
                    session = TestSession(
                        sut_name=d["sut_name"],
                        session_id=d["session_id"],
                        session_start_time=datetime.fromisoformat(
                            d["session_start_time"]
                        ),
                        session_stop_time=datetime.fromisoformat(
                            d["session_stop_time"]
                        ),
                        test_results=[
                            TestResult(
                                nodeid=t["nodeid"],
                                outcome=t["outcome"],
                                start_time=datetime.fromisoformat(t["start_time"]),
                                duration=t["duration"],
                                caplog=t.get("caplog", ""),
                                capstderr=t.get("capstderr", ""),
                                capstdout=t.get("capstdout", ""),
                                longreprtext=t.get("longreprtext", ""),
                                has_warning=t.get("has_warning", False),
                            )
                            for t in d.get(
                                "test_results", []
                            )  # Ensure test_results are deserialized properly
                        ],
                    )

                    self._session_index[session.session_id] = session
                    sessions.append(session)

                except (KeyError, ValueError) as e:
                    print(f"[pytest-insight] WARNING: Skipping malformed session: {e}")

            return sessions

        except json.JSONDecodeError:
            print(
                f"[pytest-insight] ERROR: Corrupt JSON detected in {self.FILE_PATH}. Try fixing manually."
            )
            return []

    def get_session_by_id(self, session_id: str) -> Optional[TestSession]:
        """Retrieve a test session by ID, ensuring index is populated."""
        if not self._session_index:  # Ensure index is built
            self.load_sessions()
        return self._session_index.get(session_id)

    def clear_sessions(self) -> None:
        """Delete all stored test sessions safely."""
        try:
            if self.FILE_PATH.exists():
                self.FILE_PATH.unlink()
            self._session_index.clear()  # Also clear in-memory index
        except Exception as e:
            print(f"[pytest-insight] ERROR: Failed to clear session storage - {e}")
