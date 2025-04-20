"""
filters.py: Pattern and regex-based test filters for pytest-insight v2.
Ported from v1 for context-preserving test/session queries.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from pytest_insight.core.models import TestResult


class InvalidQueryParameterError(Exception):
    """Raised when a filter receives invalid parameters."""

    pass


@dataclass
class ShellPatternFilter:
    """Filter tests using simple substring pattern matching."""

    pattern: str
    field_name: str
    ALLOWED_FIELDS = {"nodeid", "caplog", "capstdout", "capstderr", "longreprtext"}

    def __post_init__(self):
        if not isinstance(self.pattern, str) or not self.pattern:
            raise InvalidQueryParameterError("Pattern must be a non-empty string.")
        if not isinstance(self.field_name, str) or self.field_name not in self.ALLOWED_FIELDS:
            raise InvalidQueryParameterError(f"Invalid field name: {self.field_name}")

    def matches(self, test: TestResult) -> bool:
        field_value = str(getattr(test, self.field_name, ""))
        return self.pattern in field_value

    def to_dict(self) -> Dict[str, str]:
        return {
            "type": "SHELL_PATTERN",
            "pattern": self.pattern,
            "field_name": self.field_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "ShellPatternFilter":
        if "pattern" not in data:
            raise ValueError("Missing required key 'pattern' in data")
        if "field_name" not in data:
            raise ValueError("Missing required key 'field_name' in data")
        return cls(pattern=data["pattern"], field_name=data["field_name"])


@dataclass
class RegexPatternFilter:
    """Filter tests using regex pattern matching against any string field."""

    pattern: str
    field_name: str = "nodeid"
    _compiled_regex: Optional[re.Pattern] = field(default=None, init=False)

    def __post_init__(self):
        if not self.pattern:
            raise InvalidQueryParameterError("Pattern cannot be empty")
        try:
            self._compiled_regex = re.compile(self.pattern)
        except re.error as e:
            raise InvalidQueryParameterError(f"Invalid regex pattern: {e}")

    def matches(self, test: TestResult) -> bool:
        field_value = str(getattr(test, self.field_name, ""))
        return bool(self._compiled_regex.search(field_value))

    def to_dict(self) -> Dict:
        return {
            "type": "REGEX_PATTERN",
            "pattern": self.pattern,
            "field_name": self.field_name,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RegexPatternFilter":
        instance = cls(pattern=data["pattern"], field_name=data.get("field_name", "nodeid"))
        instance._compiled_regex = re.compile(instance.pattern)
        return instance
