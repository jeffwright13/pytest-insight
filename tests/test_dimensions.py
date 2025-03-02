"""Tests for comparison dimensions."""

from datetime import datetime, timedelta
from typing import List

import pytest
from faker import Faker
from pytest_insight.dimensional_comparator import DimensionalComparator
from pytest_insight.dimensions import (
    DurationDimension,
    ModuleDimension,
    OutcomeDimension,
    SUTDimension,
    TimeDimension,
)
from pytest_insight.models import TestOutcome, TestResult, TestSession


@pytest.fixture
def test_sessions():
    """Create test sessions across different SUTs and times."""
    base_time = datetime(2025, 1, 1, 12, 0)

    def make_test_result(nodeid: str, outcome: TestOutcome, duration: float) -> TestResult:
        start_time = base_time
        return TestResult(
            nodeid=nodeid,
            outcome=outcome,
            start_time=start_time,
            stop_time=start_time + timedelta(seconds=duration),
            duration=duration,
        )

    sessions = []
    for i in range(2):  # 2 SUTs
        for j in range(3):  # 3 sessions each, 1 hour apart
            session = TestSession(
                session_id=f"sut{i}-{j}",
                sut_name=f"sut{i}",
                session_start_time=base_time + timedelta(hours=j),
                session_stop_time=base_time + timedelta(hours=j, minutes=30),
                test_results=[
                    make_test_result("test_1", TestOutcome.PASSED, 1.0),
                    make_test_result("test_2", TestOutcome.FAILED if i == 0 else TestOutcome.PASSED, 2.0),
                    make_test_result(f"test_sut{i}_only", TestOutcome.PASSED, 1.5),
                ],
                session_tags={},
            )
            sessions.append(session)
    return sessions


def test_sut_dimension_groups_by_sut(test_sessions):
    """Test that SUTDimension correctly groups sessions by SUT."""
    dimension = SUTDimension()
    grouped = dimension.group_sessions(test_sessions)

    assert set(grouped.keys()) == {"sut0", "sut1"}
    assert len(grouped["sut0"]) == 3
    assert len(grouped["sut1"]) == 3
    assert all(s.sut_name == "sut0" for s in grouped["sut0"])
    assert all(s.sut_name == "sut1" for s in grouped["sut1"])


def test_time_dimension_groups_by_window(test_sessions):
    """Test that TimeDimension correctly groups sessions by time windows."""
    dimension = TimeDimension(window=timedelta(hours=2))
    grouped = dimension.group_sessions(test_sessions)

    # Should create 2 windows of 2 hours each
    assert len(grouped) == 2

    # First window should have 4 sessions (2 from each SUT)
    first_window = next(iter(grouped.values()))
    assert len(first_window) == 4

    # Second window should have 2 sessions (1 from each SUT)
    second_window = list(grouped.values())[1]
    assert len(second_window) == 2


def test_time_dimension_empty_sessions():
    """Test that TimeDimension handles empty session list."""
    dimension = TimeDimension(window=timedelta(hours=1))
    grouped = dimension.group_sessions([])
    assert grouped == {}


def test_dimensional_comparator_sut(test_sessions):
    """Test comparing sessions between SUTs."""
    comparator = DimensionalComparator(SUTDimension())
    result = comparator.compare(test_sessions, "sut0", "sut1")

    # Check basic stats
    assert result["base"]["total_tests"] == 3
    assert result["target"]["total_tests"] == 3

    # Check differences
    diffs = result["differences"]
    assert "test_sut0_only" in diffs["removed_tests"]
    assert "test_sut1_only" in diffs["new_tests"]

    # Check status changes
    status_changes = {c["nodeid"]: c for c in diffs["status_changes"]}
    assert "test_2" in status_changes
    assert status_changes["test_2"]["base_status"] == "FAILED"
    assert status_changes["test_2"]["target_status"] == "PASSED"


