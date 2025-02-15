import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pytest_insight import constants
from pytest_insight.models import TestResult, TestSession


def get_storage_instance() -> "TestResultStorage":
    """Get configured storage instance."""
    storage_classes = {"JSONTestResultStorage": JSONTestResultStorage}
    storage_class = storage_classes[constants.DEFAULT_STORAGE_CLASS]
    return storage_class()


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

    def save_session(self, test_session: TestSession) -> None:
        """Append a new session to the JSON file instead of overwriting."""
        existing_sessions = self.load_sessions()  # Load existing sessions

        # Convert existing sessions to a list of dictionaries before saving
        session_dicts = [s.to_dict() for s in existing_sessions]

        # Append the new session's dictionary
        session_dicts.append(test_session.to_dict())

        # Convert `session_duration` to a float before saving
        for session in session_dicts:
            session["session_duration"] = test_session.session_duration.total_seconds()

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
                        for t in d.get("test_results", [])  # Ensure test_results are deserialized properly
                    ],
                )
                for d in raw_data
                if isinstance(d, dict)  # Ensure each item is a dictionary
            ]

        except json.JSONDecodeError:
            print(f"[pytest-insight] ERROR: Corrupt JSON in {self.FILE_PATH}, resetting storage.")
            self.clear_sessions()
            return []

    def clear_sessions(self) -> None:
        """Delete all stored test sessions."""
        self.FILE_PATH.unlink(missing_ok=True)
