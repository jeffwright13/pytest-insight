from dataclasses import dataclass
from datetime import datetime, timedelta
from fnmatch import fnmatch
from typing import Callable, List, Optional, Set, Union

from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.storage import JSONStorage


class QueryError(Exception):
    """Base exception for Query-related errors."""

    pass


class InvalidQueryParameterError(QueryError):
    """Raised when query parameters are invalid."""

    pass


@dataclass
class QueryResult:
    """Results of executing a query."""

    sessions: List[TestSession]
    total_count: int
    execution_time: float
    matched_nodeids: Set[str]

    @property
    def empty(self) -> bool:
        """Check if query returned no results."""
        return len(self.sessions) == 0


class QueryTestFilter:
    """Builder for test-level filter criteria."""

    def __init__(self, query: "Query"):
        """Initialize test filter context."""
        self.query = query
        self._conditions = []

    def with_pattern(self, pattern: str) -> "QueryTestFilter":
        """Filter tests by pattern match."""
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError("Test pattern must be a non-empty string")
        self._conditions.append(("pattern", pattern))
        return self

    def with_duration(self, min_secs: float, max_secs: float) -> "QueryTestFilter":
        """Filter tests by duration range."""
        if not isinstance(min_secs, (int, float)) or not isinstance(max_secs, (int, float)):
            raise InvalidQueryParameterError("Duration bounds must be numbers")
        if min_secs > max_secs:
            raise InvalidQueryParameterError("Min duration must be less than max duration")
        self._conditions.append(("duration", (min_secs, max_secs)))
        return self

    def with_outcome(self, outcome: Union[str, TestOutcome]) -> "QueryTestFilter":
        """Filter tests by specific outcome."""
        outcome_str = outcome.value if hasattr(outcome, "value") else str(outcome)
        valid_outcomes = {o.value for o in TestOutcome}
        if outcome_str not in valid_outcomes:
            raise InvalidQueryParameterError(
                f"Invalid outcome: {outcome_str}. Must be one of: {', '.join(valid_outcomes)}"
            )
        self._conditions.append(("outcome", outcome_str))
        return self

    def apply(self):
        """Apply all test filters to the parent query."""
        named_conditions = [c for c in self._conditions if isinstance(c, tuple)]
        lambda_conditions = [c for c in self._conditions if callable(c)]

        # Handle named condition types
        for condition_type, value in named_conditions:
            if condition_type == "pattern":
                pattern = value
                self.query._filters.append(
                    lambda s: any(pattern == t.nodeid or pattern in t.nodeid for t in s.test_results)
                )
            elif condition_type == "duration":
                min_secs, max_secs = value
                self.query._filters.append(lambda s: any(min_secs <= t.duration <= max_secs for t in s.test_results))
            elif condition_type == "outcome":
                outcome_str = value
                self.query._filters.append(
                    lambda s: any(
                        (t.outcome.value if hasattr(t.outcome, "value") else str(t.outcome)) == outcome_str
                        for t in s.test_results
                    )
                )

        # Handle any legacy lambda-based conditions
        if lambda_conditions:
            conditions_copy = lambda_conditions.copy()
            self.query._filters.append(
                lambda s: any(all(condition(t) for condition in conditions_copy) for t in s.test_results)
            )

        return self.query


