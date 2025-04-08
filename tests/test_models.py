from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from pytest_insight.core.models import (
    RerunTestGroup,
    TestOutcome,
    TestResult,
    TestSession,
)


# ------------------------------vvv Tests vvv -------------------------------- #
class Test_TestOutcome:
    """Test the TestOutcome enum."""

    def test_test_outcome_enum(self):
        """Test TestOutcome enum functionality."""
        # Test creation from string
        assert TestOutcome.from_str("PASSED") == TestOutcome.PASSED
        assert TestOutcome.from_str("passed") == TestOutcome.PASSED

        # Test string representation matches serialization format
        assert TestOutcome.FAILED.to_str() == "failed"

    def test_test_outcome_case_handling(self):
        """Test TestOutcome enum handles case conversion correctly."""
        # Verify from_str() always creates uppercase internal values
        assert TestOutcome.from_str("passed").value == "PASSED"
        assert TestOutcome.from_str("PASSED").value == "PASSED"
        assert TestOutcome.from_str("PaSsEd").value == "PASSED"

        # Verify to_str() always returns lowercase
        assert TestOutcome.PASSED.to_str() == "passed"
        assert TestOutcome.FAILED.to_str() == "failed"
        assert TestOutcome.RERUN.to_str() == "rerun"

        # Verify raw enum values remain uppercase
        assert TestOutcome.PASSED.value == "PASSED"
        assert str(TestOutcome.PASSED) == "TestOutcome.PASSED"

    def test_test_outcome_invalid_values(self):
        """Test TestOutcome enum handles invalid values appropriately."""
        with pytest.raises(ValueError) as exc:
            TestOutcome.from_str("INVALID")
        assert "Invalid test outcome: INVALID" in str(exc.value)

        # Empty string should return SKIPPED as this is the default behavior
        # when a test has no outcome
        assert TestOutcome.from_str("") == TestOutcome.SKIPPED


class Test_TestResult:
    """Test the TestResult model."""

    def test_random_test_results(self, random_test_session_factory, get_test_time):
        """Test the random_test_session fixture's properties."""
        get_test_time()
        session = random_test_session_factory()  # Call factory function
        test_result = session.test_results[0]

        assert test_result.nodeid != ""
        assert isinstance(test_result.nodeid, str)
        assert test_result.outcome in TestOutcome

        assert isinstance(test_result.start_time, datetime)
        if hasattr(test_result, "stop_time"):
            assert isinstance(test_result.stop_time, datetime)
        if hasattr(test_result, "duration"):
            assert isinstance(test_result.duration, float)
        assert isinstance(test_result.has_warning, bool)

        # Fields that can be empty but must be strings
        assert isinstance(test_result.caplog, str)
        assert isinstance(test_result.capstderr, str)
        assert isinstance(test_result.capstdout, str)
        assert isinstance(test_result.longreprtext, str)

    def test_test_result_with_enum(self, get_test_time):
        """Test creating a TestResult with TestOutcome enum."""
        now = get_test_time()
        result = TestResult(
            nodeid="test_a.py::test_1",
            outcome=TestOutcome.FAILED,
            start_time=now,  # Base time
            duration=1.0,
            caplog="",
            capstderr="",
            capstdout="",
        )
        assert isinstance(result.outcome, TestOutcome)
        assert result.outcome == TestOutcome.FAILED

    def test_test_result_to_dict(self, random_test_session_factory, get_test_time):
        """Test the to_dict method of the TestResult model."""
        get_test_time()
        session = random_test_session_factory()  # Call factory function
        test_result = session.test_results[0]

        result_dict = test_result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["nodeid"] == test_result.nodeid
        assert (
            result_dict["outcome"] == test_result.outcome.to_str()
        )  # Use to_str() consistently
        assert result_dict["start_time"] == test_result.start_time.isoformat()
        assert result_dict["duration"] == test_result.duration
        assert result_dict["caplog"] == test_result.caplog
        assert result_dict["capstderr"] == test_result.capstderr
        assert result_dict["capstdout"] == test_result.capstdout
        assert result_dict["longreprtext"] == test_result.longreprtext
        assert result_dict["has_warning"] == test_result.has_warning

    def test_test_result_from_dict(self, random_test_session_factory, get_test_time):
        """Test the from_dict method of the TestResult model."""
        get_test_time()
        session = random_test_session_factory()  # Call factory function
        test_result = session.test_results[0]

        result_dict = test_result.to_dict()
        result = TestResult.from_dict(result_dict)

        assert isinstance(result, TestResult)
        assert result.nodeid == test_result.nodeid
        assert result.outcome == test_result.outcome
        assert result.start_time == test_result.start_time

        # Use pytest.approx for floating-point comparison
        assert result.duration == pytest.approx(test_result.duration, abs=0.1, rel=0.01)

        assert result.caplog == test_result.caplog
        assert result.capstderr == test_result.capstderr
        assert result.capstdout == test_result.capstdout
        assert result.longreprtext == test_result.longreprtext
        assert result.has_warning == test_result.has_warning

    def test_test_result_timing_calculations(self, get_test_time):
        """Test timing calculations for test results."""
        now = get_test_time()
        test_result = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=now,  # Base time
            duration=1.0,
            caplog="",
            capstderr="",
            capstdout="",
        )
        assert test_result.stop_time == test_result.start_time + timedelta(
            seconds=test_result.duration
        )


