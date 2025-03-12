from datetime import datetime, timedelta
from typing import List, Union, Optional
import fnmatch
from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.storage import get_storage_instance


class InvalidQueryParameterError(Exception):
    """Raised when query parameters are invalid."""
    pass


class QueryExecutionError(Exception):
    """Raised when query execution fails."""
    pass


class QueryResult:
    """Results from a query execution.

    QueryResult always contains full TestSession objects to preserve session context
    (warnings, reruns, relationships). When test-level filters are applied, it
    returns sessions containing matching tests, never isolated TestResult objects.

    Properties:
        sessions: List of TestSession objects matching the query filters.
        empty: True if no sessions matched the filters.
        total_count: Total number of matching sessions.
        matched_nodeids: Set of unique test nodeids from matching sessions.
        execution_time: Time taken to execute the query in seconds.
    """

    def __init__(self, sessions: List[TestSession], execution_time: float = 0.0):
        """Initialize query result.

        Args:
            sessions: List of TestSession objects matching the query.
            execution_time: Time taken to execute the query in seconds.
        """
        self.sessions = sessions
        self.execution_time = execution_time
        self._matched_nodeids = None

    @property
    def empty(self) -> bool:
        """Check if query returned no results."""
        return len(self.sessions) == 0

    @property
    def total_count(self) -> int:
        """Get total number of matching sessions."""
        return len(self.sessions)

    @property
    def matched_nodeids(self) -> set:
        """Get set of unique test nodeids from matching sessions."""
        if self._matched_nodeids is None:
            self._matched_nodeids = set()
            for session in self.sessions:
                self._matched_nodeids.update(test.nodeid for test in session.test_results)
        return self._matched_nodeids

    def __iter__(self):
        """Iterate over matching sessions."""
        return iter(self.sessions)

    def __len__(self):
        """Get number of matching sessions."""
        return len(self.sessions)

    def __bool__(self):
        """Convert to boolean (True if has results)."""
        return not self.empty