class Query:
    """Defines criteria for finding test sessions."""

    def __init__(self, storage: Optional[JSONStorage] = None):
        """Initialize query with optional storage.

        Args:
            storage: Optional storage to use. If not provided, uses default.
        """
        self.storage = storage or JSONStorage()
        self._filters: List[Callable[[TestSession], bool]] = []
        self._sessions: List[TestSession] = []
        self._last_result: Optional[QueryResult] = None

    def for_sut(self, name: str) -> "Query":
        """Filter by SUT name."""
        if not isinstance(name, str) or not name.strip():
            raise InvalidQueryParameterError("SUT name must be a non-empty string")
        self._filters.append(lambda s: s.sut_name == name)
        return self

    def in_last_days(self, days: int) -> "Query":
        """Filter sessions from last N days."""
        if not isinstance(days, int) or days < 0:
            raise InvalidQueryParameterError("Days must be a non-negative integer")
        cutoff = datetime.now() - timedelta(days=days)
        self._filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def in_last_hours(self, hours: int) -> "Query":
        """Filter sessions from last N hours."""
        if not isinstance(hours, int) or hours < 0:
            raise InvalidQueryParameterError("Hours must be a non-negative integer")
        cutoff = datetime.now() - timedelta(hours=hours)
        self._filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def in_last_minutes(self, minutes: int) -> "Query":
        """Filter sessions from last N minutes."""
        if not isinstance(minutes, int) or minutes < 0:
            raise InvalidQueryParameterError("Minutes must be a non-negative integer")
        cutoff = datetime.now() - timedelta(minutes=minutes)
        self._filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def date_range(self, start: datetime, end: datetime) -> "Query":
        """Filter sessions between two dates."""
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise InvalidQueryParameterError("Start and end must be datetime objects")
        if bool(start.tzinfo) != bool(end.tzinfo):
            raise InvalidQueryParameterError("Start and end dates must both be naive or both be timezone-aware")
        if start.tzinfo and end.tzinfo and start.tzinfo != end.tzinfo:
            raise InvalidQueryParameterError("Start and end dates must be in the same timezone")
        if start > end:
            raise InvalidQueryParameterError("Start date must be before end date")
        self._filters.append(lambda s: start <= s.session_start_time <= end)
        return self

    def duration_between(self, min_secs: float, max_secs: float) -> "Query":
        """Filter sessions by duration range."""
        if not isinstance(min_secs, (int, float)) or not isinstance(max_secs, (int, float)):
            raise InvalidQueryParameterError("Duration bounds must be numbers")
        if min_secs > max_secs:
            raise InvalidQueryParameterError("Min duration must be less than max duration")
        self._filters.append(lambda s: min_secs <= s.session_duration <= max_secs)
        return self

    def with_outcome(self, outcome: Union[str, TestOutcome]) -> "Query":
        """Filter sessions containing tests with specific outcome."""
        outcome_str = outcome.value if hasattr(outcome, "value") else str(outcome)
        valid_outcomes = {o.value for o in TestOutcome}
        if outcome_str not in valid_outcomes:
            raise InvalidQueryParameterError(
                f"Invalid outcome: {outcome_str}. Must be one of: {', '.join(valid_outcomes)}"
            )
        self._filters.append(
            lambda s: any(
                (t.outcome.value if hasattr(t.outcome, "value") else str(t.outcome)) == outcome_str
                for t in s.test_results
            )
        )
        return self

    def having_warnings(self, has_warnings: bool = True) -> "Query":
        """Filter sessions based on presence of warnings."""
        self._filters.append(lambda s: bool(s.warnings) == has_warnings)
        return self

    def with_reruns(self, has_reruns: bool) -> "Query":
        """Filter sessions based on presence of test reruns."""
        self._filters.append(lambda s: bool(s.rerun_test_groups) == has_reruns)
        return self

    def test_contains(self, pattern: str) -> "Query":
        """Filter sessions containing tests matching pattern."""
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError("Test pattern must be a non-empty string")
        self._filters.append(lambda s: any(pattern == t.nodeid or pattern in t.nodeid for t in s.test_results))
        return self

    def before(self, timestamp: datetime) -> "Query":
        """Filter sessions that occurred before given timestamp."""
        if not isinstance(timestamp, datetime):
            raise InvalidQueryParameterError("Timestamp must be a datetime object")
        self._filters.append(lambda s: s.session_start_time < timestamp)
        return self

    def after(self, timestamp: datetime) -> "Query":
        """Filter sessions that occurred after given timestamp."""
        if not isinstance(timestamp, datetime):
            raise InvalidQueryParameterError("Timestamp must be a datetime object")
        self._filters.append(lambda s: s.session_start_time > timestamp)
        return self

    def with_tag(self, key: str, value: str) -> "Query":
        """Filter test sessions by tag."""
        if not isinstance(key, str) or not isinstance(value, str):
            raise InvalidQueryParameterError("Tag key and value must be strings")
        self._filters.append(lambda s: s.session_tags.get(key) == value)
        return self

    def with_session_id_pattern(self, pattern: str) -> "Query":
        """Filter sessions by ID pattern using glob matching.

        This is particularly useful for finding base vs target sessions:
            query.with_session_id_pattern("base-*")  # Find base sessions
            query.with_session_id_pattern("target-*")  # Find target sessions
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError("Session ID pattern must be a non-empty string")
        self._filters.append(lambda s: fnmatch(s.session_id, pattern))
        return self

    def execute(self) -> QueryResult:
        """Execute query and return results."""
        start_time = datetime.now()

        # Load sessions from storage if not provided
        if self._sessions:
            from pytest_insight.storage import get_storage_instance

            storage = get_storage_instance()
            self._sessions = storage.load_sessions()

        # Apply filters
        filtered_sessions = [s for s in self._sessions if all(f(s) for f in self._filters)]

        # Extract all unique test nodeids
        all_nodeids = set()
        for session in filtered_sessions:
            all_nodeids.update(test.nodeid for test in session.test_results)

        execution_time = (datetime.now() - start_time).total_seconds()

        result = QueryResult(
            sessions=filtered_sessions,
            total_count=len(filtered_sessions),
            execution_time=execution_time,
            matched_nodeids=all_nodeids,
        )

        self._last_result = result
        return result

    def filter_tests(self) -> QueryTestFilter:
        """Start building test-level filters.

        Returns:
            A context for building test-specific filters.

        Example:
            query.filter_tests()
                .with_pattern("test_api")
                .with_duration(1.0, 5.0)
                .with_outcome(TestOutcome.FAILED)
                .apply()
        """
        return QueryTestFilter(self)
