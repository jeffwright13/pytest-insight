from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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
        assert result_dict["outcome"] == test_result.outcome.to_str()  # Use to_str() consistently
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
        assert test_result.stop_time == test_result.start_time + timedelta(seconds=test_result.duration)


class Test_TestSession:
    """Test the TestSession model."""

    def test_random_test_session(self, random_test_session_factory, get_test_time):
        """Test the random_test_session fixture's properties and methods."""
        get_test_time()
        session = random_test_session_factory()  # Call factory function
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
        assert session.duration == 60.0  # 1 minute in seconds

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
        assert session_dict["session_start_time"] == session.session_start_time.isoformat()
        assert session_dict["session_stop_time"] == session.session_stop_time.isoformat()
        assert session_dict["session_duration"] == session.session_duration
        assert len(session_dict["test_results"]) == len(session.test_results)
        assert len(session_dict["rerun_test_groups"]) == len(session.rerun_test_groups)
        assert session_dict["session_tags"] == session.session_tags

    def test_test_session_from_dict(self, random_test_session_factory, get_test_time):
        """Test the from_dict method of the TestSession model."""
        get_test_time()
        session = random_test_session_factory()  # Call factory function
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
        assert restored_session.test_results[0].start_time == session.test_results[0].start_time
        assert restored_session.test_results[1].start_time == session.test_results[1].start_time


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


