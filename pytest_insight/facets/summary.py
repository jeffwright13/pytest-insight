from pytest_insight.core.analysis import calculate_reliability
from pytest_insight.core.models import TestSession, TestOutcome


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

    def insight(self):
        stats = self.aggregate_stats()
        avg_duration = self.suite_level_metrics().get("avg_duration")
        # Build a human-readable outcome breakdown table
        outcome_lines = ["Outcome Breakdown:"]
        outcome_lines.append(f"{'Outcome':<10} | {'Count':>6} | {'Percent':>7}")
        outcome_lines.append("-" * 30)
        for k in stats["outcome_counts"]:
            outcome_lines.append(f"{k.capitalize():<10} | {stats['outcome_counts'][k]:>6} | {stats['outcome_percentages'][k]:>6.2f}%")
        outcome_table = "\n".join(outcome_lines)
        return (
            f"Sessions: {stats['total_sessions']}, "
            f"Tests: {stats['total_tests']}, "
            f"Reliability: {stats['reliability']:.2%} " if stats['reliability'] is not None else "Reliability: N/A "
            + (f"Avg Duration: {avg_duration:.2f}s" if avg_duration is not None else "Avg Duration: N/A")
            + "\n" + outcome_table
        )
