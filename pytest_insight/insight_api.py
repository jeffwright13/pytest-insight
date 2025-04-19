from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from pytest_insight.utils import NormalizedDatetime


class InsightAPI:
    """
    Unified entry point for all test insights.
    Each method is a stub for a different insight type.
    Extend these with real logic as you build out the system.
    """

    def __init__(self, profile: Optional[str] = None) -> None:
        self.profile: Optional[str] = profile
        self._sessions: Dict[str, Any] = {}  # session_id -> TestSession
        self._last_session_id: Optional[str] = None

    def register_session(self, session: Any) -> None:
        self._sessions[session.session_id] = session
        self._last_session_id = session.session_id

    def session(self, session_id: Optional[str] = None) -> "SessionInsightStub":
        # Return a stub that can access the session
        if session_id is None:
            session_id = self._last_session_id
        return SessionInsightStub(self._sessions.get(session_id))

    def tests(self) -> "TestInsightStub":
        """Test-level insight stub (all tests)."""
        return TestInsightStub()

    def over_time(self, days: int = 30) -> "TemporalInsightStub":
        """Temporal insight stub (trends over time)."""
        return TemporalInsightStub(days)

    def compare(self, sut_a: Optional[str] = None, sut_b: Optional[str] = None) -> "ComparativeInsightStub":
        """Comparative insight stub (compare SUTs or versions)."""
        return ComparativeInsightStub(sut_a, sut_b)

    def trend(self) -> "TrendInsightStub":
        """Trend-focused insight stub (emerging patterns)."""
        return TrendInsightStub()

    def predictive(self) -> "PredictiveInsightStub":
        """Predictive insight stub (forecasting/anomaly detection)."""
        return PredictiveInsightStub()

    def meta(self) -> "MetaInsightStub":
        """Meta/process insight stub (maintenance, process health)."""
        return MetaInsightStub()

    def summary(self) -> "SummaryInsight":
        """Return the summary insight facet."""
        return SummaryInsight(self._sessions)


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

    def insight(self, kind: str = "flakiness") -> str:
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


class SummaryInsight:
    """Facet for computing high-level summary metrics over test sessions."""

    def __init__(self, sessions: Dict[str, Any]) -> None:
        """
        Args:
            sessions (dict): Mapping of session_id to TestSession objects.
        """
        self.sessions: Dict[str, Any] = sessions

    def get(
        self,
        duration: Optional[timedelta] = None,
        since: Optional["datetime"] = None,
        days: Optional[int] = None,
        hours: Optional[int] = None,
        minutes: Optional[int] = None,
        seconds: Optional[int] = None,
        outcome: Optional[str] = None,
        sut: Optional[str] = None,
    ) -> dict:
        """
        Compute summary metrics for filtered sessions.

        Args:
            duration (timedelta, optional): Time window for filtering.
            since (datetime, optional): Only sessions since this timestamp.
            days, hours, minutes, seconds (int, optional): Alternative time window.
            outcome (str, optional): Filter by session outcome.
            sut (str, optional): Filter by system under test.

        Returns:
            dict: Summary metrics.
        """
        sessions = list(self.sessions.values())
        now = NormalizedDatetime.now()

        # Determine cutoff time
        cutoff = None
        if since is not None:
            cutoff = NormalizedDatetime(since)
        elif duration is not None:
            cutoff = NormalizedDatetime(now.dt - duration)
        elif any([days, hours, minutes, seconds]):
            delta = timedelta(days=days or 0, hours=hours or 0, minutes=minutes or 0, seconds=seconds or 0)
            cutoff = NormalizedDatetime(now.dt - delta)

        # Filter sessions
        if cutoff:
            sessions = [
                s
                for s in sessions
                if hasattr(s, "session_start_time") and NormalizedDatetime(s.session_start_time) >= cutoff
            ]
        if outcome is not None:
            sessions = [s for s in sessions if getattr(s, "outcome", None) == outcome]
        if sut is not None:
            sessions = [s for s in sessions if getattr(s, "sut", None) == sut]

        # Compute metrics (replace with actual analysis logic if available)
        total_sessions = len(sessions)
        total_tests = sum(len(getattr(s, "test_results", [])) for s in sessions)
        pass_rate = (
            sum(1 for s in sessions if getattr(s, "outcome", None) == "passed") / total_sessions
            if total_sessions
            else None
        )
        reliability_score = pass_rate  # For now, reliability = pass_rate
        first_session = min(
            (getattr(s, "session_start_time", None) for s in sessions if getattr(s, "session_start_time", None)),
            default=None,
        )
        last_session = max(
            (getattr(s, "session_start_time", None) for s in sessions if getattr(s, "session_start_time", None)),
            default=None,
        )

        return {
            "total_sessions": total_sessions,
            "total_tests": total_tests,
            "pass_rate": pass_rate,
            "reliability_score": reliability_score,
            "first_session": first_session,
            "last_session": last_session,
        }
