"""Main entry point for pytest-insight API.

This module provides the top-level API for interacting with pytest-insight.
It follows a fluent interface design with three main operations:
1. Query - Find and filter test sessions
2. Compare - Compare between versions/times
3. Analyze - Extract insights and metrics
"""

from typing import Optional

from pytest_insight.analysis import Analysis  # Import Analysis class
from pytest_insight.comparison import Comparison
from pytest_insight.query import Query
from pytest_insight.storage import BaseStorage, get_storage_instance


class InsightAPI:
    """Main entry point for pytest-insight.

    This class provides access to the three core operations:
    1. Query - Find specific tests/sessions
    2. Compare - Compare between versions/times
    3. Analyze - Extract insights

    Example:
        api = InsightAPI()

        # Query tests
        results = api.query().for_sut("my-service").execute()

        # Compare versions
        diff = api.compare().between_suts("v1", "v2").execute()

        # Analyze patterns
        insights = api.analyze().tests().stability()
    """

    def __init__(self, storage: Optional[BaseStorage] = None):
        """Initialize API with optional storage instance.

        Args:
            storage: Optional storage instance to use. If not provided,
                    will use default storage from get_storage_instance().
        """
        self.storage = storage or get_storage_instance()

    def query(self) -> Query:
        """Build and execute a query to find specific tests/sessions.

        Returns:
            Query instance for finding and filtering test sessions.

        Example:
            api.query()
               .for_sut("my-service")
               .filter_by_test()
               .with_pattern("test_api")
               .apply()
               .execute()
        """
        return Query(storage=self.storage)

    def compare(self) -> Comparison:
        """Build and execute a comparison between versions/times.

        Returns:
            Comparison instance for comparing test sessions.

        Example:
            api.compare()
               .between_suts("v1", "v2")
               .with_test_pattern("test_api")
               .execute()
        """
        return Comparison(storage=self.storage)

    def analyze(self) -> "Analysis":
        """Build and execute analysis of test patterns and health.

        Returns:
            Analysis instance for extracting insights.

        Example:
            api.analyze()
               .tests()
               .stability()
        """
        return Analysis(storage=self.storage)
