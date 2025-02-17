from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class TestResult:
    """
    Represents a single test result for an individual test run.
    """

    __test__ = False  # Tell Pytest this is NOT a test class

    nodeid: str
    outcome: str
    start_time: datetime
    duration: float
    caplog: str = ""
    capstderr: str = ""
    capstdout: str = ""
    longreprtext: str = ""
    has_warning: bool = False

    def to_dict(self) -> Dict:
        """Convert test result to a dictionary for JSON serialization."""
        return {
            "nodeid": self.nodeid,
            "outcome": self.outcome,
            "start_time": self.start_time.isoformat(),
            "duration": self.duration,
            "longreprtext": self.longreprtext,
            "caplog": self.caplog,
            "capstderr": self.capstderr,
            "capstdout": self.capstdout,
            "has_warning": self.has_warning,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TestResult":
        """Create a TestResult from a dictionary."""
        return cls(
            nodeid=data["nodeid"],
            outcome=data["outcome"],
            start_time=datetime.fromisoformat(data["start_time"]),
            duration=data["duration"],
            caplog=data.get("caplog", ""),
            capstderr=data.get("capstderr", ""),
            capstdout=data.get("capstdout", ""),
            longreprtext=data.get("longreprtext", ""),
            has_warning=data.get("has_warning", False),
        )


@dataclass
class RerunTestGroup:
    """Represents a test that has been run multiple times."""
    nodeid: str
    _final_outcome: str = field(default="UNKNOWN")
    _reruns: List[TestResult] = field(default_factory=list)
    _full_test_list: List[TestResult] = field(default_factory=list)

    def __init__(self, nodeid: str, final_outcome: str):
        """Initialize a rerun test group."""
        self.nodeid = nodeid
        self._final_outcome = final_outcome
        self._reruns = []
        self._full_test_list = []

    @property
    def final_outcome(self) -> str:
        """Get the final outcome of all test runs."""
        return self.final_test.outcome if self.final_test else self._final_outcome

    @property
    def reruns(self) -> List[TestResult]:
        """Get rerun test results."""
        return self._reruns

    @property
    def full_test_list(self) -> List[TestResult]:
        """Get all test results."""
        return self._full_test_list

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

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "nodeid": self.nodeid,
            "final_outcome": self.final_outcome,
            "reruns": [r.to_dict() for r in self._reruns],
            "full_test_list": [t.to_dict() for t in self._full_test_list]
        }


@dataclass
class TestSession:
    """Represents a single test session for a single SUT."""

    __test__ = False  # Tell Pytest this is NOT a test class

    sut_name: str
    session_id: str
    session_start_time: datetime
    session_stop_time: datetime
    test_results: List[TestResult] = field(default_factory=list)
    rerun_test_groups: List[RerunTestGroup] = field(default_factory=list)
    session_tags: Dict[str, str] = field(default_factory=dict)

    @property
    def session_duration(self) -> timedelta:
        """Compute session duration dynamically based on start and stop times."""
        return self.session_stop_time - self.session_start_time

    def to_dict(self) -> Dict:
        """Convert the test session to a dictionary for JSON serialization."""
        return {
            "sut_name": self.sut_name,
            "session_id": self.session_id,
            "session_start_time": self.session_start_time.isoformat(),
            "session_stop_time": self.session_stop_time.isoformat(),
            "session_duration": self.session_duration.total_seconds(),
            "test_results": [test.to_dict() for test in self.test_results],
            "rerun_test_groups": [group.to_dict() for group in self.rerun_test_groups],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TestSession":
        """Create a TestSession from a dictionary."""
        return cls(
            sut_name=data["sut_name"],
            session_id=data["session_id"],
            session_start_time=datetime.fromisoformat(data["session_start_time"]),
            session_stop_time=datetime.fromisoformat(data["session_stop_time"]),
            test_results=[
                TestResult.from_dict(t) for t in data.get("test_results", [])
            ],
        )

    def add_test_result(self, result: TestResult) -> None:
        """Add a test result to this session."""
        self.test_results.append(result)


@dataclass
class SUTGroup:
    """Represents a collection of test sessions for a single SUT."""

    sut_name: str
    sessions: List[TestSession] = field(default_factory=list)

    def add_session(self, session: TestSession) -> None:
        self.sessions.append(session)

    def latest_session(self) -> Optional[TestSession]:
        return (
            max(self.sessions, key=lambda s: s.session_start_time)
            if self.sessions
            else None
        )


@dataclass
class TestHistory:
    """Collection of test sessions grouped by SUT."""

    def __init__(self):
        self._sessions_by_sut = {}  # Initialize sessions dict

    @property
    def sessions(self) -> List[TestSession]:
        """Get all sessions across all SUTs, sorted by start time."""
        all_sessions = []
        for sut_sessions in self._sessions_by_sut.values():
            all_sessions.extend(sut_sessions)
        return sorted(all_sessions, key=lambda s: s.session_start_time)

    def add_test_session(self, session: TestSession) -> None:
        """Add a test session to the appropriate SUT group."""
        if session.sut_name not in self._sessions_by_sut:
            self._sessions_by_sut[session.sut_name] = []
        self._sessions_by_sut[session.sut_name].append(session)

    def latest_session(self) -> Optional[TestSession]:
        """Get the most recent test session."""
        if not self.sessions:
            return None
        return self.sessions[-1]
