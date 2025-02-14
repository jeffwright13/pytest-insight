from datetime import datetime, timedelta

from pytest_insight.models import RerunTestGroup, TestHistory, TestResult, TestSession, OutputFieldType, OutputFields, OutputField


def test_random_test_results(random_test_result):
    assert random_test_result.nodeid != ""
    assert random_test_result.nodeid == str(random_test_result.nodeid)
    assert random_test_result.outcome in ["PASSED", "FAILED", "SKIPPED", "XFAILED", "XPASSED", "RERUN", "ERROR"]
    assert isinstance(random_test_result.start_time, datetime)
    assert isinstance(random_test_result.duration, float)
    assert random_test_result.has_warning in [True, False]
    assert random_test_result.caplog != ""
    if random_test_result.outcome in ["FAILED", "ERROR"]:
        assert random_test_result.capstderr != ""
        assert random_test_result.longreprtext != ""
    else:
        assert random_test_result.capstderr == ""
        assert random_test_result.longreprtext == ""
    assert random_test_result.capstdout != ""


def test_random_test_session(random_test_session):
    """Test random test session properties and methods."""

    # Test basic session properties
    assert isinstance(random_test_session.sut_name, str) and random_test_session.sut_name.startswith("SUT-")
    assert isinstance(random_test_session.session_id, str) and random_test_session.session_id.startswith("session-")

    # Test timestamp properties
    assert isinstance(random_test_session.session_start_time, datetime)
    assert isinstance(random_test_session.session_stop_time, datetime)
    assert isinstance(random_test_session.session_duration, timedelta)
    assert random_test_session.session_stop_time > random_test_session.session_start_time

    # Test collections have expected content
    assert len(random_test_session.test_results) >= 2, "Should have multiple test results"
    assert len(random_test_session.rerun_test_groups) >= 1, "Should have at least one rerun group"

    # Test output fields and tags
    for field_name in random_test_session.output_fields.fields:
        assert random_test_session.output_fields.get(field_name) is not None
    assert random_test_session.session_tags, "Should have session tags"

    # Test result categorization methods
    test_categories = [
        random_test_session.all_passes(),
        random_test_session.all_failures(),
        random_test_session.all_skipped(),
        random_test_session.all_xfailed(),
        random_test_session.all_xpassed(),
        random_test_session.all_reruns(),
        random_test_session.with_error(),
        random_test_session.with_warning()
    ]
    assert any(test_categories), "Should have results in at least one category"

    # Test result lookup functionality
    nonexistent_nodeid = "nonexistent/test_file.py::test_fake"
    assert random_test_session.find_test_result_by_nodeid(nonexistent_nodeid) is None

    # Test we can find an existing result
    first_result = random_test_session.test_results[0]
    found_result = random_test_session.find_test_result_by_nodeid(str(first_result.nodeid))
    assert found_result is not None and found_result is first_result


def test_test_session():
    start_time = datetime.utcnow()
    session = TestSession("SUT-1", "session-123", start_time, start_time, timedelta(seconds=10))

    session.test_counts = {
        "passed": 5,
        "failed": 2,
        "skipped": 1,
        "xfailed": 1,
        "xpassed": 0,
        "warnings": 1,
        "errors": 0,
        "reruns": 0,
    }

    assert session.sut_name == "SUT-1"
    assert session.session_id == "session-123"
    assert session.session_start_time == start_time
    assert session.session_duration == timedelta(seconds=10)
    assert session.all_passes() == 5
    assert session.all_failures() == 2
    assert session.all_skipped() == 1
    assert session.all_xfailed() == 1
    assert session.all_xpassed() == 0
    assert session.with_warning() == 1
    assert session.with_errors() == 0
    assert session.all_reruns() == 0


def test_rerun_test_group():
    group = RerunTestGroup("test_example.py::test_case", "FAILED")

    result1 = TestResult("test_example.py::test_case", "FAILED", datetime.utcnow(), 0.5)
    result2 = TestResult("test_example.py::test_case", "PASSED", datetime.utcnow(), 0.7)

    group.reruns.append(result1)
    group.full_test_list.append(result1)
    group.full_test_list.append(result2)

    assert group.nodeid == "test_example.py::test_case"
    assert group.final_outcome == "FAILED"
    assert group.final_test == result2


def test_test_history():
    history = TestHistory()
    history.sessions = []
    session1 = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow(), timedelta(seconds=5))
    session2 = TestSession("SUT-1", "session-002", datetime.utcnow(), datetime.utcnow(), timedelta(seconds=10))

    history.add_test_session(session1)
    history.add_test_session(session2)

    assert len(history.sessions) == 2
    assert history.latest_session() == session2


def test_output_fields():
    """Test OutputFields functionality."""
    fields = OutputFields()

    # Test empty fields
    assert not fields
    assert not fields.get(OutputFieldType.ERRORS)

    # Test setting and getting fields
    fields.set(OutputFieldType.ERRORS, "Test error occurred")
    error_field = fields.get(OutputFieldType.ERRORS)
    assert error_field
    assert error_field.content == "Test error occurred"
    assert error_field.field_type == OutputFieldType.ERRORS

    # Test getting content directly
    assert fields.get_content(OutputFieldType.ERRORS) == "Test error occurred"
    assert fields.get_content(OutputFieldType.WARNINGS_SUMMARY) == ""

    # Test multiple fields
    fields.set(OutputFieldType.SHORT_TEST_SUMMARY, "1 passed, 1 failed")
    assert len(fields.fields) == 2


def test_output_field_string_representation():
    """Test OutputField string conversion."""
    field = OutputField(OutputFieldType.ERRORS, "Test error")
    assert str(field) == "Test error"
    assert bool(field) is True

    empty_field = OutputField(OutputFieldType.ERRORS, "")
    assert str(empty_field) == ""
    assert bool(empty_field) is False
