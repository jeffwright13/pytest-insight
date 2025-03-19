"""Test the pytest-insight plugin functionality."""

from datetime import timedelta

import pytest
from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.query import InvalidQueryParameterError, Query
from pytest_insight.storage import InMemoryStorage


class Test_SessionCapture:
    """Test capturing of test sessions and results.

    Core functionality for the Query and Compare operations.
    """

    def test_basic_session_capture(self, test_session_basic):
        """Test that basic test session is captured with proper context."""
        storage = InMemoryStorage()
        storage.save_session(test_session_basic)

        # Verify session was captured with proper context
        sessions = storage.load_sessions()
        assert len(sessions) == 1

        session = sessions[0]
        assert len(session.test_results) == len(test_session_basic.test_results)
        assert (
            session.test_results[0].outcome
            == test_session_basic.test_results[0].outcome
        )
        assert session.session_start_time < session.session_stop_time

    def test_test_result_context(self, test_result_fail):
        """Test that test results maintain full context for analysis."""
        storage = InMemoryStorage()
        session = TestSession(
            sut_name="test-service",
            session_id="test-456",
            session_start_time=test_result_fail.start_time,
            session_stop_time=test_result_fail.start_time + timedelta(seconds=1),
            test_results=[test_result_fail],
            rerun_test_groups=[],
            session_tags={},
        )
        storage.save_session(session)

        # Verify test context is preserved for analysis
        sessions = storage.load_sessions()
        test_result = sessions[0].test_results[0]

        assert test_result.outcome == TestOutcome.FAILED
        assert test_result.capstdout
        assert test_result.caplog
        assert test_result.capstderr

    def test_session_metadata(self, test_session_basic):
        """Test that session metadata is preserved for querying."""
        storage = InMemoryStorage()
        session = test_session_basic
        session.session_tags = {"env": "test", "branch": "main"}
        storage.save_session(session)

        # Verify metadata for query operations
        sessions = storage.load_sessions()
        session = sessions[0]

        assert session.sut_name == test_session_basic.sut_name
        assert session.session_tags["env"] == "test"
        assert session.session_tags["branch"] == "main"
        assert len(session.test_results) == len(test_session_basic.test_results)

    def test_empty_session_handling(self, get_test_time):
        """Test handling of sessions with no test results."""
        storage = InMemoryStorage()
        test_time = get_test_time()
        session = TestSession(
            sut_name="empty-service",
            session_id="empty-123",
            session_start_time=test_time,
            session_stop_time=test_time + timedelta(seconds=1),
            test_results=[],
            rerun_test_groups=[],
            session_tags={},
        )
        storage.save_session(session)

        # Verify empty session handling
        sessions = storage.load_sessions()
        assert len(sessions) == 1
        assert len(sessions[0].test_results) == 0
        assert sessions[0].session_id == "empty-123"


