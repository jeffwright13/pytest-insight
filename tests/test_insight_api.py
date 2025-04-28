import datetime

import pytest
from pytest_insight.core.models import TestResult, TestSession
from pytest_insight.facets.comparative import ComparativeInsight
from pytest_insight.facets.meta import MetaInsight
from pytest_insight.facets.predictive import PredictiveInsight
from pytest_insight.facets.session import SessionInsight
from pytest_insight.facets.summary import SummaryInsight
from pytest_insight.facets.temporal import TemporalInsight
from pytest_insight.facets.test import TestInsight
from pytest_insight.facets.trend import TrendInsight
from pytest_insight.insight_api import InsightAPI


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
        ],
    )
    s2 = TestSession(
        sut_name="db",
        session_id="sess-2",
        session_start_time=now,
        session_duration=1.5,
        test_results=[
            TestResult(nodeid="test_c", outcome="passed", start_time=now, duration=1.5),
        ],
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
    test = api.tests()
    assert isinstance(test, TestInsight)


def test_trend_returns_trend_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    trend = api.trend()
    assert isinstance(trend, TrendInsight)


def test_compare_returns_comparative_insight(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    comp = api.compare()
    assert isinstance(comp, (ComparativeInsight, str))


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
    # Match canonical API output (as exposed by _insight_* methods)
    assert set(available) == {
        "summary",
        "session",
        "trend",
        "compare",
        "predictive",
        "meta",
        "temporal",
        "test",
        "health",
        "reliability",
    }


def test_universal_insight_method(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    assert isinstance(api.insight("summary"), SummaryInsight)
    assert isinstance(api.insight("session", session_id="sess-1"), SessionInsight)
    tests_obj = api.tests()
    assert tests_obj is not None
    trend = api.insight("trend")
    assert isinstance(trend, dict)
    assert "failure_trends" in trend
    compare = api.insight("compare")
    # Accept dict or string table for compare
    assert isinstance(compare, (dict, str))
    predictive = api.insight("predictive")
    assert isinstance(predictive, (dict, str))
    meta = api.insight("meta")
    assert isinstance(meta, (dict, str))
    temporal = api.insight("temporal")
    assert isinstance(temporal, (dict, str))


def test_summary_dict_returns_expected_keys(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    summary = api.summary_dict()
    assert isinstance(summary, dict)
    for key in ["total_sessions", "total_tests", "pass_rate", "fail_rate", "reliability", "outcome_counts"]:
        assert key in summary


def test_predictive_dict_returns_expected_keys(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    predictive = api.predictive_dict()
    assert isinstance(predictive, dict)
    for key in ["future_reliability", "trend", "warning"]:
        assert key in predictive


def test_meta_dict_returns_expected_keys(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    meta = api.meta_dict()
    assert isinstance(meta, dict)
    for key in ["unique_tests", "total_sessions", "tests_per_session"]:
        assert key in meta


def test_trend_dict_returns_expected_keys(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    trend = api.trend_dict()
    assert isinstance(trend, dict)
    assert "failure_trends" in trend
    assert "failures_by_day" in trend["failure_trends"]


def test_comparative_dict_returns_dict(sample_sessions):
    api = InsightAPI(sessions=sample_sessions)
    comparative = api.comparative_dict()
    assert isinstance(comparative, dict)


def test_api_profile_creation(tmp_path):
    """Test that InsightAPI can load sessions from a newly created profile (when no profiles.json exists)."""
    from pytest_insight.core.storage import ProfileManager

    profiles_path = tmp_path / "profiles.json"
    pm = ProfileManager(profiles_path=profiles_path)
    assert not profiles_path.exists(), "profiles.json should not exist initially"
    pm.create_profile("api_profile", "json")
    assert profiles_path.exists(), "profiles.json should be created after API profile creation"
    # Now use InsightAPI to load from this profile
    from pytest_insight.insight_api import InsightAPI

    api = InsightAPI(profile="api_profile")
    # Should load with zero sessions, but not error
    assert hasattr(api, "_sessions")
    assert isinstance(api._sessions, list)


def test_api_explicit_create_profile(tmp_path):
    """Test that InsightAPI.create_profile explicitly creates a new profile and returns its metadata."""
    import uuid

    from pytest_insight.insight_api import InsightAPI

    profiles_path = tmp_path / "profiles.json"
    # Patch environment to use our test profiles path
    import os

    os.environ["PYTEST_INSIGHT_PROFILES_PATH"] = str(profiles_path)
    # Reset the profile manager singleton to ensure isolation
    import pytest_insight.core.storage as storage_mod

    storage_mod._profile_manager = None
    api = InsightAPI()
    profile_name = f"explicit_profile_{uuid.uuid4().hex}"
    # Create profile via API
    meta = api.create_profile(profile_name, storage_type="json")
    assert meta["name"] == profile_name
    assert meta["storage_type"] == "json"
    # Should now exist in manager
    from pytest_insight.core.storage import get_profile_manager

    pm = get_profile_manager(force_reload=True)
    assert profile_name in pm.profiles
    # Creating the same profile again should raise ValueError
    with pytest.raises(ValueError):
        api.create_profile(profile_name, storage_type="json")
    # Clean up env
    del os.environ["PYTEST_INSIGHT_PROFILES_PATH"]
    storage_mod._profile_manager = None
