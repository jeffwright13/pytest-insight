import datetime as dt
from types import SimpleNamespace

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


def test_normalized_datetime_init_and_str():
    naive = dt.datetime(2023, 1, 1, 12, 0, 0)
    aware = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    nd_naive = NormalizedDatetime(naive)
    nd_aware = NormalizedDatetime(aware)
    assert str(nd_naive) == str(naive)
    assert str(nd_aware) == str(aware)
    assert "naive" in repr(nd_naive)
    assert "aware" in repr(nd_aware)


def test_normalized_datetime_now():
    nd = NormalizedDatetime.now()
    assert isinstance(nd, NormalizedDatetime)


def test_normalized_datetime_from_iso_and_json():
    iso = "2023-01-01T12:00:00+00:00"
    nd = NormalizedDatetime.from_iso(iso)
    assert nd.dt == dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    # from_json None
    assert NormalizedDatetime.from_json(None) is None
    # from_json datetime
    d = dt.datetime(2023, 1, 1, 12, 0, 0)
    nd2 = NormalizedDatetime.from_json(d)
    assert isinstance(nd2, NormalizedDatetime)
    # from_json iso string
    nd3 = NormalizedDatetime.from_json(iso)
    assert nd3.dt == dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    # from_json already NormalizedDatetime
    nd4 = NormalizedDatetime.from_json(nd3)
    assert nd4 is nd3


def test_normalized_datetime_to_iso_and_json():
    aware = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    nd = NormalizedDatetime(aware)
    assert nd.to_iso() == aware.isoformat()
    assert nd.to_json().endswith("Z")
    naive = dt.datetime(2023, 1, 1, 12, 0, 0)
    nd2 = NormalizedDatetime(naive)
    assert nd2.to_json() == naive.isoformat()


def test_normalized_datetime_comparisons():
    base = dt.datetime(2023, 1, 1, 12, 0, 0)
    nd = NormalizedDatetime(base)
    nd2 = NormalizedDatetime(base)
    later = NormalizedDatetime(base + dt.timedelta(hours=1))
    assert nd == nd2
    assert nd != later
    assert nd < later
    assert nd <= later
    assert later > nd
    assert later >= nd
    # Compare with datetime
    assert nd == base
    assert not (nd != base)
    assert nd < base + dt.timedelta(hours=1)
    # Compare with None
    assert nd is not None
    assert nd is not None


def test_normalized_datetime_arithmetic():
    base = dt.datetime(2023, 1, 1, 12, 0, 0)
    nd = NormalizedDatetime(base)
    one_hour = dt.timedelta(hours=1)
    nd2 = nd + one_hour
    assert isinstance(nd2, NormalizedDatetime)
    assert nd2.dt == base + one_hour
    nd3 = nd2 - one_hour
    assert nd3.dt == base
    # Subtract two NormalizedDatetime
    diff = nd2 - nd
    assert diff == one_hour
    # Subtract datetime
    diff2 = nd2 - base
    assert diff2 == one_hour


def test_normalized_datetime_type_errors():
    nd = NormalizedDatetime(dt.datetime(2023, 1, 1, 12, 0, 0))
    with pytest.raises(TypeError):
        nd._get_normalized_pair("not a datetime")
    assert nd.__add__("not a timedelta") is NotImplemented
    assert nd.__sub__("not a datetime") is NotImplemented


def test_normalized_datetime_getattr_delegation():
    d = dt.datetime(2023, 1, 1, 12, 34, 56)
    nd = NormalizedDatetime(d)
    # Should delegate .year, .month, .day, .hour, etc.
    assert nd.year == 2023
    assert nd.month == 1
    assert nd.day == 1
    assert nd.hour == 12
    assert nd.minute == 34
    assert nd.second == 56


def test_normalized_datetime_naive_aware_comparison():
    naive = dt.datetime(2023, 1, 1, 12, 0, 0)
    aware = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
    nd_naive = NormalizedDatetime(naive)
    nd_aware = NormalizedDatetime(aware)
    # Should compare equal when times match (after normalization)
    assert nd_naive == aware.replace(tzinfo=None)
    assert nd_aware == naive.replace(tzinfo=None)
    # Should compare less/greater as expected
    later_aware = dt.datetime(2023, 1, 1, 13, 0, 0, tzinfo=dt.timezone.utc)
    nd_later_aware = NormalizedDatetime(later_aware)
    assert nd_naive < nd_later_aware
    assert nd_later_aware > nd_naive


def make_session(dt_obj):
    return SimpleNamespace(session_start_time=dt_obj)


def test_create_equals_filter():
    d = dt.datetime(2023, 1, 1, 12, 0, 0)
    f = create_equals_filter(d)
    assert f(make_session(d))
    assert not f(make_session(d + dt.timedelta(seconds=1)))


def test_create_not_equals_filter():
    d = dt.datetime(2023, 1, 1, 12, 0, 0)
    f = create_not_equals_filter(d)
    assert not f(make_session(d))
    assert f(make_session(d + dt.timedelta(seconds=1)))


def test_create_before_filter():
    d = dt.datetime(2023, 1, 1, 12, 0, 0)
    f = create_before_filter(d)
    assert f(make_session(d - dt.timedelta(seconds=1)))
    assert not f(make_session(d))


def test_create_before_or_equals_filter():
    d = dt.datetime(2023, 1, 1, 12, 0, 0)
    f = create_before_or_equals_filter(d)
    assert f(make_session(d - dt.timedelta(seconds=1)))
    assert f(make_session(d))
    assert not f(make_session(d + dt.timedelta(seconds=1)))


def test_create_after_filter():
    d = dt.datetime(2023, 1, 1, 12, 0, 0)
    f = create_after_filter(d)
    assert f(make_session(d + dt.timedelta(seconds=1)))
    assert not f(make_session(d))


def test_create_after_or_equals_filter():
    d = dt.datetime(2023, 1, 1, 12, 0, 0)
    f = create_after_or_equals_filter(d)
    assert f(make_session(d + dt.timedelta(seconds=1)))
    assert f(make_session(d))
    assert not f(make_session(d - dt.timedelta(seconds=1)))
