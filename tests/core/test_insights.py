"""
Unit tests for Insights and SessionInsights orchestrator in pytest-insight.
Covers summary reports, health reports, and session metrics.
"""
import pytest
from datetime import datetime
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.insights import Insights, SessionInsights

def make_session(test_results, session_id="sess1"):
    t0 = datetime(2025, 4, 21, 10, 0, 0)
    t1 = t0
    return TestSession(
        sut_name="service-a",
        session_id=session_id,
        session_start_time=t0,
        session_stop_time=t1,
        test_results=test_results,
    )

def test_sessioninsights_metrics_and_health():
    tests = [TestResult(nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=datetime(2025,4,21,10,0,0), duration=1.0),
             TestResult(nodeid="test_bar", outcome=TestOutcome.FAILED, start_time=datetime(2025,4,21,10,0,0), duration=1.0)]
    sessions = [make_session(tests)]
    insights = SessionInsights(sessions)
    metrics = insights.session_metrics()
    assert metrics["total_sessions"] == 1
    assert metrics["total_tests"] == 2
    assert isinstance(metrics["passed"], int)
    assert isinstance(metrics["failed"], int)
    health = insights.health_report()
    assert "reliability" in health
    assert health["total_sessions"] == 1

def test_insights_summary_report():
    tests = [TestResult(nodeid="test_foo", outcome=TestOutcome.PASSED, start_time=datetime(2025,4,21,10,0,0), duration=1.0)]
    sessions = [make_session(tests)]
    insights = Insights(sessions)
    summary = insights.summary_report()
    assert "health" in summary
    assert "session_insights" in summary
    assert isinstance(summary["health"], dict)
    assert isinstance(summary["session_insights"], dict)

def test_empty_sessions():
    insights = Insights([])
    summary = insights.summary_report()
    assert summary["health"]["reliability"] == 0.0
    assert summary["health"]["total_sessions"] == 0
    assert summary["session_insights"]["total_sessions"] == 0
