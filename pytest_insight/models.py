from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional


class TestResult:
    """
    Represents a single test result for an individual test run.
    """

    __test__ = False  # Tell Pytest this is NOT a test class

    def __init__(
        self,
        nodeid: str,
        outcome: str,
        start_time: datetime,
        duration: float,
        caplog: str = "",
        capstderr: str = "",
        capstdout: str = "",
        longreprtext: str = "",
        has_warning: bool = False,
    ):
        self.nodeid = nodeid
        self.outcome = outcome
        self.start_time = start_time
        self.duration = duration
        self.caplog = caplog
        self.capstderr = capstderr
        self.capstdout = capstdout
        self.longreprtext = longreprtext
        self.has_warning = has_warning


class OutputFieldType(Enum):
    """Valid output field types in pytest terminal output."""

    ERRORS = "errors"
    WARNINGS_SUMMARY = "warnings_summary"  # Added to match usage
    RERUN_TEST_SUMMARY = "rerun_test_summary"
    SHORT_TEST_SUMMARY = "short_test_summary"
    SESSION_START = "session_start"


class OutputField:
    """A section of pytest terminal output with specific content."""

    def __init__(self, field_type: OutputFieldType, content: str):
        self.field_type = field_type
        self.content = content.strip()

    def __str__(self) -> str:
        return self.content

    def __bool__(self) -> bool:
        return bool(self.content)


class OutputFields:
    """Collection of pytest terminal output sections."""

    def __init__(self):
        self._fields: Dict[OutputFieldType, OutputField] = {}

    @property
    def fields(self) -> Dict[OutputFieldType, OutputField]:
        """Get a copy of all output fields."""
        return self._fields.copy()

    def set(self, field_type: OutputFieldType, content: str) -> None:
        """Set content for a specific output field type."""
        self._fields[field_type] = OutputField(field_type, content)

    def get(self, field_type: OutputFieldType) -> Optional[OutputField]:
        """Get an output field by type."""
        return self._fields.get(field_type)

    def get_content(self, field_type: OutputFieldType) -> str:
        """Get content string for a field type."""
        field = self.get(field_type)
        return str(field) if field else ""

    @property
    def errors(self) -> str:
        """Get error output content."""
        return self.get_content(OutputFieldType.ERRORS)

    @property
    def warnings(self) -> str:
        """Get warnings output content."""
        return self.get_content(OutputFieldType.WARNINGS)

    @property
    def final_summary(self) -> str:
        """Get the final summary line."""
        return self.get_content(OutputFieldType.SHORT_TEST_SUMMARY)

    @property
    def rerun_summary(self) -> str:
        """Get rerun test summary."""
        return self.get_content(OutputFieldType.RERUN_SUMMARY)

    def __bool__(self) -> bool:
        return bool(self._fields)

    def __str__(self) -> str:
        return self.final_summary


class RerunTestGroup:
    """Represents a test that has been run multiple times using pytest-rerunfailures."""

    def __init__(self, nodeid: str, final_outcome: str):
        self.nodeid = nodeid
        self.final_outcome = final_outcome
        self._reruns: List[TestResult] = []
        self._full_test_list: List[TestResult] = []

    @property
    def reruns(self) -> List[TestResult]:
        """Get rerun test results."""
        return self._reruns.copy()

    @property
    def full_test_list(self) -> List[TestResult]:
        """Get full list of test results including original and reruns."""
        return self._full_test_list.copy()

    def add_rerun(self, result: TestResult) -> None:
        """Add a rerun test result."""
        self._reruns.append(result)

    def add_test(self, result: TestResult) -> None:
        """Add a test result to the full list."""
        self._full_test_list.append(result)

    @property
    def final_test(self) -> Optional[TestResult]:
        """Get the final test result."""
        return self._full_test_list[-1] if self._full_test_list else None


