from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional


class TestOutcome(Enum):
    """Test outcome states."""

    __test__ = False  # Tell Pytest this is NOT a test class

    PASSED = "PASSED"  # Internal representation in UPPERCASE
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    XFAILED = "XFAILED"
    XPASSED = "XPASSED"
    RERUN = "RERUN"
    ERROR = "ERROR"

    @classmethod
    def from_str(cls, outcome: Optional[str]) -> "TestOutcome":
        """Convert string to TestOutcome, always uppercase internally."""
        if not outcome:
            return cls.SKIPPED  # Return a default enum value instead of None
        try:
            return cls[outcome.upper()]
        except KeyError:
            raise ValueError(f"Invalid test outcome: {outcome}")

    def to_str(self) -> str:
        """Convert TestOutcome to string, always lowercase externally."""
        return self.value.lower()

    @classmethod
    def to_list(cls) -> List[str]:
        """Convert entire TestOutcome enum to a list of possible string values."""
        return [outcome.value.lower() for outcome in cls]


@dataclass
class TestResult:
    """
    Represents a single test result for an individual test run.
    """

    __test__ = False  # Tell Pytest this is NOT a test class

    nodeid: str
    outcome: TestOutcome
    start_time: datetime
    stop_time: Optional[datetime] = None
    duration: Optional[float] = None
    caplog: str = ""
    capstderr: str = ""
    capstdout: str = ""
    longreprtext: str = ""
    has_warning: bool = False

    def __post_init__(self):
        """Validate and process initialization data."""
        if self.stop_time is None and self.duration is None:
            raise ValueError("Either stop_time or duration must be provided")

        if self.stop_time is None:
            # Only duration provided - calculate stop_time
            self.stop_time = self.start_time + timedelta(seconds=self.duration)
        elif self.duration is None:
            # Only stop_time provided - calculate duration
            self.duration = (self.stop_time - self.start_time).total_seconds()
        # If both are provided, trust the duration value and adjust stop_time
        else:
            self.stop_time = self.start_time + timedelta(seconds=self.duration)

    def to_dict(self) -> Dict:
        """Convert test result to a dictionary for JSON serialization."""
        return {
            "nodeid": self.nodeid,
            "outcome": self.outcome.to_str(),  # Use to_str() for consistent lowercase serialization
            "start_time": self.start_time.isoformat(),
            "stop_time": self.stop_time.isoformat() if self.stop_time else None,
            "duration": self.duration,
            "caplog": self.caplog,
            "capstderr": self.capstderr,
            "capstdout": self.capstdout,
            "longreprtext": self.longreprtext,
            "has_warning": self.has_warning,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TestResult":
        """Create a TestResult from a dictionary."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid data for TestResult. Expected dict, got {type(data)}")

        start_time = datetime.fromisoformat(data["start_time"])
        stop_time = datetime.fromisoformat(data["stop_time"])

        return cls(
            nodeid=data["nodeid"],
            outcome=TestOutcome.from_str(data["outcome"]),
            start_time=start_time,
            stop_time=stop_time,
            caplog=data.get("caplog", ""),
            capstderr=data.get("capstderr", ""),
            capstdout=data.get("capstdout", ""),
            longreprtext=data.get("longreprtext", ""),
            has_warning=data.get("has_warning", False),
        )


@dataclass
class RerunTestGroup:
    """Groups test results for tests that were rerun, chronologically ordered with final result last."""

    __test__ = False  # Tell Pytest this is NOT a test class

    nodeid: str
    tests: List[TestResult] = field(default_factory=list)

    def add_test(self, result: TestResult) -> None:
        """Add a test result and maintain chronological order."""
        if not isinstance(result, TestResult):
            raise ValueError(
                f"Invalid test result {result}; must be a TestResult object, instead was type {type(result)}"
            )

        self.tests.append(result)
        self.tests.sort(key=lambda x: x.start_time)

        # TODO: Add validation for final test in RerunTestGroup (fails at end of gems-qa-auto session?)
        # # Validate one-and-only-one final test (not RERUN or ERROR)
        # intermediate_outcomes = {TestOutcome.RERUN, TestOutcome.ERROR}
        # final_tests = [t for t in self.tests if t.outcome not in intermediate_outcomes]
        # if len(final_tests) > 1:
        #     raise ValueError(f"Found {len(final_tests)} final tests (non-RERUN/ERROR), expected exactly one")

    @property
    def final_outcome(self) -> TestOutcome:
        """Get the outcome of the final test (non-RERUN and non-ERROR)."""
        return self.tests[-1].outcome if self.tests else TestOutcome.RERUN

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {"nodeid": self.nodeid, "tests": [t.to_dict() for t in self.tests]}

    @classmethod
    def from_dict(cls, data: Dict) -> "RerunTestGroup":
        """Create RerunTestGroup from dictionary."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid data for RerunTestGroup. Expected dict, got {type(data)}")

        group = cls(nodeid=data["nodeid"])
        group.tests = [TestResult.from_dict(t) for t in data["tests"]]
        return group