class Test_QueryOperations:
    """Test the Query operation functionality."""

    def test_sut_filtering(self, test_session_basic):
        """Test filtering sessions by SUT."""
        storage = InMemoryStorage()
        storage.save_session(test_session_basic)

        # Test Query operation
        query = Query(storage=storage)
        result = query.for_sut("test-service").execute()

        assert len(result.sessions) == 1
        assert result.sessions[0].sut_name == "test-service"

    def test_outcome_filtering(self, test_session_basic, test_result_fail):
        """Test filtering by test outcome while preserving context."""
        storage = InMemoryStorage()
        storage.save_session(test_session_basic)
        session = TestSession(
            sut_name="test-service",
            session_id="test-456",
            session_start_time=test_result_fail.start_time,
            session_stop_time=test_result_fail.start_time + timedelta(seconds=1),
            test_results=[test_result_fail],
            rerun_test_groups=[],
            session_tags={},
        )
        storage.save_session(session)

        # Test two-level filtering
        query = Query(storage=storage)
        result = (
            query.filter_by_test().with_outcome(TestOutcome.PASSED).apply().execute()
        )

        assert len(result.sessions) == 1
        session = result.sessions[0]
        assert len(session.test_results) == 1
        assert session.test_results[0].outcome == TestOutcome.PASSED

    def test_invalid_sut_filter(self, test_session_basic):
        """Test error handling for invalid SUT filter."""
        storage = InMemoryStorage()
        storage.save_session(test_session_basic)

        query = Query(storage=storage)
        with pytest.raises(InvalidQueryParameterError) as exc_info:
            query.for_sut("").execute()
        assert "SUT name must be a non-empty string" in str(exc_info.value)

    def test_multiple_session_handling(self, test_session_basic, test_result_fail):
        """Test handling multiple test sessions with different outcomes."""
        storage = InMemoryStorage()
        storage.save_session(test_session_basic)
        session = TestSession(
            sut_name="test-service",
            session_id="test-456",
            session_start_time=test_result_fail.start_time,
            session_stop_time=test_result_fail.start_time + timedelta(seconds=1),
            test_results=[test_result_fail],
            rerun_test_groups=[],
            session_tags={},
        )
        storage.save_session(session)

        # Test filtering with multiple sessions
        query = Query(storage=storage)
        result = (
            query.filter_by_test().with_outcome(TestOutcome.FAILED).apply().execute()
        )

        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "test-456"
        assert result.sessions[0].test_results[0].outcome == TestOutcome.FAILED

    def test_complex_query_chain(self, test_session_basic, test_result_fail):
        """Test complex query chaining with multiple filters."""
        storage = InMemoryStorage()
        storage.save_session(test_session_basic)
        session = TestSession(
            sut_name="test-service",
            session_id="test-456",
            session_start_time=test_result_fail.start_time,
            session_stop_time=test_result_fail.start_time + timedelta(seconds=1),
            test_results=[test_result_fail],
            rerun_test_groups=[],
            session_tags={},
        )
        storage.save_session(session)

        # Test complex query chain
        query = Query(storage=storage)
        result = (
            query.for_sut("test-service")
            .filter_by_test()
            .with_outcome(TestOutcome.PASSED)
            .with_nodeid_containing("basic")  # Use new explicit method
            .apply()
            .execute()
        )

        assert len(result.sessions) == 1
        assert (
            result.sessions[0].test_results[0].nodeid == "test_example.py::test_basic"
        )


class Test_StorageConfiguration:
    """Test storage configuration for persistence."""

    def test_storage_path_validation(self, tester, tmp_path):
        """Test storage path validation."""
        # Create a test file to ensure we have tests to run
        tester.makepyfile(
            """
            def test_example():
                assert True
            """
        )

        invalid_path = tmp_path / "nonexistent" / "test.json"
        result = tester.runpytest("--insight", f"--insight-json-path={invalid_path}")
        assert result.ret != 0  # Should fail on invalid path
        assert "Invalid storage path" in result.stderr.str()  # Verify error message

    def test_storage_type_validation(self, tester, tmp_path):
        """Test storage type validation."""
        # Create a test file to ensure we have tests to run
        tester.makepyfile(
            """
            def test_example():
                assert True
            """
        )

        # Test with invalid storage type
        result = tester.runpytest("--insight", "--insight-storage-type=invalid")
        assert result.ret != 0  # Should fail with invalid storage type

    def test_json_storage_creation(self, tester, tmp_path):
        """Test JSON storage creation and initialization."""
        # Create a test file to ensure we have tests to run
        tester.makepyfile(
            """
            def test_example():
                assert True
            """
        )

        # Create valid storage directory
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        storage_path = storage_dir / "test.json"

        # Run with valid storage path
        result = tester.runpytest("--insight", f"--insight-json-path={storage_path}")
        assert result.ret == 0  # Should succeed with valid path
        assert storage_path.exists()  # Storage file should be created

    def test_storage_path_permissions(self, tester, tmp_path):
        """Test storage path permission validation."""
        # Create a test file to ensure we have tests to run
        tester.makepyfile(
            """
            def test_example():
                assert True
            """
        )

        # Create read-only directory
        storage_dir = tmp_path / "readonly"
        storage_dir.mkdir()
        storage_path = storage_dir / "test.json"
        storage_dir.chmod(0o555)  # Read and execute only

        # Run with read-only directory
        result = tester.runpytest("--insight", f"--insight-json-path={storage_path}")
        assert result.ret != 0  # Should fail with read-only directory
        assert "is not writable" in result.stderr.str()  # Verify error message

    def test_storage_path_file_exists(self, tester, tmp_path):
        """Test handling of existing storage files."""
        # Create a test file to ensure we have tests to run
        tester.makepyfile(
            """
            def test_example():
                assert True
            """
        )

        # Create storage directory and file
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        storage_path = storage_dir / "test.json"
        storage_path.write_text("{}")  # Create empty JSON file

        # Run with existing file
        result = tester.runpytest("--insight", f"--insight-json-path={storage_path}")
        assert result.ret == 0  # Should succeed with existing file