class Test_TestSession:
    """Test the TestSession model."""

    def test_random_test_session(self, random_test_session_factory, get_test_time):
        """Test the random_test_session fixture's properties and methods."""
        get_test_time()
        session = random_test_session_factory()  # Call factory function

        # Validate core session properties
        assert isinstance(session.sut_name, str) and session.sut_name
        assert isinstance(session.session_id, str) and session.session_id

        # Validate session timing
        assert isinstance(session.session_start_time, datetime)
        assert isinstance(session.session_stop_time, datetime)
        assert isinstance(session.session_duration, float)
        assert session.session_stop_time > session.session_start_time

        # Validate session context preservation
        assert len(session.test_results) >= 2  # Multiple tests per session
        if session.rerun_test_groups:  # Rerun groups are optional
            for group in session.rerun_test_groups:
                assert group.tests  # Each group has tests
                assert all(
                    test.outcome == TestOutcome.RERUN for test in group.tests[:-1]
                )  # All but last are reruns
                assert (
                    group.tests[-1].outcome != TestOutcome.RERUN
                )  # Last test has final outcome

        # Validate test relationships
        outcomes = {test.outcome for test in session.test_results}
        warnings = any(test.has_warning for test in session.test_results)

        # Verify meaningful test outcomes exist
        assert any(
            [
                TestOutcome.PASSED in outcomes,
                TestOutcome.FAILED in outcomes,
                TestOutcome.SKIPPED in outcomes,
                TestOutcome.XPASSED in outcomes,
                TestOutcome.RERUN in outcomes,
                TestOutcome.ERROR in outcomes,
                warnings,
            ]
        )

        # Validate session tags
        assert isinstance(session.session_tags, dict)

    def test_test_session(self, get_test_time):
        """Test basic TestSession initialization."""
        now = get_test_time()
        start_time = now  # Base time
        session = TestSession(
            sut_name="test-app",
            session_id="session-123",
            session_start_time=start_time,
            session_stop_time=get_test_time(60),  # 1 minute later
            test_results=[],
            rerun_test_groups=[],
        )
        assert session.sut_name == "test-app"
        assert session.session_id == "session-123"
        assert session.session_duration == 60.0  # 1 minute in seconds

    def test_test_session_tags(self, get_test_time):
        """Test TestSession tags handling."""
        now = get_test_time()
        session = TestSession(
            sut_name="test-app",
            session_id="session-123",
            session_start_time=now,  # Base time
            session_stop_time=get_test_time(60),  # 1 minute later
            test_results=[],
            rerun_test_groups=[],
            session_tags={"env": "test", "version": "1.0"},
        )
        assert session.session_tags == {"env": "test", "version": "1.0"}

    def test_test_session_to_dict(self, random_test_session_factory, get_test_time):
        """Test the to_dict method of the TestSession model."""
        get_test_time()
        session = random_test_session_factory()  # Call factory function
        session_dict = session.to_dict()
        assert isinstance(session_dict, dict)
        assert session_dict["sut_name"] == session.sut_name
        assert session_dict["session_id"] == session.session_id
        assert (
            session_dict["session_start_time"] == session.session_start_time.isoformat()
        )
        assert (
            session_dict["session_stop_time"] == session.session_stop_time.isoformat()
        )
        assert session_dict["session_duration"] == session.session_duration
        assert len(session_dict["test_results"]) == len(session.test_results)
        assert len(session_dict["rerun_test_groups"]) == len(session.rerun_test_groups)
        assert session_dict["session_tags"] == session.session_tags

    def test_test_session_from_dict(self, random_test_session_factory, get_test_time):
        """Test the from_dict method of the TestSession model."""
        get_test_time()
        session = random_test_session_factory()
        session_dict = session.to_dict()
        new_session = TestSession.from_dict(session_dict)

        # Verify core session properties
        assert isinstance(new_session, TestSession)
        assert new_session.sut_name == session.sut_name
        assert new_session.session_id == session.session_id
        assert new_session.session_start_time == session.session_start_time
        assert new_session.session_stop_time == session.session_stop_time

        # Duration should be calculated from timestamps
        expected_duration = (
            session.session_stop_time - session.session_start_time
        ).total_seconds()
        assert new_session.session_duration == expected_duration

        # Verify test results
        assert len(new_session.test_results) == len(session.test_results)
        for new_result, orig_result in zip(
            new_session.test_results, session.test_results
        ):
            assert new_result.nodeid == orig_result.nodeid
            assert new_result.outcome == orig_result.outcome
            assert new_result.duration == orig_result.duration

        # Verify rerun groups
        assert len(new_session.rerun_test_groups) == len(session.rerun_test_groups)
        for new_group, orig_group in zip(
            new_session.rerun_test_groups, session.rerun_test_groups
        ):
            assert new_group.nodeid == orig_group.nodeid
            assert len(new_group.tests) == len(orig_group.tests)

        # Verify session tags
        assert new_session.session_tags == session.session_tags

    def test_test_session_serialization(self, get_test_time):
        """Test serialization of TestSession objects."""
        # Create test session with timezone-aware timestamps
        now = get_test_time()
        session = TestSession(
            sut_name="test_sut",
            session_id="test-123",
            session_start_time=now,  # Base time
            session_stop_time=get_test_time(10),  # 10 seconds later
            test_results=[
                TestResult(
                    nodeid="test_api.py::test_get",
                    outcome=TestOutcome.PASSED,
                    start_time=now,  # Same as session start
                    duration=1.0,
                ),
                TestResult(
                    nodeid="test_api.py::test_post",
                    outcome=TestOutcome.FAILED,
                    start_time=get_test_time(5),  # 5 seconds later
                    duration=1.0,
                ),
            ],
            rerun_test_groups=[],
        )

        # Serialize and deserialize
        session_dict = session.to_dict()
        restored_session = TestSession.from_dict(session_dict)

        # Verify timestamps are preserved with timezone info
        assert restored_session.session_start_time == session.session_start_time
        assert restored_session.session_stop_time == session.session_stop_time
        assert (
            restored_session.test_results[0].start_time
            == session.test_results[0].start_time
        )
        assert (
            restored_session.test_results[1].start_time
            == session.test_results[1].start_time
        )


