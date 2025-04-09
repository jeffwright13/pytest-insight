"""Core API for pytest-insight.

This module provides the main entry points for the pytest-insight Core API,
which follows a fluent interface design with three main operations:
1. Query - Find and filter test sessions
2. Compare - Compare between versions/times
3. Analyze - Extract insights and metrics

Example usage:
    from pytest_insight.core.core_api import InsightAPI, query, compare, analyze, get_insights

    # Query for specific tests
    results = query().for_sut("my-service").in_last_days(7).execute()

    # Compare between versions
    diff = compare().between_suts("v1", "v2").execute()

    # Analyze patterns
    health_report = analyze().health_report()

    # Get comprehensive insights
    report = get_insights().with_query(lambda q: q.for_sut("service")).summary_report()
"""

import importlib.metadata
from typing import Optional

from pytest_insight.core.analysis import Analysis, analysis, analysis_with_profile
from pytest_insight.core.comparison import (
    Comparison,
    comparison,
    comparison_with_profiles,
)
from pytest_insight.core.insights import Insights, insights, insights_with_profile
from pytest_insight.core.predictive import PredictiveAnalytics, predictive_analytics
from pytest_insight.core.query import Query
from pytest_insight.core.storage import (
    create_profile,
    get_active_profile,
    get_profile_manager,
    list_profiles,
    switch_profile,
)

# Get version directly from package metadata to avoid circular imports
__version__ = importlib.metadata.version("pytest-insight")


class InsightAPI:
    """
    Unified API for pytest-insight providing access to all core components.

    This class serves as a single entry point for all pytest-insight functionality,
    maintaining the fluent interface design pattern while providing a consistent
    interface for users.
    """

    def __init__(self, profile_name: Optional[str] = None):
        """
        Initialize the InsightAPI with an optional profile name.

        Args:
            profile_name: Optional name of the storage profile to use
        """
        self._profile_name = profile_name

    def with_profile(self, profile_name: str) -> "InsightAPI":
        """
        Create a new InsightAPI instance with the specified profile.

        Args:
            profile_name: Name of the storage profile to use

        Returns:
            A new InsightAPI instance configured with the specified profile
        """
        return InsightAPI(profile_name=profile_name)

    def query(self) -> Query:
        """
        Create a new Query instance for finding and filtering test sessions.

        Returns:
            A new Query instance configured with the current profile
        """
        if self._profile_name:
            return Query(profile_name=self._profile_name)
        return query()

    def compare(self) -> Comparison:
        """
        Create a new Comparison instance for comparing test results.

        Returns:
            A new Comparison instance configured with the current profile
        """
        if self._profile_name:
            return comparison_with_profiles(self._profile_name, self._profile_name)
        return compare()

    def analyze(self) -> Analysis:
        """
        Create a new Analysis instance for analyzing test results.

        Returns:
            A new Analysis instance configured with the current profile
        """
        if self._profile_name:
            return analysis_with_profile(self._profile_name)
        return analyze()

    def insights(self) -> Insights:
        """
        Create a new Insights instance for comprehensive test insights.

        Returns:
            A new Insights instance configured with the current profile
        """
        if self._profile_name:
            return insights_with_profile(self._profile_name)
        return get_insights()

    def predictive(self) -> PredictiveAnalytics:
        """
        Create a new PredictiveAnalytics instance for forecasting and anomaly detection.

        Returns:
            A new PredictiveAnalytics instance configured with the current profile
        """
        analysis_instance = self.analyze()
        return predictive_analytics(analysis_instance)


# Re-export the factory functions with consistent naming
def query(profile_name: Optional[str] = None):
    """Create a new Query instance for finding and filtering test sessions.

    Args:
        profile_name: Optional profile name to use for storage configuration

    Returns:
        A new Query instance
    """
    return Query(profile_name=profile_name)


compare = comparison
analyze = analysis
get_insights = insights
get_predictive = predictive_analytics

__all__ = [
    # Main entry points
    "query",
    "compare",
    "analyze",
    "get_insights",
    "get_predictive",
    # Classes for advanced usage
    "Query",
    "Comparison",
    "Analysis",
    "Insights",
    "PredictiveAnalytics",
    "InsightAPI",
    # Profile-specific variants
    "comparison_with_profiles",
    "analysis_with_profile",
    "insights_with_profile",
    # Storage profile management
    "get_profile_manager",
    "create_profile",
    "list_profiles",
    "get_active_profile",
    "switch_profile",
    # Version information
    "__version__",
]
