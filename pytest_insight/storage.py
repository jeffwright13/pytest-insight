import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from pytest_insight.models import TestSession


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


class JSONTestResultStorage:
    """Store test sessions in a JSON file for persistence."""

    FILE_PATH = Path("test_sessions.json")

    def save_session(self, test_session: TestSession) -> None:
        """Append a new session to the JSON file instead of overwriting."""
        existing_sessions = self.load_sessions()  # Load existing sessions

        # Convert existing sessions to a list of dictionaries before saving
        session_dicts = [s.to_dict() for s in existing_sessions]

        # Append the new session's dictionary
        session_dicts.append(test_session.to_dict())

        # Write back all sessions
        self.FILE_PATH.write_text(json.dumps(session_dicts, indent=4))

    def load_sessions(self) -> List[TestSession]:
        """Retrieve all stored test sessions and ensure they are properly loaded."""
        if not self.FILE_PATH.exists():
            return []

        try:
            raw_data = json.loads(self.FILE_PATH.read_text())

            if not isinstance(raw_data, list):
                print(f"[pytest-insight] WARNING: Invalid JSON format in {self.FILE_PATH}, resetting.")
                self.clear_sessions()
                return []

            # Deserialize each session properly
            return [
                TestSession(
                    sut_name=d["sut_name"],
                    session_id=d["session_id"],
                    session_start_time=datetime.fromisoformat(d["session_start_time"]),
                    session_stop_time=datetime.fromisoformat(d["session_stop_time"]),
                    session_duration=timedelta(seconds=float(d["session_duration"].split(":")[-1])),
                )
                for d in raw_data
            ]

        except json.JSONDecodeError:
            print(f"[pytest-insight] ERROR: Corrupt JSON in {self.FILE_PATH}, resetting storage.")
            self.clear_sessions()
            return []

    def clear_sessions(self) -> None:
        """Delete all stored test sessions."""
        self.FILE_PATH.unlink(missing_ok=True)
