import datetime as dt

import pytest
from pytest_insight.utils.utils import (
    NormalizedDatetime,
    create_after_filter,
    create_after_or_equals_filter,
    create_before_filter,
    create_before_or_equals_filter,
    create_equals_filter,
    create_not_equals_filter,
)


class DummySession:
    def __init__(self, session_start_time):
        self.session_start_time = session_start_time


def test_normalized_datetime_equality():
    """
    Test equality of NormalizedDatetime objects.

    This test checks that NormalizedDatetime objects can be compared to each other
    and to datetime objects, and that the comparison is done correctly.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    dt2 = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    nd1 = NormalizedDatetime(dt1)
    nd2 = NormalizedDatetime(dt2)
    assert nd1 == dt1
    assert nd2 == dt2
    assert nd1 == nd2
    assert nd2 == nd1
    assert nd1 != dt.datetime(2024, 1, 1, 12, 1, 0)


def test_normalized_datetime_comparison():
    """
    Test comparison of NormalizedDatetime objects.

    This test checks that NormalizedDatetime objects can be compared to each other
    using the <, <=, >, and >= operators, and that the comparison is done correctly.
    """
    base = dt.datetime(2024, 1, 1, 12, 0, 0)
    later = dt.datetime(2024, 1, 1, 13, 0, 0, tzinfo=dt.timezone.utc)
    nd_base = NormalizedDatetime(base)
    nd_later = NormalizedDatetime(later)
    assert nd_base < nd_later
    assert nd_base <= nd_later
    assert nd_later > nd_base
    assert nd_later >= nd_base
    assert not (nd_base > nd_later)
    assert not (nd_base >= nd_later)


def test_normalized_datetime_subtraction():
    """
    Test subtraction of NormalizedDatetime objects.

    This test checks that subtracting one NormalizedDatetime object from another
    returns a timedelta object, and that the result is correct.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    dt2 = dt.datetime(2024, 1, 1, 13, 0, 0, tzinfo=dt.timezone.utc)
    nd1 = NormalizedDatetime(dt1)
    nd2 = NormalizedDatetime(dt2)
    delta = nd2 - nd1
    assert isinstance(delta, dt.timedelta)
    assert delta.total_seconds() == 3600


def test_normalized_datetime_total_seconds_and_date():
    """
    Test total_seconds and date methods of NormalizedDatetime objects.

    This test checks that the total_seconds method returns the correct number of
    seconds since the epoch, and that the date method returns the correct date.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    nd1 = NormalizedDatetime(dt1)
    assert abs(nd1.timestamp() - dt1.timestamp()) < 1e-6
    assert nd1.date() == dt1.date()


def test_normalized_datetime_str_and_repr():
    """
    Test str and repr methods of NormalizedDatetime objects.

    This test checks that the str method returns the same string as the str method
    of the underlying datetime object, and that the repr method returns a string
    that includes the class name.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    nd1 = NormalizedDatetime(dt1)
    assert str(nd1) == str(dt1)
    assert "NormalizedDatetime" in repr(nd1)


def test_normalized_datetime_type_errors():
    """
    Test that NormalizedDatetime objects raise TypeErrors when compared to non-datetime objects.

    This test checks that comparing a NormalizedDatetime object to a non-datetime
    object raises a TypeError.
    """
    nd1 = NormalizedDatetime(dt.datetime(2024, 1, 1, 12, 0, 0))
    with pytest.raises(TypeError):
        nd1 == "not a datetime"
    with pytest.raises(TypeError):
        nd1._get_normalized_pair("not a datetime")
    with pytest.raises(TypeError):
        nd1 - "not a datetime"


def test_create_equals_filter():
    """
    Test create_equals_filter function.

    This test checks that the create_equals_filter function returns a filter that
    returns True when the session start time is equal to the specified time, and
    False otherwise.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    filt = create_equals_filter(dt1)
    session = DummySession(dt1)
    assert filt(session)
    session2 = DummySession(dt.datetime(2024, 1, 1, 13, 0, 0))
    assert not filt(session2)


def test_create_not_equals_filter():
    """
    Test create_not_equals_filter function.

    This test checks that the create_not_equals_filter function returns a filter
    that returns False when the session start time is equal to the specified time,
    and True otherwise.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    filt = create_not_equals_filter(dt1)
    session = DummySession(dt1)
    assert not filt(session)
    session2 = DummySession(dt.datetime(2024, 1, 1, 13, 0, 0))
    assert filt(session2)


def test_create_before_filter():
    """
    Test create_before_filter function.

    This test checks that the create_before_filter function returns a filter that
    returns True when the session start time is before the specified time, and
    False otherwise.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    filt = create_before_filter(dt1)
    session = DummySession(dt.datetime(2024, 1, 1, 11, 59, 59))
    assert filt(session)
    session2 = DummySession(dt.datetime(2024, 1, 1, 12, 0, 0))
    assert not filt(session2)


def test_create_before_or_equals_filter():
    """
    Test create_before_or_equals_filter function.

    This test checks that the create_before_or_equals_filter function returns a
    filter that returns True when the session start time is before or equal to the
    specified time, and False otherwise.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    filt = create_before_or_equals_filter(dt1)
    session = DummySession(dt.datetime(2024, 1, 1, 12, 0, 0))
    assert filt(session)
    session2 = DummySession(dt.datetime(2024, 1, 1, 12, 0, 1))
    assert not filt(session2)


def test_create_after_filter():
    """
    Test create_after_filter function.

    This test checks that the create_after_filter function returns a filter that
    returns True when the session start time is after the specified time, and
    False otherwise.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    filt = create_after_filter(dt1)
    session = DummySession(dt.datetime(2024, 1, 1, 12, 0, 1))
    assert filt(session)
    session2 = DummySession(dt.datetime(2024, 1, 1, 12, 0, 0))
    assert not filt(session2)


def test_create_after_or_equals_filter():
    """
    Test create_after_or_equals_filter function.

    This test checks that the create_after_or_equals_filter function returns a
    filter that returns True when the session start time is after or equal to the
    specified time, and False otherwise.
    """
    dt1 = dt.datetime(2024, 1, 1, 12, 0, 0)
    filt = create_after_or_equals_filter(dt1)
    session = DummySession(dt.datetime(2024, 1, 1, 12, 0, 0))
    assert filt(session)
    session2 = DummySession(dt.datetime(2024, 1, 1, 11, 59, 59))
    assert not filt(session2)


def test_normalized_datetime_now(monkeypatch):
    """Test that NormalizedDatetime.now() returns a NormalizedDatetime wrapping the current datetime."""
    import datetime as dt

    from pytest_insight.utils.utils import NormalizedDatetime

    # Patch datetime.now to return a fixed value
    fixed_now = dt.datetime(2025, 4, 18, 19, 0, 0)

    class FixedDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.replace(tzinfo=tz)

    monkeypatch.setattr("pytest_insight.utils.utils.datetime", FixedDatetime)

    print("NormalizedDatetime loaded from:", NormalizedDatetime.__module__)
    print("Class dict:", dir(NormalizedDatetime))
    nd_now = NormalizedDatetime.now()
    assert isinstance(nd_now, NormalizedDatetime)
    assert nd_now.dt == fixed_now
    # Should be equal to NormalizedDatetime(fixed_now)
    assert nd_now == NormalizedDatetime(fixed_now)
