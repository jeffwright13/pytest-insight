"""
Filterable dimension system for flexible test analytics. Key features:

Flexible Filtering Base:
 Created FilterableDimension as a new base class
 Supports pattern matching, tag filtering, and custom predicates
 All existing dimensions now inherit from this base class
Filter Types:
 Pattern filters for matching test nodeids (supports both string and regex)
 Tag filters for matching session tags
 Custom predicate filters for complex logic
Composable Filters:
 Multiple filters can be combined
 All filters must match for a session to be included
 Each dimension type can have its own set of filters
Enhanced Tests:
 Added comprehensive test cases for all filter types
 Demonstrated combining multiple filters
 Included real-world use cases like filtering by environment

Allows for powerful queries like:

# Group by module, but only production tests with warnings
module_dim = ModuleDimension(filters=[
    DimensionFilter(tags={"environment": "prod"}),
    DimensionFilter(predicate=lambda s: any(r.has_warning for r in s.test_results))
])

# Group by outcome, but only for specific test patterns
outcome_dim = OutcomeDimension(filters=[
    DimensionFilter(pattern=re.compile(r"test_api_.*")),
    DimensionFilter(tags={"feature": "auth"})
])
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Union

from pytest_insight.models import TestSession


@dataclass
class DimensionFilter:
    """Filter that can be used within dimensions.

    Attributes:
        pattern: Optional regex pattern or string to match against test nodeids
        tags: Optional dictionary of tags that must all match
        predicate: Optional custom function for complex filtering logic
    """

    pattern: Optional[Union[str, re.Pattern]] = None
    tags: Optional[Dict[str, str]] = None
    predicate: Optional[Callable[[TestSession], bool]] = None

    def matches(self, session: TestSession) -> bool:
        """Check if a session matches this filter's criteria."""
        # Pattern matching
        if self.pattern:
            if isinstance(self.pattern, re.Pattern):
                if not any(self.pattern.search(t.nodeid) for t in session.test_results):
                    return False
            elif all(self.pattern not in t.nodeid for t in session.test_results):
                return False

        # Tag matching
        if self.tags and any(session.session_tags.get(k) != v for k, v in self.tags.items()):
            return False

        # Custom predicate
        if self.predicate and not self.predicate(session):
            return False
        return True


class FilterableDimension(ABC):
    """Base class for dimensions that support filtering.

    This class provides the foundation for creating dimensions that can filter
    test sessions based on various criteria before grouping them.
    """

    def __init__(self, filters: Optional[List[DimensionFilter]] = None):
        """Initialize with optional list of filters.

        Args:
            filters: List of DimensionFilter objects to apply
        """
        self.filters = filters or []

    def filter_sessions(self, sessions: List[TestSession]) -> List[TestSession]:
        """Apply all filters to a list of sessions.

        Args:
            sessions: List of test sessions to filter

        Returns:
            List of sessions that match all filters
        """
        if not self.filters:
            return sessions
        return [s for s in sessions if all(f.matches(s) for f in self.filters)]

    def group_sessions(self, sessions: List[TestSession]) -> Dict[str, List[TestSession]]:
        """Group sessions after applying filters.

        Args:
            sessions: List of test sessions to group

        Returns:
            Dictionary mapping dimension keys to lists of sessions
        """
        filtered_sessions = self.filter_sessions(sessions)
        return self._group_filtered_sessions(filtered_sessions)

    @abstractmethod
    def _group_filtered_sessions(self, sessions: List[TestSession]) -> Dict[str, List[TestSession]]:
        """Implement actual grouping logic in subclasses.

        Args:
            sessions: List of filtered test sessions to group

        Returns:
            Dictionary mapping dimension keys to lists of sessions
        """
        pass

    @abstractmethod
    def get_key(self, session: TestSession) -> str:
        """Get the dimension key for a session.

        Args:
            session: Test session to get key for

        Returns:
            String key representing the session in this dimension
        """
        pass