"""Tests for dimension classes."""

import re

import pytest
from pytest_insight.filterable import DimensionFilter

fake = Faker()


def create_test_session(
    sut_name: str,
    test_results: List[TestResult],
    start_time: datetime = None,
    session_duration: float = None,
    tags: dict = None,
) -> TestSession:
    """Create a test session with the given parameters."""
    if start_time is None:
        start_time = datetime.now()
    if session_duration is None:
        session_duration = sum(r.duration for r in test_results)
    return TestSession(
        sut_name=sut_name,
        session_id=f"{sut_name}-{start_time.strftime('%Y%m%d-%H%M%S')}-{fake.hexify('^'*8)}",
        session_start_time=start_time,
        session_stop_time=start_time + timedelta(seconds=session_duration),
        session_duration=session_duration,
        test_results=test_results,
        rerun_test_groups=[],
        session_tags=tags or {"platform": "darwin", "python_version": "3.9.16", "environment": "test"},
    )


@pytest.fixture
def test_sessions():
    """Create test sessions for testing."""
    now = datetime.now()

    # Create sessions for SUT dimension tests
    sut0_session = create_test_session(
        "sut0",
        [
            TestResult(
                nodeid="tests/test_foo.py::test_bar",
                outcome=TestOutcome.PASSED,
                start_time=now,
                stop_time=now + timedelta(seconds=0.5),
                duration=0.5,
                caplog="",
                capstderr="",
                capstdout="",
                longreprtext="",
                has_warning=False,
            ),
            TestResult(
                nodeid="tests/test_foo.py::test_baz",
                outcome=TestOutcome.PASSED,
                start_time=now + timedelta(seconds=1),
                stop_time=now + timedelta(seconds=2),
                duration=1.0,
                caplog="",
                capstderr="",
                capstdout="",
                longreprtext="",
                has_warning=False,
            ),
        ],
        now,
        2.5,  # Total duration
        tags={"environment": "dev", "feature": "auth"},
    )

    sut1_session = create_test_session(
        "sut1",
        [
            TestResult(
                nodeid="tests/test_foo.py::test_bar",
                outcome=TestOutcome.FAILED,
                start_time=now,
                stop_time=now + timedelta(seconds=0.5),
                duration=0.5,
                caplog="",
                capstderr="",
                capstdout="",
                longreprtext="",
                has_warning=False,
            ),
            TestResult(
                nodeid="tests/test_foo.py::test_baz",
                outcome=TestOutcome.FAILED,
                start_time=now + timedelta(seconds=1),
                stop_time=now + timedelta(seconds=3),
                duration=2.0,
                caplog="",
                capstderr="",
                capstdout="",
                longreprtext="",
                has_warning=False,
            ),
        ],
        now,
        2.5,  # Total duration
        tags={"environment": "prod", "feature": "auth"},
    )

    # Create sessions for outcome dimension tests
    passed_session = create_test_session(
        "passed_sut",
        [
            TestResult(
                nodeid="tests/test_pass.py::test_1",
                outcome=TestOutcome.PASSED,
                start_time=now,
                stop_time=now + timedelta(seconds=0.5),
                duration=0.5,
                caplog="",
                capstderr="",
                capstdout="",
                longreprtext="",
                has_warning=False,
            ),
        ],
        now,
        0.5,  # Total duration
        tags={"environment": "stage", "feature": "login"},
    )

    failed_session = create_test_session(
        "failed_sut",
        [
            TestResult(
                nodeid="tests/test_fail.py::test_1",
                outcome=TestOutcome.FAILED,
                start_time=now + timedelta(hours=3),  # Create in a different time window
                stop_time=now + timedelta(hours=3, seconds=0.5),
                duration=0.5,
                caplog="",
                capstderr="",
                capstdout="",
                longreprtext="",
                has_warning=False,
            ),
        ],
        now + timedelta(hours=3),  # Create in a different time window
        0.5,  # Total duration
        tags={"environment": "prod", "feature": "login"},
    )

    return [sut0_session, sut1_session, passed_session, failed_session]


