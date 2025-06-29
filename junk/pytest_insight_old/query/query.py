"""Query system for filtering and retrieving test sessions.

This module implements a two-level filtering design:
1. Session-Level: Filter entire test sessions (SUT, time range, warnings)
2. Test-Level: Filter by individual test properties while preserving session context

Both levels return full TestSession objects to preserve session context (warnings,
reruns, relationships). Test-level filtering returns sessions containing matching
tests, never isolated TestResult objects.
"""

import fnmatch
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Union,
)

from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.storage import BaseStorage, get_storage_instance


class InvalidQueryParameterError(Exception):
    """Raised when query parameters are invalid."""


class QueryExecutionError(Exception):
    """Raised when query execution fails."""


class FilterType(Enum):
    """Types of filters supported by the query system."""

    GLOB_PATTERN = auto()
    REGEX_PATTERN = auto()
    DURATION = auto()
    OUTCOME = auto()
    CUSTOM = auto()


class TestFilter(Protocol):
    """Protocol defining the interface for test filters."""

    def matches(self, test: TestResult) -> bool:
        """Check if a test matches this filter."""
        ...

    def to_dict(self) -> Dict:
        """Convert filter to dictionary for serialization."""
        ...

    @classmethod
    def from_dict(cls, data: Dict) -> "TestFilter":
        """Create filter from dictionary."""
        ...


@dataclass
class BasePatternFilter(ABC):
    """Base class for pattern-based test filters."""

    pattern: str

    def __post_init__(self):
        """Validate pattern."""
        if not isinstance(self.pattern, str) or not self.pattern.strip():
            raise InvalidQueryParameterError("Pattern must be a non-empty string")

    @abstractmethod
    def matches(self, test: TestResult) -> bool:
        """Check if test matches the pattern."""
        ...

    @abstractmethod
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        ...


@dataclass
class GlobPatternFilter(BasePatternFilter):
    """Filter tests using glob pattern matching.

    Pattern matching rules:
    - Pattern is wrapped with wildcards: *{pattern}*
    - Test nodeid is split on :: into parts
    - For module part (parts[0]):
      - .py extension is stripped before matching
      - Pattern is matched against stripped module name
    - For test name part (parts[1:]):
      - Pattern is matched directly against each part
    - Test matches if ANY part matches the pattern
    """

    def matches(self, test: TestResult) -> bool:
        """Check if test matches the glob pattern.

        Pattern matching rules:
        - Pattern is wrapped with wildcards: *{pattern}*
        - Test nodeid is split on :: into parts
        - For module part (parts[0]):
          - .py extension is stripped before matching
          - Pattern is matched against stripped module name
        - For test name part (parts[1:]):
          - Pattern is matched directly against each part
        - Test matches if ANY part matches the pattern
        """
        parts = test.nodeid.split("::")
        if not parts:  # Must have at least one part
            return False

        # Match module part (strip .py extension)
        module_part = parts[0].replace(".py", "")
        if fnmatch.fnmatch(module_part, f"*{self.pattern}*"):
            return True

        # Match all other parts directly
        return any(fnmatch.fnmatch(part, f"*{self.pattern}*") for part in parts[1:])

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.GLOB_PATTERN.name,
            "pattern": self.pattern,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GlobPatternFilter":
        """Create from dictionary."""
        return cls(pattern=data["pattern"])


@dataclass
class RegexPatternFilter(BasePatternFilter):
    """Filter tests using regex pattern matching.

    Pattern matching rules:
    - Pattern is used as-is (no wildcards added)
    - Pattern is matched against full nodeid using re.search()
    - Test matches if pattern matches anywhere in nodeid
    """

    _compiled_regex: Optional[re.Pattern] = field(default=None, init=False)

    def __post_init__(self):
        """Validate and compile pattern."""
        super().__post_init__()
        try:
            self._compiled_regex = re.compile(self.pattern)
        except re.error as e:
            raise InvalidQueryParameterError(f"Invalid regex pattern: {e}")

    def matches(self, test: TestResult) -> bool:
        """Check if test matches the regex pattern.

        Pattern matching rules:
        - Pattern is used as-is (no wildcards added)
        - Pattern is matched against full nodeid using re.search()
        - Test matches if pattern matches anywhere in nodeid
        """
        # Apply regex pattern to full nodeid
        return bool(self._compiled_regex.search(test.nodeid))

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.REGEX_PATTERN.name,
            "pattern": self.pattern,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RegexPatternFilter":
        """Create from dictionary."""
        return cls(pattern=data["pattern"])


