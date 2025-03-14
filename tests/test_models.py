from datetime import datetime, timedelta

import pytest
from pytest_insight.models import (
    RerunTestGroup,
    TestHistory,
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

    def test_random_test_results(self, random_test_session):
        """Test the random_test_session fixture's properties."""
        session = random_test_session()  # Call factory function
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

    def test_test_result_with_enum(self):
        """Test TestResult with TestOutcome enum."""
        result = TestResult(
            nodeid="test_nodeid",
            outcome=TestOutcome.PASSED,
            start_time=datetime.utcnow(),
            duration=1.0,  # Add required duration
        )
        assert isinstance(result.outcome, TestOutcome)

        # Test string conversion
        result = TestResult(
            nodeid="test_nodeid",
            outcome=TestOutcome.FAILED,
            start_time=datetime.utcnow(),
            duration=1.0,  # Add required duration
        )
        assert isinstance(result.outcome, TestOutcome)
        assert result.outcome == TestOutcome.FAILED

    def test_test_result_to_dict(self, random_test_session):
        """Test the to_dict method of the TestResult model."""
        session = random_test_session()  # Call factory function
        test_result = session.test_results[0]

        result_dict = test_result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["nodeid"] == test_result.nodeid
        assert result_dict["outcome"] == test_result.outcome.to_str()  # Use to_str() consistently
        assert result_dict["start_time"] == test_result.start_time.isoformat()
        assert result_dict["duration"] == test_result.duration
        assert result_dict["caplog"] == test_result.caplog
        assert result_dict["capstderr"] == test_result.capstderr
        assert result_dict["capstdout"] == test_result.capstdout
        assert result_dict["longreprtext"] == test_result.longreprtext
        assert result_dict["has_warning"] == test_result.has_warning

    def test_test_result_from_dict(self, random_test_session):
        """Test the from_dict method of the TestResult model."""
        session = random_test_session()  # Call factory function
        test_result = session.test_results[0]

        result_dict = test_result.to_dict()
        result = TestResult.from_dict(result_dict)

        assert isinstance(result, TestResult)
        assert result.nodeid == test_result.nodeid
        assert result.outcome == test_result.outcome
        assert result.start_time == test_result.start_time

        # Use pytest.approx for floating-point comparison
        assert result.duration == pytest.approx(test_result.duration)

        assert result.caplog == test_result.caplog
        assert result.capstderr == test_result.capstderr
        assert result.capstdout == test_result.capstdout
        assert result.longreprtext == test_result.longreprtext
        assert result.has_warning == test_result.has_warning

    def test_test_result_timing_calculations(self):
        """Test TestResult handles timing calculations correctly."""
        now = datetime.utcnow()

        # Test with duration provided
        result1 = TestResult(nodeid="test_a.py::test_1", outcome=TestOutcome.PASSED, start_time=now, duration=1.5)
        assert result1.stop_time == now + timedelta(seconds=1.5)

        # Test with stop_time provided
        result2 = TestResult(
            nodeid="test_a.py::test_1",
            outcome=TestOutcome.PASSED,
            start_time=now,
            stop_time=now + timedelta(seconds=2.0),
        )
        assert result2.duration == 2.0

        # Test invalid initialization
        with pytest.raises(ValueError) as exc:
            TestResult(nodeid="test_a.py::test_1", outcome=TestOutcome.PASSED, start_time=now)
        assert "Either stop_time or duration must be provided" in str(exc.value)


class test_TestSession:
    """Test the TestSession model."""

    def test_random_test_session(self, random_test_session):
        """Test the random_test_session fixture's properties and methods."""
        session = random_test_session()  # Call factory function
        assert isinstance(session.sut_name, str) and session.sut_name.startswith("SUT-")
        assert isinstance(session.session_id, str) and session.session_id.startswith("session-")

        assert isinstance(session.session_start_time, datetime)
        assert isinstance(session.session_stop_time, datetime)
        assert isinstance(session.session_duration, timedelta)
        assert session.session_stop_time > session.session_start_time

        # Ensure test results and rerun groups are populated
        assert len(session.test_results) >= 2
        assert len(session.rerun_test_groups) >= 1

        # Test outcome categorization
        outcomes = {test.outcome for test in session.test_results}
        warnings = any(test.has_warning for test in session.test_results)

        # Verify we have at least one test result with a meaningful outcome
        assert any(
            [
                TestOutcome.PASSED in outcomes,
                TestOutcome.FAILED in outcomes,
                TestOutcome.SKIPPED in outcomes,
                TestOutcome.FAILED in outcomes,
                TestOutcome.XPASSED in outcomes,
                TestOutcome.RERUN in outcomes,
                TestOutcome.ERROR in outcomes,
                warnings,
            ]
        )

    def test_test_session(self):
        """Test basic TestSession functionality."""
        start_time = datetime.utcnow()
        stop_time = start_time + timedelta(seconds=10)

        session = TestSession(
            sut_name="SUT-1",
            session_id="session-123",
            session_start_time=start_time,
            session_stop_time=stop_time,
        )

        # Add test results
        for _ in range(5):
            session.add_test_result(
                TestResult(
                    nodeid="test_pass",
                    outcome=TestOutcome.PASSED,
                    start_time=start_time,
                    duration=0.1,
                )
            )

        assert len(session.test_results) == 5
        assert session.session_duration.total_seconds() == 10.0

    def test_test_session_tags(self):
        """Test session tags functionality."""
        session = TestSession(
            sut_name="SUT-1",
            session_id="session-123",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow(),
        )

        session.add_tag("environment", "dev")
        session.add_tag("platform", "linux")
        session.add_tag("python_version", "3.8")

        assert session.session_tags == {
            "environment": "dev",
            "platform": "linux",
            "python_version": "3.8",
        }

    def test_test_session_to_dict(self, random_test_session):
        """Test the to_dict method of the TestSession model."""
        session = random_test_session()  # Call factory function
        session_dict = session.to_dict()
        assert isinstance(session_dict, dict)
        assert session_dict["sut_name"] == session.sut_name
        assert session_dict["session_id"] == session.session_id
        assert session_dict["session_start_time"] == session.session_start_time.isoformat()
        assert session_dict["session_stop_time"] == session.session_stop_time.isoformat()
        assert session_dict["session_duration"] == session.session_duration.total_seconds()
        assert len(session_dict["test_results"]) == len(session.test_results)
        assert len(session_dict["rerun_test_groups"]) == len(session.rerun_test_groups)
        assert session_dict["session_tags"] == session.session_tags

    def test_test_session_from_dict(self, random_test_session):
        """Test the from_dict method of the TestSession model."""
        session = random_test_session()  # Call factory function
        session_dict = session.to_dict()
        session = TestSession.from_dict(session_dict)
        assert isinstance(session, TestSession)
        assert session.sut_name == session_dict["sut_name"]
        assert session.session_id == session_dict["session_id"]
        assert session.session_start_time == datetime.fromisoformat(session_dict["session_start_time"])
        assert session.session_stop_time == datetime.fromisoformat(session_dict["session_stop_time"])
        assert session.session_duration == timedelta(seconds=session_dict["session_duration"])
        assert len(session.test_results) == len(session_dict["test_results"])
        assert len(session.rerun_test_groups) == len(session_dict["rerun_test_groups"])
        assert session.session_tags == session_dict["session_tags"]

    def test_test_session_serialization(self):
        """Test TestSession serialization to dictionary."""
        now = datetime.utcnow()
        session = TestSession(
            sut_name="test-app",
            session_id="session-123",
            session_start_time=now,
            session_stop_time=now + timedelta(minutes=1),
            test_results=[
                TestResult(nodeid="test_a.py::test_1", outcome=TestOutcome.PASSED, start_time=now, duration=1.0)
            ],
            session_tags={"env": "test"},
        )

        data = session.to_dict()
        assert data["sut_name"] == "test-app"
        assert data["session_id"] == "session-123"
        assert isinstance(data["session_start_time"], str)
        assert isinstance(data["session_stop_time"], str)
        assert isinstance(data["test_results"], list)
        assert data["session_tags"] == {"env": "test"}


class Test_RerunTestGroup:
    """Test the RerunTestGroup model."""

    def test_rerun_test_group(self):
        """Test RerunTestGroup functionality."""
        now = datetime.utcnow()
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
            start_time=now + timedelta(seconds=1),
            duration=0.7,
        )

        # Add tests in order
        group.add_test(result1)
        group.add_test(result2)

        assert group.nodeid == "test_example.py::test_case"
        assert group.final_outcome == TestOutcome.PASSED
        assert len(group.tests) == 2
        assert group.tests == [result1, result2]

    def test_rerun_test_group_to_dict(self):
        """Test the to_dict method of the RerunTestGroup model."""
        now = datetime.utcnow()
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
            start_time=now + timedelta(seconds=1),
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

    def test_rerun_test_group_from_dict(self):
        """Test the from_dict method of the RerunTestGroup model."""
        now = datetime.utcnow()
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
            start_time=now + timedelta(seconds=1),
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


