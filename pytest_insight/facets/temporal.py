from pytest_insight.core.models import TestSession
from collections import defaultdict

class TemporalInsight:
    """How things change over time (trends, regressions, improvements)."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def trend_over_time(self, metric="reliability", interval="day"):
        """Return a time series of reliability or other metric, grouped by interval."""
        # Group sessions by interval (e.g., day)
        buckets = defaultdict(list)
        for s in self.sessions:
            key = s.session_start_time.date() if interval == "day" else s.session_start_time
            buckets[key].append(s)
        series = []
        for key, group in sorted(buckets.items()):
            total_tests = sum(len(s.test_results) for s in group)
            passes = sum(
                1 for s in group for t in s.test_results if t.outcome == "passed"
            )
            reliability = passes / total_tests if total_tests else None
            series.append({
                "interval": key,
                metric: reliability,
                "total_tests": total_tests,
            })
        return series