class Test_RerunTestGroup:
    """Test the RerunTestGroup model."""

    def test_rerun_test_group(self, get_test_time):
        """Test RerunTestGroup functionality."""
        now = get_test_time()
        group = RerunTestGroup(nodeid="test_example.py::test_case")

        # Create test results in chronological order
        result1 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=0.5,
        )
        result2 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.PASSED,
            start_time=get_test_time(1),  # 1 second later
            duration=0.7,
        )

        # Add tests in order
        group.add_test(result1)
        group.add_test(result2)

        assert group.nodeid == "test_example.py::test_case"
        assert group.final_outcome == TestOutcome.PASSED
        assert len(group.tests) == 2
        assert group.tests == [result1, result2]

    def test_rerun_test_group_to_dict(self, get_test_time):
        """Test the to_dict method of the RerunTestGroup model."""
        now = get_test_time()
        group = RerunTestGroup(nodeid="test_example.py::test_case")

        result1 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=0.5,
        )
        result2 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.PASSED,
            start_time=get_test_time(1),  # 1 second later
            duration=0.7,
        )

        group.add_test(result1)
        group.add_test(result2)

        group_dict = group.to_dict()
        assert isinstance(group_dict, dict)
        assert group_dict["nodeid"] == group.nodeid
        assert len(group_dict["tests"]) == 2
        assert group_dict["tests"][0]["outcome"] == "rerun"
        assert group_dict["tests"][1]["outcome"] == "passed"

    def test_rerun_test_group_from_dict(self, get_test_time):
        """Test the from_dict method of the RerunTestGroup model."""
        now = get_test_time()
        group = RerunTestGroup(nodeid="test_example.py::test_case")

        result1 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=0.5,
        )
        result2 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.PASSED,
            start_time=get_test_time(1),  # 1 second later
            duration=0.7,
        )

        group.add_test(result1)
        group.add_test(result2)

        # Test serialization/deserialization
        group_dict = group.to_dict()
        new_group = RerunTestGroup.from_dict(group_dict)

        assert isinstance(new_group, RerunTestGroup)
        assert new_group.nodeid == group.nodeid
        assert new_group.final_outcome == TestOutcome.PASSED
        assert len(new_group.tests) == 2
        assert new_group.tests[0].outcome == TestOutcome.RERUN
        assert new_group.tests[1].outcome == TestOutcome.PASSED


