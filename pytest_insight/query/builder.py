from datetime import datetime, timedelta
import re
from typing import List, Optional, Any

from pytest_insight.models import TestSession, TestOutcome

class QueryError(Exception):
    """Base exception for Query-related errors."""
    pass

class InvalidQueryParameterError(QueryError):
    """Raised when query parameters are invalid."""
    pass

class Query:
    """Builder for creating and executing test session queries."""

    def __init__(self):
        self._filters = []
        self._results: Optional[List[TestSession]] = None

    def for_sut(self, name: str) -> 'Query':
        """Filter by SUT name."""
        if not isinstance(name, str) or not name.strip():
            raise InvalidQueryParameterError("SUT name must be a non-empty string")
        self._filters.append(lambda s: s.sut_name == name)
        return self

    def in_last_days(self, days: int) -> 'Query':
        """Filter sessions from last N days."""
        if not isinstance(days, int) or days <= 0:
            raise InvalidQueryParameterError("Days must be a positive integer")
        cutoff = datetime.now() - timedelta(days=days)
        self._filters.append(lambda s: s.session_start_time >= cutoff)
        return self

    def with_outcome(self, outcome: str) -> 'Query':
        """Filter sessions containing tests with specific outcome."""
        valid_outcomes = {o.value for o in TestOutcome}
        if outcome not in valid_outcomes:
            raise InvalidQueryParameterError(
                f"Invalid outcome: {outcome}. Must be one of: {', '.join(valid_outcomes)}"
            )
        self._filters.append(
            lambda s: any(t.outcome == outcome for t in s.test_results)
        )
        return self

    def having_warnings(self, has_warnings: bool) -> 'Query':
        """Filter sessions based on presence of warnings."""
        self._filters.append(
            lambda s: any(t.has_warning == has_warnings for t in s.test_results)
        )
        return self

    def with_reruns(self, has_reruns: bool) -> 'Query':
        """Filter sessions based on presence of test reruns."""
        self._filters.append(
            lambda s: bool(s.rerun_test_groups) == has_reruns
        )
        return self

    def test_contains(self, pattern: str) -> 'Query':
        """Filter sessions containing tests matching pattern."""
        self._filters.append(
            lambda s: any(pattern in t.nodeid for t in s.test_results)
        )
        return self

    def execute(self, sessions: List[TestSession]) -> List[TestSession]:
        """Execute query against session list."""
        self._results = []
        for session in sessions:
            if all(f(session) for f in self._filters):
                self._results.append(session)
        return self._results
