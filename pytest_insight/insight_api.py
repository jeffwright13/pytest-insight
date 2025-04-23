from pytest_insight.core.insight_base import Insight
from pytest_insight.facets.comparative import ComparativeInsight
from pytest_insight.facets.meta import MetaInsight
from pytest_insight.facets.predictive import PredictiveInsight
from pytest_insight.facets.session import SessionInsight
from pytest_insight.facets.summary import SummaryInsight
from pytest_insight.facets.temporal import TemporalInsight
from pytest_insight.facets.test import TestInsight
from pytest_insight.facets.trend import TrendInsight


class InsightAPI(Insight):
    """
    Canonical orchestrator for pytest-insight analytics.

    - Fluent, chainable API for all core operations: query, compare, analyze.
    - All analytics/reporting routed through canonical methods.
    - High-level summary and introspective insight kind dispatch.
    - Optionally exposes facets as properties for discoverability.

    Example:
        api = InsightAPI(sessions)
        api.summary_report()
        api.trend().insight("trend")
        api.meta().insight("meta")
        api.compare().insight("regression")
        api.filter_by_test().with_outcome("fail").apply().trend().insight("trend")
    """

    def __init__(self, sessions: list = None, profile: str = None):
        if sessions is not None:
            self._sessions = sessions
        elif profile is not None:
            from pytest_insight.core.storage import get_storage_instance
            storage = get_storage_instance(profile)
            self._sessions = storage.load_sessions()
        else:
            self._sessions = []

    # --- Fluent Facet Methods ---
    def sessions(self):
        return SessionInsight(self._sessions)

    def tests(self):
        return TestInsight(self._sessions)

    def trend(self):
        return TrendInsight(self._sessions)

    def session(self, session_id=None, **kwargs):
        if session_id is not None:
            filtered = [s for s in self._sessions if getattr(s, "session_id", None) == session_id]
            return SessionInsight(filtered)
        return SessionInsight(self._sessions)

    def temporal(self):
        return TemporalInsight(self._sessions)

    def compare(self, **kwargs):
        return ComparativeInsight(self._sessions)

    def predictive(self):
        return PredictiveInsight(self._sessions)

    def meta(self):
        return MetaInsight(self._sessions)

    # --- High-Level Reports ---
    def summary(self):
        """Return summary metrics as a dict for the sessions."""
        return SummaryInsight(self._sessions).as_dict()

    def summary_as_text(self):
        """Return a formatted string summary for the sessions (for CLI/reporting)."""
        return str(SummaryInsight(self._sessions))

    def summary_report(self):
        """Comprehensive summary report (health, session, trend, etc)."""
        return {
            "health": self.session().insight("health"),
            "session_insights": self.session().insight("summary"),
            "trend": self.temporal().insight("trend"),
            "meta": self.meta().insight("meta"),
            "predictive": self.predictive().insight("predictive_failure"),
            "comparison": self.compare().insight("regression"),
        }

    def available_insights(self):
        """List available insight kinds."""
        import inspect
        return sorted(
            name[len("_insight_") :]
            for name, method in inspect.getmembers(self, predicate=inspect.ismethod)
            if name.startswith("_insight_")
        )

    def insight(self, kind: str, **kwargs):
        method_name = f"_insight_{kind}"
        if hasattr(self, method_name):
            return getattr(self, method_name)(**kwargs)
        raise ValueError(f"Unsupported insight kind: {kind}")

    # --- Canonical Methods for Structured Data ---
    def summary_dict(self):
        """Return summary analytics as a structured dict.
        Returns:
            dict: Summary metrics (total_sessions, total_tests, pass_rate, fail_rate, reliability, outcome_counts).
        """
        return SummaryInsight(self._sessions).as_dict()

    def session_dict(self):
        """Return session-level analytics as a structured dict.
        Returns:
            dict: Session metrics and summaries.
        """
        return SessionInsight(self._sessions).as_dict()

    def test_dict(self):
        """Return test-level analytics as a structured dict.
        Returns:
            dict: Test metrics (unreliable, slowest, flakiest, etc).
        """
        return TestInsight(self._sessions).as_dict()

    def predictive_dict(self):
        """Return predictive analytics as a structured dict.
        Returns:
            dict: Predictive metrics such as forecasted reliability and trends.
        """
        return PredictiveInsight(self._sessions).as_dict()

    def meta_dict(self):
        """Return meta analytics as a structured dict.
        Returns:
            dict: Meta-level metrics (maintenance burden, stability, etc).
        """
        return MetaInsight(self._sessions).as_dict()

    def trend_dict(self):
        """Return trend analytics as a structured dict.
        Returns:
            dict: Trend metrics and emerging patterns.
        """
        return TrendInsight(self._sessions).as_dict()

    def comparative_dict(self):
        """Return comparative analytics as a structured dict.
        Returns:
            dict: Comparative metrics between SUTs, versions, etc.
        """
        return ComparativeInsight(self._sessions).as_dict()

    def temporal_dict(self):
        """Return temporal analytics as a structured dict.
        Returns:
            dict: Temporal metrics (changes over time, regressions, improvements).
        """
        return TemporalInsight(self._sessions).as_dict()

    # --- Introspective/Dispatch Methods ---
    def _insight_summary(self, **kwargs):
        return SummaryInsight(self._sessions)

    def _insight_health(self, **kwargs):
        return self.session().insight("health")

    def _insight_reliability(self, **kwargs):
        return self.tests().insight("reliability", **kwargs)

    def _insight_trend(self, **kwargs):
        return self.trend().insight("trend", **kwargs)

    def _insight_session(self, **kwargs):
        return self.session(**kwargs)

    def _insight_test(self, **kwargs):
        return self.tests(**kwargs)

    def _insight_predictive(self, **kwargs):
        return self.predictive().insight("predictive_failure", **kwargs)

    def _insight_meta(self, **kwargs):
        return self.meta().insight("meta", **kwargs)

    def _insight_compare(self, **kwargs):
        return self.compare().insight("regression", **kwargs)

    def _insight_temporal(self, **kwargs):
        return self.temporal().insight("trend", **kwargs)

    # --- Fluent Filtering (stubs for now) ---
    def filter(self, **kwargs):
        # Implement filtering logic as needed
        return InsightAPI(self._sessions)  # Placeholder

    def over_time(self, days=30):
        # Implement time filtering logic as needed
        return InsightAPI(self._sessions)  # Placeholder

    # --- Optional: Expose facets as properties for discoverability ---
    @property
    def predictive_facet(self):
        return PredictiveInsight(self._sessions)

    @property
    def meta_facet(self):
        return MetaInsight(self._sessions)

    @property
    def comparative_facet(self):
        return ComparativeInsight(self._sessions)

    @property
    def temporal_facet(self):
        return TemporalInsight(self._sessions)

    @property
    def session_facet(self):
        return SessionInsight(self._sessions)

    @property
    def test_facet(self):
        return TestInsight(self._sessions)

    @property
    def trend_facet(self):
        return TrendInsight(self._sessions)
