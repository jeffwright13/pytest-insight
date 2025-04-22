"""Query/filter logic with fluent interface."""

from datetime import datetime, timedelta
from typing import List

from pytest_insight.utils.utils import NormalizedDatetime

from .filters import RegexPatternFilter, ShellPatternFilter
from .models import TestSession

# --- Filter Serialization Registry ---
FILTER_TYPE_REGISTRY = {}


def register_filter_type(type_name, cls):
    FILTER_TYPE_REGISTRY[type_name] = cls


# --- Filter Serialization for ShellPatternFilter and RegexPatternFilter ---
from dataclasses import asdict

register_filter_type("SHELL_PATTERN", ShellPatternFilter)
register_filter_type("REGEX_PATTERN", RegexPatternFilter)


class SerializableFilter:
    """
    Base class for filters that can be serialized to and from dictionaries.

    Provides methods for converting filter objects to a dictionary (for storage or transmission)
    and reconstructing them from a dictionary.
    """

    def to_dict(self):
        """
        Convert the filter object to a dictionary.

        Returns:
            dict: Dictionary representation of the filter object.
        """
        d = asdict(self)
        d["type"] = self.__class__.__name__
        return d

    @classmethod
    def from_dict(cls, data):
        """
        Reconstruct a filter object from a dictionary.

        Args:
            data (dict): Dictionary representation of the filter object.

        Returns:
            SerializableFilter: Reconstructed filter object.
        """
        return cls(**{k: v for k, v in data.items() if k != "type"})


