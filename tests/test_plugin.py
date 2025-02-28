from datetime import datetime, timedelta
from pathlib import Path
import json

from pytest_insight.models import TestOutcome, TestResult
from pytest_insight.plugin import group_tests_into_rerun_test_groups


def create_test_result(nodeid: str, outcome: TestOutcome, offset_seconds: int = 0) -> TestResult:
    """Helper to create test results for testing with ordered timestamps."""
    now = datetime.utcnow()
    return TestResult(nodeid=nodeid, outcome=outcome, start_time=now + timedelta(seconds=offset_seconds), duration=0.1)


def test_group_tests_into_rerun_test_groups_with_enum_outcomes():
    """Test rerun grouping with TestOutcome enum values."""
    # Create a set of test results with enum outcomes and ordered timestamps
    test_results = [
        create_test_result("test_a.py::test_1", TestOutcome.RERUN, 0),  # First run
        create_test_result("test_a.py::test_1", TestOutcome.RERUN, 1),  # Second run
        create_test_result("test_a.py::test_1", TestOutcome.PASSED, 2),  # Final pass
        create_test_result("test_b.py::test_2", TestOutcome.RERUN, 3),  # First run
        create_test_result("test_b.py::test_2", TestOutcome.FAILED, 4),  # Final fail
    ]

    rerun_groups = group_tests_into_rerun_test_groups(test_results)

    assert len(rerun_groups) == 2, "Should have two rerun groups"

    # Check first group
    group_a = next(g for g in rerun_groups if g.nodeid == "test_a.py::test_1")
    assert len(group_a.tests) == 3
    assert [t.outcome for t in group_a.tests] == [TestOutcome.RERUN, TestOutcome.RERUN, TestOutcome.PASSED]
    assert group_a.final_outcome == TestOutcome.PASSED

    # Check second group
    group_b = next(g for g in rerun_groups if g.nodeid == "test_b.py::test_2")
    assert len(group_b.tests) == 2
    assert [t.outcome for t in group_b.tests] == [TestOutcome.RERUN, TestOutcome.FAILED]
    assert group_b.final_outcome == TestOutcome.FAILED

    # Verify chronological ordering in both groups
    for group in [group_a, group_b]:
        for i in range(len(group.tests) - 1):
            assert group.tests[i].start_time < group.tests[i + 1].start_time


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


def test_insight_json_output_default_path(testdir):
    """Test JSON output is written to default path when no path specified."""
    # Create a temporary test
    testdir.makepyfile("""
        def test_example():
            assert True
    """)

    # Run pytest with insight enabled
    result = testdir.runpytest('--insight')
    result.assert_outcomes(passed=1)

    # Check default JSON file exists
    json_path = Path.home() / ".pytest_insight" / "test_sessions.json"
    assert json_path.exists()

    # Verify JSON content
    with open(json_path) as f:
        data = json.load(f)
        assert len(data['sessions']) > 0
        assert data['sessions'][-1]['test_results'][0]['outcome'] == 'passed'


def test_insight_json_output_custom_path(testdir):
    """Test JSON output is written to specified path."""
    testdir.makepyfile("""
        def test_example():
            assert True
    """)

    # Run pytest with custom JSON path
    custom_path = testdir.tmpdir / "custom_output.json"
    result = testdir.runpytest('--insight', f'--insight-json={custom_path}')
    result.assert_outcomes(passed=1)

    # Verify file exists at custom path
    assert custom_path.exists()

    # Verify JSON content
    with open(custom_path) as f:
        data = json.load(f)
        assert len(data['sessions']) > 0
        assert data['sessions'][-1]['test_results'][0]['outcome'] == 'passed'


def test_insight_json_output_disabled(testdir):
    """Test JSON output can be disabled."""
    testdir.makepyfile("""
        def test_example():
            assert True
    """)

    # Run pytest with JSON output disabled
    result = testdir.runpytest('--insight', '--insight-json=none')
    result.assert_outcomes(passed=1)

    # Verify default file was not created
    json_path = Path.home() / ".pytest_insight" / "test_sessions.json"
    assert not json_path.exists()


def test_insight_json_output_parent_dirs(testdir):
    """Test JSON output creates parent directories if needed."""
    testdir.makepyfile("""
        def test_example():
            assert True
    """)

    # Run pytest with nested path
    nested_path = testdir.tmpdir / "nested" / "dir" / "output.json"
    result = testdir.runpytest('--insight', f'--insight-json={nested_path}')
    result.assert_outcomes(passed=1)

    # Verify nested directories were created
    assert nested_path.exists()
