"""Utility functions for pytest-insight.

This module contains utility classes and functions used throughout the pytest-insight package.
"""

import datetime as dt_module
from datetime import datetime
from typing import Tuple, Union


class NormalizedDatetime:
    """Wrapper class for datetime objects that handles timezone normalization.

    Delegates all non-special attributes/methods to the underlying datetime object.
    Custom comparison and arithmetic logic is preserved for normalization.
    """

    def __init__(self, dt: dt_module.datetime):
        self.dt = dt
        self.has_tzinfo = dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None

    @classmethod
    def now(cls) -> "NormalizedDatetime":
        """Return a NormalizedDatetime for the current time (local timezone)."""
        return cls(datetime.now())

    @classmethod
    def from_iso(cls, iso_str):
        """Create a NormalizedDatetime from an ISO 8601 string."""
        return cls(dt_module.datetime.fromisoformat(iso_str))

    def to_iso(self):
        """Return ISO 8601 formatted string for the wrapped datetime."""
        return self.dt.isoformat()

    def __getattr__(self, name):
        # Delegate all unknown attributes/methods to the underlying datetime
        return getattr(self.dt, name)

    def _get_normalized_pair(
        self, other: Union["NormalizedDatetime", dt_module.datetime]
    ) -> Tuple[dt_module.datetime, dt_module.datetime]:
        if isinstance(other, NormalizedDatetime):
            other_dt = other.dt
        elif isinstance(other, datetime):
            other_dt = other
        else:
            raise TypeError(f"Cannot compare NormalizedDatetime with {type(other)}")
        return self._normalize_for_comparison(self.dt, other_dt)

    @staticmethod
    def _normalize_for_comparison(
        dt1: dt_module.datetime, dt2: dt_module.datetime
    ) -> Tuple[dt_module.datetime, dt_module.datetime]:
        dt1_has_tzinfo = dt1.tzinfo is not None and dt1.tzinfo.utcoffset(dt1) is not None
        dt2_has_tzinfo = dt2.tzinfo is not None and dt2.tzinfo.utcoffset(dt2) is not None
        if dt1_has_tzinfo == dt2_has_tzinfo:
            return dt1, dt2
        if dt1_has_tzinfo and not dt2_has_tzinfo:
            return dt1.replace(tzinfo=None), dt2
        return dt1, dt2.replace(tzinfo=None)

    def __eq__(self, other):
        if other is None:
            return False
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 == dt2

    def __ne__(self, other):
        if other is None:
            return True
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 != dt2

    def __lt__(self, other):
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 < dt2

    def __le__(self, other):
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 <= dt2

    def __gt__(self, other):
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 > dt2

    def __ge__(self, other):
        dt1, dt2 = self._get_normalized_pair(other)
        return dt1 >= dt2

    def __add__(self, other):
        if isinstance(other, dt_module.timedelta):
            return NormalizedDatetime(self.dt + other)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, dt_module.timedelta):
            return NormalizedDatetime(self.dt - other)
        elif isinstance(other, (NormalizedDatetime, dt_module.datetime)):
            dt1, dt2 = self._get_normalized_pair(other)
            return dt1 - dt2
        return NotImplemented

    def __str__(self) -> str:
        return str(self.dt)

    def __repr__(self) -> str:
        tz_status = "aware" if self.has_tzinfo else "naive"
        return f"NormalizedDatetime({self.dt}, {tz_status})"


def create_equals_filter(dt: dt_module.datetime) -> callable:
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: normalized_dt == session.session_start_time


def create_not_equals_filter(dt: dt_module.datetime) -> callable:
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: normalized_dt != session.session_start_time


def create_before_filter(dt: dt_module.datetime) -> callable:
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time < normalized_dt


def create_before_or_equals_filter(dt: dt_module.datetime) -> callable:
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time <= normalized_dt


def create_after_filter(dt: dt_module.datetime) -> callable:
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time > normalized_dt


def create_after_or_equals_filter(dt: dt_module.datetime) -> callable:
    normalized_dt = NormalizedDatetime(dt)
    return lambda session: session.session_start_time >= normalized_dt
