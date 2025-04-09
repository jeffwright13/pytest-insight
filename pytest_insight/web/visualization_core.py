"""Core visualization module for pytest-insight.

This module provides an abstraction layer between data sources and visualization
frontends, allowing for flexibility in switching between different visualization
tools (e.g., Streamlit, Grafana, etc.).
"""

import datetime
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class DataProvider(ABC):
    """Abstract base class for data providers.

    Data providers are responsible for retrieving and formatting data
    from the pytest-insight API for visualization.
    """

    @abstractmethod
    def get_health_metrics(self, sut: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get health metrics for visualization.

        Args:
            sut: Optional system under test filter
            days: Number of days to include

        Returns:
            Dictionary containing health metrics data
        """
        pass

    @abstractmethod
    def get_stability_trends(self, sut: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get stability trends for visualization.

        Args:
            sut: Optional system under test filter
            days: Number of days to include

        Returns:
            Dictionary containing stability trend data
        """
        pass

    @abstractmethod
    def get_predictive_insights(self, sut: Optional[str] = None, days_ahead: int = 7) -> Dict[str, Any]:
        """Get predictive insights for visualization.

        Args:
            sut: Optional system under test filter
            days_ahead: Number of days to predict ahead

        Returns:
            Dictionary containing predictive insights data
        """
        pass

    @abstractmethod
    def get_anomalies(self, sut: Optional[str] = None) -> Dict[str, Any]:
        """Get anomaly detection results for visualization.

        Args:
            sut: Optional system under test filter

        Returns:
            Dictionary containing anomaly detection data
        """
        pass


class InsightDataProvider(DataProvider):
    """Data provider implementation using the pytest-insight API."""

    def __init__(self, profile: Optional[str] = None):
        """Initialize the data provider.

        Args:
            profile: Optional storage profile to use
        """
        from pytest_insight.core.core_api import InsightAPI

        self.api = InsightAPI(profile=profile)

    def get_health_metrics(self, sut: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get health metrics from the pytest-insight API."""
        query = self.api.query()
        if sut:
            query = query.filter_by_sut(sut)

        analysis = query.filter_by_days(days).analyze()
        health_data = analysis.health().to_dict()

        # Format data for visualization
        return {
            "pass_rate": health_data.get("pass_rate", 0),
            "flaky_rate": health_data.get("flaky_rate", 0),
            "health_score": health_data.get("health_score", 0),
            "test_count": health_data.get("test_count", 0),
            "session_count": health_data.get("session_count", 0),
            "daily_metrics": health_data.get("daily_metrics", []),
        }

    def get_stability_trends(self, sut: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get stability trends from the pytest-insight API."""
        query = self.api.query()
        if sut:
            query = query.filter_by_sut(sut)

        analysis = query.filter_by_days(days).analyze()
        stability_data = analysis.stability().to_dict()

        # Format data for visualization
        return {
            "stability_score": stability_data.get("stability_score", 0),
            "trend": stability_data.get("trend", "stable"),
            "daily_stability": stability_data.get("daily_stability", []),
            "most_unstable_tests": stability_data.get("most_unstable_tests", []),
        }

    def get_predictive_insights(self, sut: Optional[str] = None, days_ahead: int = 7) -> Dict[str, Any]:
        """Get predictive insights from the pytest-insight API."""
        query = self.api.query()
        if sut:
            query = query.filter_by_sut(sut)

        predictive = self.api.predictive()
        failure_prediction = predictive.failure_prediction(days_ahead=days_ahead)
        stability_forecast = predictive.stability_forecast()

        # Format data for visualization
        return {
            "failure_prediction": failure_prediction,
            "stability_forecast": stability_forecast,
        }

    def get_anomalies(self, sut: Optional[str] = None) -> Dict[str, Any]:
        """Get anomaly detection results from the pytest-insight API."""
        query = self.api.query()
        if sut:
            query = query.filter_by_sut(sut)

        predictive = self.api.predictive()
        anomalies = predictive.anomaly_detection()

        # Format data for visualization
        return {
            "anomalies": anomalies.get("anomalies", []),
            "anomaly_count": len(anomalies.get("anomalies", [])),
            "detection_date": datetime.datetime.now().isoformat(),
        }


class VisualizationAdapter(ABC):
    """Abstract base class for visualization adapters.

    Visualization adapters are responsible for rendering data from
    data providers using specific visualization tools.
    """

    def __init__(self, data_provider: DataProvider):
        """Initialize the visualization adapter.

        Args:
            data_provider: Data provider to use for retrieving data
        """
        self.data_provider = data_provider

    @abstractmethod
    def render_health_dashboard(self, sut: Optional[str] = None, days: int = 30) -> None:
        """Render the health dashboard.

        Args:
            sut: Optional system under test filter
            days: Number of days to include
        """
        pass

    @abstractmethod
    def render_stability_dashboard(self, sut: Optional[str] = None, days: int = 30) -> None:
        """Render the stability dashboard.

        Args:
            sut: Optional system under test filter
            days: Number of days to include
        """
        pass

    @abstractmethod
    def render_predictive_dashboard(self, sut: Optional[str] = None, days_ahead: int = 7) -> None:
        """Render the predictive dashboard.

        Args:
            sut: Optional system under test filter
            days_ahead: Number of days to predict ahead
        """
        pass

    @abstractmethod
    def render_anomaly_dashboard(self, sut: Optional[str] = None) -> None:
        """Render the anomaly dashboard.

        Args:
            sut: Optional system under test filter
        """
        pass

    @abstractmethod
    def render_main_dashboard(self, sut: Optional[str] = None, days: int = 30, days_ahead: int = 7) -> None:
        """Render the main dashboard with all components.

        Args:
            sut: Optional system under test filter
            days: Number of days to include
            days_ahead: Number of days to predict ahead
        """
        pass


# Factory function to create the appropriate data provider
def create_data_provider(provider_type: str = "insight", profile: Optional[str] = None) -> DataProvider:
    """Create a data provider of the specified type.

    Args:
        provider_type: Type of data provider to create
        profile: Optional storage profile to use

    Returns:
        Data provider instance
    """
    if provider_type == "insight":
        return InsightDataProvider(profile=profile)
    else:
        raise ValueError(f"Unknown data provider type: {provider_type}")


# Factory function to create the appropriate visualization adapter
def create_visualization_adapter(adapter_type: str, data_provider: DataProvider) -> VisualizationAdapter:
    """Create a visualization adapter of the specified type.

    Args:
        adapter_type: Type of visualization adapter to create
        data_provider: Data provider to use

    Returns:
        Visualization adapter instance
    """
    if adapter_type == "streamlit":
        # Import here to avoid circular imports
        from pytest_insight.web.streamlit_adapter import StreamlitAdapter

        return StreamlitAdapter(data_provider)
    else:
        raise ValueError(f"Unknown visualization adapter type: {adapter_type}")