class QueryTestFilter:
    """Builder for test-level filters.

    Test-level filters are applied to individual tests within a session, but always
    return full sessions to preserve context. A session is included if it contains
    at least one test that matches all test filters.

    IMPORTANT: QueryTestFilter returns full TestSession objects, never isolated
    TestResult objects. This preserves session context (warnings, reruns, relationships)
    for analysis.

    Example:
        query.filter_by_test()  # Start test filtering
            .with_pattern("test_api")  # Filter by test name
            .with_duration(3.0, 10.0)  # Filter by duration
            .with_outcome(TestOutcome.FAILED)  # Filter by outcome
            .apply()  # Back to session context
            .execute()  # Get matching sessions
    """

    def __init__(self, query: "Query"):
        """Initialize test filter builder.

        Args:
            query: Parent Query instance.
        """
        self.query = query
        self._test_conditions = []  # Store test-level conditions
        self._lambda_conditions = []  # Store lambda-based conditions

    def with_pattern(self, pattern: str) -> "QueryTestFilter":
        """Filter tests by pattern match.

        Args:
            pattern: Pattern to match against test nodeid.

        Returns:
            QueryTestFilter instance for chaining.

        Raises:
            InvalidQueryParameterError: If pattern is empty.
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError("Test pattern must be a non-empty string")
        self._test_conditions.append(("pattern", pattern))
        return self

    def with_duration(self, min_secs: float, max_secs: float) -> "QueryTestFilter":
        """Filter tests by duration range.

        Args:
            min_secs: Minimum duration in seconds.
            max_secs: Maximum duration in seconds.

        Returns:
            QueryTestFilter instance for chaining.

        Raises:
            InvalidQueryParameterError: If duration bounds are invalid.
        """
        if not isinstance(min_secs, (int, float)) or not isinstance(max_secs, (int, float)):
            raise InvalidQueryParameterError("Duration bounds must be numbers")
        if min_secs < 0:
            raise InvalidQueryParameterError("Duration cannot be negative")
        if min_secs > max_secs:
            raise InvalidQueryParameterError("Min duration must be less than max duration")
        self._test_conditions.append(("duration", (min_secs, max_secs)))
        return self

    def with_outcome(self, outcome: Union[str, TestOutcome]) -> "QueryTestFilter":
        """Filter tests by outcome.

        Args:
            outcome: Test outcome to filter by.

        Returns:
            QueryTestFilter instance for chaining.

        Raises:
            InvalidQueryParameterError: If outcome is invalid.
        """
        outcome_str = outcome.value if hasattr(outcome, "value") else str(outcome)
        valid_outcomes = {o.value for o in TestOutcome}
        if outcome_str not in valid_outcomes:
            raise InvalidQueryParameterError(
                f"Invalid outcome: {outcome_str}. Must be one of: {', '.join(valid_outcomes)}"
            )
        self._test_conditions.append(("outcome", outcome_str))
        return self

    def apply(self) -> "Query":
        """Apply test filters and return to session context.

        This method converts test-level conditions into filters that operate on
        individual tests while preserving session context. A session is included
        if it contains at least one test that matches all test filters.

        Returns:
            Parent Query instance for chaining session-level filters.
        """
        # Convert named conditions to test filters
        test_filters = []
        for condition_type, value in self._test_conditions:
            if condition_type == "pattern":
                pattern = value
                # Add wildcards to match pattern anywhere in nodeid
                test_filters.append(lambda t, p=pattern: fnmatch.fnmatch(t.nodeid, f"*{p}*"))
            elif condition_type == "duration":
                min_secs, max_secs = value
                test_filters.append(lambda t, min=min_secs, max=max_secs: min <= t.duration <= max)
            elif condition_type == "outcome":
                outcome_str = value
                test_filters.append(
                    lambda t, o=outcome_str: (t.outcome.value if hasattr(t.outcome, "value") else str(t.outcome)) == o
                )

        # Add lambda-based conditions if any
        if self._lambda_conditions:
            test_filters.extend(self._lambda_conditions)

        # Create a single filter function that checks if any test matches all conditions
        def session_filter(session):
            if not session.test_results:
                return False
            return any(all(f(test) for f in test_filters) for test in session.test_results)

        # Add the filter to the parent query's test filters
        if test_filters:  # Only add if we have conditions
            self.query._test_filters.append(session_filter)

        return self.query


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
            .with_duration(10.0, float("inf"))
            .apply()  # Back to session context
            .execute()
    """

    def __init__(self, storage=None):
        """Initialize a new Query instance.

        Args:
            storage: Optional storage instance to use. If not provided, will use get_storage_instance().
                   This is primarily used for testing to inject mock storage.
        """
        self._session_filters = []  # Session-level filters (SUT, time range, warnings)
        self._test_filters = []    # Test-level filters (pattern, duration, outcome)
        self._sessions = []        # Cached sessions from storage
        self.storage = storage or get_storage_instance()

    def execute(self, sessions: Optional[List[TestSession]] = None) -> QueryResult:
        """Execute query and return results.

        Args:
            sessions: Optional list of sessions to query. If not provided,
                     loads sessions from storage.

        Returns:
            QueryResult containing filtered sessions.

        Raises:
            QueryExecutionError: If sessions are invalid.
        """
        start_time = datetime.now()

        # Get sessions from storage or use provided list
        if sessions is None:
            sessions = self.storage.load_sessions()
        elif not isinstance(sessions, list) or not all(isinstance(s, TestSession) for s in sessions):
            raise QueryExecutionError("Invalid session type")

        # Apply session-level filters first
        filtered_sessions = sessions
        for filter_func in self._session_filters:
            filtered_sessions = [s for s in filtered_sessions if filter_func(s)]

        # Apply test-level filters - a session passes if ANY test passes ALL filters
        if self._test_filters:
            filtered_sessions = [
                session for session in filtered_sessions
                if all(filter_func(session) for filter_func in self._test_filters)
            ]

        # Create QueryResult with execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        return QueryResult(filtered_sessions, execution_time)

    def filter_by_test(self) -> QueryTestFilter:
        """Start building test-level filters.

        Returns:
            QueryTestFilter instance for building test-level filters.

        Example:
            query.filter_by_test()
                .with_pattern("test_api")
                .with_duration(3.0, 10.0)
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
        self._session_filters.append(
            lambda s: any(t.has_warning for t in s.test_results) == has_warnings
        )
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
        """Filter sessions containing tests matching pattern.

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

        self._session_filters.append(
            lambda s: s.session_tags.get(tag_key) == tag_value
        )
        return self
