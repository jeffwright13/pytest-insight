from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from pytest_insight.models import TestResult, TestSession
from pytest_insight.query.query_builder import InvalidQueryParameterError, Query, QueryExecutionError


class Test_Query:
    """Test suite for Query builder functionality."""

    def test_query_initialization(self):
        """Test basic query initialization."""
        query = Query()
        assert query is not None
        assert query._filters == []
        assert query._results is None

    def test_for_sut_filter(self, mock_session_no_reruns):
        """Test filtering by SUT name."""
        query = Query().for_sut("test_sut")
        results = query.execute([mock_session_no_reruns])
        assert len(results) == 1
        assert results[0].sut_name == "test_sut"

    def test_for_sut_validation(self):
        """Test SUT name validation."""
        query = Query()
        with pytest.raises(InvalidQueryParameterError, match="non-empty string"):
            query.for_sut("")
        with pytest.raises(InvalidQueryParameterError, match="non-empty string"):
            query.for_sut(None)

    def test_in_last_days(self, mock_session_no_reruns):
        """Test filtering by days."""
        # Create old session
        old_session = TestSession(
            sut_name="test_sut",
            session_id="old-123",
            session_start_time=datetime.now() - timedelta(days=10),
            session_stop_time=datetime.now() - timedelta(days=10),
            test_results=[],
            rerun_test_groups=[],
        )

        query = Query().in_last_days(7)
        results = query.execute([mock_session_no_reruns, old_session])
        assert len(results) == 1
        assert results[0].session_id == mock_session_no_reruns.session_id

    def test_with_outcome(self, mock_session_no_reruns):
        """Test filtering by test outcome."""
        # Add test results with different outcomes
        mock_session_no_reruns.test_results.extend(
            [
                TestResult(nodeid="test_pass.py::test_pass", outcome="PASSED", start_time=datetime.now(), duration=1.0),
                TestResult(nodeid="test_fail.py::test_fail", outcome="FAILED", start_time=datetime.now(), duration=1.0),
            ]
        )

        query = Query().with_outcome("PASSED")
        results = query.execute([mock_session_no_reruns])
        assert len(results) == 1
        assert any(t.outcome == "PASSED" for t in results[0].test_results)

    def test_having_warnings(self, mock_session_no_reruns):
        """Test filtering by warning presence."""
        mock_session_no_reruns.test_results.append(
            TestResult(
                nodeid="test_warn.py::test_warning",
                outcome="PASSED",
                start_time=datetime.now(),
                duration=1.0,
                has_warning=True,
            )
        )

        query = Query().having_warnings(True)
        results = query.execute([mock_session_no_reruns])
        assert len(results) == 1
        assert any(t.has_warning for t in results[0].test_results)

    def test_with_reruns(self, mock_session_w_reruns, mock_session_no_reruns):
        """Test filtering by rerun presence."""
        query = Query().with_reruns(True)
        results = query.execute([mock_session_w_reruns, mock_session_no_reruns])
        assert len(results) == 1
        assert results[0].rerun_test_groups

    def test_test_contains(self, mock_session_no_reruns):
        """Test filtering by test name pattern."""
        mock_session_no_reruns.test_results.append(
            TestResult(nodeid="test_api.py::test_endpoint", outcome="PASSED", start_time=datetime.now(), duration=1.0)
        )

        query = Query().test_contains("api")
        results = query.execute([mock_session_no_reruns])
        assert len(results) == 1
        assert any("api" in t.nodeid for t in results[0].test_results)

    def test_chained_filters(self, static_test_session_list):
        """Test combining multiple filters."""
        query = Query().for_sut("test_sut").in_last_days(7).with_reruns(False)
        results = query.execute(static_test_session_list)
        assert len(results) == 7

    def test_execution_error_handling(self):
        """Test query execution error handling."""
        query = Query().for_sut("test_sut")

        # Mock storage to raise an error
        mock_storage = Mock()
        mock_storage.load_sessions.side_effect = Exception("Storage error")

        with patch("pytest_insight.query.query_builder.get_storage_instance", return_value=mock_storage):
            # Test storage failure
            with pytest.raises(QueryExecutionError, match="Failed to load sessions"):
                query.execute()

            # Test invalid session type
            with pytest.raises(QueryExecutionError, match="Invalid session type"):
                query.execute([{"not": "a session"}])

            # Test non-list input (other than None)
            with pytest.raises(QueryExecutionError, match="must be provided as a list"):
                query.execute("not a list")

    def test_execute_default_loads_sessions(self):
        """Test that execute() loads sessions from storage by default."""
        mock_storage = Mock()
        mock_storage.load_sessions.return_value = []

        with patch("pytest_insight.query.query_builder.get_storage_instance", return_value=mock_storage):
            Query().execute()
            mock_storage.load_sessions.assert_called_once()

    def test_execute_storage_error(self):
        """Test error handling when storage fails."""
        mock_storage = Mock()
        mock_storage.load_sessions.side_effect = Exception("Storage error")

        with patch("pytest_insight.query.query_builder.get_storage_instance", return_value=mock_storage):
            with pytest.raises(QueryExecutionError, match="Failed to load sessions"):
                Query().execute()

    def test_execute_with_custom_sessions(self):
        """Test that execute() uses provided sessions instead of loading from storage."""
        mock_storage = Mock()

        with patch("pytest_insight.query.query_builder.get_storage_instance", return_value=mock_storage):
            Query().execute([])  # Pass empty list explicitly
            mock_storage.load_sessions.assert_not_called()

    def test_execute_integration(self, mock_session_no_reruns):
        """Test full query execution with default session loading."""
        mock_storage = Mock()
        mock_storage.load_sessions.return_value = [mock_session_no_reruns]

        with patch("pytest_insight.query.query_builder.get_storage_instance", return_value=mock_storage):
            results = (
                Query().for_sut("test_sut").in_last_days(7).execute()  # Use default session loading
            )

            assert len(results) == 1
            assert results[0].sut_name == "test_sut"
            mock_storage.load_sessions.assert_called_once()