@dataclass
class DurationFilter:
    """Filter tests by duration range."""

    min_seconds: float
    max_seconds: float

    def __post_init__(self):
        """Validate duration bounds."""
        if self.min_seconds < 0:
            raise InvalidQueryParameterError("min_seconds must be >= 0")
        if self.max_seconds < self.min_seconds:
            raise InvalidQueryParameterError("max_seconds must be >= min_seconds")

    def matches(self, test: TestResult) -> bool:
        """Check if test duration is within range."""
        return self.min_seconds <= test.duration <= self.max_seconds

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.DURATION.name,
            "min_seconds": self.min_seconds,
            "max_seconds": self.max_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DurationFilter":
        """Create from dictionary."""
        return cls(
            min_seconds=data["min_seconds"],
            max_seconds=data["max_seconds"],
        )


@dataclass
class OutcomeFilter:
    """Filter tests by outcome."""

    outcome: TestOutcome

    def __post_init__(self):
        """Validate outcome."""
        if not isinstance(self.outcome, TestOutcome):
            try:
                self.outcome = TestOutcome.from_str(str(self.outcome))
            except ValueError as e:
                raise InvalidQueryParameterError(f"Invalid outcome: {e}")

    def matches(self, test: TestResult) -> bool:
        """Check if test outcome matches."""
        return test.outcome == self.outcome

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.OUTCOME.name,
            "outcome": self.outcome.value,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "OutcomeFilter":
        """Create from dictionary."""
        return cls(outcome=TestOutcome.from_str(data["outcome"]))


@dataclass
class CustomFilter:
    """Filter tests using a custom predicate."""

    predicate: Callable[[TestResult], bool]
    name: str

    def matches(self, test: TestResult) -> bool:
        """Apply custom predicate."""
        return self.predicate(test)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.CUSTOM.name,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CustomFilter":
        """Create from dictionary."""
        raise NotImplementedError("Custom filters cannot be serialized/deserialized")


class QueryResult:
    """Results from a query execution.

    QueryResult always contains full TestSession objects to preserve session context
    (warnings, reruns, relationships). When test-level filters are applied, it
    returns sessions containing matching tests, NOT simply isolated TestResult objects.
    """

    def __init__(self, sessions: List[TestSession], execution_time: float = 0.0):
        """Initialize query result."""
        self.sessions = sessions
        self.execution_time = execution_time
        self._matched_nodeids: Optional[Set[str]] = None

    @property
    def empty(self) -> bool:
        """Check if query returned no results."""
        return len(self.sessions) == 0

    @property
    def total_count(self) -> int:
        """Get total number of matching sessions."""
        return len(self.sessions)

    @property
    def matched_nodeids(self) -> Set[str]:
        """Get set of unique test nodeids from matching sessions."""
        if self._matched_nodeids is None:
            self._matched_nodeids = {test.nodeid for session in self.sessions for test in session.test_results}
        return self._matched_nodeids

    def __iter__(self):
        """Iterate over matching sessions."""
        return iter(self.sessions)

    def __len__(self):
        """Get number of matching sessions."""
        return len(self.sessions)

    def __bool__(self):
        """Convert to boolean (True if has results)."""
        return bool(self.sessions)


