from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from pytest_insight.core.models import TestSession
from pytest_insight.core.query import SessionQuery, TestQuery
from pytest_insight.facets.comparative import ComparativeInsight
from pytest_insight.facets.meta import MetaInsight
from pytest_insight.facets.predictive import PredictiveInsight
from pytest_insight.facets.session import SessionInsight
from pytest_insight.facets.summary import SummaryInsight
from pytest_insight.facets.temporal import TemporalInsight
from pytest_insight.facets.test import TestInsight
from pytest_insight.facets.trend import TrendInsight
from pytest_insight.utils.utils import NormalizedDatetime


class InsightAPI:
    """
    Unified entry point for all test insights (faceted interface).
    Provides fluent, composable access to all analytics facets.
    """
    def __init__(self, sessions: list[TestSession] = None, profile: str = None):
        # In a real implementation, load sessions from storage/profile
        self.sessions = sessions or []
        self.profile = profile

    def summary(self) -> SummaryInsight:
        return SummaryInsight(self.sessions)

    def session(self) -> SessionQuery:
        return SessionQuery(self.sessions)

    def test(self) -> TestQuery:
        return TestQuery(SessionQuery(self.sessions))

    def temporal(self) -> TemporalInsight:
        return TemporalInsight(self.sessions)

    def comparative(self) -> ComparativeInsight:
        return ComparativeInsight(self.sessions)

    def trend(self) -> TrendInsight:
        return TrendInsight(self.sessions)

    def predictive(self) -> PredictiveInsight:
        return PredictiveInsight(self.sessions)

    def meta(self) -> MetaInsight:
        return MetaInsight(self.sessions)


# --- Stub Classes for Each Insight Type ---


class SessionInsightStub:
    def __init__(self, session: Any) -> None:
        self.session: Any = session

    def insight(self, kind: str = "summary") -> str:
        if not self.session:
            return "[Session Insight: No session found]"
        if kind == "summary":
            return (
                f"Session {self.session.session_id}: "
                f"{len(self.session.test_results)} tests, "
                f"SUT={self.session.sut_name}"
            )
        return f"[Session Insight: {kind}] (session_id={self.session.session_id})"


class TestInsightStub:
    def filter(self, **kwargs: Any) -> "TestInsightStub":
        return self  # chaining stub

    def insight(self, kind: str = "reliability") -> str:
        return f"[Test Insight: {kind}]"


class TemporalInsightStub:
    def __init__(self, days: int) -> None:
        self.days: int = days

    def insight(self, kind: str = "trend") -> str:
        return f"[Temporal Insight: {kind}] (days={self.days})"


class ComparativeInsightStub:
    def __init__(self, sut_a: Optional[str], sut_b: Optional[str]) -> None:
        self.sut_a: Optional[str] = sut_a
        self.sut_b: Optional[str] = sut_b

    def insight(self, kind: str = "regression") -> str:
        return f"[Comparative Insight: {kind}] (A={self.sut_a}, B={self.sut_b})"


class TrendInsightStub:
    def insight(self, kind: str = "trend") -> str:
        return f"[Trend Insight: {kind}]"


class PredictiveInsightStub:
    def insight(self, kind: str = "predictive_failure") -> str:
        return f"[Predictive Insight: {kind}]"


class MetaInsightStub:
    def insight(self, kind: str = "maintenance_burden") -> str:
        return f"[Meta Insight: {kind}]"


class SummaryInsightStub:
    def __init__(self, sessions: list[Any]) -> None:
        self.sessions = sessions

    def insight(self, kind: str = "summary") -> str:
        if not self.sessions:
            return "[Summary Insight: No sessions found]"
        if kind == "summary":
            total_sessions = len(self.sessions)
            total_tests = sum(len(getattr(s, "test_results", [])) for s in self.sessions)
            return (
                f"Summary: {total_sessions} sessions, "
                f"{total_tests} tests, "
                f"SUTs: {', '.join(sorted(set(getattr(s, 'sut_name', 'unknown') for s in self.sessions)))}"
            )
        return f"[Summary Insight: {kind}] ({len(self.sessions)} sessions)"
