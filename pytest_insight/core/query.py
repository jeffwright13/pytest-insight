"""Query class for filtering and retrieving test sessions.

The Query class implements a two-level filtering design:
1. Session-Level: Filter entire test sessions (SUT, time range, has warnings)
2. Test-Level: Filter by test properties (nodeid, duration, outcome)

Key Behaviors:
1. Session-Level Filtering:
   - Returns collection of *existing* TestSession objects that match session filter criteria
   - No modification of tests (TestResult objects) within matching sessions

2. Test-Level Filtering:
   - Returns *new* TestSession objects containing only matching tests
   - Preserves session metadata (ID, tags, timing, etc.)
   - A session is included if it has at least one matching test
   - Non-matching tests are excluded from the results

3. Filter Accumulation:
   - IMPORTANT: Filters accumulate when chaining methods on the same Query instance
   - All filters are applied with AND logic (all conditions must be met)
   - To apply independent filters, create new Query instances for each filter set
   - Once execute() is called, the Query instance retains all previously added filters

4. Storage Profile Support:
   - Queries can be executed against specific storage profiles
   - Use with_profile() to switch profiles during query building
   - Profiles can be specified at initialization or via environment variables

Examples:
    # Session-level only; returns existing sessions that match criteria
    # Get TestSessions for the last 7 days for all SUTs with 'service' in name
    query = Query()
    query.for_sut("service")
        .in_last_days(7)
        .execute()

    # Test-level only; returns new session instances, identical to original sessions, but only those that match criteria
    # Retrieve all tests that failed with duration > 10 seconds
    query = Query()
    query.filter_by_test()
        .with_duration_between(10.0, float("inf"))
        .with_outcome(TestOutcome.FAILED)
        .apply()  # Back to session context
        .execute()

    # Combining session and test filters
    query = Query()
    query.for_sut("service").in_last_days(14)
        .filter_by_test()
        .with_duration_between(5.0, 10.0)
        .apply()
        .execute()

    # Using a specific profile
    query = Query()
    query.with_profile("prod").in_last_days(7).execute()

    # IMPORTANT: Filters accumulate, so these are NOT equivalent:

    # Example 1: Single query with two filters (returns sessions with BOTH env=prod AND region=us-east)
    query = Query(storage)
    result = query.with_session_tag("env", "prod").with_session_tag("region", "us-east").execute()

    # Example 2: Separate queries (returns different results for each filter independently)
    query1 = Query(storage)
    result1 = query1.with_session_tag("env", "prod").execute()

    query2 = Query(storage)
    result2 = query2.with_session_tag("region", "us-east").execute()
"""

import dataclasses
import datetime as dt_module
import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum, auto

# Import the real datetime class for isinstance checks
from typing import Callable, Dict, List, Optional, Protocol, Union

from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.storage import get_storage_instance
from pytest_insight.utils.utils import (
    create_after_filter,
    create_after_or_equals_filter,
    create_before_filter,
    create_before_or_equals_filter,
)


class InvalidQueryParameterError(Exception):
    """Raised when query parameters are invalid."""


class QueryExecutionError(Exception):
    """Raised when query execution fails."""


class FilterType(Enum):
    """Types of filters supported by the query system."""

    SHELL_PATTERN = auto()
    REGEX_PATTERN = auto()
    DURATION = auto()
    OUTCOME = auto()
    CUSTOM = auto()


class TestFilter(Protocol):
    """Protocol defining the interface for test filters."""

    def matches(self, test: TestResult) -> bool:
        """Check if a test matches this filter."""
        ...

    def to_dict(self) -> Dict:
        """Convert filter to dictionary for serialization."""
        ...

    @classmethod
    def from_dict(cls, data: Dict) -> "TestFilter":
        """Create filter from dictionary."""
        ...


