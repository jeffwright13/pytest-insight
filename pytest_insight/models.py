from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional


class TestResult:
    """
    Represents a single test result for an individual test run.
    """

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

    TEST_SESSION_STARTS = "test_session_starts"
    ERRORS = "errors"
    FAILURES = "failures"
    PASSES = "passes"
    WARNINGS_SUMMARY = "warnings_summary"
    RERUN_TEST_SUMMARY = "rerun_test_summary"
    SHORT_TEST_SUMMARY = "short_test_summary"
    LAST_LINE = "lastline"


class OutputField:
    """A section of pytest terminal output with specific content type."""

    def __init__(self, field_type: OutputFieldType, content: str):
        """
        Initialize an output field.

        Args:
            field_type: Type of output field from OutputFieldType enum
            content: The actual content of the field
        """
        self.field_type = field_type
        self.content = content

    def __str__(self) -> str:
        return self.content

    def __bool__(self) -> bool:
        return bool(self.content)


class OutputFields:
    """Collection of pytest terminal output sections."""

    def __init__(self):
        """Initialize empty output fields collection."""
        self._fields: Dict[OutputFieldType, OutputField] = {}

    def set(self, field_type: OutputFieldType, content: str) -> None:
        """
        Set content for a specific output field type.

        Args:
            field_type: Type of field to set
            content: Content to store in the field
        """
        self._fields[field_type] = OutputField(field_type, content)

    def get(self, field_type: OutputFieldType) -> Optional[OutputField]:
        """
        Get content of a specific output field type.

        Args:
            field_type: Type of field to retrieve

        Returns:
            OutputField if it exists, None otherwise
        """
        return self._fields.get(field_type)

    def get_content(self, field_type: OutputFieldType) -> str:
        """
        Get content string of a specific output field type.

        Args:
            field_type: Type of field to retrieve content from

        Returns:
            Content string if field exists, empty string otherwise
        """
        field = self.get(field_type)
        return field.content if field else ""

    @property
    def fields(self) -> Dict[OutputFieldType, OutputField]:
        """Get all output fields."""
        return self._fields.copy()

    def __bool__(self) -> bool:
        return bool(self._fields)


class RerunTestGroup:
    """
    Represents a test that has been run multiple times (aka 'rerun') using the pytest-rerunfailures plugin.
    """

    def __init__(self, nodeid: str, final_outcome: str):
        self.nodeid = nodeid
        self.final_outcome = final_outcome
        self.reruns: List[TestResult] = []
        self.full_test_list: List[TestResult] = []

    @property
    def final_test(self) -> TestResult:
        return self.full_test_list[-1] if self.full_test_list else None


class TestSession:
    """
    Represents a single test session for a single SUT. This is generally made up of multiple TestResult objects.
    """

    def __init__(
        self,
        sut_name: str,
        session_id: str,
        session_start_time: datetime,
        session_stop_time: datetime,
        session_duration: timedelta,  # TODO: Is this necessary for init(), or can we just calculate it?
    ):
        self.sut_name = sut_name
        self.session_id = session_id
        self.session_start_time = session_start_time
        self.session_stop_time = session_stop_time
        self.session_duration = session_duration

        self.test_results: List[TestResult] = []
        self.rerun_test_groups: List[RerunTestGroup] = []
        self.output_fields = OutputFields()
        self.session_tags: Dict[str, str] = {}

    def all_passes(self) -> List[TestResult]:
        return [t for t in self.test_results if t.outcome == "PASSED"]

    def all_failures(self) -> List[TestResult]:
        return [t for t in self.test_results if t.outcome == "FAILED"]

    def all_skipped(self) -> List[TestResult]:
        return [t for t in self.test_results if t.outcome == "SKIPPED"]

    def all_xfailed(self) -> List[TestResult]:
        return [t for t in self.test_results if t.outcome == "XFAILED"]

    def all_xpassed(self) -> List[TestResult]:
        return [t for t in self.test_results if t.outcome == "XPASSED"]

    def all_reruns(self) -> List[TestResult]:
        return [t for t in self.test_results if t.outcome == "RERUN"]

    def with_error(self) -> List[TestResult]:
        return [t for t in self.test_results if t.outcome == "ERROR"]

    def with_warning(self) -> List[TestResult]:
        return [t for t in self.test_results if t.has_warning]

    def find_test_result_by_nodeid(self, nodeid: str) -> TestResult:
        return next((t for t in self.test_results if t.nodeid == nodeid), None)


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
        return (
            max(self.sessions, key=lambda s: s.session_start_time)
            if self.sessions
            else None
        )


class TestHistory:
    """
    Tracks test sessions across multiple SUTs.
    """

    def __init__(self):
        self.sut_groups: Dict[str, SUTGroup] = {}

    def add_test_session(self, session: TestSession) -> None:
        if session.sut_name not in self.sut_groups:
            self.sut_groups[session.sut_name] = SUTGroup(sut_name=session.sut_name)
        self.sut_groups[session.sut_name].add_session(session)

    def get_sessions_for_sut(self, sut_name: str) -> List[TestSession]:
        return self.sut_groups.get(sut_name, SUTGroup(sut_name=sut_name)).sessions