@dataclass
class TestSession:
    """Represents a single test session for a single SUT."""

    __test__ = False  # Tell Pytest this is NOT a test class

    sut_name: str
    session_id: str
    session_start_time: datetime
    session_stop_time: Optional[datetime] = None
    session_duration: Optional[float] = None
    test_results: List[TestResult] = field(default_factory=list)  # Fix: use =list
    rerun_test_groups: List[RerunTestGroup] = field(default_factory=list)  # Fix: use =list
    session_tags: Dict[str, str] = field(default_factory=dict)  # Fix: use =dict

    def __post_init__(self):
        """Calculate timing information once at initialization."""
        if self.session_stop_time is None and self.session_duration is None:
            raise ValueError("Either session_stop_time or session_duration must be provided")

        if self.session_stop_time is None:
            self.session_stop_time = self.session_start_time + timedelta(seconds=self.session_duration)
        elif self.session_duration is None:
            self.session_duration = (self.session_stop_time - self.session_start_time).total_seconds()

    def to_dict(self) -> Dict:
        """Convert TestSession to a dictionary for JSON serialization."""
        return {
            "sut_name": self.sut_name,
            "session_id": self.session_id,
            "session_start_time": self.session_start_time.isoformat(),
            "session_stop_time": self.session_stop_time.isoformat(),
            "session_duration": self.session_duration,
            "test_results": [test.to_dict() for test in self.test_results],
            "rerun_test_groups": [
                {"nodeid": group.nodeid, "tests": [t.to_dict() for t in group.tests]}
                for group in self.rerun_test_groups
            ],
            "session_tags": self.session_tags or {},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TestSession":
        """Create a TestSession from a dictionary."""
        if not isinstance(data, dict):
            raise ValueError(f"Invalid data for TestSession. Expected dict, got {type(data)}")

        session = cls(
            sut_name=data["sut_name"],
            session_id=data["session_id"],
            session_start_time=datetime.fromisoformat(data["session_start_time"]),
            session_stop_time=datetime.fromisoformat(data["session_stop_time"]),
        )

        # Add test results
        for test_data in data.get("test_results", []):
            session.add_test_result(TestResult.from_dict(test_data))

        # Add rerun groups
        for group_data in data.get("rerun_test_groups", []):
            group = RerunTestGroup.from_dict(group_data)
            session.add_rerun_group(group)

        session.session_tags = data.get("session_tags", {})
        return session

    def add_test_result(self, result: TestResult) -> None:
        """Add a test result to this session."""
        if not isinstance(result, TestResult):
            raise ValueError(
                f"Invalid test result {result}; must be a TestResult object, nistead was type {type(result)}"
            )

        self.test_results.append(result)

    def add_rerun_group(self, group: RerunTestGroup) -> None:
        """Add a rerun test group to this session."""
        if not isinstance(group, RerunTestGroup):
            raise ValueError(
                f"Invalid rerun group {group}; must be a RerunTestGroup object, instead was type {type(group)}"
            )

        self.rerun_test_groups.append(group)


@dataclass
class TestHistory:
    """Collection of test sessions grouped by SUT with efficient access patterns."""

    __test__ = False  # Tell Pytest this is NOT a test class

    def __init__(self):
        # Main storage: Dict[sut_name, List[TestSession]]
        self._sessions_by_sut: Dict[str, List[TestSession]] = {}
        # Cache of latest sessions: Dict[sut_name, TestSession]
        self._latest_by_sut: Dict[str, TestSession] = {}
        # Cache for global session list
        self._all_sessions_cache: Optional[List[TestSession]] = None

    def add_test_session(self, session: TestSession) -> None:
        """Add a test session to the appropriate SUT group."""
        if not isinstance(session, TestSession):
            raise ValueError(
                f"Invalid test session {session}; must be a TestSession object, instead was type {type(session)}"
            )

        # Initialize SUT list if needed
        if session.sut_name not in self._sessions_by_sut:
            self._sessions_by_sut[session.sut_name] = []

        # Add session
        self._sessions_by_sut[session.sut_name].append(session)

        # Update latest session cache for this SUT
        current_latest = self._latest_by_sut.get(session.sut_name)
        if not current_latest or session.session_start_time > current_latest.session_start_time:
            self._latest_by_sut[session.sut_name] = session

        # Invalidate global cache
        self._all_sessions_cache = None

    def get_sut_sessions(self, sut_name: str) -> List[TestSession]:
        """Get all sessions for a specific SUT, chronologically ordered."""
        sessions = self._sessions_by_sut.get(sut_name, [])
        return sorted(sessions, key=lambda s: s.session_start_time)

    def get_sut_latest_session(self, sut_name: str) -> Optional[TestSession]:
        """Get the most recent session for a specific SUT."""
        return self._latest_by_sut.get(sut_name)

    @property
    def sessions(self) -> List[TestSession]:
        """Get all sessions across all SUTs, sorted by start time (cached)."""
        if self._all_sessions_cache is None:
            all_sessions = []
            for sut_sessions in self._sessions_by_sut.values():
                all_sessions.extend(sut_sessions)
            self._all_sessions_cache = sorted(all_sessions, key=lambda s: s.session_start_time)
        return self._all_sessions_cache.copy()  # Return copy to prevent cache modification

    def latest_session(self) -> Optional[TestSession]:
        """Get the most recent session across all SUTs."""
        if not self._latest_by_sut:
            return None
        return max(self._latest_by_sut.values(), key=lambda s: s.session_start_time)

    def get_sut_names(self) -> List[str]:
        """Get list of all SUT names."""
        return list(self._sessions_by_sut.keys())
