from pytest_insight.core.models import TestSession
from collections import defaultdict

class TestInsight:
    """Focus on individual tests: reliability, duration, outcome, etc."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def reliability_report(self):
        """Reliability metrics per test nodeid."""
        stats = defaultdict(lambda: {"runs": 0, "passes": 0, "failures": 0, "total_duration": 0.0})
        for s in self.sessions:
            for t in s.test_results:
                stats[t.nodeid]["runs"] += 1
                stats[t.nodeid]["passes"] += int(t.outcome == "passed")
                stats[t.nodeid]["failures"] += int(t.outcome == "failed")
                stats[t.nodeid]["total_duration"] += t.duration
        # Compute reliability as pass/runs
        report = []
        for nodeid, d in stats.items():
            reliability = d["passes"] / d["runs"] if d["runs"] else None
            avg_duration = d["total_duration"] / d["runs"] if d["runs"] else None
            report.append({
                "nodeid": nodeid,
                "runs": d["runs"],
                "reliability": reliability,
                "avg_duration": avg_duration,
                "failures": d["failures"],
            })
        return report
