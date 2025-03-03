from datetime import datetime, timedelta
import pytest

from pytest_insight.query.builder import Query
from pytest_insight.models import TestSession, TestResult, TestOutcome

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

    def test_with_outcome_filter(self, mock_session_no_reruns):
        """Test filtering by test outcome."""
        # Add a failed test to the session
        mock_session_no_reruns.test_results.append(
            TestResult(
                nodeid="test_fail.py::test_failure",
                outcome="FAILED",
                start_time=datetime.now(),
                duration=1.0
            )
        )

        query = Query().with_outcome("FAILED")
        results = query.execute([mock_session_no_reruns])
        assert len(results) == 1
        assert any(t.outcome == "FAILED" for t in results[0].test_results)

    def test_having_warnings_filter(self, mock_session_no_reruns):
        """Test filtering by warning presence."""
        mock_session_no_reruns.test_results.append(
            TestResult(
                nodeid="test_warn.py::test_warning",
                outcome="PASSED",
                start_time=datetime.now(),
                duration=1.0,
                has_warning=True
            )
        )

        query = Query().having_warnings(True)
        results = query.execute([mock_session_no_reruns])
        assert len(results) == 1
        assert any(t.has_warning for t in results[0].test_results)

    def test_with_reruns_filter(self, mock_session_w_reruns):
        """Test filtering by rerun presence."""
        query = Query().with_reruns(True)
        results = query.execute([mock_session_w_reruns])
        assert len(results) == 1
        assert len(results[0].rerun_test_groups) > 0

    def test_test_contains_filter(self, mock_session_no_reruns):
        """Test filtering by test name pattern."""
        mock_session_no_reruns.test_results.append(
            TestResult(
                nodeid="test_api.py::test_endpoint",
                outcome="PASSED",
                start_time=datetime.now(),
                duration=1.0
            )
        )

        query = Query().test_contains("api")
        results = query.execute([mock_session_no_reruns])
        assert len(results) == 1
        assert any("api" in t.nodeid for t in results[0].test_results)
