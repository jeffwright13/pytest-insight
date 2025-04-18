"""Utility functions for pytest-insight.

This module contains utility functions used throughout the pytest-insight package.
"""

import datetime as dt_module
from datetime import datetime
from typing import Tuple, Union


class NormalizedDatetime:
    """Wrapper class for datetime objects that handles timezone normalization.

    This class wraps a datetime object and provides comparison operators that
    automatically handle timezone normalization when comparing with other
    datetime objects or NormalizedDatetime instances.
    """

    def __init__(self, dt: dt_module.datetime):
        """Initialize with a datetime object.

        Args:
            dt: The datetime object to wrap
        """
        self.dt = dt
        self.has_tzinfo = dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None

    @staticmethod
    def _normalize_for_comparison(
        dt1: dt_module.datetime, dt2: dt_module.datetime
    ) -> Tuple[dt_module.datetime, dt_module.datetime]:
        """Normalize two datetime objects for comparison.

        Args:
            dt1: First datetime to compare
            dt2: Second datetime to compare

        Returns:
            Tuple of normalized datetime objects ready for comparison
        """
        dt1_has_tzinfo = dt1.tzinfo is not None and dt1.tzinfo.utcoffset(dt1) is not None
        dt2_has_tzinfo = dt2.tzinfo is not None and dt2.tzinfo.utcoffset(dt2) is not None

        # If both have the same timezone status (both aware or both naive), return as-is
        if dt1_has_tzinfo == dt2_has_tzinfo:
            return dt1, dt2

        # If dt1 is timezone-aware but dt2 is naive, convert dt1 to naive
        if dt1_has_tzinfo and not dt2_has_tzinfo:
            return dt1.replace(tzinfo=None), dt2

        # If dt2 is timezone-aware but dt1 is naive, convert dt2 to naive
        return dt1, dt2.replace(tzinfo=None)

    def _get_normalized_pair(
        self, other: Union["NormalizedDatetime", dt_module.datetime]
    ) -> Tuple[dt_module.datetime, dt_module.datetime]:
        """Get normalized pair of datetime objects for comparison.

        Args:
            other: Another NormalizedDatetime or datetime object

        Returns:
            Tuple of normalized datetime objects
        """
        if isinstance(other, NormalizedDatetime):
            other_dt = other.dt
        elif isinstance(other, datetime):
            other_dt = other
        else:
            raise TypeError(f"Cannot compare NormalizedDatetime with {type(other)}")

        return self._normalize_for_comparison(self.dt, other_dt)

    def __eq__(self, other: Union["NormalizedDatetime", dt_module.datetime]) -> bool:
        """Equal comparison with proper timezone handling."""
        if other is None:
            return False
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 == dt2

    def __ne__(self, other: Union["NormalizedDatetime", dt_module.datetime]) -> bool:
        """Not equal comparison with proper timezone handling."""
        if other is None:
            return True
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 != dt2

    def __lt__(self, other: Union["NormalizedDatetime", dt_module.datetime]) -> bool:
        """Less than comparison with proper timezone handling."""
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 < dt2

    def __le__(self, other: Union["NormalizedDatetime", dt_module.datetime]) -> bool:
        """Less than or equal comparison with proper timezone handling."""
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 <= dt2

    def __gt__(self, other: Union["NormalizedDatetime", dt_module.datetime]) -> bool:
        """Greater than comparison with proper timezone handling."""
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 > dt2

    def __ge__(self, other: Union["NormalizedDatetime", dt_module.datetime]) -> bool:
        """Greater than or equal comparison with proper timezone handling."""
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 >= dt2

    def __sub__(self, other: Union["NormalizedDatetime", dt_module.datetime]) -> dt_module.timedelta:
        """Subtraction operator with proper timezone handling.

        Args:
            other: Another NormalizedDatetime or datetime object

        Returns:
            timedelta representing the time difference

        Raises:
            TypeError: If other is not a NormalizedDatetime or datetime
        """
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 - dt2

    def total_seconds(self) -> float:
        """Get total seconds since the epoch.

        Returns:
            Number of seconds since the epoch
        """
        return self.dt.timestamp()

    def date(self) -> dt_module.date:
        """Get the date part of the datetime.

        Returns:
            Date object representing the date part of the datetime
        """
        return self.dt.date()

    def __str__(self) -> str:
        """String representation of the datetime."""
        return str(self.dt)

    def __repr__(self) -> str:
        """Detailed representation of the NormalizedDatetime."""
        tz_status = "aware" if self.has_tzinfo else "naive"
        return f"NormalizedDatetime({self.dt}, {tz_status})"


def create_equals_filter(dt: dt_module.datetime) -> callable:
    """Create a filter function that checks if a session's start time equals a datetime."""
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: normalized_dt == session.session_start_time


def create_not_equals_filter(dt: dt_module.datetime) -> callable:
    """Create a filter function that checks if a session's start time does not equal a datetime."""
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: normalized_dt != session.session_start_time


def create_before_filter(dt: dt_module.datetime) -> callable:
    """Create a filter function that checks if a session's start time is before a datetime."""
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time < normalized_dt


def create_before_or_equals_filter(dt: dt_module.datetime) -> callable:
    """Create a filter function that checks if a session's start time is before or equal to a datetime."""
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time <= normalized_dt


def create_after_filter(dt: dt_module.datetime) -> callable:
    """Create a filter function that checks if a session's start time is after a datetime."""
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time > normalized_dt


def create_after_or_equals_filter(dt: dt_module.datetime) -> callable:
    """Create a filter function that checks if a session's start time is after or equal to a datetime."""
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time >= normalized_dt
