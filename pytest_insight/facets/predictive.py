from pytest_insight.core.models import TestSession

class PredictiveInsight:
    """Machine learning-driven forecasts or anomaly detection."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def forecast(self):
        # Placeholder: forecast future reliability based on current trend
        # In a real implementation, use ML/time series analysis
        # Here, just return the average reliability as a 'forecast'
        total_tests = sum(len(s.test_results) for s in self.sessions)
        passes = sum(
            1 for s in self.sessions for t in s.test_results if t.outcome == "passed"
        )
        reliability = passes / total_tests if total_tests else None
        return {"future_reliability": reliability}