def test_sut_dimension_groups_by_sut(test_sessions):
    """Test that SUTDimension correctly groups sessions by SUT."""
    dimension = SUTDimension()
    grouped = dimension.group_sessions(test_sessions)

    assert set(grouped.keys()) == {"sut0", "sut1", "passed_sut", "failed_sut"}
    assert len(grouped["sut0"]) == 1
    assert len(grouped["sut1"]) == 1
    assert grouped["sut0"][0].sut_name == "sut0"
    assert grouped["sut1"][0].sut_name == "sut1"


def test_time_dimension_groups_by_window(test_sessions):
    """Test that TimeDimension correctly groups sessions by time windows."""
    dimension = TimeDimension(window=timedelta(hours=2))
    grouped = dimension.group_sessions(test_sessions)

    # Should create 2 windows of 2 hours each
    assert len(grouped) == 2

    # First window should have 3 sessions
    first_window = next(iter(grouped.values()))
    assert len(first_window) == 3


def test_outcome_dimension_groups_by_outcome(test_sessions):
    """Test that OutcomeDimension groups sessions by most common outcome."""
    dim = OutcomeDimension()
    groups = dim.group_sessions(test_sessions)

    assert set(groups.keys()) == {"PASSED", "FAILED"}
    assert len(groups["PASSED"]) == 2  # sut0 and passed_sut sessions
    assert len(groups["FAILED"]) == 2  # sut1 (more fails than passes) and failed_sut


def test_duration_dimension_groups_by_duration(test_sessions):
    """Test that DurationDimension groups sessions by duration ranges."""
    dim = DurationDimension()
    groups = dim.group_sessions(test_sessions)

    assert set(groups.keys()) == {"FAST", "MEDIUM"}
    assert len(groups["FAST"]) == 2  # passed_sut and failed_sut (1.0s)
    assert len(groups["MEDIUM"]) == 2  # sut0 and sut1 (2.5s)


def test_module_dimension_groups_by_module(test_sessions):
    """Test that ModuleDimension groups sessions by most common module."""
    dim = ModuleDimension()
    groups = dim.group_sessions(test_sessions)

    assert set(groups.keys()) == {"tests/test_foo.py", "tests/test_pass.py", "tests/test_fail.py"}
    assert len(groups["tests/test_foo.py"]) == 2  # sut0 and sut1
    assert len(groups["tests/test_pass.py"]) == 1  # passed_sut
    assert len(groups["tests/test_fail.py"]) == 1  # failed_sut


def test_filterable_dimension_with_pattern(test_sessions):
    """Test filtering by nodeid pattern."""
    dim = ModuleDimension(filters=[DimensionFilter(pattern=re.compile(r"test_foo"))])
    groups = dim.group_sessions(test_sessions)

    # Should only include sessions with test_foo.py
    assert set(groups.keys()) == {"tests/test_foo.py"}
    assert len(groups["tests/test_foo.py"]) == 2


def test_filterable_dimension_with_tags(test_sessions):
    """Test filtering by tags."""
    dim = OutcomeDimension(filters=[DimensionFilter(tags={"environment": "prod"})])
    groups = dim.group_sessions(test_sessions)

    # Should only include prod environment sessions
    assert len(groups) == 1  # sut1 and failed_sut are both in FAILED group
    for sessions in groups.values():
        for session in sessions:
            assert session.session_tags["environment"] == "prod"


def test_filterable_dimension_with_predicate(test_sessions):
    """Test filtering with custom predicate."""
    dim = DurationDimension(filters=[DimensionFilter(predicate=lambda s: len(s.test_results) > 1)])
    groups = dim.group_sessions(test_sessions)

    # Should only include sessions with multiple tests
    assert len(groups) == 1  # Only sut1 has multiple tests
    for sessions in groups.values():
        for session in sessions:
            assert len(session.test_results) > 1