class SessionQuery:
    """
    Query object for filtering and searching over a list of TestSession objects.

    Supports a fluent interface for chaining filters. All filters preserve session context.

    Usage Example:
        query = SessionQuery(sessions)
        recent = query.for_sut("service").in_last_days(7).execute()
    """

    def __init__(self, sessions: List[TestSession]):
        """
        Initialize a SessionQuery.

        Args:
            sessions (List[TestSession]): List of TestSession objects to query.
        """
        self.sessions = sessions
        self.filters = []

    def for_sut(self, sut_name: str, match_type: str = "exact", regex_flags: int = 0):
        """
        Filter sessions by SUT (System Under Test) name, supporting exact, substring, or regex matching.

        Args:
            sut_name (str): Name or pattern of the SUT to filter by.
            match_type (str): 'exact', 'substring', or 'regex'.
            regex_flags (int): Regex flags if using regex.
        Returns:
            self (SessionQuery): Enables method chaining.
        """
        if match_type == "exact":
            self.filters.append(
                lambda s: str(getattr(s, "sut_name", "")).lower()
                == str(sut_name).lower()
            )
        elif match_type == "substring":
            self.filters.append(
                lambda s: str(sut_name).lower()
                in str(getattr(s, "sut_name", "")).lower()
            )
        elif match_type == "regex":
            import re

            pattern = re.compile(str(sut_name), flags=regex_flags)
            self.filters.append(
                lambda s: bool(pattern.search(str(getattr(s, "sut_name", ""))))
            )
        else:
            raise ValueError(f"Invalid match_type: {match_type}")
        return self

    def in_last_days(self, days: int):
        """
        Filter sessions to only those in the last N days.

        Args:
            days (int): Number of days to look back.
        Returns:
            self (SessionQuery): Enables method chaining.
        """
        cutoff = NormalizedDatetime.now() - timedelta(days=days)
        self.filters.append(
            lambda s: NormalizedDatetime(s.session_start_time) >= cutoff
        )
        return self

    def with_reruns(self):
        """
        Filter sessions to only those with rerun test groups.

        Returns:
            self (SessionQuery): Enables method chaining.
        """
        self.filters.append(lambda s: len(s.rerun_test_groups) > 0)
        return self

    def with_tags(self, tags: dict, match_type: str = "exact", regex_flags: int = 0):
        """
        Filter sessions by matching session_tags (all items must match).

        Args:
            tags (dict): Dictionary of tags to match (key/value pairs).
            match_type (str): 'exact', 'substring', or 'regex'.
            regex_flags (int): Regex flags if using regex.
        Returns:
            self (SessionQuery): Enables method chaining.
        """

        def tag_match(s):
            for k, v in tags.items():
                val = str(s.session_tags.get(k, ""))
                v_str = str(v)
                if match_type == "exact":
                    if val.lower() != v_str.lower():
                        return False
                elif match_type == "substring":
                    if v_str.lower() not in val.lower():
                        return False
                elif match_type == "regex":
                    import re

                    pattern = re.compile(v_str, flags=regex_flags)
                    if not pattern.search(val):
                        return False
                else:
                    raise ValueError(f"Invalid match_type: {match_type}")
            return True

        self.filters.append(tag_match)
        return self

    def with_warning(self):
        """
        Filter sessions that contain at least one test with a warning.

        Returns:
            self (SessionQuery): Enables method chaining.
        """
        self.filters.append(
            lambda s: any(getattr(tr, "has_warning", False) for tr in s.test_results)
        )
        return self

    def with_outcome(self, outcome: str, test_level: bool = True):
        """
        Filter sessions by outcome.
        If test_level=True (default), matches sessions with any test of given outcome.
        If test_level=False, matches sessions only if all tests have the outcome.

        Args:
            outcome (str): Outcome to filter by.
            test_level (bool): Whether to filter at the test level (default) or session level.

        Returns:
            self (SessionQuery): Enables method chaining.
        """
        if test_level:
            self.filters.append(
                lambda s: any(
                    getattr(tr, "outcome", None) == outcome for tr in s.test_results
                )
            )
        else:
            self.filters.append(
                lambda s: all(
                    getattr(tr, "outcome", None) == outcome for tr in s.test_results
                )
            )
        return self

    def with_unreliable(self):
        """
        Filter sessions with any test marked as unreliable (if applicable).

        Returns:
            self (SessionQuery): Enables method chaining.
        """
        self.filters.append(
            lambda s: any(getattr(tr, "unreliable", False) for tr in s.test_results)
        )
        return self

    def filter_by_test(self):
        """
        Create a TestQuery object to filter tests within sessions.

        Returns:
            TestQuery: TestQuery object for filtering tests.
        """
        return TestQuery(self)

    def insight(self, kind: str = "summary"):
        """
        Compute insights from the filtered sessions.

        Args:
            kind (str): Type of insight to compute (default: "summary").

        Returns:
            dict: Insight data.
        """
        filtered = self.execute()
        if kind == "summary":
            return {"total_sessions": len(filtered)}
        elif kind == "health":
            # Example health metric: percent sessions with all tests passed
            healthy = sum(
                all(t.outcome == "passed" for t in s.test_results) for s in filtered
            )
            return {"healthy_sessions": healthy, "total_sessions": len(filtered)}
        else:
            return {"info": f"Unknown insight kind: {kind}"}

    def execute(self) -> List[TestSession]:
        """
        Execute the query and return the filtered sessions.

        Returns:
            List[TestSession]: Filtered sessions.
        """
        result = self.sessions
        for f in self.filters:
            result = [s for s in result if f(s)]
        return result

    def to_dict(self):
        """
        Convert the query object to a dictionary.

        Returns:
            dict: Dictionary representation of the query object.
        """
        return {
            "filters": [
                getattr(f, "to_dict", lambda: None)()
                for f in self.filters
                if hasattr(f, "to_dict")
            ],
            "sessions": [s.session_id for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, data, all_sessions):
        """
        Reconstruct a query object from a dictionary.

        Args:
            data (dict): Dictionary representation of the query object.
            all_sessions (List[TestSession]): List of all sessions.

        Returns:
            SessionQuery: Reconstructed query object.
        """
        obj = cls([s for s in all_sessions if s.session_id in data["sessions"]])
        for fdata in data.get("filters", []):
            ftype = fdata["type"]
            fcls = FILTER_TYPE_REGISTRY[ftype]
            obj.filters.append(fcls.from_dict(fdata))
        return obj


class TestQuery:
    """
    Query object for filtering and searching over a list of tests within sessions.

    Supports a fluent interface for chaining filters.
    """

    def __init__(self, parent_query: SessionQuery):
        """
        Initialize a TestQuery.

        Args:
            parent_query (SessionQuery): Parent query object.
        """
        self.parent_query = parent_query
        self.test_filters = []

    def with_name(self, name: str):
        """
        Filter tests by name.

        Args:
            name (str): Name to filter by.

        Returns:
            self (TestQuery): Enables method chaining.
        """
        self.test_filters.append(lambda t: getattr(t, "nodeid", None) == name)
        return self

    def with_duration(self, min_dur: float, max_dur: float):
        """
        Filter tests by duration.

        Args:
            min_dur (float): Minimum duration to filter by.
            max_dur (float): Maximum duration to filter by.

        Returns:
            self (TestQuery): Enables method chaining.
        """
        self.test_filters.append(
            lambda t: min_dur
            <= getattr(t, "duration", getattr(t, "session_duration", 0))
            <= max_dur
        )
        return self

    def with_pattern(self, pattern: str, field_name: str = "nodeid"):
        """
        Filter tests by substring pattern in the specified field.

        Args:
            pattern (str): Pattern to filter by.
            field_name (str): Field to filter by (default: "nodeid").

        Returns:
            self (TestQuery): Enables method chaining.
        """
        filter_obj = ShellPatternFilter(pattern=pattern, field_name=field_name)
        self.test_filters.append(lambda t: filter_obj.matches(t))
        return self

    def with_regex(self, pattern: str, field_name: str = "nodeid"):
        """
        Filter tests by regex pattern in the specified field.

        Args:
            pattern (str): Pattern to filter by.
            field_name (str): Field to filter by (default: "nodeid").

        Returns:
            self (TestQuery): Enables method chaining.
        """
        filter_obj = RegexPatternFilter(pattern=pattern, field_name=field_name)
        self.test_filters.append(lambda t: filter_obj.matches(t))
        return self

    def with_outcome(self, outcome: str):
        """
        Filter tests by outcome.

        Args:
            outcome (str): Outcome to filter by.

        Returns:
            self (TestQuery): Enables method chaining.
        """
        self.test_filters.append(lambda t: getattr(t, "outcome", None) == outcome)
        return self

    def with_unreliable(self):
        """
        Filter tests marked as unreliable (if applicable).

        Returns:
            self (TestQuery): Enables method chaining.
        """
        self.test_filters.append(lambda t: getattr(t, "unreliable", False))
        return self

    def with_warning(self):
        """
        Filter tests with a warning.

        Returns:
            self (TestQuery): Enables method chaining.
        """
        self.test_filters.append(lambda t: getattr(t, "has_warning", False))
        return self

    def apply(self):
        """
        Apply the test filters to the parent query.

        Returns:
            SessionQuery: Parent query object with filtered sessions.
        """
        # Filter sessions by test criteria
        filtered_sessions = []
        for session in self.parent_query.execute():
            if any(all(f(t) for f in self.test_filters) for t in session.test_results):
                filtered_sessions.append(session)
        self.parent_query.sessions = filtered_sessions
        return self.parent_query

    def insight(self, kind: str = "reliability"):
        """
        Compute insights from the filtered tests.

        Args:
            kind (str): Type of insight to compute (default: "reliability").

        Returns:
            dict: Insight data.
        """
        # Example: compute per-test reliability (pass rate)
        filtered_sessions = self.parent_query.execute()
        stats = {}
        for s in filtered_sessions:
            for t in s.test_results:
                if all(f(t) for f in self.test_filters):
                    d = stats.setdefault(
                        t.nodeid,
                        {"runs": 0, "passes": 0, "failures": 0, "total_duration": 0.0},
                    )
                    d["runs"] += 1
                    d["passes"] += int(t.outcome == "passed")
                    d["failures"] += int(t.outcome == "failed")
                    d["total_duration"] += t.duration
        report = []
        for nodeid, d in stats.items():
            reliability = d["passes"] / d["runs"] if d["runs"] else None
            avg_duration = d["total_duration"] / d["runs"] if d["runs"] else None
            report.append(
                {
                    "nodeid": nodeid,
                    "runs": d["runs"],
                    "reliability": reliability,
                    "avg_duration": avg_duration,
                    "failures": d["failures"],
                }
            )
        return report

    def to_dict(self):
        """
        Convert the query object to a dictionary.

        Returns:
            dict: Dictionary representation of the query object.
        """
        return {
            "test_filters": [
                getattr(f, "to_dict", lambda: None)()
                for f in self.test_filters
                if hasattr(f, "to_dict")
            ],
            "parent_query": (
                self.parent_query.to_dict()
                if hasattr(self.parent_query, "to_dict")
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data, all_sessions):
        """
        Reconstruct a query object from a dictionary.

        Args:
            data (dict): Dictionary representation of the query object.
            all_sessions (List[TestSession]): List of all sessions.

        Returns:
            TestQuery: Reconstructed query object.
        """
        parent = SessionQuery.from_dict(data["parent_query"], all_sessions)
        obj = cls(parent)
        for fdata in data.get("test_filters", []):
            ftype = fdata["type"]
            fcls = FILTER_TYPE_REGISTRY[ftype]
            obj.test_filters.append(fcls.from_dict(fdata))
        return obj


# --- STUB: For v1 compatibility only ---
class Query:
    """Stub for v1 compatibility. All methods raise NotImplementedError."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def for_sut(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def in_last_days(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def with_reruns(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def with_tags(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def with_warning(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def with_outcome(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def with_unreliable(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def filter_by_test(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def insight(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def execute(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    def to_dict(self, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )

    @classmethod
    def from_dict(cls, *args, **kwargs):
        raise NotImplementedError(
            "Query is not implemented in v2. Use SessionQuery instead."
        )