class Test_TestResultBehavior:
    """Test suite for TestResult behavior and relationships."""

    def test_outcome_serialization(self):
        """Test that outcomes are consistently serialized in lowercase."""
        result = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.FAILED,
            start_time=datetime.now(ZoneInfo("UTC")),
            duration=1.0,
        )

        data = result.to_dict()
        assert data["outcome"] == "failed"  # Always lowercase

        # Test string outcomes
        result.outcome = "PASSED"
        data = result.to_dict()
        assert data["outcome"] == "passed"

    def test_timezone_handling(self, get_test_time):
        """Test that all datetime operations are timezone-aware."""
        now = get_test_time()
        result = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.0,
        )

        # Verify timezone awareness
        assert result.start_time.tzinfo is not None
        assert result.stop_time.tzinfo is not None

        # Verify ISO format includes UTC timezone (either 'Z' or '+00:00')
        data = result.to_dict()
        assert any(
            marker in data["start_time"] for marker in ["Z", "+00:00"]
        ), f"Expected UTC timezone marker ('Z' or '+00:00') in {data['start_time']}"

    def test_output_fields(self):
        """Test handling of output fields (stdout, stderr, log)."""
        now = datetime.now(ZoneInfo("UTC"))
        result = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.0,
            caplog="DEBUG: message",
            capstderr="error",
            capstdout="output",
        )

        data = result.to_dict()
        assert data["caplog"] == "DEBUG: message"
        assert data["capstderr"] == "error"
        assert data["capstdout"] == "output"

        # Test empty fields
        result = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.0,
        )

        data = result.to_dict()
        assert data["caplog"] == ""
        assert data["capstderr"] == ""
        assert data["capstdout"] == ""

    def test_test_result_timing_calculations(self, get_test_time):
        """Test TestResult handles timing calculations correctly."""
        now = get_test_time()
        result = TestResult(
            nodeid="test_example",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.5,
        )

        assert isinstance(result.duration, float)
        assert result.duration == 1.5
        assert result.stop_time == now + timedelta(seconds=1.5)
        assert result.stop_time.tzinfo is not None  # Verify timezone info

    def test_test_result_serialization_1(self, get_test_time):
        """Test TestResult serialization."""
        now = get_test_time()
        result = TestResult(
            nodeid="test_example",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.0,
        )

        data = result.to_dict()
        assert isinstance(data["duration"], float)
        start_time = datetime.fromisoformat(data["start_time"])
        stop_time = datetime.fromisoformat(data["stop_time"])
        assert start_time.tzinfo is not None
        assert stop_time.tzinfo is not None

    def test_test_result_serialization_2(self, get_test_time):
        """Test serialization of TestResult objects."""
        # Create test result with timezone-aware timestamp
        now = get_test_time()
        test_result = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=now,  # Use get_test_time for consistent timezone handling
            duration=1.0,
            caplog="",
            capstderr="",
            capstdout="",
            longreprtext="",
        )

        # Serialize and deserialize
        result_dict = test_result.to_dict()
        restored_result = TestResult.from_dict(result_dict)

        # Verify timestamps are preserved with timezone info
        assert restored_result.start_time == test_result.start_time
        assert restored_result.stop_time == test_result.stop_time

    def test_test_result_timing(self, get_test_time):
        """Test timing calculations for test results."""
        now = get_test_time()  # Use get_test_time for consistent timezone handling
        test_result = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.0,
            caplog="",
            capstderr="",
            capstdout="",
            longreprtext="",
        )

        assert test_result.stop_time == now + timedelta(seconds=1.0)


