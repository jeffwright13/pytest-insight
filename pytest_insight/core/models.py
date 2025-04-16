"""Models for test session data.

Core models:
1. TestOutcome - Enum for test result outcomes
2. TestResult - Single test execution result
3. TestSession - Collection of test results with metadata
4. RerunTestGroup - Group of related test reruns
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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

    def is_failed(self) -> bool:
        """Check if the outcome represents a failure."""
        return self in (self.FAILED, self.ERROR)


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
        # Handle both string and enum outcomes for backward compatibility
        if not hasattr(self.outcome, "to_str"):
            logger.warning(
                "Non-enum (probably string outcome detected where TestOutcome enum expected. "
                f"nodeid={self.nodeid}, outcome={self.outcome}, type={type(self.outcome)}. "
                "For proper session context and query filtering, use TestOutcome enum: "
                "outcome=TestOutcome.FAILED instead of outcome='failed'. "
                "String outcomes are deprecated and will be removed in a future version."
            )
            outcome_str = str(self.outcome).lower()
        else:
            outcome_str = self.outcome.to_str()

        return {
            "nodeid": self.nodeid,
            "outcome": outcome_str,
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
            raise ValueError(
                f"Invalid data for TestResult. Expected dict, got {type(data)}"
            )

        start_time = datetime.fromisoformat(data["start_time"])
        stop_time = (
            datetime.fromisoformat(data["stop_time"]) if data.get("stop_time") else None
        )
        duration = data.get("duration")

        return cls(
            nodeid=data["nodeid"],
            outcome=TestOutcome.from_str(data["outcome"]),
            start_time=start_time,
            stop_time=stop_time,
            duration=duration,
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
            raise ValueError(
                f"Invalid data for RerunTestGroup. Expected dict, got {type(data)}"
            )

        group = cls(nodeid=data["nodeid"])
        group.tests = [TestResult.from_dict(t) for t in data["tests"]]
        return group


@dataclass
class TestSession:
    """Represents a single test session for a single SUT."""

    __test__ = False  # Tell Pytest this is NOT a test class

    sut_name: str = ""
    testing_system: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    session_start_time: datetime = None
    session_stop_time: Optional[datetime] = None
    session_duration: Optional[float] = None
    session_tags: Dict[str, str] = field(default_factory=dict)
    rerun_test_groups: List[RerunTestGroup] = field(default_factory=list)
    test_results: List[TestResult] = field(default_factory=list)

    def __post_init__(self):
        """Calculate timing information once at initialization."""
        if self.session_stop_time is None and self.session_duration is None:
            raise ValueError(
                "Either session_stop_time or session_duration must be provided"
            )

        if self.session_stop_time is None:
            self.session_stop_time = self.session_start_time + timedelta(
                seconds=self.session_duration
            )
        elif self.session_duration is None:
            self.session_duration = (
                self.session_stop_time - self.session_start_time
            ).total_seconds()

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
            "testing_system": self.testing_system or {},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TestSession":
        """Create a TestSession from a dictionary."""
        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid data for TestSession. Expected dict, got {type(data)}"
            )

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
        session.testing_system = data.get("testing_system", {})
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
