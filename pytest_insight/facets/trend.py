from pytest_insight.core.models import TestSession

class TrendInsight:
    """Detect and highlight emerging patterns."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def emerging_patterns(self):
        # For now, stub: could implement pattern mining, regression detection, etc.
        # Example: return patterns if test reliability drops sharply
        patterns = []
        for s in self.sessions:
            for t in s.test_results:
                if t.outcome == "failed" and t.duration > 30:  # Arbitrary example
                    patterns.append({
                        "nodeid": t.nodeid,
                        "session_id": s.session_id,
                        "issue": "Long failure duration"
                    })
        return patterns
