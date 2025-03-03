import pytest
from pytest_mock import MockerFixture

from pytest_insight.models import TestSession, TestResult, TestOutcome
from pytest_insight.filters import TestFilter

class Test_TestFilter:
    """Test suite for TestFilter functionality."""

    def test_filter_initialization(self, mock_session_no_reruns):
        """Test basic initialization of TestFilter with no criteria."""
        test_filter = TestFilter()
        assert test_filter is not None
        # Start with simplest possible test - filter accepts everything
        assert test_filter.matches(mock_session_no_reruns)
