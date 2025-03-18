"""Test the pytest-insight plugin functionality."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query import Query, InvalidQueryParameterError
from pytest_insight.storage import InMemoryStorage


@pytest.fixture
def basic_test_session():
    """Create a basic test session with a single passing test."""
    test_time = datetime.now(timezone.utc)  # Use UTC for consistent timezone handling
    test_result = TestResult(
        nodeid="test_example.py::test_basic",
        outcome=TestOutcome.PASSED,
        start_time=test_time,
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
    )
    return TestSession(
        sut_name="test-service",
        session_id="test-123",
        session_start_time=test_time,
        session_stop_time=test_time + timedelta(seconds=1),
        test_results=[test_result],
        rerun_test_groups=[],
        session_tags={},  # Initialize empty tags
    )


@pytest.fixture
def failed_test_session():
    """Create a test session with a failing test that has output."""
    test_time = datetime.now(timezone.utc)  # Use UTC for consistent timezone handling
    test_result = TestResult(
        nodeid="test_example.py::test_failing",
        outcome=TestOutcome.FAILED,
        start_time=test_time,
        duration=0.1,
        caplog="log message",
        capstderr="stderr message",
        capstdout="stdout message",
    )
    return TestSession(
        sut_name="test-service",
        session_id="test-456",
        session_start_time=test_time,
        session_stop_time=test_time + timedelta(seconds=1),
        test_results=[test_result],
        rerun_test_groups=[],
        session_tags={},  # Initialize empty tags
    )


@pytest.fixture
def empty_test_session():
    """Create an empty test session for edge case testing."""
    test_time = datetime.now(timezone.utc)
    return TestSession(
        sut_name="empty-service",
        session_id="empty-123",
        session_start_time=test_time,
        session_stop_time=test_time + timedelta(seconds=1),
        test_results=[],
        rerun_test_groups=[],
        session_tags={},
    )


class Test_SessionCapture:
    """Test capturing of test sessions and results.

    Core functionality for the Query and Compare operations.
    """

    def test_basic_session_capture(self, basic_test_session):
        """Test that basic test session is captured with proper context."""
        storage = InMemoryStorage()
        storage.save_session(basic_test_session)

        # Verify session was captured with proper context
        sessions = storage.load_sessions()
        assert len(sessions) == 1

        session = sessions[0]
        assert len(session.test_results) == 1
        assert session.test_results[0].outcome == TestOutcome.PASSED
        assert session.session_start_time < session.session_stop_time

    def test_test_result_context(self, failed_test_session):
        """Test that test results maintain full context for analysis."""
        storage = InMemoryStorage()
        storage.save_session(failed_test_session)

        # Verify test context is preserved for analysis
        sessions = storage.load_sessions()
        test_result = sessions[0].test_results[0]

        assert test_result.outcome == TestOutcome.FAILED
        assert "stdout message" in test_result.capstdout
        assert "log message" in test_result.caplog
        assert "stderr message" in test_result.capstderr

    def test_session_metadata(self, basic_test_session):
        """Test that session metadata is preserved for querying."""
        storage = InMemoryStorage()
        session = basic_test_session
        session.session_tags = {"env": "test", "branch": "main"}
        storage.save_session(session)

        # Verify metadata for query operations
        sessions = storage.load_sessions()
        session = sessions[0]

        assert session.sut_name == "test-service"
        assert session.session_tags["env"] == "test"
        assert session.session_tags["branch"] == "main"
        assert len(session.test_results) == 1

    def test_empty_session_handling(self, empty_test_session):
        """Test handling of sessions with no test results."""
        storage = InMemoryStorage()
        storage.save_session(empty_test_session)

        # Verify empty session handling
        sessions = storage.load_sessions()
        assert len(sessions) == 1
        assert len(sessions[0].test_results) == 0
        assert sessions[0].session_id == "empty-123"


class Test_QueryOperations:
    """Test the Query operation functionality."""

    def test_sut_filtering(self, basic_test_session):
        """Test filtering sessions by SUT."""
        storage = InMemoryStorage()
        storage.save_session(basic_test_session)

        # Test Query operation
        query = Query(storage=storage)
        result = query.for_sut("test-service").execute()

        assert len(result.sessions) == 1
        assert result.sessions[0].sut_name == "test-service"

    def test_outcome_filtering(self, basic_test_session, failed_test_session):
        """Test filtering by test outcome while preserving context."""
        storage = InMemoryStorage()
        storage.save_session(basic_test_session)
        storage.save_session(failed_test_session)

        # Test two-level filtering
        query = Query(storage=storage)
        result = (
            query.filter_by_test()
            .with_outcome(TestOutcome.PASSED)
            .apply()
            .execute()
        )

        assert len(result.sessions) == 1
        session = result.sessions[0]
        assert len(session.test_results) == 1
        assert session.test_results[0].outcome == TestOutcome.PASSED

    def test_invalid_sut_filter(self, basic_test_session):
        """Test error handling for invalid SUT filter."""
        storage = InMemoryStorage()
        storage.save_session(basic_test_session)

        query = Query(storage=storage)
        with pytest.raises(InvalidQueryParameterError) as exc_info:
            query.for_sut("").execute()
        assert "SUT name must be a non-empty string" in str(exc_info.value)

    def test_multiple_session_handling(self, basic_test_session, failed_test_session):
        """Test handling multiple test sessions with different outcomes."""
        storage = InMemoryStorage()
        storage.save_session(basic_test_session)
        storage.save_session(failed_test_session)

        # Test filtering with multiple sessions
        query = Query(storage=storage)
        result = query.filter_by_test().with_outcome(TestOutcome.FAILED).apply().execute()

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "test-456"
        assert result.sessions[0].test_results[0].outcome == TestOutcome.FAILED

    def test_complex_query_chain(self, basic_test_session, failed_test_session):
        """Test complex query chaining with multiple filters."""
        storage = InMemoryStorage()
        storage.save_session(basic_test_session)
        storage.save_session(failed_test_session)

        # Test complex query chain
        query = Query(storage=storage)
        result = (
            query.for_sut("test-service")
            .filter_by_test()
            .with_outcome(TestOutcome.PASSED)
            .with_pattern("*basic")
            .apply()
            .execute()
        )

        assert len(result.sessions) == 1
        assert result.sessions[0].test_results[0].nodeid == "test_example.py::test_basic"


class Test_StorageConfiguration:
    """Test storage configuration for persistence."""

    def test_storage_path_validation(self, testdir, tmp_path):
        """Test storage path validation."""
        # Create a test file to ensure we have tests to run
        testdir.makepyfile(
            """
            def test_example():
                assert True
            """
        )

        invalid_path = tmp_path / "nonexistent" / "test.json"
        result = testdir.runpytest("--insight", f"--insight-json-path={invalid_path}")
        assert result.ret != 0  # Should fail on invalid path
        assert "Invalid storage path" in result.stderr.str()  # Verify error message

    def test_storage_type_validation(self, testdir, tmp_path):
        """Test storage type validation."""
        testdir.makepyfile(
            """
            def test_example():
                assert True
            """
        )
        storage_path = tmp_path / "test.json"

        # Test valid storage type
        result = testdir.runpytest(
            "--insight",
            f"--insight-json-path={storage_path}",
            "--insight-storage-type=json"
        )
        assert result.ret == 0  # Should succeed with valid type

        # Test invalid storage type
        result = testdir.runpytest(
            "--insight",
            f"--insight-json-path={storage_path}",
            "--insight-storage-type=invalid"
        )
        assert result.ret != 0  # Should fail with invalid type
        assert "invalid choice: 'invalid'" in result.stderr.str()  # Verify error message from pytest

    def test_storage_initialization(self, testdir, tmp_path):
        """Test storage initialization with test session data."""
        testdir.makepyfile(
            """
            def test_pass():
                assert True
            def test_fail():
                assert False
            """
        )
        storage_path = tmp_path / "test.json"

        # Run tests and verify storage contains session data
        result = testdir.runpytest(
            "--insight",
            f"--insight-json-path={storage_path}",
            "--insight-storage-type=json"
        )
        assert result.ret == 1  # One test fails
        assert storage_path.exists()  # Storage file created

        # Verify stored data
        with open(storage_path) as f:
            data = json.load(f)
            assert len(data["sessions"]) == 1
            session = data["sessions"][0]
            assert len(session["test_results"]) == 2
            assert any(t["outcome"] == "passed" for t in session["test_results"])
            assert any(t["outcome"] == "failed" for t in session["test_results"])

    def test_concurrent_storage_access(self, testdir, tmp_path):
        """Test concurrent access to storage."""
        testdir.makepyfile(
            """
            import pytest

            @pytest.mark.parallel
            def test_one():
                assert True

            @pytest.mark.parallel
            def test_two():
                assert True
            """
        )
        storage_path = tmp_path / "test.json"

        # Run tests with parallel marker
        result = testdir.runpytest(
            "--insight",
            f"--insight-json-path={storage_path}",
            "-v",
            "-n", "2"  # Run with 2 workers
        )
        assert result.ret == 0
        assert storage_path.exists()

        # Verify stored data integrity
        with open(storage_path) as f:
            data = json.load(f)
            assert len(data["sessions"]) >= 1  # At least one session
            assert all(isinstance(s["test_results"], list) for s in data["sessions"])