class QueryTestFilter:
    """Builder for test-level filters.

    Test-level filters are applied to individual tests within a session, but always
    return full sessions to preserve context. A session is included if it contains
    at least one test that matches all test filters.

    IMPORTANT: QueryTestFilter returns full TestSession objects, never isolated
    TestResult objects. This preserves session context (warnings, reruns, relationships)
    for analysis.
    """

    def __init__(self, query: "Query"):
        """Initialize test filter builder."""
        self.query = query
        self.filters: List[TestFilter] = []

    def with_pattern(self, pattern: str, use_regex: bool = False) -> "QueryTestFilter":
        """Filter tests by pattern."""
        filter_class = RegexPatternFilter if use_regex else GlobPatternFilter
        self.filters.append(filter_class(pattern))
        return self

    def with_duration_between(self, min_seconds: float, max_seconds: float) -> "QueryTestFilter":
        """Filter tests by duration range."""
        self.filters.append(DurationFilter(min_seconds, max_seconds))
        return self

    def with_outcome(self, outcome: Union[str, TestOutcome]) -> "QueryTestFilter":
        """Filter tests by outcome."""
        self.filters.append(OutcomeFilter(outcome))
        return self

    def with_custom_filter(self, predicate: Callable[[TestResult], bool], name: str) -> "QueryTestFilter":
        """Add custom test filter."""
        self.filters.append(CustomFilter(predicate, name))
        return self

    def apply(self) -> "Query":
        """Apply test filters and return to session context."""
        if not self.filters:
            return self.query

        def session_filter(session: TestSession) -> bool:
            """Check if session contains any matching tests."""
            if not session.test_results:
                return False
            return any(all(f.matches(test) for f in self.filters) for test in session.test_results)

        self.query._session_filters.append(session_filter)
        return self.query

    def to_dict(self) -> Dict:
        """Convert filters to dictionary."""
        return {"filters": [f.to_dict() for f in self.filters if not isinstance(f, CustomFilter)]}

    @classmethod
    def from_dict(cls, data: Dict, query: "Query") -> "QueryTestFilter":
        """Create filters from dictionary."""
        filter_types = {
            FilterType.GLOB_PATTERN.name: GlobPatternFilter,
            FilterType.REGEX_PATTERN.name: RegexPatternFilter,
            FilterType.DURATION.name: DurationFilter,
            FilterType.OUTCOME.name: OutcomeFilter,
        }

        instance = cls(query)
        for filter_data in data["filters"]:
            filter_type = filter_data["type"]
            filter_class = filter_types[filter_type]
            instance.filters.append(filter_class.from_dict(filter_data))
        return instance