class Test_TestSessionBehavior:
    """Test suite for TestSession behavior and relationships."""

    def test_session_timing(self, get_test_time):
        """Test session timing calculations and timezone handling."""
        now = get_test_time()
        start_time = now
        stop_time = get_test_time(3600)  # 1 hour later

        session = TestSession(
            sut_name="api",
            session_id="test",
            session_start_time=start_time,
            session_stop_time=stop_time,
            test_results=[],
            session_tags={"env": "test"},
        )

        assert session.session_start_time.tzinfo is not None
        assert session.session_stop_time.tzinfo is not None
        assert (
            session.session_duration == 3600.0
        )  # Check float duration instead of timedelta

    def test_test_relationships(self, get_test_time):
        """Test relationships between tests in a session."""
        now = get_test_time()

        test1 = TestResult(
            nodeid="test_api.py::test_get",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.0,
        )

        test2 = TestResult(
            nodeid="test_api.py::test_post",
            outcome=TestOutcome.FAILED,
            start_time=get_test_time(1),  # 1 second later
            duration=1.0,
        )

        session = TestSession(
            sut_name="api",
            session_id="test",
            session_start_time=now,
            session_stop_time=get_test_time(10),  # 10 seconds later
            test_results=[test1, test2],
            session_tags={"env": "test"},
        )

        # Test ordering
        assert session.test_results[0].start_time < session.test_results[1].start_time

        # Test outcome aggregation
        assert (
            len([t for t in session.test_results if t.outcome == TestOutcome.PASSED])
            == 1
        )
        assert (
            len([t for t in session.test_results if t.outcome == TestOutcome.FAILED])
            == 1
        )

    def test_session_metadata(self):
        """Test session metadata handling."""
        now = datetime.now(ZoneInfo("UTC"))
        session = TestSession(
            sut_name="api",
            session_id="test",
            session_start_time=now,
            session_stop_time=now + timedelta(seconds=10),
            test_results=[],
            session_tags={"environment": "staging", "branch": "main"},
        )

        data = session.to_dict()
        assert data["sut_name"] == "api"
        assert data["session_tags"] == {"environment": "staging", "branch": "main"}

        # Test tag updates
        session.session_tags["version"] = "1.0"
        data = session.to_dict()
        assert data["session_tags"]["version"] == "1.0"

    def test_session_test_result_relationships(self, get_test_time):
        """Test relationships between session and test results."""
        now = get_test_time()
        session = TestSession(
            sut_name="test-app",
            session_id="session-123",
            session_start_time=now,
            session_duration=10.0,
            test_results=[],
            session_tags={"env": "test"},
        )

        # Add test results
        test1 = TestResult(
            nodeid="test_example.py::test_1",
            outcome=TestOutcome.PASSED,
            start_time=now,
            duration=1.0,
        )
        test2 = TestResult(
            nodeid="test_example.py::test_2",
            outcome=TestOutcome.FAILED,
            start_time=get_test_time(5),  # 5 seconds later
            duration=2.0,
            longreprtext="Test failed",
        )

        session.add_test_result(test1)
        session.add_test_result(test2)

        # Verify test results are maintained in order
        assert len(session.test_results) == 2
        assert session.test_results[0].nodeid == "test_example.py::test_1"
        assert session.test_results[1].nodeid == "test_example.py::test_2"

        # Verify serialization preserves relationships
        data = session.to_dict()
        restored = TestSession.from_dict(data)

        assert len(restored.test_results) == 2
        assert restored.test_results[0].nodeid == "test_example.py::test_1"
        assert restored.test_results[1].nodeid == "test_example.py::test_2"
        assert restored.test_results[1].longreprtext == "Test failed"

    def test_session_rerun_group_relationships(self, get_test_time):
        """Test relationships between session and rerun groups."""
        now = get_test_time()
        session = TestSession(
            sut_name="test-app",
            session_id="session-123",
            session_start_time=now,
            session_duration=10.0,
            test_results=[],
            session_tags={"env": "test"},
        )

        # Create rerun groups
        group1 = RerunTestGroup(nodeid="test_example.py::test_1")
        test1 = TestResult(
            nodeid="test_example.py::test_1",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=1.0,
        )
        test2 = TestResult(
            nodeid="test_example.py::test_1",
            outcome=TestOutcome.PASSED,
            start_time=get_test_time(5),  # 5 seconds later
            duration=1.0,
        )
        group1.add_test(test1)
        group1.add_test(test2)

        group2 = RerunTestGroup(nodeid="test_example.py::test_2")
        test3 = TestResult(
            nodeid="test_example.py::test_2",
            outcome=TestOutcome.RERUN,
            start_time=get_test_time(10),  # 10 seconds later
            duration=1.0,
        )
        group2.add_test(test3)

        session.add_rerun_group(group1)
        session.add_rerun_group(group2)

        # Verify rerun groups are maintained in order
        assert len(session.rerun_test_groups) == 2
        assert session.rerun_test_groups[0].nodeid == "test_example.py::test_1"
        assert session.rerun_test_groups[1].nodeid == "test_example.py::test_2"
        assert len(session.rerun_test_groups[0].tests) == 2
        assert len(session.rerun_test_groups[1].tests) == 1

        # Verify serialization preserves relationships
        data = session.to_dict()
        restored = TestSession.from_dict(data)

        assert len(restored.rerun_test_groups) == 2
        assert restored.rerun_test_groups[0].nodeid == "test_example.py::test_1"
        assert restored.rerun_test_groups[1].nodeid == "test_example.py::test_2"
        assert len(restored.rerun_test_groups[0].tests) == 2
        assert len(restored.rerun_test_groups[1].tests) == 1

        # Verify test outcomes in order
        assert restored.rerun_test_groups[0].tests[0].outcome == TestOutcome.RERUN
        assert restored.rerun_test_groups[0].tests[1].outcome == TestOutcome.PASSED
        assert restored.rerun_test_groups[1].tests[0].outcome == TestOutcome.RERUN
