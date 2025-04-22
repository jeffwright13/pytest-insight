"""Tests for utility functions in pytest_insight.utils.utils."""

import datetime
from datetime import timedelta, timezone

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


class TestNormalizedDatetime:
    """Tests for the NormalizedDatetime class."""

    def test_init(self):
        """Test initialization of NormalizedDatetime."""
        # Test with naive datetime
        dt_naive = datetime.datetime(2023, 1, 1, 12, 0, 0)
        nd_naive = NormalizedDatetime(dt_naive)
        assert nd_naive.dt == dt_naive
        assert nd_naive.has_tzinfo is False

        # Test with timezone-aware datetime
        dt_aware = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        nd_aware = NormalizedDatetime(dt_aware)
        assert nd_aware.dt == dt_aware
        assert nd_aware.has_tzinfo is True

    def test_equality_comparison(self):
        """Test equality comparison (__eq__, __ne__)."""
        # Same naive datetimes
        dt1 = datetime.datetime(2023, 1, 1, 12, 0, 0)
        dt2 = datetime.datetime(2023, 1, 1, 12, 0, 0)
        nd1 = NormalizedDatetime(dt1)
        nd2 = NormalizedDatetime(dt2)
        assert nd1 == nd2
        assert not (nd1 != nd2)
        assert nd1 == dt2
        assert not (nd1 != dt2)

        # Different naive datetimes
        dt3 = datetime.datetime(2023, 1, 1, 13, 0, 0)
        nd3 = NormalizedDatetime(dt3)
        assert nd1 != nd3
        assert not (nd1 == nd3)
        assert nd1 != dt3
        assert not (nd1 == dt3)

        # Same time, one naive and one aware
        dt4 = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        nd4 = NormalizedDatetime(dt4)
        assert nd1 == nd4  # Should normalize and compare equal
        assert not (nd1 != nd4)

        # None comparison
        assert nd1 is not None
        assert nd1 is not None

    def test_ordering_comparison(self):
        """Test ordering comparison (__lt__, __le__, __gt__, __ge__)."""
        dt1 = datetime.datetime(2023, 1, 1, 12, 0, 0)
        dt2 = datetime.datetime(2023, 1, 1, 13, 0, 0)
        dt3 = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        nd1 = NormalizedDatetime(dt1)
        nd2 = NormalizedDatetime(dt2)
        nd3 = NormalizedDatetime(dt3)

        # Less than
        assert nd1 < nd2
        assert nd1 < dt2
        assert not (nd2 < nd1)
        assert not (nd2 < dt1)

        # Less than or equal
        assert nd1 <= nd2
        assert nd1 <= dt2
        assert nd1 <= nd1
        assert nd1 <= dt1
        assert not (nd2 <= nd1)
        assert not (nd2 <= dt1)

        # Greater than
        assert nd2 > nd1
        assert nd2 > dt1
        assert not (nd1 > nd2)
        assert not (nd1 > dt2)

        # Greater than or equal
        assert nd2 >= nd1
        assert nd2 >= dt1
        assert nd1 >= nd1
        assert nd1 >= dt1
        assert not (nd1 >= nd2)
        assert not (nd1 >= dt2)

        # Timezone-aware comparison
        assert not (nd1 < nd3)  # Should be equal after normalization
        assert nd1 <= nd3
        assert not (nd1 > nd3)
        assert nd1 >= nd3

    def test_subtraction(self):
        """Test subtraction operation (__sub__)."""
        # Test subtraction between two naive datetimes
        dt1 = datetime.datetime(2023, 1, 1, 12, 0, 0)
        dt2 = datetime.datetime(2023, 1, 1, 13, 0, 0)
        nd1 = NormalizedDatetime(dt1)
        nd2 = NormalizedDatetime(dt2)

        # NormalizedDatetime - NormalizedDatetime
        delta = nd2 - nd1
        assert isinstance(delta, timedelta)
        assert delta.total_seconds() == 3600  # 1 hour difference

        # NormalizedDatetime - datetime
        delta = nd2 - dt1
        assert isinstance(delta, timedelta)
        assert delta.total_seconds() == 3600

        # Test with timezone-aware datetimes
        dt3 = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt4 = datetime.datetime(2023, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        nd3 = NormalizedDatetime(dt3)
        nd4 = NormalizedDatetime(dt4)

        delta = nd4 - nd3
        assert delta.total_seconds() == 3600

        # Test mixed timezone-aware and naive
        delta = nd3 - dt1  # UTC aware - naive
        assert delta.total_seconds() == 0  # Should normalize and be equal

        # Test with different timezones
        eastern = timezone(timedelta(hours=-5))
        dt5 = datetime.datetime(2023, 1, 1, 7, 0, 0, tzinfo=eastern)  # 12:00 UTC
        nd5 = NormalizedDatetime(dt5)

        delta = nd4 - nd5  # 13:00 UTC - 12:00 UTC
        assert delta.total_seconds() == 3600

    def test_total_seconds(self):
        """Test total_seconds method."""
        # Create a datetime with a known timestamp
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        nd = NormalizedDatetime(dt)

        # Get the expected timestamp
        expected_timestamp = dt.timestamp()

        # Test the total_seconds method
        assert nd.total_seconds() == expected_timestamp

    def test_string_representation(self):
        """Test string representation (__str__, __repr__)."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        nd = NormalizedDatetime(dt)

        # Test __str__
        assert str(nd) == str(dt)

        # Test __repr__
        assert repr(nd) == f"NormalizedDatetime({dt}, naive)"

        dt_aware = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        nd_aware = NormalizedDatetime(dt_aware)
        assert repr(nd_aware) == f"NormalizedDatetime({dt_aware}, aware)"

    def test_error_handling(self):
        """Test error handling for invalid operations."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        nd = NormalizedDatetime(dt)

        # Test comparison with invalid type
        with pytest.raises(TypeError):
            nd == "not a datetime"

        with pytest.raises(TypeError):
            nd < "not a datetime"

        with pytest.raises(TypeError):
            nd - "not a datetime"


class TestDatetimeFilters:
    """Tests for the datetime filter creation functions."""

    # We'll create a simple mock session class for testing
    class MockSession:
        def __init__(self, start_time):
            self.session_start_time = start_time

    def test_equals_filter(self):
        """Test create_equals_filter function."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        filter_func = create_equals_filter(dt)

        # Test with equal datetime
        session1 = self.MockSession(dt)
        assert filter_func(session1) is True

        # Test with different datetime
        session2 = self.MockSession(datetime.datetime(2023, 1, 1, 13, 0, 0))
        assert filter_func(session2) is False

        # Test with timezone-aware equal datetime
        session3 = self.MockSession(
            datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        assert filter_func(session3) is True

    def test_not_equals_filter(self):
        """Test create_not_equals_filter function."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        filter_func = create_not_equals_filter(dt)

        # Test with equal datetime
        session1 = self.MockSession(dt)
        assert filter_func(session1) is False

        # Test with different datetime
        session2 = self.MockSession(datetime.datetime(2023, 1, 1, 13, 0, 0))
        assert filter_func(session2) is True

    def test_before_filter(self):
        """Test create_before_filter function."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        filter_func = create_before_filter(dt)

        # Test with earlier datetime
        session1 = self.MockSession(datetime.datetime(2023, 1, 1, 11, 0, 0))
        assert filter_func(session1) is True

        # Test with equal datetime
        session2 = self.MockSession(dt)
        assert filter_func(session2) is False

        # Test with later datetime
        session3 = self.MockSession(datetime.datetime(2023, 1, 1, 13, 0, 0))
        assert filter_func(session3) is False

    def test_before_or_equals_filter(self):
        """Test create_before_or_equals_filter function."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        filter_func = create_before_or_equals_filter(dt)

        # Test with earlier datetime
        session1 = self.MockSession(datetime.datetime(2023, 1, 1, 11, 0, 0))
        assert filter_func(session1) is True

        # Test with equal datetime
        session2 = self.MockSession(dt)
        assert filter_func(session2) is True

        # Test with later datetime
        session3 = self.MockSession(datetime.datetime(2023, 1, 1, 13, 0, 0))
        assert filter_func(session3) is False

    def test_after_filter(self):
        """Test create_after_filter function."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        filter_func = create_after_filter(dt)

        # Test with earlier datetime
        session1 = self.MockSession(datetime.datetime(2023, 1, 1, 11, 0, 0))
        assert filter_func(session1) is False

        # Test with equal datetime
        session2 = self.MockSession(dt)
        assert filter_func(session2) is False

        # Test with later datetime
        session3 = self.MockSession(datetime.datetime(2023, 1, 1, 13, 0, 0))
        assert filter_func(session3) is True

    def test_after_or_equals_filter(self):
        """Test create_after_or_equals_filter function."""
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0)
        filter_func = create_after_or_equals_filter(dt)

        # Test with earlier datetime
        session1 = self.MockSession(datetime.datetime(2023, 1, 1, 11, 0, 0))
        assert filter_func(session1) is False

        # Test with equal datetime
        session2 = self.MockSession(dt)
        assert filter_func(session2) is True

        # Test with later datetime
        session3 = self.MockSession(datetime.datetime(2023, 1, 1, 13, 0, 0))
        assert filter_func(session3) is True
