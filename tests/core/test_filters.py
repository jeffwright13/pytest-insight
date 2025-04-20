"""
Unit tests for ShellPatternFilter and RegexPatternFilter in pytest-insight v2.
Covers matching logic, error handling, and edge cases.
"""
from types import SimpleNamespace

import pytest
from pytest_insight.core.filters import InvalidQueryParameterError, RegexPatternFilter, ShellPatternFilter


@pytest.mark.parametrize(
    "pattern,field_name,field_value,expected",
    [
        ("foo", "nodeid", "foobar", True),
        ("bar", "nodeid", "foobar", True),
        ("baz", "nodeid", "foobar", False),
        ("", "nodeid", "foobar", False),
        ("log", "caplog", "log output", True),
        ("err", "capstderr", "error message", True),
        ("err", "capstdout", "no error", True),
    ],
)
def test_shell_pattern_filter_matching(pattern, field_name, field_value, expected):
    if pattern == "":
        with pytest.raises(InvalidQueryParameterError):
            ShellPatternFilter(pattern=pattern, field_name=field_name)
        return
    f = ShellPatternFilter(pattern=pattern, field_name=field_name)
    fake_test = SimpleNamespace(**{field_name: field_value})
    assert f.matches(fake_test) is expected


def test_shell_pattern_filter_invalid_field():
    with pytest.raises(InvalidQueryParameterError):
        ShellPatternFilter(pattern="foo", field_name="invalid_field")


@pytest.mark.parametrize(
    "pattern,field_name,field_value,expected",
    [
        (r"foo.*bar", "nodeid", "foo123bar", True),
        (r"^test_.*", "nodeid", "test_func", True),
        (r"baz$", "nodeid", "foobar", False),
        (r"[0-9]+", "caplog", "log 123", True),
        (r"error", "capstderr", "no error", True),
        (r"error", "capstdout", "all good", False),
    ],
)
def test_regex_pattern_filter_matching(pattern, field_name, field_value, expected):
    f = RegexPatternFilter(pattern=pattern, field_name=field_name)
    fake_test = SimpleNamespace(**{field_name: field_value})
    assert f.matches(fake_test) is expected


def test_regex_pattern_filter_invalid_pattern():
    with pytest.raises(InvalidQueryParameterError):
        RegexPatternFilter(pattern="[", field_name="nodeid")


def test_regex_pattern_filter_empty_pattern():
    with pytest.raises(InvalidQueryParameterError):
        RegexPatternFilter(pattern="", field_name="nodeid")
