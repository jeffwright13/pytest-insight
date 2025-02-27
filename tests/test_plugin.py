from datetime import datetime

from pytest_insight.models import TestOutcome, TestResult
from pytest_insight.plugin import group_rerun_tests


def create_test_result(nodeid: str, outcome: TestOutcome) -> TestResult:
    """Helper to create test results for testing."""
    return TestResult(nodeid=nodeid, outcome=outcome, start_time=datetime.utcnow(), duration=0.1)


def test_group_rerun_tests_with_enum_outcomes():
    """Test rerun grouping with TestOutcome enum values."""
    # Create a set of test results with enum outcomes
    test_results = [
        create_test_result("test_a.py::test_1", TestOutcome.RERUN),
        create_test_result("test_a.py::test_1", TestOutcome.RERUN),
        create_test_result("test_a.py::test_1", TestOutcome.PASSED),
        create_test_result("test_b.py::test_2", TestOutcome.RERUN),
        create_test_result("test_b.py::test_2", TestOutcome.FAILED),
    ]

    rerun_groups = group_rerun_tests(test_results)

    assert len(rerun_groups) == 2, "Should have two rerun groups"

    # Check first group
    group_a = next(g for g in rerun_groups if g.nodeid == "test_a.py::test_1")
    assert len(group_a.reruns) == 2, "Should have two reruns"
    assert group_a.final_outcome == "passed"

    # Check second group
    group_b = next(g for g in rerun_groups if g.nodeid == "test_b.py::test_2")
    assert len(group_b.reruns) == 1, "Should have one rerun"
    assert group_b.final_outcome == "failed"


def test_test_outcome_enum_conversion():
    """Test converting between strings and TestOutcome enum values."""
    # Test string to enum conversion
    assert TestOutcome.from_str("PASSED") == TestOutcome.PASSED
    assert TestOutcome.from_str("FAILED") == TestOutcome.FAILED
    assert TestOutcome.from_str("SKIPPED") == TestOutcome.SKIPPED
    assert TestOutcome.from_str("XFAILED") == TestOutcome.XFAILED
    assert TestOutcome.from_str("XPASSED") == TestOutcome.XPASSED
    assert TestOutcome.from_str("RERUN") == TestOutcome.RERUN
    assert TestOutcome.from_str("ERROR") == TestOutcome.ERROR

    # Test enum to string conversion
    result = create_test_result("test.py::test_1", TestOutcome.PASSED)
    assert result.outcome.to_str() == "passed"
    result = create_test_result("test.py::test_2", TestOutcome.FAILED)
    assert result.outcome.to_str() == "failed"
    result = create_test_result("test.py::test_3", TestOutcome.SKIPPED)
    assert result.outcome.to_str() == "skipped"
    result = create_test_result("test.py::test_4", TestOutcome.XFAILED)
    assert result.outcome.to_str() == "xfailed"
    result = create_test_result("test.py::test_5", TestOutcome.XPASSED)
    assert result.outcome.to_str() == "xpassed"
    result = create_test_result("test.py::test_6", TestOutcome.RERUN)
    assert result.outcome.to_str() == "rerun"
    result = create_test_result("test.py::test_7", TestOutcome.ERROR)
    assert result.outcome.to_str() == "error"

    # Test sorting behavior
    outcomes = [TestOutcome.FAILED, TestOutcome.PASSED, TestOutcome.RERUN]
    outcome_strs = [o.to_str() for o in outcomes]
    assert sorted(outcome_strs) == ["failed", "passed", "rerun"]
