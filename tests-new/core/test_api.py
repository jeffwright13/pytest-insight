from datetime import datetime, timedelta
import pytest
from pytest_insight.core.api import InsightAPI
from pytest_insight.models import TestResult, TestSession

class TestInsightAPI:
    """Test suite for public API."""

    def test_get_session_summary(self, storage, test_session):
        """Test session summary retrieval."""
        # Setup
        storage.save_session(test_session)
        api = InsightAPI(storage)

        # Execute
        summary = api.get_session_summary(test_session.session_id)

        # Verify
        assert "metrics" in summary
        assert "trends" in summary
        assert "patterns" in summary

        metrics = summary["metrics"]
        assert "failure_rate" in metrics
        assert isinstance(metrics["failure_rate"], float)
        assert "total_count" in metrics
        assert isinstance(metrics["total_count"], int)
        assert "avg_duration" in metrics
        assert isinstance(metrics["avg_duration"], float)
        assert "min_duration" in metrics
        assert isinstance(metrics["min_duration"], float)
        assert "max_duration" in metrics
        assert isinstance(metrics["max_duration"], float)

    def test_get_trend_analysis(self, storage, test_session):
        """Test trend analysis retrieval."""
        # Setup
        storage.save_session(test_session)
        api = InsightAPI(storage)

        # Execute
        analysis = api.get_trend_analysis(timedelta(days=1))

        # Verify
        assert "duration_trend" in analysis
        assert "outcome_trend" in analysis
        assert "failure_rate" in analysis

        duration_trend = analysis["duration_trend"]
        assert duration_trend["trend"] in ["increasing", "decreasing", "stable"]
        assert len(duration_trend["data_points"]) == 3

    def test_get_trend_analysis_with_data(self, storage, random_test_session):
        """Test trend analysis with actual data."""
        # Setup
        storage.save_session(random_test_session)
        api = InsightAPI(storage)

        # Execute
        analysis = api.get_trend_analysis(timedelta(days=1))

        # Verify trend with data
        duration_trend = analysis["duration_trend"]
        assert duration_trend["trend"] in ["increasing", "decreasing", "stable"]
        assert len(duration_trend["data_points"]) == len(random_test_session.test_results)

    def test_get_session_summary_nonexistent(self, storage):
        """Test handling of nonexistent session."""
        api = InsightAPI(storage)
        summary = api.get_session_summary("nonexistent-session")
        assert summary == {}

    def test_get_trend_analysis_empty_timespan(self, storage):
        """Test trend analysis with no data in timespan."""
        api = InsightAPI(storage)
        analysis = api.get_trend_analysis(timedelta(minutes=1))

        # Check empty data response
        assert analysis["duration_trend"]["trend"] == "insufficient_data"
        assert len(analysis["duration_trend"]["data_points"]) == 0
        assert analysis["outcome_trend"]["trend"] == "insufficient_data"
        assert analysis["failure_rate"] == 0.0