@dataclass
class ShellPatternFilter:
    """Filter tests using simple substring pattern matching.

    Key aspects:
    1. Pattern Matching:
       - Simple case-sensitive substring match
       - field_name parameter is required
       - No special handling for any fields
       - No automatic wildcards or transformations

    2. Field Validation:
       - Field names must be valid test result attributes
       - Common fields: nodeid, caplog, capstdout, capstderr, longreprtext
       - Invalid fields raise InvalidQueryParameterError

    3. Pattern Validation:
       - Pattern must be a non-empty string
       - No type conversion or coercion
       - Invalid patterns raise InvalidQueryParameterError
    """

    pattern: str
    field_name: str

    ALLOWED_FIELDS = {"nodeid", "caplog", "capstderr", "capstdout", "longreprtext"}

    def __post_init__(self):
        """Validate pattern and field name."""
        if not isinstance(self.pattern, str):
            raise InvalidQueryParameterError(
                f"Invalid pattern type: {type(self.pattern)}"
            )

        if not self.pattern:
            raise InvalidQueryParameterError("Pattern cannot be empty")

        if not isinstance(self.field_name, str):
            raise InvalidQueryParameterError(
                f"Invalid field_name type: {type(self.field_name)}"
            )

        if self.field_name not in self.ALLOWED_FIELDS:
            raise InvalidQueryParameterError(f"Invalid field name: {self.field_name}")

    def matches(self, test: TestResult) -> bool:
        """Check if test matches the pattern using simple substring matching.

        Args:
            test: TestResult to check for match

        Returns:
            True if pattern is found in the specified field, False otherwise
        """
        field_value = str(getattr(test, self.field_name, ""))
        return self.pattern in field_value

    def to_dict(self) -> Dict[str, str]:
        """Convert filter to dictionary for serialization."""
        return {
            "type": FilterType.SHELL_PATTERN.name,
            "pattern": self.pattern,
            "field_name": self.field_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "ShellPatternFilter":
        """Create filter from dictionary.

        Args:
            data: Dictionary containing filter parameters

        Returns:
            New ShellPatternFilter instance

        Raises:
            ValueError: If required parameters are missing
            InvalidQueryParameterError: If parameters are invalid
        """
        if "pattern" not in data:
            raise ValueError("Missing required key 'pattern' in data")

        if "field_name" not in data:
            raise ValueError("Missing required key 'field_name' in data")

        return cls(pattern=data["pattern"], field_name=data["field_name"])


@dataclass
class RegexPatternFilter:
    """Filter tests using regex pattern matching against any string field.

    Pattern matching rules:
    - Pattern is used as-is (no automatic wildcards)
    - Pattern is matched against the specified field value
    - For nodeid field, matches full nodeid as a single string
    """

    pattern: str
    field_name: str = "nodeid"  # Default to nodeid for backward compatibility
    _compiled_regex: Optional[re.Pattern] = field(default=None, init=False)

    def __post_init__(self):
        """Validate and compile pattern."""
        if not self.pattern:
            raise InvalidQueryParameterError("Pattern cannot be empty")

        try:
            self._compiled_regex = re.compile(self.pattern)
        except re.error as e:
            raise InvalidQueryParameterError(f"Invalid regex pattern: {e}")

    def matches(self, test: TestResult) -> bool:
        """Check if test matches the regex pattern."""
        field_value = str(getattr(test, self.field_name, ""))  # Default to empty string
        return bool(self._compiled_regex.search(field_value))

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.REGEX_PATTERN.name,
            "pattern": self.pattern,
            "field_name": self.field_name,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RegexPatternFilter":
        """Create from dictionary."""
        instance = cls(
            pattern=data["pattern"], field_name=data.get("field_name", "nodeid")
        )
        instance._compiled_regex = re.compile(instance.pattern)
        return instance


@dataclass
class DurationFilter:
    """Filter tests by duration range."""

    min_seconds: float
    max_seconds: float

    def __post_init__(self):
        """Validate duration bounds."""
        if self.min_seconds < 0:
            raise InvalidQueryParameterError("min_seconds must be >= 0")
        if self.max_seconds < self.min_seconds:
            raise InvalidQueryParameterError("max_seconds must be >= min_seconds")

    def matches(self, test: TestResult) -> bool:
        """Check if test duration is within range."""
        return self.min_seconds <= test.duration <= self.max_seconds

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.DURATION.name,
            "min_seconds": self.min_seconds,
            "max_seconds": self.max_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DurationFilter":
        """Create from dictionary, ensuring validation via dataclasses.replace."""
        instance = cls(
            min_seconds=data["min_seconds"],
            max_seconds=data["max_seconds"],
        )
        return dataclasses.replace(instance)  # Triggers __post_init__


@dataclass
class OutcomeFilter:
    """Filter tests by outcome."""

    outcome: TestOutcome

    def __post_init__(self):
        """Validate outcome."""
        if not isinstance(self.outcome, TestOutcome):
            try:
                self.outcome = TestOutcome.from_str(str(self.outcome))
            except ValueError as e:
                raise InvalidQueryParameterError(f"Invalid outcome: {e}")

    def matches(self, test: TestResult) -> bool:
        """Check if test outcome matches.

        Handles both string and enum outcomes by converting to TestOutcome.
        """
        test_outcome = test.outcome
        if isinstance(test_outcome, str):
            test_outcome = TestOutcome.from_str(test_outcome)
        return test_outcome == self.outcome

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "type": FilterType.OUTCOME.name,
            "outcome": self.outcome.value,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "OutcomeFilter":
        """Create from dictionary with validation."""
        outcome_str = data.get("outcome")
        if not outcome_str:
            raise InvalidQueryParameterError("Outcome field is required")

        return cls(outcome=TestOutcome.from_str(outcome_str))


@dataclass
class CustomFilter:
    """Filter tests using a custom predicate."""

    predicate: Callable[[TestResult], bool]
    name: str

    def matches(self, test: TestResult) -> bool:
        """Apply custom predicate."""
        return self.predicate(test)

    def to_dict(self) -> Dict:
        """Convert to dictionary with a predicate description."""
        return {
            "type": FilterType.CUSTOM.name,
            "name": self.name,
            "predicate_repr": repr(self.predicate),  # Stores function representation
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CustomFilter":
        """Create from dictionary."""
        raise NotImplementedError("Custom filters cannot be deserialized")


class QueryResult:
    """Results from a query execution.

    QueryResult always contains full TestSession objects to preserve session context
    (warnings, reruns, relationships). When test-level filters are applied, it
    returns sessions containing matching tests, never isolated TestResult objects.
    """

    def __init__(self, sessions: List[TestSession]):
        """Initialize QueryResult.

        Args:
            sessions: List of matching TestSession objects
        """
        self.sessions = sessions

    @property
    def empty(self) -> bool:
        """Check if query returned no results."""
        return len(self.sessions) == 0

    def __iter__(self):
        """Iterate over matching sessions."""
        return iter(self.sessions)

    def __len__(self):
        """Get number of matching sessions."""
        return len(self.sessions)

    def __bool__(self):
        """Convert to boolean (True if has results)."""
        return bool(self.sessions)


class QueryTestFilter:
    """Builder for test-level filters.

    Test-level filters are applied to individual tests within a session, but always
    return full sessions to preserve context. A session is included if it contains
    at least one test that matches all test filters.

    IMPORTANT: QueryTestFilter returns full TestSession objects, never isolated
    TestResult objects. This preserves session context (warnings, reruns, relationships)
    for analysis. Note that the returned sessions may not contain all tests from the
    original sessions, only those that match the test filters, and as such represent
    NEW sessions with only matching tests.
    """

    def __init__(self, query: "Query"):
        """Initialize test filter builder."""
        self.query = query
        self.filters: List[TestFilter] = []

    def with_pattern(
        self, pattern: str, *, field_name: str, use_regex: bool = False
    ) -> "QueryTestFilter":
        """Filter tests by pattern matching against any string field.

        Key aspects:
        1. Pattern Matching:
           - Simple substring or regex pattern matching
           - Case-sensitive comparison
           - field_name parameter is required
           - No special handling for any fields

        2. Field Validation:
           - Field names must be valid test result attributes
           - Common fields: nodeid, caplog, capstdout, capstderr, longreprtext
           - Invalid fields raise InvalidQueryParameterError

        3. Filter Chain:
           - Returns full TestSession objects, each populated with matching tests
           - Preserves session context (warnings, reruns)
           - Never returns isolated TestResult objects

        Args:
            pattern: Pattern to match against test field
            field_name: Field to match against (required)
            use_regex: Whether to use regex matching (default: False)

        Returns:
            QueryTestFilter instance for chaining (may be one of two types: substring
            or regex pattern filter)

        Raises:
            TypeError: If pattern is not a string
            InvalidQueryParameterError: If field_name is invalid or empty
        """
        if not isinstance(pattern, str):
            raise TypeError(f"Invalid pattern type: {type(pattern)}")

        if not isinstance(field_name, str) or not field_name:
            raise InvalidQueryParameterError("field_name parameter is required")

        if not pattern:
            raise InvalidQueryParameterError("Pattern cannot be empty")

        filter_cls = RegexPatternFilter if use_regex else ShellPatternFilter
        self.filters.append(filter_cls(pattern=pattern, field_name=field_name))
        return self

    def with_nodeid_containing(
        self, pattern: str, use_regex: bool = False
    ) -> "QueryTestFilter":
        """Filter tests by pattern in nodeid.

        This is a convenience method that sets field_name="nodeid".
        See with_pattern() for full pattern matching documentation.

        Args:
            pattern: Pattern to match against nodeid
            use_regex: Whether to use regex matching (default: False)

        Returns:
            QueryTestFilter instance for chaining
        """
        return self.with_pattern(pattern, field_name="nodeid", use_regex=use_regex)

    def with_output_containing(
        self, pattern: str, use_regex: bool = False
    ) -> "QueryTestFilter":
        """Filter tests by pattern in any output field.

        This is a convenience method that checks all output fields.
        An 'output field' in pytest is any of capstdout, capstderr, caplog.

        Args:
            pattern: Pattern to match in output
            use_regex: Whether to use regex matching (default: False)

        Returns:
            QueryTestFilter instance for chaining
        """
        for fld in ["capstdout", "capstderr", "caplog"]:
            self.with_pattern(pattern, field_name=fld, use_regex=use_regex)
        return self

    def with_error_containing(
        self, pattern: str, use_regex: bool = False
    ) -> "QueryTestFilter":
        """Filter tests by pattern in error output (longreprtext).

        This is a convenience method that sets field_name="longreprtext".
        See with_pattern() for full pattern matching documentation.

        Args:
            pattern: Pattern to match in error output
            use_regex: Whether to use regex matching (default: False)

        Returns:
            QueryTestFilter instance for chaining
        """
        return self.with_pattern(
            pattern, field_name="longreprtext", use_regex=use_regex
        )

    def with_log_containing(
        self, pattern: str, use_regex: bool = False
    ) -> "QueryTestFilter":
        """Filter tests by pattern in log output (caplog).

        This is a convenience method that sets field_name="caplog".
        See with_pattern() for full pattern matching documentation.

        Args:
            pattern: Pattern to match in log output
            use_regex: Whether to use regex matching (default: False)

        Returns:
            QueryTestFilter instance for chaining
        """
        return self.with_pattern(pattern, field_name="caplog", use_regex=use_regex)

    def with_stdout_containing(
        self, pattern: str, use_regex: bool = False
    ) -> "QueryTestFilter":
        """Filter tests by pattern in stdout (capstdout).

        This is a convenience method that sets field_name="capstdout".
        See with_pattern() for full pattern matching documentation.

        Args:
            pattern: Pattern to match in stdout
            use_regex: Whether to use regex matching (default: False)

        Returns:
            QueryTestFilter instance for chaining
        """
        return self.with_pattern(pattern, field_name="capstdout", use_regex=use_regex)

    def with_stderr_containing(
        self, pattern: str, use_regex: bool = False
    ) -> "QueryTestFilter":
        """Filter tests by pattern in stderr (capstderr).

        This is a convenience method that sets field_name="capstderr".
        See with_pattern() for full pattern matching documentation.

        Args:
            pattern: Pattern to match in stderr
            use_regex: Whether to use regex matching (default: False)

        Returns:
            QueryTestFilter instance for chaining
        """
        return self.with_pattern(pattern, field_name="capstderr", use_regex=use_regex)

    def with_warning(self, has_warning: bool = True) -> "QueryTestFilter":
        """Filter tests by warning presence.

        Test-level filter that:
        1. Returns sessions containing ANY test with warning
        2. Creates new sessions with only tests containing warnings
        3. Maintains session context (metadata, relationships)

        Args:
            has_warning: If True, keep tests with warnings. If False, keep tests without warnings.

        Returns:
            QueryTestFilter instance for chaining
        """

        def warning_predicate(test: TestResult) -> bool:
            return bool(test.has_warning) == has_warning

        return self.with_custom_filter(
            warning_predicate, name=f"warning_filter(has_warning={has_warning})"
        )

    def with_duration_between(
        self, min_seconds: float, max_seconds: float
    ) -> "QueryTestFilter":
        """Filter tests by duration range.

        Test-level filter that:
        1. Returns sessions containing ANY test within the duration range
        2. Creates new sessions with only tests within the duration range
        3. Maintains session context (metadata, relationships)

        Args:
            min_seconds: Minimum duration in seconds
            max_seconds: Maximum duration in seconds

        Returns:
            QueryTestFilter instance for chaining
        """
        self.filters.append(DurationFilter(min_seconds, max_seconds))
        return self

    def with_outcome(self, outcome: Union[str, TestOutcome]) -> "QueryTestFilter":
        """Filter tests by outcome.

        Test-level filter that:
        1. Returns sessions containing ANY test with the specified outcome
        2. Creates new sessions with only tests with the specified outcome
        3. Maintains session context (metadata, relationships)

        Args:
            outcome: Test outcome to filter by (str or TestOutcome)

        Returns:
            QueryTestFilter instance for chaining
        """
        self.filters.append(OutcomeFilter(outcome))
        return self

    def with_custom_filter(
        self, predicate: Callable[[TestResult], bool], name: str
    ) -> "QueryTestFilter":
        """Add custom test filter.

        Test-level filter that:
        1. Returns sessions containing ANY test matching the predicate
        2. Creates new sessions with only tests matching the predicate
        3. Maintains session context (metadata, relationships)

        Args:
            predicate: Callable that takes a TestResult and returns a boolean
            name: Name for the filter (used in error messages)

        Returns:
            QueryTestFilter instance for chaining
        """
        self.filters.append(CustomFilter(predicate, name))
        return self

    def apply(self) -> "Query":
        """Apply test filters and return to session context.

        Key aspects:
        1. Filter Logic:
           - All filters use AND logic
           - A test must match ALL filters to be included
           - No special handling for output vs non-output filters

        2. Context Preservation:
           - Returns full TestSession objects, each populated with matching tests
           - Preserves session metadata (warnings, reruns)
           - Never returns isolated TestResult objects

        Returns:
            Query instance for chaining
        """
        if not self.filters:
            return self.query

        # Store test filters directly in Query._test_filters
        # This ensures test-level filtering creates new sessions with only matching tests
        self.query._test_filters.extend(self.filters)
        return self.query

    def to_dict(self) -> Dict:
        """Convert filters to dictionary."""
        return {
            "filters": [
                f.to_dict() for f in self.filters if not isinstance(f, CustomFilter)
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict, query: "Query") -> "QueryTestFilter":
        """Create filters from dictionary."""
        filter_types = {
            FilterType.SHELL_PATTERN.name: ShellPatternFilter,
            FilterType.REGEX_PATTERN.name: RegexPatternFilter,
            FilterType.DURATION.name: DurationFilter,
            FilterType.OUTCOME.name: OutcomeFilter,
        }

        instance = cls(query)
        for filter_type_data in data["filters"]:
            filter_type = filter_type_data["type"]
            filter_cls = filter_types[filter_type]
            instance.filters.append(filter_cls.from_dict(filter_type_data))
        return instance


class Query:
    """Query class for filtering and retrieving test sessions.

    The Query class implements a two-level filtering design:
    1. Session-Level: Filter entire test sessions (SUT, time range, warnings)
    2. Test-Level: Filter by test properties (pattern, duration, outcome)

    Key Behaviors:
    1. Session-Level Filtering:
       - Returns complete TestSession objects that match session criteria
       - No modification of test results within matching sessions

    2. Test-Level Filtering:
       - Returns NEW TestSession objects containing only matching tests
       - Preserves session metadata (ID, tags, timing, etc.)
       - A session is included if it has at least one matching test
       - Non-matching tests are excluded from the results

    3. Filter Accumulation:
       - IMPORTANT: Filters accumulate when chaining methods on the same Query instance
       - All filters are applied with AND logic (all conditions must be met)
       - To apply independent filters, create new Query instances for each filter set
       - Once execute() is called, the Query instance retains all previously added filters

    4. Storage Profile Support:
       - Queries can be executed against specific storage profiles
       - Use with_profile() to switch profiles during query building
       - Profiles can be specified at initialization or via environment variables

    Examples:
        # Session-level only
        # Get TestSessions for the last 7 days for all SUTs with 'service' in name
        query.for_sut("service").in_last_days(7).execute()

        # Test-level with context
        query.filter_by_test()  # Returns new sessions with only matching tests
            .with_duration_between(10.0, float("inf"))
            .with_outcome(TestOutcome.FAILED)
            .apply()  # Back to session context
            .execute()

        # Combining session and test filters
        query.for_sut("service").in_last_days(14)
            .filter_by_test()
            .with_duration_between(5.0, 10.0)
            .apply()
            .execute()

        # Using a specific profile
        query.with_profile("prod").in_last_days(7).execute()

        # IMPORTANT: Filters accumulate, so these are NOT equivalent:

        # Example 1: Single query with two filters (returns sessions with BOTH env=prod AND region=us-east)
        query = Query(storage)
        result = query.with_session_tag("env", "prod").with_session_tag("region", "us-east").execute()

        # Example 2: Separate queries (returns different results for each filter independently)
        query1 = Query(storage)
        result1 = query1.with_session_tag("env", "prod").execute()

        query2 = Query(storage)
        result2 = query2.with_session_tag("region", "us-east").execute()
    """

    def __init__(self, profile_name: Optional[str] = None):
        """Initialize a new Query instance.

        Args:
            profile_name: Optional profile name to use for storage configuration.
                         If not provided, will use the active profile.
        """
        self._session_filters = []  # Session-level filters (SUT, time range, warnings)
        self._test_filters = []  # Test-level filters (pattern, duration, outcome)
        self._sessions = []  # Cached sessions from storage
        self._profile_name = profile_name or None  # Storage profile name

        # Get storage instance from profile
        self.storage = get_storage_instance(profile_name=profile_name)


    def fred_flintstone(self) -> None:
        pass

    def execute(self, sessions: Optional[List[TestSession]] = None) -> QueryResult:
        """Execute query and return results as QueryResult class instance.

        Key aspects:
        1. Two-Level Filtering:
           - Session-level filters (SUT, time range, warnings)
           - Test-level filters (pattern, duration, outcome)
           - Returns full TestSession objects

        2. Test Filter Behavior:
           - Multiple test filters use AND logic
           - A test must match ALL filters to be included
           - Example: with_pattern("DB", field="caplog") AND
                     with_pattern("stdout", field="capstdout")
           - No partial matches allowed

        3. Context Preservation:
           - Sessions containing ANY matching test are included
           - Only matching tests are kept, in their original order
           - Session metadata (tags, IDs) is maintained
           - Test relationships are preserved

        Args:
            sessions: Optional list of sessions to query. If not provided,
                     loads (all) sessions from storage.

        Returns:
            QueryResult containing filtered sessions.

        Raises:
            InvalidQueryParameterError: If sessions list is empty or contains invalid sessions.
        """
        if sessions is None:
            sessions = self.storage.load_sessions()
        elif not sessions:
            raise InvalidQueryParameterError("No sessions provided")
        elif not isinstance(sessions, list) or not all(
            isinstance(s, TestSession) for s in sessions
        ):
            raise InvalidQueryParameterError("Invalid session type")

        # Apply session-level filters
        filtered_sessions: List[TestSession] = sessions
        for filter_func in self._session_filters:
            filtered_sessions = [s for s in filtered_sessions if filter_func(s)]

        # Apply test-level filters
        if self._test_filters:
            sessions_with_matching_tests = []
            for session in filtered_sessions:
                # Find tests that match all filters, preserving order
                matching_tests = [
                    test
                    for test in session.test_results
                    if all(
                        filter_func.matches(test) for filter_func in self._test_filters
                    )
                ]

                # If any tests match all filters, create new session with only matching tests
                if matching_tests:
                    filtered_session = TestSession(
                        sut_name=session.sut_name,
                        session_id=session.session_id,
                        session_start_time=session.session_start_time,
                        session_stop_time=session.session_stop_time,
                        test_results=matching_tests,  # Only matching tests in original order
                        rerun_test_groups=session.rerun_test_groups,
                        session_tags=session.session_tags,
                    )
                    sessions_with_matching_tests.append(filtered_session)
            filtered_sessions = sessions_with_matching_tests

        return QueryResult(filtered_sessions)

    def to_dict(self) -> Dict:
        """Convert query to dictionary."""
        data = {"version": 1}
        if self._test_filters:
            data["test_filters"] = [f.to_dict() for f in self._test_filters]
        return data

    @classmethod
    def from_dict(
        cls,
        data: Dict,
        profile_name: Optional[str] = None,
    ) -> "Query":
        """Create query from dictionary."""
        query = cls(profile_name)
        filter_map = {
            FilterType.SHELL_PATTERN.name: ShellPatternFilter,
            FilterType.REGEX_PATTERN.name: RegexPatternFilter,
            FilterType.DURATION.name: DurationFilter,
            FilterType.OUTCOME.name: OutcomeFilter,
        }

        if "test_filters" in data:
            for filter_type_data in data["test_filters"]:
                filter_type = filter_type_data["type"]
                filter_cls = filter_map[filter_type]
                query._test_filters.append(filter_cls.from_dict(filter_type_data))
        return query

    def filter_by_test(self) -> QueryTestFilter:
        """Start building test-level filters.

        Returns:
            QueryTestFilter instance for building test-level filters.

        Example:
            query.filter_by_test()
                .with_duration_between(10.0, float("inf"))
                .with_outcome(TestOutcome.FAILED)
                .apply()
                .execute()
        """
        return QueryTestFilter(self)

    def for_sut(self, name: str) -> "Query":
        """Filter sessions by SUT name.

        Args:
            name: Name of the SUT to filter by.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If name is empty or None.
        """
        if not isinstance(name, str) or not name.strip():
            raise InvalidQueryParameterError("SUT name must be a non-empty string")
        self._session_filters.append(lambda s: s.sut_name == name)
        return self

    def in_last_days(self, days: int) -> "Query":
        """Filter sessions from the last N days.

        This method includes sessions that started exactly N days ago or more recently.
        For example, if days=1, it includes sessions from exactly 24 hours ago up to now.
        Sessions that started even 1 second before the cutoff will not be included.

        Args:
            days: Number of days to look back.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If days is not a non-negative integer.
        """
        if not isinstance(days, int) or days < 0:
            raise InvalidQueryParameterError("Days must be a non-negative integer")
        cutoff = dt_module.datetime.now(dt_module.timezone.utc) - dt_module.timedelta(
            days=days
        )
        self._session_filters.append(create_after_or_equals_filter(cutoff))
        return self

    def in_last_hours(self, hours: int) -> "Query":
        """Filter sessions from last N hours.

        Args:
            hours: Number of hours to look back.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If hours is not a non-negative integer.
        """
        if not isinstance(hours, int) or hours < 0:
            raise InvalidQueryParameterError("Hours must be a non-negative integer")
        cutoff = dt_module.datetime.now(dt_module.timezone.utc) - dt_module.timedelta(
            hours=hours
        )
        self._session_filters.append(create_after_or_equals_filter(cutoff))
        return self

    def in_last_minutes(self, minutes: int) -> "Query":
        """Filter sessions from last N minutes.

        Args:
            minutes: Number of minutes to look back.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If minutes is not a non-negative integer.
        """
        if not isinstance(minutes, int) or minutes < 0:
            raise InvalidQueryParameterError("Minutes must be a non-negative integer")
        cutoff = dt_module.datetime.now(dt_module.timezone.utc) - dt_module.timedelta(
            minutes=minutes
        )
        self._session_filters.append(create_after_or_equals_filter(cutoff))
        return self

    def in_last_seconds(self, seconds: int) -> "Query":
        """Filter sessions from last N seconds.

        Args:
            seconds: Number of seconds to look back.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If seconds is not a non-negative integer.
        """
        if not isinstance(seconds, int) or seconds < 0:
            raise InvalidQueryParameterError("Seconds must be a non-negative integer")
        cutoff = dt_module.datetime.now(dt_module.timezone.utc) - dt_module.timedelta(
            seconds=seconds
        )
        self._session_filters.append(create_after_or_equals_filter(cutoff))
        return self

    def date_range(self, start: dt_module.datetime, end: dt_module.datetime) -> "Query":
        """Filter sessions between two dates.

        This method includes sessions that started at or after the start datetime
        and at or before the end datetime. Both boundaries are inclusive.

        For example, if start=2023-01-01 00:00:00 and end=2023-01-31 23:59:59,
        sessions starting exactly at 2023-01-01 00:00:00 or exactly at
        2023-01-31 23:59:59 will be included in the results.

        Args:
            start: Start datetime (inclusive).
            end: End datetime (inclusive).

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If dates are invalid.
        """
        if not isinstance(start, dt_module.datetime) or not isinstance(
            end, dt_module.datetime
        ):
            raise InvalidQueryParameterError("Start and end must be datetime objects")
        if start > end:
            raise InvalidQueryParameterError("Start date must be before end date")

        # We no longer need to check timezone compatibility as our NormalizedDatetime class handles that
        self._session_filters.append(create_after_or_equals_filter(start))
        self._session_filters.append(create_before_or_equals_filter(end))
        return self

    def before(self, timestamp: dt_module.datetime) -> "Query":
        """Filter sessions before given timestamp.

        This method includes sessions that started before the given timestamp, but does
        not include sessions that started exactly at the timestamp.

        Args:
            timestamp: Datetime to filter before.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If timestamp is not a datetime object.
        """
        if not isinstance(timestamp, dt_module.datetime):
            raise InvalidQueryParameterError("Timestamp must be a datetime object")

        self._session_filters.append(create_before_filter(timestamp))
        return self

    def after(self, timestamp: dt_module.datetime) -> "Query":
        """Filter sessions after given timestamp.

        This method includes sessions that started after the given timestamp, but does
        not include sessions that started exactly at the timestamp.

        Args:
            timestamp: Datetime to filter after.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If timestamp is not a datetime object.
        """
        if not isinstance(timestamp, dt_module.datetime):
            raise InvalidQueryParameterError("Timestamp must be a datetime object")

        self._session_filters.append(create_after_filter(timestamp))
        return self

    def between(self, start: dt_module.datetime, end: dt_module.datetime) -> "Query":
        """Filter sessions between given timestamps.

        This method includes sessions that started at or after the start timestamp
        and at or before the end timestamp. Both boundaries are inclusive.

        Args:
            start: Start datetime (inclusive).
            end: End datetime (inclusive).

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If either timestamp is not a datetime object.
        """
        if not isinstance(start, dt_module.datetime) or not isinstance(
            end, dt_module.datetime
        ):
            raise InvalidQueryParameterError("Start and end must be datetime objects")

        # Use both after and before filters together
        self._session_filters.append(
            lambda session: session.session_start_time >= start
            and session.session_start_time <= end
        )
        return self

    def with_outcome(self, outcome: Union[str, TestOutcome]) -> "Query":
        """Filter sessions containing tests with specific outcome.

        Args:
            outcome: Test outcome to filter by.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If outcome is invalid.
        """
        outcome_str = outcome.value if hasattr(outcome, "value") else str(outcome)
        valid_outcomes = {o.value for o in TestOutcome}
        if outcome_str not in valid_outcomes:
            raise InvalidQueryParameterError(
                f"Invalid outcome: {outcome_str}. Must be one of: {', '.join(valid_outcomes)}"
            )

        # Create a test filter function
        def test_filter(test):
            test_outcome = (
                test.outcome.value
                if hasattr(test.outcome, "value")
                else str(test.outcome)
            )
            return test_outcome == outcome_str

        # Use filter_by_test to filter at the test level
        return (
            self.filter_by_test()
            .with_custom_filter(test_filter, f"outcome_{outcome_str}")
            .apply()
        )

    def with_warning(self, has_warnings: bool = True) -> "Query":
        """Filter sessions by presence of warnings in test results.

        Args:
            has_warnings: If True, keep sessions with warnings. If False, keep sessions without warnings.

        Returns:
            Query instance for chaining.
        """
        self._session_filters.append(
            lambda s: any(t.has_warning for t in s.test_results) == has_warnings
        )
        return self

    def with_reruns(self, has_reruns: bool = True) -> "Query":
        """Filter sessions based on presence of test reruns.

        Args:
            has_reruns: If True, keep sessions with reruns. If False, keep sessions without.

        Returns:
            Query instance for chaining.
        """
        self._session_filters.append(lambda s: bool(s.rerun_test_groups) == has_reruns)
        return self

    def test_nodeid_contains(self, pattern: str) -> "Query":
        """Filter sessions containing tests with nodeid matching pattern.

        Args:
            pattern: Pattern to match against test nodeid.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If pattern is empty.
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError("Test pattern must be a non-empty string")
        self._session_filters.append(
            lambda s: any(
                pattern == t.nodeid or pattern in t.nodeid for t in s.test_results
            )
        )
        return self

    def with_session_id_pattern(self, pattern: str) -> "Query":
        """Filter sessions by ID pattern using glob matching.

        This is particularly useful for finding base vs target sessions:
            query.with_session_id_pattern("base-*")  # Find base sessions
            query.with_session_id_pattern("target-*")  # Find target sessions

        Args:
            pattern: Pattern to match against session ID.

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If pattern is empty.
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise InvalidQueryParameterError(
                "Session ID pattern must be a non-empty string"
            )
        self._session_filters.append(lambda s: fnmatch.fnmatch(s.session_id, pattern))
        return self

    def with_session_tag(
        self, tag_key: str, tag_value: str, combine_with_or: bool = False
    ) -> "Query":
        """Filter sessions by session tag.

        Args:
            tag_key: Session tag key.
            tag_value: Session tag value.
            combine_with_or: If True, combines with previous tag filters using OR logic.
                             If False (default), combines using AND logic.

        Example:
            # Filter sessions where session_tags = {"env": "prod"}
            query.with_session_tag("env", "prod")

            # Filter sessions where env is either "prod" OR "staging"
            query.with_session_tag("env", "prod").with_session_tag("env", "staging", combine_with_or=True)

        Returns:
            Query instance for chaining.

        Raises:
            InvalidQueryParameterError: If tag_key or tag_value is invalid.
        """
        if not tag_key or not isinstance(tag_key, str):
            raise InvalidQueryParameterError("Tag key must be a non-empty string")
        if not tag_value or not isinstance(tag_value, str):
            raise InvalidQueryParameterError("Tag value must be a non-empty string")

        # Create the new filter
        def new_filter(s):
            return s.session_tags.get(tag_key) == tag_value

        # If combine_with_or is True and there are existing filters, combine with OR logic
        if combine_with_or and self._session_filters:
            # Get the last filter
            last_filter = self._session_filters.pop()

            # Create a new filter that combines the last filter with the new one using OR
            def combined_filter(s):
                return last_filter(s) or new_filter(s)

            self._session_filters.append(combined_filter)
        else:
            # Otherwise, just add the new filter (AND logic by default)
            self._session_filters.append(new_filter)

        return self

    def with_profile(self, profile_name: str) -> "Query":
        """Switch to a different storage profile for this query.

        This method allows changing the storage profile during query building,
        which is useful for comparing data across different environments or
        configurations.

        Args:
            profile_name: Name of the profile to use

        Returns:
            Query instance for chaining

        Raises:
            ValueError: If profile does not exist
        """
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise InvalidQueryParameterError("Profile name must be a non-empty string")

        # Update the profile name and reconfigure storage
        self._profile_name = profile_name
        self.storage = get_storage_instance(profile_name=profile_name)
        return self
