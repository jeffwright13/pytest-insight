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

    def sessions(self):
        """Return a SessionInsight over all sessions."""
        return SessionInsight(self.sessions)

    def tests(self):
        """Return a TestInsight over all sessions/tests."""
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
        """Return summary metrics as a dict for the sessions."""
        return SummaryInsight(self.sessions).as_dict()

    def summary_as_text(self):
        """Return a formatted string summary for the sessions (for CLI/reporting)."""
        return str(SummaryInsight(self.sessions))

    def available_insights(self):
        """Return a list of available insight kinds (introspected from insight methods)."""
        import inspect
        # Find all methods starting with _insight_*
        insight_methods = [
            name[len("_insight_"):] for name, method in inspect.getmembers(self, predicate=inspect.ismethod)
            if name.startswith("_insight_")
        ]
        return sorted(insight_methods)

    def insight(self, kind: str, **kwargs):
        # Introspective registry: call self._insight_<kind>(**kwargs) if it exists
        method_name = f"_insight_{kind}"
        if hasattr(self, method_name):
            method = getattr(self, method_name)
            return method(**kwargs)
        raise ValueError(f"Unsupported insight kind: {kind}")

    # --- Insight factory methods ---
    def _insight_summary(self, **kwargs):
        return SummaryInsight(self.sessions)
    def _insight_health(self, **kwargs):
        return SummaryInsight(self.sessions)
    def _insight_reliability(self, **kwargs):
        return self.tests().insight("reliability", **kwargs)
    def _insight_trend(self, **kwargs):
        return self.trend(**kwargs)
    def _insight_session(self, **kwargs):
        return self.session(**kwargs)
    def _insight_test(self, **kwargs):
        return self.tests(**kwargs)
    def _insight_predictive(self, **kwargs):
        return self.predictive(**kwargs)
    def _insight_meta(self, **kwargs):
        return self.meta(**kwargs)
    def _insight_compare(self, **kwargs):
        return self.compare(**kwargs)
    def _insight_temporal(self, **kwargs):
        return self.temporal(**kwargs)

    # Fluent API example methods for filtering, etc. (stubs)
    def filter(self, **kwargs):
        # Example: filter(name="test_login")
        # Implement filtering logic as needed
        return InsightAPI(self.sessions)  # Placeholder

    def over_time(self, days=30):
        # Example: restrict sessions to last N days
        # Implement time filtering logic as needed
        return InsightAPI(self.sessions)  # Placeholder
