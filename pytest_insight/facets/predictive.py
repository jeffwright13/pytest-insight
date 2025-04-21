from pytest_insight.core.models import TestSession
from collections import defaultdict
import numpy as np
from tabulate import tabulate


class PredictiveInsight:
    """Machine learning-driven forecasts or anomaly detection."""

    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def forecast(self):
        """
        Forecast future reliability and flag likely upcoming failures using a simple trend analysis.
        This is a placeholder for ML/time series, but now uses a rolling window to estimate trend.
        """
        # Group sessions by date
        if not self.sessions:
            return {"future_reliability": None, "trend": None, "warning": "No sessions available."}
        buckets = defaultdict(list)
        for s in self.sessions:
            date = getattr(s, 'session_start_time', None)
            if date is not None:
                buckets[date.date()].append(s)
        # Calculate reliability per day
        daily_reliability = []
        for day, group in sorted(buckets.items()):
            total_tests = sum(len(sess.test_results) for sess in group)
            passes = sum(1 for sess in group for t in sess.test_results if t.outcome == "passed")
            reliability = passes / total_tests if total_tests else 0.0
            daily_reliability.append((day, reliability))
        if len(daily_reliability) < 2:
            return {"future_reliability": daily_reliability[-1][1] if daily_reliability else None, "trend": None, "warning": "Not enough data for trend."}
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

    def insight(self, kind: str = "predictive_failure", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            from pytest_insight.facets.summary import SummaryInsight
            return SummaryInsight(self.sessions)
        if kind == "predictive_failure":
            forecast = self.forecast()
            rel = forecast.get("future_reliability")
            trend = forecast.get("trend")
            warning = forecast.get("warning")
            if tabular:
                rows = [[
                    f"{rel:.2%}" if rel is not None else "N/A",
                    f"{'downward' if trend < 0 else 'upward'} ({trend:+.2%}/day)" if trend is not None else "N/A",
                    warning or ""
                ]]
                return tabulate(rows, headers=["Forecasted Reliability", "Trend", "Warning"], tablefmt="github")
            else:
                if rel is None:
                    return warning or "Forecasted Reliability: N/A"
                msg = f"Next session forecasted reliability: {rel:.2%}. "
                if trend is not None:
                    msg += f"Trend: {'downward' if trend < 0 else 'upward'} ({trend:+.2%}/day). "
                if warning:
                    msg += f"Warning: {warning}"
                return msg
        raise ValueError(f"Unsupported insight kind: {kind}")
