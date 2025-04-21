import pytest
from pytest_insight.insight_api import InsightAPI
from pytest_insight.core.models import TestSession, TestResult
from pytest_insight.facets.summary import SummaryInsight
from pytest_insight.facets.session import SessionInsight
from pytest_insight.facets.test import TestInsight
from pytest_insight.facets.trend import TrendInsight
from pytest_insight.facets.comparative import ComparativeInsight
from pytest_insight.facets.predictive import PredictiveInsight
from pytest_insight.facets.meta import MetaInsight
from pytest_insight.facets.temporal import TemporalInsight
import datetime

@pytest.fixture
def sample_sessions():
    now = datetime.datetime(2025, 4, 20, 8, 0, 0)
    s1 = TestSession(
        sut_name="api",
        session_id="sess-1",
        session_start_time=now,
        session_duration=3.0,
        test_results=[
            TestResult(nodeid="test_a", outcome="passed", start_time=now, duration=1.0),
            TestResult(nodeid="test_b", outcome="failed", start_time=now, duration=2.0),
        ]
    )
    s2 = TestSession(
        sut_name="db",
        session_id="sess-2",
        session_start_time=now,
        session_duration=1.5,
        test_results=[
            TestResult(nodeid="test_c", outcome="passed", start_time=now, duration=1.5),
        ]
    )
    return [s1, s2]

def test_summary_returns_summary_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    summary = api.insight("summary")
    assert isinstance(summary, SummaryInsight)
    stats = summary.aggregate_stats()
    assert stats["total_sessions"] == 2
    assert stats["total_tests"] == 3

def test_session_returns_session_insight(sample_sessions):
    api = InsightAPI(sample_sessions)
    session_insight = api.session("sess-1")
    assert isinstance(session_insight, SessionInsight)
    metrics = session_insight.metrics()
    assert any(m.get("failed", 0) > 0 for m in metrics), "Expected at least one failed test in metrics."

def test_test_returns_test_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    test = api.test("test_a")
    assert isinstance(test, TestInsight)

def test_trend_returns_trend_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    trend = api.trend()
    assert isinstance(trend, TrendInsight)

def test_compare_returns_comparative_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    comp = api.compare()
    assert isinstance(comp, ComparativeInsight)

def test_predictive_returns_predictive_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    pred = api.predictive()
    assert isinstance(pred, PredictiveInsight)

def test_meta_returns_meta_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    meta = api.meta()
    assert isinstance(meta, MetaInsight)

def test_temporal_returns_temporal_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    temporal = api.temporal()
    assert isinstance(temporal, TemporalInsight)

def test_available_insights_lists_all(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    available = api.available_insights()
    assert set(available) == {"summary", "session", "sessions", "test", "tests", "trend", "compare", "predictive", "meta", "temporal"}

def test_universal_insight_method(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    assert isinstance(api.insight("summary"), SummaryInsight)
    assert isinstance(api.insight("session", session_id="sess-1"), SessionInsight)
    assert isinstance(api.insight("test", nodeid="test_a"), TestInsight)
    assert isinstance(api.insight("trend"), TrendInsight)
    assert isinstance(api.insight("compare"), ComparativeInsight)
    assert isinstance(api.insight("predictive"), PredictiveInsight)
    assert isinstance(api.insight("meta"), MetaInsight)
    assert isinstance(api.insight("temporal"), TemporalInsight)