class Test_TestHistory:
    """Test the TestHistory model."""

    def test_test_history(self, get_test_time):
        """Test TestHistory functionality."""
        history = TestHistory()
        now = get_test_time()
        stop_time1 = now + timedelta(seconds=5)
        stop_time2 = now + timedelta(seconds=20)

        session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
        session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

        history.add_test_session(session1)
        history.add_test_session(session2)

        assert len(history.sessions) == 2
        assert history.latest_session() == session2

    def test_test_history_sessions_property(self, get_test_time):
        """Test sessions property of TestHistory."""
        history = TestHistory()
        now = get_test_time()
        session = TestSession("SUT-1", "session-001", now, now + timedelta(seconds=60), [], [])
        history.add_test_session(session)
        assert history.sessions == [session]

    def test_test_history_latest_session(self, get_test_time):
        """Test getting latest session from TestHistory."""
        history = TestHistory()
        now = get_test_time()
        session1 = TestSession(
            sut_name="test-app",
            session_id="session-1",
            session_start_time=now,  # Base time
            session_stop_time=get_test_time(60),  # 1 minute later
            test_results=[],
            rerun_test_groups=[],
        )
        session2 = TestSession(
            sut_name="test-app",
            session_id="session-2",
            session_start_time=get_test_time(120),  # 2 minutes later
            session_stop_time=get_test_time(180),  # 3 minutes from base
            test_results=[],
            rerun_test_groups=[],
        )
        history.add_test_session(session1)
        history.add_test_session(session2)
        assert history.get_latest_session("test-app") == session2

    def test_test_history_initialization(self, test_history):
        """Test TestHistory initialization."""
        assert test_history.sessions == []
        assert test_history._latest_by_sut == {}
        assert test_history._all_sessions_cache is None

    def test_add_test_session(self, test_history, get_test_time):
        """Test adding a session to TestHistory."""
        now = get_test_time()
        sample_session = TestSession(
            sut_name="test-sut",
            session_id="session-1",
            session_start_time=now,  # Base time
            session_stop_time=get_test_time(60),  # 1 minute later
            test_results=[],
            session_tags={"env": "test"},
        )
        test_history.add_test_session(sample_session)

        # Check main storage
        assert "test-sut" in test_history._sessions_by_sut
        assert test_history._sessions_by_sut["test-sut"][0] == sample_session

        # Check latest cache
        assert test_history._latest_by_sut["test-sut"] == sample_session

        # Check global cache invalidation
        assert test_history._all_sessions_cache is None

    def test_multiple_sessions_same_sut(self, test_history, get_test_time):
        """Test adding multiple sessions for same SUT."""
        get_test_time()

        # Create sessions with different times
        sessions = [
            TestSession(
                sut_name="test-sut",
                session_id=f"session-{i}",
                session_start_time=get_test_time(i * 3600),  # i hours later
                session_stop_time=get_test_time(i * 3600 + 300),  # i hours + 5 mins later
                test_results=[],
                session_tags={"env": "test" if i % 2 == 0 else "prod"},
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

    def test_multiple_suts(self, test_history, get_test_time):
        """Test handling multiple SUTs."""
        now = get_test_time()

        # Create sessions for different SUTs
        sut_sessions = {
            "sut-1": TestSession(
                sut_name="sut-1",
                session_id="session-1",
                session_start_time=now,
                session_stop_time=get_test_time(300),  # 5 mins later
                test_results=[],
                session_tags={"env": "test"},
            ),
            "sut-2": TestSession(
                sut_name="sut-2",
                session_id="session-2",
                session_start_time=get_test_time(3600),  # 1 hour later
                session_stop_time=get_test_time(3900),  # 1 hour + 5 mins later
                test_results=[],
                session_tags={"env": "prod"},
            ),
        }

        for session in sut_sessions.values():
            test_history.add_test_session(session)

        # Check SUT names
        assert set(test_history.get_sut_names()) == {"sut-1", "sut-2"}

        # Check latest session across all SUTs
        assert test_history.latest_session() == sut_sessions["sut-2"]

    def test_sessions_cache_invalidation(self, test_history, get_test_time):
        """Test that sessions cache is properly invalidated on updates."""
        now = get_test_time()

        # Create sessions
        session1 = TestSession(
            sut_name="test-sut",
            session_id="session-1",
            session_start_time=now,
            session_stop_time=get_test_time(300),  # 5 mins later
            test_results=[],
            session_tags={"env": "test"},
        )
        session2 = TestSession(
            sut_name="test-sut",
            session_id="session-2",
            session_start_time=get_test_time(3600),  # 1 hour later
            session_stop_time=get_test_time(3900),  # 1 hour + 5 mins later
            test_results=[],
            session_tags={"env": "prod"},
        )

        # Add first session and cache sessions
        test_history.add_test_session(session1)
        _ = test_history.sessions  # Access to build cache

        # Add second session
        test_history.add_test_session(session2)

        # Cache should be invalidated
        assert test_history._all_sessions_cache is None

        # Rebuild cache and verify
        sessions = test_history.sessions
        assert len(sessions) == 2
        assert sessions == sorted([session1, session2], key=lambda s: s.session_start_time)

    def test_latest_session_across_suts(self, test_history, get_test_time):
        """Test latest_session returns most recent across all SUTs."""
        now = get_test_time()

        # Create sessions for different SUTs with different times
        sessions = [
            TestSession(
                sut_name="sut-1",
                session_id="session-1",
                session_start_time=now,
                session_stop_time=get_test_time(300),  # 5 mins later
                test_results=[],
                session_tags={"env": "test"},
            ),
            TestSession(
                sut_name="sut-2",
                session_id="session-2",
                session_start_time=get_test_time(3600),  # 1 hour later
                session_stop_time=get_test_time(3900),  # 1 hour + 5 mins later
                test_results=[],
                session_tags={"env": "prod"},
            ),
            TestSession(
                sut_name="sut-1",
                session_id="session-3",
                session_start_time=get_test_time(7200),  # 2 hours later
                session_stop_time=get_test_time(7500),  # 2 hours + 5 mins later
                test_results=[],
                session_tags={"env": "test"},
            ),
        ]

        # Add sessions in random order
        test_history.add_test_session(sessions[1])  # sut-2 middle time
        test_history.add_test_session(sessions[0])  # sut-1 earliest
        test_history.add_test_session(sessions[2])  # sut-1 latest

        # Latest session overall should be sessions[2]
        assert test_history.latest_session() == sessions[2]

        # Latest for sut-1 should be sessions[2]
        assert test_history._latest_by_sut["sut-1"] == sessions[2]

        # Latest for sut-2 should be sessions[1]
        assert test_history._latest_by_sut["sut-2"] == sessions[1]

    def test_nonexistent_sut(self, test_history):
        """Test handling of nonexistent SUT requests."""
        assert test_history.get_sut_sessions("nonexistent") == []
        assert test_history.get_sut_latest_session("nonexistent") is None

    def test_empty_history_latest_session(self, test_history):
        """Test latest_session with empty history."""
        assert test_history.latest_session() is None

    def test_sessions_cache_invalidation(self, test_history, get_test_time):
        """Test that sessions cache is properly invalidated on updates."""
        now = get_test_time()

        # Create sessions
        session1 = TestSession(
            sut_name="test-sut",
            session_id="session-1",
            session_start_time=now,
            session_stop_time=get_test_time(300),  # 5 mins later
            test_results=[],
            session_tags={"env": "test"},
        )
        session2 = TestSession(
            sut_name="test-sut",
            session_id="session-2",
            session_start_time=get_test_time(3600),  # 1 hour later
            session_stop_time=get_test_time(3900),  # 1 hour + 5 mins later
            test_results=[],
            session_tags={"env": "prod"},
        )

        # Add first session and cache sessions
        test_history.add_test_session(session1)
        _ = test_history.sessions  # Access to build cache

        # Add second session
        test_history.add_test_session(session2)

        # Cache should be invalidated
        assert test_history._all_sessions_cache is None

        # Rebuild cache and verify
        sessions = test_history.sessions
        assert len(sessions) == 2
        assert sessions == sorted([session1, session2], key=lambda s: s.session_start_time)

    def test_latest_session_across_suts(self, test_history, get_test_time):
        """Test latest_session returns most recent across all SUTs."""
        now = get_test_time()

        # Create sessions for different SUTs with different times
        sessions = [
            TestSession(
                sut_name="sut-1",
                session_id="session-1",
                session_start_time=now,
                session_stop_time=get_test_time(300),  # 5 mins later
                test_results=[],
                session_tags={"env": "test"},
            ),
            TestSession(
                sut_name="sut-2",
                session_id="session-2",
                session_start_time=get_test_time(3600),  # 1 hour later
                session_stop_time=get_test_time(3900),  # 1 hour + 5 mins later
                test_results=[],
                session_tags={"env": "prod"},
            ),
            TestSession(
                sut_name="sut-1",
                session_id="session-3",
                session_start_time=get_test_time(7200),  # 2 hours later
                session_stop_time=get_test_time(7500),  # 2 hours + 5 mins later
                test_results=[],
                session_tags={"env": "test"},
            ),
        ]

        # Add sessions in random order
        test_history.add_test_session(sessions[1])  # sut-2 middle time
        test_history.add_test_session(sessions[0])  # sut-1 earliest
        test_history.add_test_session(sessions[2])  # sut-1 latest

        # Latest session overall should be sessions[2]
        assert test_history.latest_session() == sessions[2]

        # Latest for sut-1 should be sessions[2]
        assert test_history._latest_by_sut["sut-1"] == sessions[2]

        # Latest for sut-2 should be sessions[1]
        assert test_history._latest_by_sut["sut-2"] == sessions[1]

    def test_test_history_cache_invalidation(self, get_test_time):
        """Test cache invalidation in TestHistory."""
        history = TestHistory()
        get_test_time()

        # Create test sessions with timezone-aware datetimes
        sessions = [
            TestSession(
                sut_name=f"sut-{i}",
                session_id=f"session-{i}",
                session_start_time=get_test_time(i * 3600),  # i hours later
                session_stop_time=get_test_time(i * 3600 + 300),  # i hours + 5 mins later
                test_results=[],
                session_tags={"env": "test" if i % 2 == 0 else "prod"},
            )
            for i in range(3)
        ]

        # Add sessions and verify cache behavior
        for session in sessions:
            history.add_test_session(session)
            assert session.sut_name in history._latest_by_sut
            assert history._latest_by_sut[session.sut_name] == session

        # Verify cache is updated correctly
        assert len(history._latest_by_sut) == 3
        assert all(sut in history._latest_by_sut for sut in ["sut-0", "sut-1", "sut-2"])

    def test_test_history_latest_session_by_sut(self, get_test_time):
        """Test getting latest session by SUT."""
        history = TestHistory()
        now = get_test_time()

        # Create sessions with different SUTs
        sessions = {
            "sut-1": TestSession(
                sut_name="sut-1",
                session_id="session-1",
                session_start_time=now,
                session_stop_time=get_test_time(300),  # 5 mins later
                test_results=[],
                session_tags={"env": "test"},
            ),
            "sut-2": TestSession(
                sut_name="sut-2",
                session_id="session-2",
                session_start_time=get_test_time(3600),  # 1 hour later
                session_stop_time=get_test_time(3900),  # 1 hour + 5 mins later
                test_results=[],
                session_tags={"env": "prod"},
            ),
        }

        # Add sessions and verify latest by SUT
        for session in sessions.values():
            history.add_test_session(session)

        assert history.get_sut_latest_session("sut-1") == sessions["sut-1"]
        assert history.get_sut_latest_session("sut-2") == sessions["sut-2"]
        assert history.get_sut_latest_session("non-existent") is None


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

    def test_test_result_serialization(self, get_test_time):
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

    def test_test_result_serialization(self, get_test_time):
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
        assert session.session_duration == 3600.0  # Check float duration instead of timedelta

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
        assert len([t for t in session.test_results if t.outcome == TestOutcome.PASSED]) == 1
        assert len([t for t in session.test_results if t.outcome == TestOutcome.FAILED]) == 1

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
