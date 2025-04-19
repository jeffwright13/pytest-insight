from pytest_insight.core.models import TestSession

class SessionInsight:
    """Metrics and health for a single session or group of sessions."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def metrics(self):
        metrics = []
        for s in self.sessions:
            total_tests = len(s.test_results)
            passes = sum(1 for t in s.test_results if t.outcome == "passed")
            failures = sum(1 for t in s.test_results if t.outcome == "failed")
            reliability = passes / total_tests if total_tests else None
            avg_duration = sum(t.duration for t in s.test_results) / total_tests if total_tests else None
            metrics.append({
                "session_id": s.session_id,
                "total_tests": total_tests,
                "reliability": reliability,
                "avg_duration": avg_duration,
                "failures": failures,
            })
        return metrics