def test_filterable_dimension_with_multiple_filters(test_sessions):
    """Test combining multiple filters."""
    dim = ModuleDimension(
        filters=[
            DimensionFilter(pattern=re.compile(r"test_.*\.py")),
            DimensionFilter(tags={"environment": "prod"}),
            DimensionFilter(predicate=lambda s: s.session_duration >= 1.0),
        ]
    )
    groups = dim.group_sessions(test_sessions)

    # Should only include prod sessions with long duration
    for sessions in groups.values():
        for session in sessions:
            assert session.session_tags["environment"] == "prod"
            assert session.session_duration >= 1.0


def test_dimensional_comparator_outcome(test_sessions):
    """Test DimensionalComparator with OutcomeDimension."""
    dim = OutcomeDimension()
    comparator = DimensionalComparator(dim)
    results = comparator.compare(test_sessions, "PASSED", "FAILED")

    assert "error" not in results
    assert results["base"]["total_tests"] == 3  # sut0 (2) and passed_sut (1) sessions
    assert results["target"]["total_tests"] == 3  # sut1 (2) and failed_sut (1) sessions
    assert results["base"]["passed"] == 3
    assert results["target"]["failed"] == 3


def test_dimensional_comparator_duration(test_sessions):
    """Test DimensionalComparator with DurationDimension."""
    dim = DurationDimension()
    comparator = DimensionalComparator(dim)
    results = comparator.compare(test_sessions, "FAST", "MEDIUM")

    assert "error" not in results
    assert results["base"]["total_tests"] == 2  # passed_sut and failed_sut
    assert results["target"]["total_tests"] == 2  # sut0 and sut1 tests
    assert abs(results["base"]["duration"] - 1.0) < 0.01  # 0.5s + 0.5s
    assert abs(results["target"]["duration"] - 1.5) < 0.01  # session_duration for sut0 and sut1


def test_dimensional_comparator_module(test_sessions):
    """Test DimensionalComparator with ModuleDimension."""
    dim = ModuleDimension()
    comparator = DimensionalComparator(dim)
    results = comparator.compare(test_sessions, "tests/test_foo.py", "tests/test_pass.py")

    assert "error" not in results
    assert results["base"]["total_tests"] == 2  # sut0 and sut1 tests
    assert results["target"]["total_tests"] == 1  # passed_sut test
    assert len(results["differences"]["new_tests"]) == 1  # test_pass.py::test_1
    assert len(results["differences"]["removed_tests"]) == 2  # test_foo.py::test_bar and test_baz


def test_dimensional_comparator_sut(test_sessions):
    """Test comparing sessions between SUTs."""
    comparator = DimensionalComparator(SUTDimension())
    result = comparator.compare(test_sessions, "sut0", "sut1")

    # Check basic stats
    assert result["base"]["total_tests"] == 2  # sut0 has 2 tests
    assert result["target"]["total_tests"] == 2  # sut1 has 2 tests

    # Check differences
    diffs = result["differences"]
    assert len(diffs["removed_tests"]) == 0  # No unique tests in sut0
    assert len(diffs["new_tests"]) == 0  # No unique tests in sut1

    # Check status changes
    status_changes = {c["nodeid"]: c for c in diffs["status_changes"]}
    assert "tests/test_foo.py::test_bar" in status_changes
    assert status_changes["tests/test_foo.py::test_bar"]["base_status"] == "PASSED"
    assert status_changes["tests/test_foo.py::test_bar"]["target_status"] == "FAILED"
    assert "tests/test_foo.py::test_baz" in status_changes
    assert status_changes["tests/test_foo.py::test_baz"]["base_status"] == "PASSED"
    assert status_changes["tests/test_foo.py::test_baz"]["target_status"] == "FAILED"
