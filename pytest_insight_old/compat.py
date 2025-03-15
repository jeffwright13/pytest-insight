"""Compatibility layer for transitioning from old filter system to new query system."""

from typing import List, Optional

from pytest_insight.models import TestSession
from pytest_insight.query.query import Query


class FilterAdapter:
    """Adapts old TestFilter interface to new Query system."""

    def __init__(
        self,
        sut: Optional[str] = None,
        days: Optional[int] = None,
        outcome: Optional[str] = None,
        has_warnings: Optional[bool] = None,
        has_reruns: Optional[bool] = None,
        nodeid_contains: Optional[str] = None,
    ):
        self.query = Query()

        # Convert old filter params to new query methods
        if sut:
            self.query.for_sut(sut)
        if days:
            self.query.in_last_days(days)
        if outcome:
            self.query.with_outcome(outcome)
        if has_warnings is not None:
            self.query.having_warnings(has_warnings)
        if has_reruns is not None:
            self.query.with_reruns(has_reruns)
        if nodeid_contains:
            self.query.test_contains(nodeid_contains)

    def filter_sessions(self, sessions: List[TestSession]) -> List[TestSession]:
        """Match old filter_sessions interface."""
        return self.query.execute(sessions)