class Test_TestHistory:
    """Test the TestHistory model."""

    def test_test_history(self):
        """Test TestHistory functionality."""
        history = TestHistory()
        now = datetime.utcnow()
        stop_time1 = now + timedelta(seconds=5)
        stop_time2 = now + timedelta(seconds=20)

        session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
        session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

        history.add_test_session(session1)
        history.add_test_session(session2)

        assert len(history.sessions) == 2
        assert history.latest_session() == session2

    def test_test_history_sessions_property(self):
        """Test the sessions property."""
        history = TestHistory()
        assert history.sessions == []

        session = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow(), [], [])
        history.add_test_session(session)

        assert history.sessions == [session]

    def test_test_history_add_test_session(self):
        """Test the add_test_session method."""
        history = TestHistory()
        now = datetime.utcnow()
        stop_time1 = now + timedelta(seconds=5)
        stop_time2 = now + timedelta(seconds=20)

        session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
        session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

        history.add_test_session(session1)
        history.add_test_session(session2)

        assert len(history.sessions) == 2
        assert history.latest_session() == session2

    def test_test_history_latest_session(self):
        """Test the latest_session method."""
        history = TestHistory()
        now = datetime.utcnow()
        stop_time1 = now + timedelta(seconds=5)
        stop_time2 = now + timedelta(seconds=20)

        session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
        session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

        history.add_test_session(session1)
        history.add_test_session(session2)

        assert history.latest_session() == session2

    def test_test_history_initialization(self, test_history):
        """Test TestHistory initializes with empty collections."""
        assert test_history._sessions_by_sut == {}
        assert test_history._latest_by_sut == {}
        assert test_history._all_sessions_cache is None

    def test_add_test_session(self, test_history, sample_session):
        """Test adding a session to TestHistory."""
        test_history.add_test_session(sample_session)

        # Check main storage
        assert "test-sut" in test_history._sessions_by_sut
        assert test_history._sessions_by_sut["test-sut"][0] == sample_session

        # Check latest cache
        assert test_history._latest_by_sut["test-sut"] == sample_session

        # Check global cache invalidation
        assert test_history._all_sessions_cache is None

    def test_multiple_sessions_same_sut(self, test_history):
        """Test adding multiple sessions for same SUT."""
        now = datetime.now()

        # Create sessions with different times
        sessions = [
            TestSession(
                sut_name="test-sut",
                session_id=f"session-{i}",
                session_start_time=now + timedelta(hours=i),
                session_stop_time=now + timedelta(hours=i, minutes=1),
                test_results=[],
            )
            for i in range(3)
        ]

        # Add sessions in random order
        test_history.add_test_session(sessions[1])
        test_history.add_test_session(sessions[0])
        test_history.add_test_session(sessions[2])

        # Check latest session is most recent
        assert test_history._latest_by_sut["test-sut"] == sessions[2]

        # Check chronological order in get_sut_sessions
        ordered_sessions = test_history.get_sut_sessions("test-sut")
        assert ordered_sessions == sorted(sessions, key=lambda s: s.session_start_time)

    def test_multiple_suts(self, test_history):
        """Test handling multiple SUTs."""
        now = datetime.now()

        # Create sessions for different SUTs
        sut_sessions = {
            "sut-1": TestSession(
                sut_name="sut-1",
                session_id="session-1",
                session_start_time=now,
                session_stop_time=now + timedelta(minutes=1),
                test_results=[],
            ),
            "sut-2": TestSession(
                sut_name="sut-2",
                session_id="session-2",
                session_start_time=now + timedelta(hours=1),
                session_stop_time=now + timedelta(hours=1, minutes=1),
                test_results=[],
            ),
        }

        for session in sut_sessions.values():
            test_history.add_test_session(session)

        # Check SUT names
        assert set(test_history.get_sut_names()) == {"sut-1", "sut-2"}

        # Check latest session across all SUTs
        assert test_history.latest_session() == sut_sessions["sut-2"]

    def test_sessions_property_caching(self, test_history, sample_session):
        """Test caching behavior of sessions property."""
        test_history.add_test_session(sample_session)

        # First access should create cache
        first_access = test_history.sessions
        assert test_history._all_sessions_cache is not None

        # Cache should be copied
        assert first_access is not test_history._all_sessions_cache

        # Second access should use cache
        second_access = test_history.sessions
        assert second_access == first_access
        assert second_access is not first_access  # Should be a new copy

    def test_nonexistent_sut(self, test_history):
        """Test handling of nonexistent SUT requests."""
        assert test_history.get_sut_sessions("nonexistent") == []
        assert test_history.get_sut_latest_session("nonexistent") is None

    def test_empty_history_latest_session(self, test_history):
        """Test latest_session with empty history."""
        assert test_history.latest_session() is None

    def test_sessions_cache_invalidation(self, test_history):
        """Test that sessions cache is properly invalidated on updates."""
        now = datetime.now()
        session1 = TestSession(
            sut_name="test-sut",
            session_id="session-1",
            session_start_time=now,
            session_stop_time=now + timedelta(seconds=10),
            test_results=[],
        )

        # Add first session and access cache
        test_history.add_test_session(session1)
        first_cache = test_history.sessions

        # Add another session
        session2 = TestSession(
            sut_name="test-sut",
            session_id="session-2",
            session_start_time=now + timedelta(minutes=1),
            session_stop_time=now + timedelta(minutes=1, seconds=10),
            test_results=[],
        )
        test_history.add_test_session(session2)

        # Verify cache was invalidated and new data is present
        updated_sessions = test_history.sessions
        assert len(updated_sessions) == 2
        assert updated_sessions != first_cache

    def test_latest_session_across_suts(self, test_history):
        """Test latest_session returns most recent across all SUTs."""
        now = datetime.now()

        # Create sessions with different times across SUTs
        sessions = [
            TestSession(
                sut_name="sut-1",
                session_id="old-1",
                session_start_time=now - timedelta(hours=2),
                session_stop_time=now - timedelta(hours=2) + timedelta(seconds=10),
                test_results=[],
            ),
            TestSession(
                sut_name="sut-2",
                session_id="newest",
                session_start_time=now,
                session_stop_time=now + timedelta(seconds=10),
                test_results=[],
            ),
            TestSession(
                sut_name="sut-1",
                session_id="old-2",
                session_start_time=now - timedelta(hours=1),
                session_stop_time=now - timedelta(hours=1) + timedelta(seconds=10),
                test_results=[],
            ),
        ]

        for session in sessions:
            test_history.add_test_session(session)

        latest = test_history.latest_session()
        assert latest.session_id == "newest"
        assert latest.sut_name == "sut-2"
