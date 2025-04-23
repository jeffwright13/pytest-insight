from collections import defaultdict

from pytest_insight.core.insight_base import Insight
from pytest_insight.core.models import TestSession


class TemporalInsight(Insight):
    """
    How things change over time (trends, regressions, improvements).
    Inherits the Insight base interface.
    """

    def __init__(self, sessions: list[TestSession]):
        self._sessions = sessions

    def trend_over_time(self, metric="reliability", interval="day"):
        """Return a time series of reliability or other metric, grouped by interval."""
        buckets = defaultdict(list)
        for s in self._sessions:
            key = s.session_start_time.date() if interval == "day" else s.session_start_time
            buckets[key].append(s)
        series = []
        for key, group in sorted(buckets.items()):
            total_tests = sum(len(s.test_results) for s in group)
            passes = sum(1 for s in group for t in s.test_results if t.outcome == "passed")
            reliability = passes / total_tests if total_tests else None
            series.append(
                {
                    "interval": key,
                    metric: reliability,
                    "total_tests": total_tests,
                }
            )
        return series

    def insight(self, kind: str = "trend", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight

            return SummaryInsight(self._sessions).as_dict()
        if kind == "trend":
            series = self.trend_over_time()
            return {"trend_series": series}
        raise ValueError(f"Unsupported insight kind: {kind}")

    def as_dict(self):
        """Return temporal metrics as a dict for dashboard rendering."""
        # Placeholder: just return all sessions for now
        return {"sessions": [s.session_id for s in self._sessions]}

    def available_insights(self):
        """
        Return the available insight types for temporal analytics.
        """
        return ["temporal"]
