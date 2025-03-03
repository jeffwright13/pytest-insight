from datetime import datetime, timedelta
from typing import List, Optional

from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.storage import get_storage_instance


class QueryError(Exception):
    """Base exception for Query-related errors."""

    pass


class InvalidQueryParameterError(QueryError):
    """Raised when query parameters are invalid."""

    pass


class QueryExecutionError(QueryError):
    """Raised when query execution fails."""

    pass


class Query:
    """Builder for creating and executing test session queries."""

    def __init__(self):
        self._filters = []
        self._results: Optional[List[TestSession]] = None

    def for_sut(self, name: str) -> "Query":
        """Filter by SUT name."""
        if not isinstance(name, str) or not name.strip():
            raise InvalidQueryParameterError("SUT name must be a non-empty string")
        self._filters.append(lambda s: s.sut_name == name)
        return self

    def in_last_days(self, days: int) -> "Query":
        """Filter sessions from last N days."""
        if not isinstance(days, int) or days <= 0:
            raise InvalidQueryParameterError("Days must be a positive integer")
        cutoff = datetime.now() - timedelta(days=days)
        self._filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def in_last_hours(self, hours: int) -> "Query":
        """Filter sessions from last N hours."""
        if not isinstance(hours, int) or hours <= 0:
            raise InvalidQueryParameterError("Hours must be a positive integer")
        cutoff = datetime.now() - timedelta(hours=hours)
        self._filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def in_last_minutes(self, minutes: int) -> "Query":
        """Filter sessions from last N minutes."""
        if not isinstance(minutes, int) or minutes <= 0:
            raise InvalidQueryParameterError("Minutes must be a positive integer")
        cutoff = datetime.now() - timedelta(minutes=minutes)
        self._filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def date_range(self, start: datetime, end: datetime) -> "Query":
        """Filter sessions between two dates."""
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise InvalidQueryParameterError("Start and end must be datetime objects")
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

    def with_outcome(self, outcome: str) -> "Query":
        """Filter sessions containing tests with specific outcome, as taken from TestOutcome class."""
        valid_outcomes = {o.value for o in TestOutcome}
        if outcome not in valid_outcomes:
            raise InvalidQueryParameterError(f"Invalid outcome: {outcome}. Must be one of: {', '.join(valid_outcomes)}")
        self._filters.append(lambda s: any(t.outcome == outcome for t in s.test_results if hasattr(t, "outcome")))
        return self

    def having_warnings(self, has_warnings: bool) -> "Query":
        """Filter sessions based on presence of warnings."""
        self._filters.append(lambda s: any(t.has_warning == has_warnings for t in s.test_results))
        return self

    def with_reruns(self, has_reruns: bool) -> "Query":
        """Filter sessions based on presence of test reruns."""
        if not isinstance(has_reruns, bool):
            raise InvalidQueryParameterError("has_reruns must be a boolean")
        self._filters.append(lambda s: bool(getattr(s, "rerun_test_groups", [])) == has_reruns)
        return self

    def test_contains(self, pattern: str) -> "Query":
        """Filter sessions containing tests matching pattern."""
        self._filters.append(lambda s: any(pattern in t.nodeid for t in s.test_results))
        return self

    def execute(self, sessions: Optional[List[TestSession]] = None) -> List[TestSession]:
        """Execute query against session list.

        Args:
            sessions: Optional list of sessions to query. If None, loads all sessions
                     from storage.

        Returns:
            List of sessions matching all query criteria.

        Raises:
            QueryExecutionError: If session loading or filtering fails.
        """
        if sessions is None:
            try:
                storage = get_storage_instance()
                sessions = storage.load_sessions()
            except Exception as e:
                raise QueryExecutionError(f"Failed to load sessions: {str(e)}") from e

        if not isinstance(sessions, list):
            raise QueryExecutionError("Sessions must be provided as a list")

        try:
            self._results = []
            for session in sessions:
                if not isinstance(session, TestSession):
                    raise QueryExecutionError(f"Invalid session type: {type(session)}")
                try:
                    if all(f(session) for f in self._filters):
                        self._results.append(session)
                except Exception as e:
                    raise QueryExecutionError(f"Filter execution failed: {str(e)}") from e
            return self._results
        except Exception as e:
            raise QueryExecutionError(f"Query execution failed: {str(e)}") from e
