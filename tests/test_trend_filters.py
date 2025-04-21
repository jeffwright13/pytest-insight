"""
Unit tests for TrendInsight filtering (by SUT, by test nodeid).
Uses pytest and pytest-mock. Covers edge cases and verifies correct filtering.
"""
import pytest
from types import SimpleNamespace
from pytest_insight.facets.trend import TrendInsight

def make_session(sut_name, nodeids):
    """Helper to create a fake TestSession-like object."""
    return SimpleNamespace(
        sut_name=sut_name,
        test_results=[SimpleNamespace(nodeid=n, outcome="passed", duration=1.0) for n in nodeids],
        session_start_time=None,
        session_duration=10.0,
    )

def test_filter_by_sut():
    sessions = [
        make_session("api-service", ["test_a", "test_b"]),
        make_session("web", ["test_c"]),
        make_session("api-service", ["test_d"]),
    ]
    trend = TrendInsight(sessions)
    filtered = trend.filter(sut="api-service")
    assert all(s.sut_name == "api-service" for s in filtered.sessions)
    assert len(filtered.sessions) == 2

def test_filter_by_nodeid():
    sessions = [
        make_session("api-service", ["test_a", "test_b"]),
        make_session("web", ["test_c", "test_b"]),
        make_session("api-service", ["test_d"]),
    ]
    trend = TrendInsight(sessions)
    filtered = trend.filter(nodeid="test_b")
    # Only sessions containing test_b
    assert all(any(t.nodeid == "test_b" for t in s.test_results) for s in filtered.sessions)
    assert len(filtered.sessions) == 2

def test_filter_by_sut_and_nodeid():
    sessions = [
        make_session("api-service", ["test_a", "test_b"]),
        make_session("web", ["test_c", "test_b"]),
        make_session("api-service", ["test_d"]),
    ]
    trend = TrendInsight(sessions)
    filtered = trend.filter(sut="api-service", nodeid="test_b")
    # Only sessions with sut_name==api-service and test_b present
    assert len(filtered.sessions) == 1
    assert filtered.sessions[0].sut_name == "api-service"
    assert any(t.nodeid == "test_b" for t in filtered.sessions[0].test_results)

def test_filter_no_match():
    sessions = [
        make_session("api-service", ["test_a"]),
        make_session("web", ["test_c"]),
    ]
    trend = TrendInsight(sessions)
    filtered = trend.filter(sut="nonexistent")
    assert filtered.sessions == []
    filtered2 = trend.filter(nodeid="does_not_exist")
    assert filtered2.sessions == []

def test_trend_methods_on_filtered():
    sessions = [
        make_session("api-service", ["test_a", "test_b"]),
        make_session("api-service", ["test_b"]),
    ]
    trend = TrendInsight(sessions)
    filtered = trend.filter(nodeid="test_b")
    # Should not error
    assert isinstance(filtered.duration_trends(), dict)
    assert isinstance(filtered.failure_trends(), dict)
    assert isinstance(filtered.emerging_patterns(), list)
    assert isinstance(filtered.as_dict(), dict)
    assert isinstance(filtered.unified_insight(), str)
