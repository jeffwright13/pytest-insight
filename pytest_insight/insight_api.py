from pytest_insight.facets.comparative import ComparativeInsight
from pytest_insight.facets.meta import MetaInsight
from pytest_insight.facets.predictive import PredictiveInsight
from pytest_insight.facets.session import SessionInsight
from pytest_insight.facets.summary import SummaryInsight
from pytest_insight.facets.temporal import TemporalInsight
from pytest_insight.facets.test import TestInsight
from pytest_insight.facets.trend import TrendInsight


class InsightAPI:
    """
    Unified entry point for all test insights (faceted interface).
    Provides fluent, composable access to all analytics facets.
    """

    def __init__(self, sessions: list = None, profile: str = None):
        """Initialize InsightAPI with sessions or by loading from a profile."""
        if sessions is not None:
            self.sessions = sessions
        elif profile is not None:
            from pytest_insight.core.storage import get_storage_instance

            storage = get_storage_instance(profile)
            self.sessions = storage.load_sessions()
        else:
            self.sessions = []

    def test(self, nodeid=None, **kwargs):
        """Return TestInsight for a single test or all tests if nodeid is None."""
        if nodeid is not None:
            filtered = []
            for s in self.sessions:
                for t in getattr(s, "test_results", []):
                    if getattr(t, "nodeid", None) == nodeid:
                        filtered.append(s)
                        break
            return TestInsight(filtered)
        return TestInsight(self.sessions)

    def trend(self):
        """Return TrendInsight for all sessions."""
        return TrendInsight(self.sessions)

    def session(self, session_id=None, **kwargs):
        """Return SessionInsight for all or a filtered session."""
        if session_id is not None:
            filtered = [s for s in self.sessions if getattr(s, "session_id", None) == session_id]
            return SessionInsight(filtered)
        return SessionInsight(self.sessions)

    def temporal(self):
        """Return TemporalInsight for all sessions."""
        return TemporalInsight(self.sessions)

    def compare(self, **kwargs):
        """Return ComparativeInsight for comparison analytics."""
        # kwargs could be sut, env, etc.
        return ComparativeInsight(self.sessions)

    def predictive(self):
        """Return PredictiveInsight for ML-driven analytics."""
        return PredictiveInsight(self.sessions)

    def meta(self):
        """Return MetaInsight for meta analytics."""
        return MetaInsight(self.sessions)

    def summary(self):
        """Return a SummaryInsight object for the sessions."""
        return SummaryInsight(self.sessions)

    def available_insights(self):
        """Return a list of available insight kinds."""
        return ["summary", "session", "sessions", "test", "tests", "trend", "compare", "predictive", "meta", "temporal"]

    # Fluent API example methods for filtering, etc. (stubs)
    def filter(self, **kwargs):
        # Example: filter(name="test_login")
        # Implement filtering logic as needed
        return InsightAPI(self.sessions)  # Placeholder

    def over_time(self, days=30):
        # Example: restrict sessions to last N days
        # Implement time filtering logic as needed
        return InsightAPI(self.sessions)  # Placeholder

    # Unified insight access
    def insight(self, kind: str, **kwargs):
        # Example: api.insight("reliability")
        # Dispatch to the correct facet
        if kind == "summary":
            return SummaryInsight(self.sessions)
        if kind == "reliability":
            return self.test().insight("reliability", **kwargs)
        if kind == "trend":
            return self.trend(**kwargs)
        if kind == "session":
            return self.session(**kwargs)
        if kind == "test":
            return self.test(**kwargs)
        if kind == "predictive":
            return self.predictive(**kwargs)
        if kind == "meta":
            return self.meta(**kwargs)
        if kind == "compare":
            return self.compare(**kwargs)
        if kind == "temporal":
            return self.temporal(**kwargs)
        raise ValueError(f"Unknown insight kind: {kind}")
