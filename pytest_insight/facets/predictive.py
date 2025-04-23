from collections import defaultdict
import numpy as np

from pytest_insight.core.insight_base import Insight
from pytest_insight.core.models import TestSession


class PredictiveInsight(Insight):
    """
    Predictive analytics for test sessions (future reliability, trend warnings).
    Inherits the Insight base interface.
    """

    def __init__(self, sessions: list[TestSession]):
        self._sessions = sessions

    def forecast(self):
        """
        Forecast future reliability and flag likely upcoming failures using a simple trend analysis.
        This is a placeholder for ML/time series, but now uses a rolling window to estimate trend.
        """
        # Group sessions by date
        if not self._sessions:
            return {
                "future_reliability": None,
                "trend": None,
                "warning": "No sessions available.",
            }
        buckets = defaultdict(list)
        for s in self._sessions:
            date = getattr(s, "session_start_time", None)
            if date is not None:
                buckets[date.date()].append(s)
        daily_reliability = []
        for date, group in sorted(buckets.items()):
            total_tests = sum(len(s.test_results) for s in group)
            passes = sum(1 for s in group for t in s.test_results if t.outcome == "passed")
            reliability = passes / total_tests if total_tests else None
            daily_reliability.append((date, reliability))
        if len(daily_reliability) < 2:
            return {
                "future_reliability": None,
                "trend": None,
                "warning": "Not enough data for trend.",
            }
        # Fit a simple linear trend
        x = np.arange(len(daily_reliability))
        y = np.array([r for _, r in daily_reliability])
        coeffs = np.polyfit(x, y, 1)
        trend = coeffs[0]
        forecast_next = y[-1] + trend
        forecast_next = max(0.0, min(1.0, forecast_next))
        warning = None
        if trend < -0.05:
            warning = "Reliability is trending downward. Possible regression risk!"
        return {"future_reliability": forecast_next, "trend": trend, "warning": warning}

    def as_dict(self):
        """Return predictive metrics as a dict for dashboard rendering."""
        return self.forecast()

    def available_insights(self):
        """
        Return the available insight types for predictive analytics.
        """
        return ["predictive"]

    def insight(self, kind: str = "predictive_failure", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight
            return SummaryInsight(self._sessions).as_dict()
        if kind == "predictive_failure":
            forecast = self.forecast()
            rel = forecast.get("future_reliability")
            trend = forecast.get("trend")
            warning = forecast.get("warning")
            # Always return structured data
            return {"future_reliability": rel, "trend": trend, "warning": warning}
        raise ValueError(f"Unsupported insight kind: {kind}")
