from pytest_insight.core.models import TestSession
from pytest_insight.core.analysis import calculate_reliability

class SummaryInsight:
    """Aggregate stats and session-level metrics."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def aggregate_stats(self):
        total_sessions = len(self.sessions)
        total_tests = sum(len(s.test_results) for s in self.sessions)
        reliability = calculate_reliability(self.sessions)
        outcomes = {}
        for s in self.sessions:
            outcomes[s.outcome] = outcomes.get(s.outcome, 0) + 1
        return {
            "total_sessions": total_sessions,
            "total_tests": total_tests,
            "reliability": reliability,
            "outcomes": outcomes,
        }

    def suite_level_metrics(self):
        # Example: average session duration
        if not self.sessions:
            return {"avg_duration": None}
        avg_duration = sum(
            (sum(t.duration for t in s.test_results) for s in self.sessions)
        ) / len(self.sessions)
        return {"avg_duration": avg_duration}