class TestSession:
    """Represents a single test session for a single SUT."""

    __test__ = False  # Tell Pytest this is NOT a test class

    def __init__(
        self,
        sut_name: str,
        session_id: str,
        session_start_time: datetime,
        session_stop_time: datetime,
        session_duration: timedelta,
    ):
        self.sut_name = sut_name
        self.session_id = session_id
        self.session_start_time = session_start_time
        self.session_stop_time = session_stop_time
        self.session_duration = session_duration

        self._test_results: List[TestResult] = []
        self._rerun_test_groups: List[RerunTestGroup] = []
        self._output_fields = OutputFields()  # Make private
        self.session_tags: Dict[str, str] = {}

    @property
    def output_fields(self) -> OutputFields:
        """Get output fields."""
        return self._output_fields

    @output_fields.setter
    def output_fields(self, fields: OutputFields) -> None:
        """Set output fields."""
        self._output_fields = fields

    @property
    def test_results(self) -> List[TestResult]:
        """Get all test results."""
        return self._test_results.copy()

    @property
    def rerun_test_groups(self) -> List[RerunTestGroup]:
        """Get all rerun test groups."""
        return self._rerun_test_groups.copy()

    def add_test_result(self, result: TestResult) -> None:
        """Add a test result to the session."""
        self._test_results.append(result)

    def add_rerun_group(self, group: RerunTestGroup) -> None:
        """Add a rerun test group to the session."""
        self._rerun_test_groups.append(group)

    @property
    def test_counts(self) -> Dict[str, int]:
        """Get counts of test results by outcome."""
        counts = {
            "passed": len(self.all_passes()),
            "failed": len(self.all_failures()),
            "skipped": len(self.all_skipped()),
            "xfailed": len(self.all_xfailed()),
            "xpassed": len(self.all_xpassed()),
            "rerun": len(self.all_reruns()),
            "error": len(self.with_error()),
            "warnings": len(self.with_warning()),
        }
        return counts

    def all_passes(self) -> List[TestResult]:
        return [t for t in self._test_results if t.outcome == "PASSED"]

    def all_failures(self) -> List[TestResult]:
        return [t for t in self._test_results if t.outcome == "FAILED"]

    def all_skipped(self) -> List[TestResult]:
        return [t for t in self._test_results if t.outcome == "SKIPPED"]

    def all_xfailed(self) -> List[TestResult]:
        return [t for t in self._test_results if t.outcome == "XFAILED"]

    def all_xpassed(self) -> List[TestResult]:
        return [t for t in self._test_results if t.outcome == "XPASSED"]

    def all_reruns(self) -> List[TestResult]:
        return [t for t in self._test_results if t.outcome == "RERUN"]

    def with_error(self) -> List[TestResult]:
        return [t for t in self._test_results if t.outcome == "ERROR"]

    def with_warning(self) -> List[TestResult]:
        return [t for t in self._test_results if t.has_warning]

    def find_test_result_by_nodeid(self, nodeid: str) -> TestResult:
        return next((t for t in self._test_results if t.nodeid == nodeid), None)

    def to_dict(self) -> dict:
        """Convert TestSession to a dictionary for JSON storage."""
        return {
            "sut_name": self.sut_name,
            "session_id": self.session_id,
            "session_start_time": self.session_start_time.isoformat(),
            "session_stop_time": self.session_stop_time.isoformat(),
            "session_duration": str(self.session_duration),
            "test_results": [tr.__dict__ for tr in self.test_results],
        }


class SUTGroup:
    """
    Represents a collection of test sessions for a single SUT.
    """

    def __init__(self, sut_name: str):
        self.sut_name = sut_name
        self.sessions: List[TestSession] = []

    def add_session(self, session: TestSession) -> None:
        self.sessions.append(session)

    def latest_session(self) -> TestSession:
        return max(self.sessions, key=lambda s: s.session_start_time) if self.sessions else None


class TestHistory:
    """Tracks test sessions across multiple SUTs."""

    __test__ = False  # Tell Pytest this is NOT a test class

    def __init__(self):
        self._sessions: Dict[str, SUTGroup] = {}

    @property
    def sessions(self) -> List[TestSession]:
        """Get all sessions across all SUTs."""
        all_sessions = []
        for sut_group in self._sessions.values():
            all_sessions.extend(sut_group.sessions)
        return all_sessions

    def add_test_session(self, session: TestSession) -> None:
        """Add a test session to the appropriate SUT group."""
        if session.sut_name not in self._sessions:
            self._sessions[session.sut_name] = SUTGroup(session.sut_name)
        self._sessions[session.sut_name].add_session(session)

    def get_sessions_for_sut(self, sut_name: str) -> List[TestSession]:
        return self._sessions.get(sut_name, SUTGroup(sut_name=sut_name)).sessions
