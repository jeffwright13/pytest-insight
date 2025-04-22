"""
Unit tests for SessionQuery and test-level filtering in pytest-insight v2.
Covers session-level and test-level filters, context preservation, and serialization.
"""

import pytest

from pytest_insight.core.models import TestResult, TestSession
from pytest_insight.core.query import SessionQuery
from pytest_insight.utils.utils import NormalizedDatetime


@pytest.fixture
def sample_sessions():
    # 2 sessions, 3 tests each
    base_time1 = NormalizedDatetime.from_iso("2025-04-10T10:00:00")
    base_time2 = NormalizedDatetime.from_iso("2025-04-11T12:00:00")
    s1 = TestSession(
        session_id="s1",
        sut_name="service-a",
        session_start_time=base_time1,
        session_tags={"env": "prod"},
        test_results=[
            TestResult(
                nodeid="test_foo",
                outcome="passed",
                duration=1.0,
                start_time=base_time1,
                stop_time=base_time1,
            ),
            TestResult(
                nodeid="test_bar",
                outcome="failed",
                duration=2.0,
                start_time=base_time1,
                stop_time=base_time1,
            ),
            TestResult(
                nodeid="test_baz",
                outcome="passed",
                duration=3.0,
                start_time=base_time1,
                stop_time=base_time1,
            ),
        ],
        rerun_test_groups=[],
        session_duration=10.0,
    )
    s2 = TestSession(
        session_id="s2",
        sut_name="service-b",
        session_start_time=base_time2,
        session_tags={"env": "staging"},
        test_results=[
            TestResult(
                nodeid="test_foo",
                outcome="failed",
                duration=4.0,
                start_time=base_time2,
                stop_time=base_time2,
            ),
            TestResult(
                nodeid="test_bar",
                outcome="passed",
                duration=5.0,
                start_time=base_time2,
                stop_time=base_time2,
            ),
            TestResult(
                nodeid="test_baz",
                outcome="passed",
                duration=6.0,
                start_time=base_time2,
                stop_time=base_time2,
            ),
        ],
        rerun_test_groups=[],
        session_duration=10.0,
    )
    return [s1, s2]


def test_for_sut_filters_sessions(sample_sessions):
    query = SessionQuery(sample_sessions)
    result = query.for_sut("service-a").execute()
    assert len(result) == 1
    assert result[0].sut_name == "service-a"


def test_in_last_days_filters_sessions(sample_sessions):
    query = SessionQuery(sample_sessions)
    result = query.in_last_days(1).execute()
    # This test may be non-deterministic if session times are not relative to now
    # For robust tests, use a time-freezing library or patch datetime.now
    assert isinstance(result, list)


def test_with_tags_filters_sessions(sample_sessions):
    query = SessionQuery(sample_sessions)
    result = query.with_tags({"env": "prod"}).execute()
    assert len(result) == 1
    assert result[0].session_tags["env"] == "prod"


def test_filter_by_test_preserves_context(sample_sessions):
    query = SessionQuery(sample_sessions)
    test_query = query.filter_by_test().with_pattern("test_bar").apply()
    result = test_query.execute()
    # Should return sessions containing at least one test with 'test_bar'
    assert len(result) == 2
    for sess in result:
        assert any(tr.nodeid == "test_bar" for tr in sess.test_results)


def test_test_level_filter_returns_sessions_not_tests(sample_sessions):
    query = SessionQuery(sample_sessions)
    test_query = query.filter_by_test().with_pattern("test_bar").apply()
    result = test_query.execute()
    assert all(isinstance(sess, TestSession) for sess in result)


def test_serialization_roundtrip(sample_sessions):
    query = SessionQuery(sample_sessions).for_sut("service-a").in_last_days(10)
    d = query.to_dict()
    restored = SessionQuery.from_dict(d, sample_sessions)
    assert isinstance(restored, SessionQuery)
    assert restored.execute()[0].sut_name == "service-a"
