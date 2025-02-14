from datetime import datetime, timedelta

from pytest_insight.models import (
    OutputField,
    OutputFields,
    OutputFieldType,
    RerunTestGroup,
    TestHistory,
    TestResult,
    TestSession,
)


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
        random_test_session.with_warning(),
    ]
    assert any(test_categories), "Should have results in at least one category"

    # Test result lookup functionality
    nonexistent_nodeid = "nonexistent/test_file.py::test_fake"
    assert random_test_session.find_test_result_by_nodeid(nonexistent_nodeid) is None

    # Test we can find an existing result
    first_result = random_test_session.test_results[0]
    found_result = random_test_session.find_test_result_by_nodeid(str(first_result.nodeid))
    assert found_result is not None
    assert found_result.nodeid == first_result.nodeid

    # Example of incorrect direct attribute setting that needs to be fixed:
    random_test_session.output_fields = OutputFields()  # This is OK, has setter

    # Instead, use proper methods:
    for result in test_results:
        random_test_session.add_test_result(result)

    # Test modifying test results properly
    new_result = TestResult(
        nodeid="test_new.py::test_case",
        outcome="PASSED",
        start_time=datetime.utcnow(),
        duration=0.1
    )
    random_test_session.add_test_result(new_result)

    # Verify the new result was added
    found_result = random_test_session.find_test_result_by_nodeid("test_new.py::test_case")
    assert found_result is not None
    assert found_result.nodeid == "test_new.py::test_case"


def test_test_session():
    """Test basic TestSession functionality."""
    start_time = datetime.utcnow()
    session = TestSession("SUT-1", "session-123", start_time, start_time, timedelta(seconds=10))

    # Add test results instead of trying to set counts directly
    for _ in range(5):
        session.add_test_result(TestResult(nodeid="test_pass", outcome="PASSED", start_time=start_time, duration=0.1))
    for _ in range(2):
        session.add_test_result(TestResult(nodeid="test_fail", outcome="FAILED", start_time=start_time, duration=0.1))
    session.add_test_result(TestResult(nodeid="test_skip", outcome="SKIPPED", start_time=start_time, duration=0.1))
    session.add_test_result(TestResult(nodeid="test_xfail", outcome="XFAILED", start_time=start_time, duration=0.1))
    session.add_test_result(
        TestResult(nodeid="test_warn", outcome="PASSED", start_time=start_time, duration=0.1, has_warning=True)
    )

    # Test properties
    assert session.sut_name == "SUT-1"
    assert session.session_id == "session-123"
    assert session.session_start_time == start_time
    assert session.session_duration == timedelta(seconds=10)

    # Test counts through result categorization methods
    assert len(session.all_passes()) == 6  # Updated to include warning test case
    assert len(session.all_failures()) == 2
    assert len(session.all_skipped()) == 1
    assert len(session.all_xfailed()) == 1
    assert len(session.all_xpassed()) == 0
    assert len(session.with_warning()) == 1
    assert len(session.with_error()) == 0
    assert len(session.all_reruns()) == 0


def test_test_session_properties():
    """Test TestSession property getters and setters."""
    session = TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=datetime.utcnow(),
        session_stop_time=datetime.utcnow() + timedelta(seconds=10),
        session_duration=timedelta(seconds=10),
    )

    # Test output fields setter (has proper setter method)
    fields = OutputFields()
    fields.set(OutputFieldType.ERRORS, "Test error")
    session.output_fields = fields
    assert session.output_fields.get_content(OutputFieldType.ERRORS) == "Test error"

    # Test adding test results (using add method)
    result = TestResult(nodeid="test_file.py::test_case", outcome="PASSED", start_time=datetime.utcnow(), duration=0.1)
    session.add_test_result(result)
    assert len(session.test_results) == 1

    # Test adding rerun groups (using add method)
    rerun_group = RerunTestGroup(nodeid="test_file.py::test_case", final_outcome="PASSED")
    session.add_rerun_group(rerun_group)
    assert len(session.rerun_test_groups) == 1

    # Test test counts (readonly property)
    assert isinstance(session.test_counts, dict)
    assert session.test_counts["passed"] == 1


def test_rerun_test_group():
    """Test RerunTestGroup functionality."""
    group = RerunTestGroup("test_example.py::test_case", "FAILED")
    now = datetime.utcnow()

    result1 = TestResult(nodeid="test_example.py::test_case", outcome="FAILED", start_time=now, duration=0.5)
    result2 = TestResult(
        nodeid="test_example.py::test_case", outcome="PASSED", start_time=now + timedelta(seconds=1), duration=0.7
    )

    # Use proper methods if available, otherwise modify lists directly
    group.reruns.append(result1)
    group.full_test_list.append(result1)
    group.full_test_list.append(result2)

    assert group.nodeid == "test_example.py::test_case"
    assert group.final_outcome == "FAILED"
    assert group.final_test == result2


def test_test_history():
    """Test TestHistory functionality."""
    history = TestHistory()
    now = datetime.utcnow()

    session1 = TestSession("SUT-1", "session-001", now, now + timedelta(seconds=5), timedelta(seconds=5))
    session2 = TestSession(
        "SUT-1", "session-002", now + timedelta(seconds=10), now + timedelta(seconds=20), timedelta(seconds=10)
    )

    # Use proper add method
    history.add_test_session(session1)
    history.add_test_session(session2)

    assert len(history.sessions) == 2
    assert history.latest_session() == session2


def test_output_fields():
    """Test OutputFields functionality."""
    fields = OutputFields()

    # Test empty fields
    assert not fields.fields  # Access through property

    # Test setting and getting fields
    fields.set(OutputFieldType.ERRORS, "Test error")
    assert fields.fields[OutputFieldType.ERRORS].content == "Test error"


def test_output_field_string_representation():
    """Test OutputField string conversion."""
    field = OutputField(OutputFieldType.ERRORS, "Test error")
    assert str(field) == "Test error"
    assert bool(field) is True

    empty_field = OutputField(OutputFieldType.ERRORS, "")
    assert str(empty_field) == ""
    assert bool(empty_field) is False
