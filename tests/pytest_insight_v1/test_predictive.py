"""Unit tests for PredictiveAnalytics in pytest_insight.core.predictive."""

from datetime import datetime, timedelta

from pytest_insight.core.analysis import Analysis
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.predictive import PredictiveAnalytics


def make_sessions(num_sessions=6, fail_every=2):
    """Create a list of TestSession objects for predictive tests."""
    base_time = datetime.now() - timedelta(days=num_sessions)
    sessions = []
    for i in range(num_sessions):
        test_results = [
            TestResult(
                nodeid="test_predict.py::test_always_pass",
                outcome=TestOutcome.PASSED,
                start_time=base_time + timedelta(days=i),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_predict.py::test_unreliable",
                outcome=TestOutcome.FAILED if i % 2 == 0 else TestOutcome.PASSED,
                start_time=base_time + timedelta(days=i, seconds=10),
                duration=1.5,
            ),
            TestResult(
                nodeid="test_predict.py::test_always_fail",
                outcome=TestOutcome.FAILED,
                start_time=base_time + timedelta(days=i, seconds=20),
                duration=2.0,
            ),
        ]
        sessions.append(
            TestSession(
                sut_name="sut-A",
                session_id=f"sess-{i}",
                session_start_time=base_time + timedelta(days=i),
                session_stop_time=base_time + timedelta(days=i, seconds=60),
                session_duration=60.0,
                test_results=test_results,
                rerun_test_groups=[],
                session_tags={},
            )
        )
    return sessions


def test_failure_prediction_basic():
    sessions = make_sessions()
    analysis = Analysis(sessions=sessions)
    pa = PredictiveAnalytics(analysis)
    result = pa.failure_prediction(days_ahead=3)
    assert "predictions" in result
    assert "confidence" in result
    assert "high_risk_tests" in result
    assert isinstance(result["predictions"], dict)
    assert isinstance(result["high_risk_tests"], list)
    # Should predict high risk for always failing test
    nodeids = [t["nodeid"] for t in result["high_risk_tests"]]
    assert "test_predict.py::test_always_fail" in nodeids


def test_failure_prediction_insufficient_data():
    sessions = make_sessions(num_sessions=3)  # Less than 5
    analysis = Analysis(sessions=sessions)
    pa = PredictiveAnalytics(analysis)
    result = pa.failure_prediction()
    assert result["confidence"] == 0
    assert "error" in result


def test_anomaly_detection():
    sessions = make_sessions()
    analysis = Analysis(sessions=sessions)
    pa = PredictiveAnalytics(analysis)
    result = pa.anomaly_detection()
    assert "anomalies" in result
    assert "anomaly_scores" in result
    assert "detection_confidence" in result
    assert isinstance(result["anomalies"], list)
    assert isinstance(result["anomaly_scores"], dict)
    assert 0 <= result["detection_confidence"] <= 1


def test_stability_forecast():
    sessions = make_sessions()
    analysis = Analysis(sessions=sessions)
    pa = PredictiveAnalytics(analysis)
    result = pa.stability_forecast()
    assert "current_stability" in result
    assert "forecasted_stability" in result
    assert "trend_direction" in result
    assert "contributing_factors" in result
    assert result["trend_direction"] in ["improving", "declining", "stable", "unknown"]


def test_stability_forecast_insufficient_data():
    sessions = make_sessions(num_sessions=2)
    analysis = Analysis(sessions=sessions)
    pa = PredictiveAnalytics(analysis)
    result = pa.stability_forecast()
    assert result["forecasted_stability"] is None
    assert result["trend_direction"] == "unknown"
    assert "error" in result
