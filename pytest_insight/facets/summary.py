from pytest_insight.core.analysis import calculate_reliability
from pytest_insight.core.models import TestSession, TestOutcome
from tabulate import tabulate


class SummaryInsight:
    """Aggregate stats and session-level metrics."""

    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def aggregate_stats(self):
        total_sessions = len(self.sessions)
        total_tests = sum(len(s.test_results) for s in self.sessions)
        reliability = calculate_reliability(self.sessions)
        # Compute total counts for all possible outcomes at the session level
        outcome_counts = {k: 0 for k in TestOutcome.to_list()}
        for s in self.sessions:
            for t in getattr(s, "test_results", []):
                outcome = getattr(t, "outcome", None)
                if isinstance(outcome, TestOutcome):
                    outcome_key = outcome.value.lower()
                else:
                    outcome_key = str(outcome).lower()
                if outcome_key in outcome_counts:
                    outcome_counts[outcome_key] += 1
        # Compute percentages
        outcome_percentages = {k: (outcome_counts[k] / total_tests * 100 if total_tests else 0.0) for k in outcome_counts}
        return {
            "total_sessions": total_sessions,
            "total_tests": total_tests,
            "reliability": reliability,
            "outcome_counts": outcome_counts,
            "outcome_percentages": outcome_percentages,
        }

    def suite_level_metrics(self):
        # Example: average session duration
        if not self.sessions:
            return {"avg_duration": None}
        avg_duration = sum((sum(t.duration for t in s.test_results) for s in self.sessions)) / len(self.sessions)
        return {"avg_duration": avg_duration}

    def insight(self, kind: str = "summary", tabular: bool = True, **kwargs):
        if kind in {"summary", "health"}:
            return self
        raise ValueError(f"Unsupported insight kind: {kind}")

    def as_dict(self):
        """Return summary metrics as a dict for dashboard rendering."""
        total_sessions = len(self.sessions)
        total_tests = sum(len(s.test_results) for s in self.sessions)
        reliability = calculate_reliability(self.sessions)
        outcome_counts = {k: 0 for k in TestOutcome.to_list()}
        for s in self.sessions:
            for t in getattr(s, "test_results", []):
                outcome = getattr(t, "outcome", None)
                if isinstance(outcome, TestOutcome):
                    outcome_key = outcome.value.lower()
                else:
                    outcome_key = str(outcome).lower()
                if outcome_key in outcome_counts:
                    outcome_counts[outcome_key] += 1
        outcome_percentages = {k: (outcome_counts[k] / total_tests * 100 if total_tests else 0.0) for k in outcome_counts}
        return {
            "total_sessions": total_sessions,
            "total_tests": total_tests,
            "pass_rate": outcome_percentages.get("passed", 0.0),
            "fail_rate": outcome_percentages.get("failed", 0.0),
            "reliability": reliability,
            "outcome_counts": outcome_counts,
        }