class Query:
    """Query class for filtering and retrieving test sessions.

    The Query class implements a two-level filtering design:
    1. Session-Level: Filter entire test sessions (SUT, time range, warnings)
    2. Test-Level: Filter by individual test properties while preserving session context

    Both levels return full TestSession objects to preserve session context (warnings,
    reruns, relationships). Test-level filtering returns sessions containing matching
    tests, never isolated TestResult objects.

    Examples:
        # Session-level only
        query.for_sut("service").in_last_days(7).execute()

        # Test-level with context
        query.filter_by_test()  # Filters sessions by test criteria
            .with_duration_between(10.0, float("inf"))
            .apply()  # Back to session context
            .execute()
    """

    def __init__(self, storage: Optional[BaseStorage] = None):
        """Initialize a new Query instance.

        Args:
            storage: Optional storage instance to use. If not provided, will use get_storage_instance().
                   This is primarily used for testing to inject mock storage.
        """
        self._session_filters = []  # Session-level filters (SUT, time range, warnings)
        self._test_filters = []  # Test-level filters (pattern, duration, outcome)
        self._sessions = []  # Cached sessions from storage
        self.storage = storage or get_storage_instance()

    def execute(self, sessions: Optional[List[TestSession]] = None) -> QueryResult:
        """Execute query and return results.

        Args:
            sessions: Optional list of sessions to query. If not provided,
                     loads (all) sessions from storage.

        Returns:
            QueryResult containing filtered sessions.

        Raises:
            QueryExecutionError: If sessions are invalid.
        """
        start_time: datetime = datetime.now()

        if sessions is None:
            sessions = self.storage.load_sessions()
        elif not isinstance(sessions, list) or not all(isinstance(s, TestSession) for s in sessions):
            raise QueryExecutionError("Invalid session type")

        filtered_sessions: List[TestSession] = sessions
        for filter_func in self._session_filters:
            filtered_sessions = [s for s in filtered_sessions if filter_func(s)]

        if self._test_filters:
            filtered_sessions = [
                session
                for session in filtered_sessions
                if all(filter_func(session) for filter_func in self._test_filters)
            ]

        execution_time: float = (datetime.now() - start_time).total_seconds()
        return QueryResult(filtered_sessions, execution_time)

    def filter_by_test(self) -> QueryTestFilter:
        """Start building test-level filters.

        Returns:
            QueryTestFilter instance for building test-level filters.

        Example:
            query.filter_by_test()
                .with_pattern("test_api")
                .with_duration_between(3.0, 10.0)
                .with_outcome(TestOutcome.FAILED)
                .apply()
                .execute()
        """
        return QueryTestFilter(self)

    def for_sut(self, name: str) -> "Query":
        """Filter sessions by SUT name.

        Args:
            name: Name of the SUT to filter by.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If name is empty or None.
        """
        if not isinstance(name, str) or not name.strip():
            raise InvalidQueryParameterError("SUT name must be a non-empty string")
        self._session_filters.append(lambda s: s.sut_name == name)
        return self

    def in_last_days(self, days: int) -> "Query":
        """Filter sessions from the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If days is not a non-negative integer.
        """
        if not isinstance(days, int) or days < 0:
            raise InvalidQueryParameterError("Days must be a non-negative integer")
        cutoff = datetime.now() - timedelta(days=days)
        self._session_filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def in_last_hours(self, hours: int) -> "Query":
        """Filter sessions from last N hours.

        Args:
            hours: Number of hours to look back.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If hours is not a non-negative integer.
        """
        if not isinstance(hours, int) or hours < 0:
            raise InvalidQueryParameterError("Hours must be a non-negative integer")
        cutoff = datetime.now() - timedelta(hours=hours)
        self._session_filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def in_last_minutes(self, minutes: int) -> "Query":
        """Filter sessions from last N minutes.

        Args:
            minutes: Number of minutes to look back.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If minutes is not a non-negative integer.
        """
        if not isinstance(minutes, int) or minutes < 0:
            raise InvalidQueryParameterError("Minutes must be a non-negative integer")
        cutoff = datetime.now() - timedelta(minutes=minutes)
        self._session_filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def date_range(self, start: datetime, end: datetime) -> "Query":
        """Filter sessions between two dates.

        Args:
            start: Start datetime.
            end: End datetime.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If dates are invalid.
        """
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise InvalidQueryParameterError("Start and end must be datetime objects")
        if bool(start.tzinfo) != bool(end.tzinfo):
            raise InvalidQueryParameterError("Start and end dates must both be naive or both be timezone-aware")
        if start.tzinfo and end.tzinfo and start.tzinfo != end.tzinfo:
            raise InvalidQueryParameterError("Start and end dates must be in the same timezone")
        if start > end:
            raise InvalidQueryParameterError("Start date must be before end date")
        self._session_filters.append(lambda s: start <= s.session_start_time <= end)
        return self

    def with_outcome(self, outcome: Union[str, TestOutcome]) -> "Query":
        """Filter sessions containing tests with specific outcome.

        Args:
            outcome: Test outcome to filter by.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If outcome is invalid.
        """
        outcome_str = outcome.value if hasattr(outcome, "value") else str(outcome)
        valid_outcomes = {o.value for o in TestOutcome}
        if outcome_str not in valid_outcomes:
            raise InvalidQueryParameterError(
                f"Invalid outcome: {outcome_str}. Must be one of: {', '.join(valid_outcomes)}"
            )

        self._session_filters.append(
            lambda s: any(
                (t.outcome.value if hasattr(t.outcome, "value") else str(t.outcome)) == outcome_str
                for t in s.test_results
            )
        )
        return self

    def having_warnings(self, has_warnings: bool = True) -> "Query":
        """Filter sessions by presence of warnings in test results.

        Args:
            has_warnings: If True, keep sessions with warnings. If False, keep sessions without warnings.

        Returns:
            Query instance for chaining.
        """
        self._session_filters.append(lambda s: any(t.has_warning for t in s.test_results) == has_warnings)
        return self

    def with_reruns(self, has_reruns: bool = True) -> "Query":
        """Filter sessions based on presence of test reruns.

        Args:
            has_reruns: If True, keep sessions with reruns. If False, keep sessions without.

        Returns:
            Query instance for chaining.
        """
        self._session_filters.append(lambda s: bool(s.rerun_test_groups) == has_reruns)
        return self

    def test_contains(self, pattern: str) -> "Query":
        """Filter sessions containing tests with nodeid matching pattern.

        Args:
            pattern: Pattern to match against test nodeid.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If pattern is empty.
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError("Test pattern must be a non-empty string")
        self._session_filters.append(lambda s: any(pattern == t.nodeid or pattern in t.nodeid for t in s.test_results))
        return self

    def before(self, timestamp: datetime) -> "Query":
        """Filter sessions before given timestamp.

        Args:
            timestamp: Datetime to filter before.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If timestamp is not a datetime object.
        """
        if not isinstance(timestamp, datetime):
            raise InvalidQueryParameterError("Timestamp must be a datetime object")

        self._session_filters.append(lambda s: s.session_start_time < timestamp)
        return self

    def after(self, timestamp: datetime) -> "Query":
        """Filter sessions after given timestamp.

        Args:
            timestamp: Datetime to filter after.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If timestamp is not a datetime object.
        """
        if not isinstance(timestamp, datetime):
            raise InvalidQueryParameterError("Timestamp must be a datetime object")

        self._session_filters.append(lambda s: s.session_start_time > timestamp)
        return self

    def with_tag(self, key: str, value: str) -> "Query":
        """Filter sessions by tag key-value pair.

        Args:
            key: Tag key to filter by.
            value: Tag value to match.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If key or value is invalid.
        """
        if not key or not isinstance(key, str):
            raise InvalidQueryParameterError("Tag key must be a non-empty string")
        if not value or not isinstance(value, str):
            raise InvalidQueryParameterError("Tag value must be a non-empty string")

        self._session_filters.append(lambda s: s.session_tags.get(key) == value)
        return self

    def with_session_id_pattern(self, pattern: str) -> "Query":
        """Filter sessions by ID pattern using glob matching.

        This is particularly useful for finding base vs target sessions:
            query.with_session_id_pattern("base-*")  # Find base sessions
            query.with_session_id_pattern("target-*")  # Find target sessions

        Args:
            pattern: Pattern to match against session ID.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If pattern is empty.
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError("Session ID pattern must be a non-empty string")
        self._session_filters.append(lambda s: fnmatch.fnmatch(s.session_id, pattern))
        return self

    def with_session_tag(self, tag_key: str, tag_value: str) -> "Query":
        """Filter sessions by session tag.

        Args:
            tag_key: Session tag key.
            tag_value: Session tag value.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If tag_key or tag_value is invalid.
        """
        if not tag_key or not isinstance(tag_key, str):
            raise InvalidQueryParameterError("Tag key must be a non-empty string")
        if not tag_value or not isinstance(tag_value, str):
            raise InvalidQueryParameterError("Tag value must be a non-empty string")

        self._session_filters.append(lambda s: s.session_tags.get(tag_key) == tag_value)
        return self

    def to_dict(self) -> Dict:
        """Convert query to dictionary."""
        data = {"version": 1}
        if self._test_filter:
            data["test_filter"] = self._test_filter.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict, storage: Optional[BaseStorage] = None) -> "Query":
        """Create query from dictionary."""
        query = cls(storage)
        if "test_filter" in data:
            query._test_filter = QueryTestFilter.from_dict(data["test_filter"], query)
            query._test_filter.apply()
        return query
