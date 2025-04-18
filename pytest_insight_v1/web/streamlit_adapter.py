"""Streamlit adapter for pytest-insight visualizations.

This module provides a Streamlit implementation of the VisualizationAdapter
interface, allowing for rendering pytest-insight data using Streamlit.
"""

import datetime
from typing import List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st
from pytest_insight.web.visualization_core import VisualizationAdapter


class StreamlitAdapter(VisualizationAdapter):
    """Streamlit implementation of the VisualizationAdapter interface."""

    def render_health_dashboard(self, sut: Optional[str] = None, days: int = 30) -> None:
        """Render the health dashboard using Streamlit."""
        st.header("Test Health Metrics")

        # Get health metrics data
        health_data = self.data_provider.get_health_metrics(sut=sut, days=days)

        # Display overall metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pass Rate", f"{health_data['pass_rate']:.1f}%")
        with col2:
            st.metric("Reliability Rate", f"{health_data['reliability_rate']:.1f}%")
        with col3:
            st.metric("Health Score", f"{health_data['health_score']:.1f}/10")

        # Display daily metrics chart if available
        if health_data.get("daily_metrics"):
            st.subheader("Daily Health Trends")

            # Convert to DataFrame for plotting
            df = pd.DataFrame(health_data["daily_metrics"])

            # Create chart
            fig = px.line(
                df,
                x="date",
                y=["pass_rate", "health_score"],
                title="Daily Health Metrics",
                labels={"value": "Percentage / Score", "variable": "Metric"},
            )
            st.plotly_chart(fig, use_container_width=True)

        # Display test counts
        st.subheader("Test Statistics")
        st.write(f"Total Tests: {health_data['test_count']}")
        st.write(f"Total Sessions: {health_data['session_count']}")

    def render_stability_dashboard(self, sut: Optional[str] = None, days: int = 30) -> None:
        """Render the stability dashboard using Streamlit."""
        st.header("Test Stability Analysis")

        # Get stability data
        stability_data = self.data_provider.get_stability_trends(sut=sut, days=days)

        # Display overall stability score
        st.metric(
            "Stability Score",
            f"{stability_data['stability_score']:.1f}/10",
            delta=(
                None
                if stability_data["trend"] == "stable"
                else ("↑" if stability_data["trend"] == "improving" else "↓")
            ),
        )

        # Display stability trend description
        trend_descriptions = {
            "improving": "🟢 Stability is improving over time",
            "stable": "🟡 Stability is consistent over time",
            "declining": "🔴 Stability is declining over time",
        }
        st.info(trend_descriptions.get(stability_data["trend"], "Unknown trend"))

        # Display daily stability chart if available
        if stability_data.get("daily_stability"):
            st.subheader("Daily Stability Trends")

            # Convert to DataFrame for plotting
            df = pd.DataFrame(stability_data["daily_stability"])

            # Create chart
            fig = px.line(
                df,
                x="date",
                y="stability_score",
                title="Daily Stability Score",
                labels={"stability_score": "Stability Score"},
            )
            st.plotly_chart(fig, use_container_width=True)

        # Display most unstable tests
        if stability_data.get("most_unstable_tests"):
            st.subheader("Most Unstable Tests")

            # Convert to DataFrame for display
            df = pd.DataFrame(stability_data["most_unstable_tests"])

            # Display as table
            st.dataframe(df, use_container_width=True)

    def render_predictive_dashboard(self, sut: Optional[str] = None, days_ahead: int = 7) -> None:
        """Render the predictive dashboard using Streamlit."""
        st.header("Predictive Insights")

        # Get predictive data
        predictive_data = self.data_provider.get_predictive_insights(sut=sut, days_ahead=days_ahead)

        # Display failure prediction
        st.subheader("Failure Prediction")
        failure_data = predictive_data.get("failure_prediction", {})

        if failure_data:
            # Display prediction summary
            predicted_failures = failure_data.get("predicted_failures", 0)
            confidence = failure_data.get("confidence", 0)

            st.metric("Predicted Failures (Next Week)", predicted_failures)
            st.progress(confidence / 100, text=f"Prediction Confidence: {confidence}%")

            # Display daily prediction chart if available
            if failure_data.get("daily_predictions"):
                # Convert to DataFrame for plotting
                df = pd.DataFrame(failure_data["daily_predictions"])

                # Create chart
                fig = px.bar(
                    df,
                    x="date",
                    y="predicted_failures",
                    title="Daily Failure Predictions",
                    labels={"predicted_failures": "Predicted Failures"},
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No failure prediction data available")

        # Display stability forecast
        st.subheader("Stability Forecast")
        stability_data = predictive_data.get("stability_forecast", {})

        if stability_data:
            # Display forecast summary
            forecast_trend = stability_data.get("forecast_trend", "stable")
            confidence = stability_data.get("confidence", 0)

            trend_descriptions = {
                "improving": "🟢 Stability is predicted to improve",
                "stable": "🟡 Stability is predicted to remain stable",
                "declining": "🔴 Stability is predicted to decline",
            }

            st.info(trend_descriptions.get(forecast_trend, "Unknown trend"))
            st.progress(confidence / 100, text=f"Forecast Confidence: {confidence}%")

            # Display forecast chart if available
            if stability_data.get("forecast_data"):
                # Convert to DataFrame for plotting
                df = pd.DataFrame(stability_data["forecast_data"])

                # Create chart
                fig = px.line(
                    df,
                    x="date",
                    y="stability_score",
                    title="Stability Score Forecast",
                    labels={"stability_score": "Stability Score"},
                )

                # Add vertical line to separate historical data from predictions
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                fig.add_vline(
                    x=today,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text="Today",
                    annotation_position="top right",
                )

                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No stability forecast data available")

    def render_anomaly_dashboard(self, sut: Optional[str] = None) -> None:
        """Render the anomaly dashboard using Streamlit."""
        st.header("Anomaly Detection")

        # Get anomaly data
        anomaly_data = self.data_provider.get_anomalies(sut=sut)

        # Display anomaly summary
        anomaly_count = anomaly_data.get("anomaly_count", 0)
        detection_date = anomaly_data.get("detection_date", datetime.datetime.now().isoformat())

        st.metric("Detected Anomalies", anomaly_count)
        st.caption(f"Last detection run: {detection_date}")

        # Display anomalies if available
        anomalies = anomaly_data.get("anomalies", [])
        if anomalies:
            st.subheader("Detected Anomalies")

            # Convert to DataFrame for display
            df = pd.DataFrame(anomalies)

            # Display as table
            st.dataframe(df, use_container_width=True)

            # Display anomaly visualization if possible
            if "score" in df.columns and "test_id" in df.columns:
                fig = px.bar(
                    df,
                    x="test_id",
                    y="score",
                    title="Anomaly Scores",
                    labels={"score": "Anomaly Score", "test_id": "Test ID"},
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No anomalies detected")

    def render_main_dashboard(self, sut: Optional[str] = None, days: int = 30, days_ahead: int = 7) -> None:
        """Render the main dashboard with all components using Streamlit."""
        st.title("Pytest Insight Dashboard")

        # Sidebar for filters
        with st.sidebar:
            st.header("Filters")

            # SUT filter
            available_suts = self._get_available_suts()
            selected_sut = st.selectbox("System Under Test", options=["All"] + available_suts, index=0)

            # Convert "All" to None for API calls
            filter_sut = None if selected_sut == "All" else selected_sut

            # Time range filter
            selected_days = st.slider("Historical Data (days)", min_value=7, max_value=90, value=days, step=7)

            # Prediction range filter
            selected_days_ahead = st.slider(
                "Prediction Horizon (days)",
                min_value=1,
                max_value=30,
                value=days_ahead,
                step=1,
            )

            # About section
            st.divider()
            st.caption("Pytest Insight Dashboard")
            st.caption("Version: 0.1.0")

        # Create tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs(
            [
                "Health Metrics",
                "Stability Analysis",
                "Predictive Insights",
                "Anomaly Detection",
            ]
        )

        # Render each tab
        with tab1:
            self.render_health_dashboard(sut=filter_sut, days=selected_days)

        with tab2:
            self.render_stability_dashboard(sut=filter_sut, days=selected_days)

        with tab3:
            self.render_predictive_dashboard(sut=filter_sut, days_ahead=selected_days_ahead)

        with tab4:
            self.render_anomaly_dashboard(sut=filter_sut)

    def _get_available_suts(self) -> List[str]:
        """Get a list of available SUTs from the API.

        Returns:
            List of SUT names
        """
        try:
            # This would ideally come from the API
            # For now, return a placeholder list
            return ["service-a", "service-b", "service-c"]
        except Exception:
            return []
