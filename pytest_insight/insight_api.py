class InsightAPI:
    """
    Unified entry point for all test insights.
    Each method is a stub for a different insight type.
    Extend these with real logic as you build out the system.
    """
    def __init__(self, profile=None):
        self.profile = profile
        self._sessions = {}  # session_id -> TestSession
        self._last_session_id = None

    def register_session(self, session):
        self._sessions[session.session_id] = session
        self._last_session_id = session.session_id

    def session(self, session_id=None):
        # Return a stub that can access the session
        if session_id is None:
            session_id = self._last_session_id
        return SessionInsightStub(self._sessions.get(session_id))

    def tests(self):
        """Test-level insight stub (all tests)."""
        return TestInsightStub()

    def over_time(self, days=30):
        """Temporal insight stub (trends over time)."""
        return TemporalInsightStub(days)

    def compare(self, sut_a=None, sut_b=None):
        """Comparative insight stub (compare SUTs or versions)."""
        return ComparativeInsightStub(sut_a, sut_b)

    def trend(self):
        """Trend-focused insight stub (emerging patterns)."""
        return TrendInsightStub()

    def predictive(self):
        """Predictive insight stub (forecasting/anomaly detection)."""
        return PredictiveInsightStub()

    def meta(self):
        """Meta/process insight stub (maintenance, process health)."""
        return MetaInsightStub()


# --- Stub Classes for Each Insight Type ---


class SessionInsightStub:
    def __init__(self, session):
        self.session = session

    def insight(self, kind="summary"):
        if not self.session:
            return "[Session Insight: No session found]"
        if kind == "summary":
            return (
                f"Session {self.session.session_id}: "
                f"{len(self.session.test_results)} tests, "
                f"SUT={self.session.sut_name}"
            )
        return f"[Session Insight: {kind}] (session_id={self.session.session_id})"


class TestInsightStub:
    def filter(self, **kwargs):
        return self  # chaining stub

    def insight(self, kind="flakiness"):
        return f"[Test Insight: {kind}]"


class TemporalInsightStub:
    def __init__(self, days):
        self.days = days

    def insight(self, kind="trend"):
        return f"[Temporal Insight: {kind}] (days={self.days})"


class ComparativeInsightStub:
    def __init__(self, sut_a, sut_b):
        self.sut_a = sut_a
        self.sut_b = sut_b

    def insight(self, kind="regression"):
        return f"[Comparative Insight: {kind}] (A={self.sut_a}, B={self.sut_b})"


class TrendInsightStub:
    def insight(self, kind="trend"):
        return f"[Trend Insight: {kind}]"


class PredictiveInsightStub:
    def insight(self, kind="predictive_failure"):
        return f"[Predictive Insight: {kind}]"


class MetaInsightStub:
    def insight(self, kind="maintenance_burden"):
        return f"[Meta Insight: {kind}]"
