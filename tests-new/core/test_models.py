from datetime import datetime, timedelta
import pytest
from pytest_insight.models import TestResult, TestSession

class TestTimingBehavior:
    """Test timing behavior for TestResult and TestSession."""

    def test_test_result_with_duration(self):
        """Test initializing TestResult with duration."""
        start = datetime.now()
        result = TestResult(
            nodeid="test_example",
            outcome="passed",
            start_time=start,
            duration=5.0
        )

        assert result.stop_time == start + timedelta(seconds=5.0)
        assert result.duration == 5.0

    def test_test_result_with_stop_time(self):
        """Test initializing TestResult with stop_time."""
        start = datetime.now()
        stop = start + timedelta(seconds=5.0)
        result = TestResult(
            nodeid="test_example",
            outcome="passed",
            start_time=start,
            stop_time=stop
        )

        assert result.stop_time == stop
        assert result.duration == 5.0

    def test_test_result_missing_timing(self):
        """Test TestResult requires either stop_time or duration."""
        with pytest.raises(ValueError, match="Either stop_time or duration must be provided"):
            TestResult(
                nodeid="test_example",
                outcome="passed",
                start_time=datetime.now()
            )

    def test_test_session_with_duration(self):
        """Test initializing TestSession with duration."""
        start = datetime.now()
        session = TestSession(
            sut_name="my-sut",
            session_id="session-1",
            session_start_time=start,
            session_duration=10.0
        )

        assert session.session_stop_time == start + timedelta(seconds=10.0)
        assert session.session_duration == 10.0

    def test_test_session_with_stop_time(self):
        """Test initializing TestSession with stop_time."""
        start = datetime.now()
        stop = start + timedelta(seconds=10.0)
        session = TestSession(
            sut_name="my-sut",
            session_id="session-1",
            session_start_time=start,
            session_stop_time=stop
        )

        assert session.session_stop_time == stop
        assert session.session_duration == 10.0

    def test_test_session_missing_timing(self):
        """Test TestSession requires either stop_time or duration."""
        with pytest.raises(ValueError, match="Either session_stop_time or session_duration must be provided"):
            TestSession(
                sut_name="my-sut",
                session_id="session-1",
                session_start_time=datetime.now()
            )
