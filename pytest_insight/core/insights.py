"""Base classes and orchestrator for insight facets.

This module provides the main Insights orchestrator and all insight facet base classes for pytest-insight.
"""

from typing import Any, Dict, Optional

from pytest_insight.facets.meta import MetaInsight
from pytest_insight.facets.predictive import PredictiveInsight

from .analysis import calculate_reliability


class Insights:
    """
    Top-level insights for pytest-insight v2.

    Provides access to all insight components:
    - SessionInsights: Session-level insights
    - PredictiveInsight: Predictive analytics insights
    - MetaInsight: Meta analytics insights

    Args:
        sessions (Optional[list]): List of TestSession objects.
    """
    def __init__(self, sessions: Optional[list] = None):
        self._sessions = sessions if sessions is not None else []
        self.sessions = SessionInsights(self._sessions)
        self.predictive = PredictiveInsight(self._sessions)
        self.meta = MetaInsight(self._sessions)

    def summary_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive summary report.

        Returns:
            dict: Summary report with health, session, and trend insights.
        """
        health_report = self.sessions.health_report()
        session_insights = self.sessions.key_metrics()
        return {
            "health": health_report,
            "session_insights": session_insights,
        }

class SessionInsights:
    """
    Session-level insights and analytics.

    Args:
        sessions (list): List of TestSession objects.
    """
    def __init__(self, sessions):
        self._sessions = sessions

    def session_metrics(self) -> Dict[str, Any]:
        """
        Calculate basic session metrics.

        Returns:
            dict: Session metrics including totals and counts.
        """
        total_sessions = len(self._sessions)
        total_tests = sum(len(getattr(s, "test_results", [])) for s in self._sessions)
        passed = sum(
            1 for s in self._sessions for t in getattr(s, "test_results", []) if getattr(t, "outcome", None) == "passed"
        )
        failed = sum(
            1 for s in self._sessions for t in getattr(s, "test_results", []) if getattr(t, "outcome", None) == "failed"
        )
        unreliable = sum(
            1 for s in self._sessions for t in getattr(s, "test_results", []) if getattr(t, "unreliable", False)
        )
        return {
            "total_sessions": total_sessions,
            "total_tests": total_tests,
            "passed": passed,
            "failed": failed,
            "unreliable": unreliable,
        }

    def health_report(self) -> Dict[str, Any]:
        """
        Generate a health report for the test suite.

        Returns:
            dict: Health report including reliability and session metrics.
        """
        reliability = calculate_reliability(self._sessions)
        metrics = self.session_metrics()
        return {"reliability": reliability, **metrics}

    def key_metrics(self) -> Dict[str, Any]:
        """
        Return key session metrics.

        Returns:
            dict: Key session metrics.
        """
        return self.session_metrics()

# --- STUB: For v1 compatibility only ---
class TestInsights:
    """Stub for v1 compatibility. All methods raise NotImplementedError."""
    def __init__(self, *args, **kwargs):
        pass
    def error_patterns(self, *args, **kwargs):
        raise NotImplementedError("TestInsights is not implemented in v2.")
    def flakiness(self, *args, **kwargs):
        raise NotImplementedError("TestInsights is not implemented in v2.")
    def trends(self, *args, **kwargs):
        raise NotImplementedError("TestInsights is not implemented in v2.")

# Removed TestInsights and TrendInsights classes. All analytics logic will be moved to the corresponding singular classes in facets/.
