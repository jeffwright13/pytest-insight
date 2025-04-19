from pytest_insight.core.models import TestSession

class MetaInsight:
    """Insights about the test process itself (maintenance burden, stability over time)."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def maintenance_burden(self):
        # Example: count number of unique tests and sessions as a proxy for maintenance
        unique_tests = set()
        for s in self.sessions:
            for t in s.test_results:
                unique_tests.add(t.nodeid)
        return {
            "unique_tests": len(unique_tests),
            "total_sessions": len(self.sessions),
            "tests_per_session": len(unique_tests) / len(self.sessions) if self.sessions else None
        }
