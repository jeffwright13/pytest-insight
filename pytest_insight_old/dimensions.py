"""Dimension classes for grouping test sessions."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from pytest_insight.filterable import DimensionFilter, FilterableDimension
from pytest_insight.models import TestSession


class ComparisonDimension(FilterableDimension):
    """Base class for dimensions used in test session comparisons."""

    pass


class SUTDimension(ComparisonDimension):
    """Group test sessions by SUT name."""

    def _group_filtered_sessions(self, sessions: List[TestSession]) -> Dict[str, List[TestSession]]:
        """Group sessions by SUT name."""
        groups: Dict[str, List[TestSession]] = {}
        for session in sessions:
            sut = session.sut_name
            if sut not in groups:
                groups[sut] = []
            groups[sut].append(session)
        return groups

    def get_key(self, session: TestSession) -> str:
        """Get the key for a session in this dimension."""
        return session.sut_name


class TimeDimension(ComparisonDimension):
    """Group test sessions by time window."""

    def __init__(self, window: timedelta, filters: Optional[List[DimensionFilter]] = None):
        """Initialize with time window."""
        super().__init__(filters)
        self.window = window

    def _group_filtered_sessions(self, sessions: List[TestSession]) -> Dict[str, List[TestSession]]:
        """Group sessions by time window."""
        if not sessions:
            return {}

        # Sort sessions by start time
        sorted_sessions = sorted(sessions, key=lambda s: s.session_start_time)

        # Find time range
        start_time = sorted_sessions[0].session_start_time
        end_time = sorted_sessions[-1].session_start_time

        # Create time windows
        windows = {}
        current = start_time
        while current <= end_time:
            window_end = current + self.window
            key = self._format_window(current, window_end)
            windows[key] = [s for s in sessions if current <= s.session_start_time < window_end]
            if not windows[key]:  # Remove empty windows
                del windows[key]
            current = window_end

        return windows

    def get_key(self, session: TestSession) -> str:
        """Get the key for a session in this dimension."""
        window_start = session.session_start_time.replace(microsecond=0)
        window_end = window_start + self.window
        return self._format_window(window_start, window_end)

    def _format_window(self, start: datetime, end: datetime) -> str:
        """Format a time window as a string."""
        return f"{start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')}"


class OutcomeDimension(ComparisonDimension):
    """Group test sessions by test outcome."""

    def _group_filtered_sessions(self, sessions: List[TestSession]) -> Dict[str, List[TestSession]]:
        """Group sessions by most common outcome."""
        groups: Dict[str, List[TestSession]] = {}
        for session in sessions:
            key = self.get_key(session)
            if key not in groups:
                groups[key] = []
            groups[key].append(session)
        return groups

    def get_key(self, session: TestSession) -> str:
        """Get the key for a session in this dimension."""
        # Count outcomes in session
        outcome_counts = {}
        for result in session.test_results:
            outcome = result.outcome.value
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

        if outcome_counts:
            # Get most common outcome
            return max(outcome_counts.items(), key=lambda x: x[1])[0]
        else:
            # Handle empty sessions
            return "NO_TESTS"


class DurationDimension(ComparisonDimension):
    """Group test sessions by duration ranges."""

    def __init__(
        self, ranges: Optional[List[Tuple[float, str]]] = None, filters: Optional[List[DimensionFilter]] = None
    ):
        """Initialize with duration ranges in seconds.

        Args:
            ranges: List of (threshold, label) tuples, sorted by threshold.
                   Default ranges are:
                   - Fast: < 1s
                   - Medium: 1s - 5s
                   - Slow: > 5s
            filters: Optional list of DimensionFilter objects
        """
        super().__init__(filters)
        self.ranges = ranges or [(1.0, "FAST"), (5.0, "MEDIUM"), (float("inf"), "SLOW")]

    def _group_filtered_sessions(self, sessions: List[TestSession]) -> Dict[str, List[TestSession]]:
        """Group sessions by average test duration."""
        groups: Dict[str, List[TestSession]] = {}
        for session in sessions:
            key = self.get_key(session)
            if key not in groups:
                groups[key] = []
            groups[key].append(session)
        return groups

    def get_key(self, session: TestSession) -> str:
        """Get the key for a session in this dimension."""
        if not session.test_results:
            return "NO_TESTS"

        # Use session duration since it's more accurate than sum of test durations
        # (includes setup/teardown time)
        return self._get_range_label(session.session_duration)

    def _get_range_label(self, duration: float) -> str:
        """Get the label for a duration value."""
        for threshold, label in self.ranges:
            if duration <= threshold:
                return label
        return self.ranges[-1][1]  # Should never happen with inf threshold


class ModuleDimension(ComparisonDimension):
    """Group test sessions by test module."""

    def _group_filtered_sessions(self, sessions: List[TestSession]) -> Dict[str, List[TestSession]]:
        """Group sessions by most common test module."""
        groups: Dict[str, List[TestSession]] = {}
        for session in sessions:
            key = self.get_key(session)
            if key not in groups:
                groups[key] = []
            groups[key].append(session)
        return groups

    def get_key(self, session: TestSession) -> str:
        """Get the key for a session in this dimension."""
        # Count modules in session
        module_counts = {}
        for result in session.test_results:
            # Extract module path from nodeid (e.g., "tests/test_foo.py::test_bar" -> "tests/test_foo.py")
            module = result.nodeid.split("::")[0]
            module_counts[module] = module_counts.get(module, 0) + 1

        if module_counts:
            # Get most common module
            return max(module_counts.items(), key=lambda x: x[1])[0]
        else:
            # Handle empty sessions
            return "NO_TESTS"
