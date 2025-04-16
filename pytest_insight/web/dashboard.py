#!/usr/bin/env python
"""Streamlit dashboard for pytest-insight."""

import os
import re
import sys
import traceback
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pytest_insight.core.core_api import InsightAPI
from pytest_insight.core.models import TestOutcome
from pytest_insight.core.storage import get_active_profile, list_profiles
from pytest_insight.utils.utils import NormalizedDatetime


def setup_page():
    """Set up the Streamlit page configuration."""
    st.set_page_config(
        page_title="pytest-insight Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("pytest-insight Dashboard")


def select_profile() -> str:
    """Select a storage profile to use.

    Returns:
        Name of the selected profile
    """
    # Initialize session state for profile tracking if it doesn't exist
    if "last_profile_check" not in st.session_state:
        st.session_state.last_profile_check = datetime.now()
        st.session_state.cached_profiles = None

        # Check if a profile was specified via environment variable (from CLI)
        cli_profile = os.environ.get("PYTEST_INSIGHT_PROFILE")
        if cli_profile:
            st.session_state.cli_profile = cli_profile

    # Get available profiles - refresh every 5 seconds
    current_time = datetime.now()
    time_diff = (current_time - st.session_state.last_profile_check).total_seconds()

    # Always refresh profiles on first load or if it's been more than 5 seconds
    if st.session_state.cached_profiles is None or time_diff > 5:
        profiles = list_profiles()
        st.session_state.cached_profiles = profiles
        st.session_state.last_profile_check = current_time
    else:
        profiles = st.session_state.cached_profiles

    active_profile = get_active_profile()

    # Check if profiles is a dict (old format) or list (new format)
    if isinstance(profiles, dict):
        profile_options = list(profiles.keys())
    else:
        profile_options = profiles

    # Default to active profile
    default_index = 0
    if active_profile:
        if isinstance(active_profile, dict) and "name" in active_profile:
            active_name = active_profile["name"]
        elif hasattr(active_profile, "name"):
            active_name = active_profile.name
        else:
            active_name = str(active_profile)

        if active_name in profile_options:
            default_index = profile_options.index(active_name)

    # If a profile was specified via CLI, use that as the default
    if (
        hasattr(st.session_state, "cli_profile")
        and st.session_state.cli_profile in profile_options
    ):
        default_index = profile_options.index(st.session_state.cli_profile)
        # Show a message indicating we're using the CLI-specified profile
        st.sidebar.success(
            f"Using profile specified from command line: {st.session_state.cli_profile}"
        )

    # Let user select profile
    col1, col2 = st.sidebar.columns([3, 1])

    profile_name = col1.selectbox(
        "Storage Profile",
        options=profile_options,
        index=default_index,
        help="Select a storage profile to use",
    )

    # Add refresh button
    if col2.button("🔄", help="Refresh profile list"):
        # Force refresh profiles
        st.session_state.cached_profiles = None
        st.rerun()

    return profile_name


def get_session_id(session):
    """Helper function to get session ID from a session object.

    Checks both id and session_id attributes for compatibility with different session formats.

    Args:
        session: Session object

    Returns:
        Session ID or None if not found
    """
    if hasattr(session, "session_id") and session.session_id:
        return session.session_id
    elif hasattr(session, "id") and session.id:
        return session.id
    return None


def display_health_metrics(api: InsightAPI, sut: Optional[str], days: int):
    """Display health metrics for the selected SUT and time range."""
    try:
        st.header("Test Health Metrics")

        # Get sessions for the selected SUT and time range
        sessions = []
        try:
            query = api.query()
            if sut:
                query = query.for_sut(sut)
            result = query.execute()
            sessions = result.sessions
            st.sidebar.info(f"Found {len(sessions)} sessions")
        except Exception as e:
            st.error(f"Error retrieving sessions: {e}")
            st.sidebar.error(f"Query error: {str(e)}")
            st.code(traceback.format_exc())
            return

        # Filter sessions by time range if needed
        if days and sessions:
            try:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                normalized_cutoff = NormalizedDatetime(cutoff)

                filtered_sessions = []
                for s in sessions:
                    if hasattr(s, "session_start_time") and s.session_start_time:
                        # Use NormalizedDatetime to handle timezone differences
                        if (
                            NormalizedDatetime(s.session_start_time)
                            >= normalized_cutoff
                        ):
                            filtered_sessions.append(s)

                sessions = filtered_sessions
                st.sidebar.info(
                    f"Filtered to {len(sessions)} sessions in last {days} days"
                )
            except Exception as e:
                st.error(f"Error filtering sessions by date: {e}")
                st.code(traceback.format_exc())

        if not sessions:
            st.warning("No test sessions found for the selected filters.")
            return

        # Create analysis with filtered sessions
        analyzer = api.analyze()
        analyzer._sessions = sessions

        # Get health report
        try:
            health_report = analyzer.health_report()
            # Debug: Show raw health report data
            with st.expander("Debug: Raw Health Report Data"):
                st.json(health_report)
        except Exception as e:
            st.error(f"Error generating health report: {e}")
            st.code(traceback.format_exc())
            health_report = {}

        # Extract metrics from the health report
        session_metrics = health_report.get("session_metrics", {})
        trends = health_report.get("trends", {})
        reliability_metrics = health_report.get("reliability_metrics", {})

        # Extract duration trend
        duration_trend = trends.get("duration", {})
        duration_change = duration_trend.get("change_percent", 0)

        # Extract failure trend for pass rate trend calculation
        failure_trend = trends.get("failures", {})
        failure_change = failure_trend.get("change_percent", 0)
        # Invert failure change to get pass rate change (if failures go up, pass rate goes down)
        pass_rate_trend = -failure_change if failure_change else 0

        # Get reliability metrics from the health report
        try:
            reliability_index = reliability_metrics.get("reliability_index", 100)
            rerun_recovery_rate = reliability_metrics.get("rerun_recovery_rate", 100)
            health_score_penalty = reliability_metrics.get("health_score_penalty", 0)

            # For trends, we don't have historical data yet, so use default of 0
            reliability_index_trend = 0
            rerun_recovery_trend = 0
        except Exception as e:
            st.sidebar.warning(f"Error accessing reliability metrics: {e}")
            reliability_index = 100
            rerun_recovery_rate = 100
            health_score_penalty = 0
            reliability_index_trend = 0
            rerun_recovery_trend = 0

        # Calculate pass rate and trend
        total_tests = session_metrics.get("total_tests", 0)
        passed_tests = session_metrics.get("passed_tests", 0)
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Calculate average duration
        avg_duration = session_metrics.get("avg_duration", 0)

        # Calculate health score (scale of 0-10)
        health_score = health_report.get("health_score", 0)
        if isinstance(health_score, dict):
            # Extract the overall score from the health_score dictionary
            health_score = health_score.get("overall_score", 0)

        # Apply health score penalty from reliability metrics
        try:
            # Adjust health score based on reliability metrics
            # Dock 1 percentage point for each percent of unstable tests
            if health_score_penalty > 0:
                # Convert health score to 0-100 scale if needed
                health_score_100 = (
                    health_score * 10 if health_score <= 10 else health_score
                )

                # Apply penalty (capped at 50% of the score to avoid excessive penalties)
                max_penalty = health_score_100 * 0.5
                actual_penalty = min(health_score_penalty, max_penalty)
                health_score_100 = max(health_score_100 - actual_penalty, 0)

                # Convert back to original scale if needed
                health_score = (
                    health_score_100 / 10
                    if health_score_100 <= 100
                    else health_score_100
                )
        except Exception as e:
            st.sidebar.warning(f"Error applying health score penalty: {e}")

        # Ensure we have a valid number
        try:
            health_score = float(health_score)
            # The health score from the analysis is typically 0-1
            # If it's larger than 1, it might be on a different scale (like 0-100)
            if health_score > 10:
                health_score = health_score / 10  # Scale down if it's too large
            elif health_score <= 1.0:
                health_score = health_score * 10  # Scale up if it's 0-1
        except (ValueError, TypeError):
            health_score = 0.0

        # Display metrics in columns
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            try:
                st.metric(
                    "Pass Rate",
                    f"{float(pass_rate):.1f}%",
                    delta=f"{float(pass_rate_trend):.1f}%",
                    delta_color="normal",
                    help="Percentage of tests that passed on the first attempt. Calculated as: (Number of Passed Tests / Total Tests) * 100%. Higher is better.",
                )
            except Exception as e:
                st.metric("Pass Rate", "N/A")
                st.error(f"Error displaying pass rate: {e}")

        with col2:
            try:
                st.metric(
                    "Reliability Index",
                    f"{float(reliability_index):.1f}%",
                    delta=f"{float(reliability_index_trend):.1f}%",
                    delta_color="normal",
                    help="Percentage of tests with consistent outcomes. Higher values indicate more reliable tests. Calculated as: 100% - (Unstable Tests / Total Tests) * 100%.",
                )
            except Exception as e:
                st.metric("Reliability Index", "N/A")
                st.error(f"Error displaying reliability index: {e}")

        with col3:
            try:
                st.metric(
                    "Avg Duration",
                    f"{float(avg_duration):.2f}s",
                    delta=f"{-float(duration_change):.2f}s",
                    delta_color="inverse",
                    help="Average time taken to execute a test. Lower durations indicate more efficient tests. Sudden increases may indicate performance regressions.",
                )
            except Exception as e:
                st.metric("Avg Duration", "N/A")
                st.error(f"Error displaying duration: {e}")

        with col4:
            try:
                st.metric(
                    "Health Score",
                    f"{float(health_score):.1f}/10",
                    delta=None,
                    help="A composite score (0-10) that measures the overall health of your test suite. Based on a weighted formula considering pass rate (50%), reliability (20%), duration stability (15%), and failure patterns (15%). Higher scores indicate healthier test suites.",
                )
            except Exception as e:
                st.metric("Health Score", "N/A")
                st.error(f"Error displaying health score: {e}")

        with col5:
            try:
                st.metric(
                    "Rerun Recovery Rate",
                    f"{float(rerun_recovery_rate):.1f}%",
                    delta=f"{float(rerun_recovery_trend):.1f}%",
                    delta_color="normal",
                    help="Percentage of tests that passed after being rerun. Higher values indicate tests that are unreliable but recoverable. Calculated as: (Tests That Passed After Rerun / Total Rerun Tests) * 100%.",
                )
            except Exception as e:
                st.metric("Rerun Recovery Rate", "N/A")
                st.error(f"Error displaying rerun recovery rate: {e}")

        # Display recommendations based on metrics
        st.subheader("Recommendations")

        # Create recommendations based on metrics
        recommendations = []

        # Test stability recommendations
        if reliability_index < 95:
            recommendations.append(
                "📊 **Low reliability index detected.** Consider investigating test stability issues."
            )
            if rerun_recovery_rate > 70:
                recommendations.append(
                    "✅ Good rerun recovery rate. Focus on tests that fail consistently."
                )
            else:
                recommendations.append(
                    "❌ Low rerun recovery rate. Tests may have genuine failures."
                )

        # Pass rate recommendations
        if pass_rate < 90:
            recommendations.append(
                "🔴 **Low pass rate detected.** Consider investigating test failures."
            )

        # Display recommendations or a healthy message
        if recommendations:
            for rec in recommendations:
                st.markdown(rec)
        else:
            st.success("✨ No issues detected. Test suite is healthy!")

        # Add a divider
        st.markdown("---")

        # Display test outcome breakdown
        st.subheader("Test Outcome Distribution")

        # Calculate outcome counts
        outcome_counts = {}
        try:
            # First try to get from health report if available
            if "outcome_distribution" in health_report:
                outcome_counts = health_report["outcome_distribution"]
            else:
                # Otherwise calculate from sessions
                for session in sessions:
                    if hasattr(session, "test_results") and session.test_results:
                        for test in session.test_results:
                            if hasattr(test, "outcome") and test.outcome:
                                outcome = test.outcome
                                if isinstance(outcome, TestOutcome):
                                    outcome = outcome.value.lower()
                                outcome_counts[outcome] = (
                                    outcome_counts.get(outcome, 0) + 1
                                )

            if outcome_counts:
                # Create DataFrame for plotting
                df = pd.DataFrame(
                    {
                        "Outcome": list(outcome_counts.keys()),
                        "Count": list(outcome_counts.values()),
                    }
                )

                # Create pie chart
                fig = px.pie(
                    df,
                    values="Count",
                    names="Outcome",
                    color="Outcome",
                    color_discrete_map={
                        "passed": "green",
                        "failed": "red",
                        "skipped": "gray",
                        "error": "darkred",
                        "xfailed": "orange",
                        "xpassed": "lightgreen",
                    },
                )
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No outcome distribution data available.")
        except Exception as e:
            st.error(f"Error displaying outcome distribution: {e}")
            st.code(traceback.format_exc())
    except Exception as e:
        st.error(f"Unexpected error in health metrics display: {e}")
        st.code(traceback.format_exc())


def display_stability_trends(api: InsightAPI, sut: Optional[str], days: int):
    """Display stability trends for the selected SUT and time range."""
    try:
        st.header("Stability Trends")

        # Get sessions for the selected SUT and time range
        sessions = []
        try:
            query = api.query()
            if sut:
                query = query.for_sut(sut)
            result = query.execute()
            sessions = result.sessions
        except Exception as e:
            st.error(f"Error retrieving sessions: {e}")
            st.code(traceback.format_exc())
            return

        # Filter sessions by time range if needed
        if days and sessions:
            try:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                normalized_cutoff = NormalizedDatetime(cutoff)

                filtered_sessions = []
                for s in sessions:
                    if hasattr(s, "session_start_time") and s.session_start_time:
                        # Use NormalizedDatetime to handle timezone differences
                        if (
                            NormalizedDatetime(s.session_start_time)
                            >= normalized_cutoff
                        ):
                            filtered_sessions.append(s)

                sessions = filtered_sessions
            except Exception as e:
                st.error(f"Error filtering sessions by date: {e}")
                st.code(traceback.format_exc())

        if not sessions:
            st.warning("No test sessions found for the selected filters.")
            return

        # Create analysis with filtered sessions
        analyzer = api.analyze()
        analyzer._sessions = sessions

        # Get trend data
        try:
            # Create a dictionary to store trend data
            trends = {
                "failure_trend": {
                    "direction": "stable",
                    "significant": False,
                    "data_points": [],
                },
                "duration_trend": {
                    "direction": "stable",
                    "significant": False,
                    "data_points": [],
                },
            }

            # Group sessions by date
            sessions_by_date = {}
            for session in sessions:
                if (
                    hasattr(session, "session_start_time")
                    and session.session_start_time
                ):
                    # Get the date part only
                    date_key = session.session_start_time.date().isoformat()
                    if date_key not in sessions_by_date:
                        sessions_by_date[date_key] = []
                    sessions_by_date[date_key].append(session)

            # Calculate metrics for each date
            for date_key, date_sessions in sorted(sessions_by_date.items()):
                # Calculate failure rate
                total_tests = 0
                failed_tests = 0
                total_duration = 0

                for session in date_sessions:
                    if not (hasattr(session, "test_results") and session.test_results):
                        continue

                    for test in session.test_results:
                        total_tests += 1
                        if (
                            hasattr(test, "outcome")
                            and test.outcome == TestOutcome.FAILED
                        ):
                            failed_tests += 1
                        if hasattr(test, "duration") and test.duration:
                            total_duration += test.duration

                # Add failure rate data point
                failure_rate = failed_tests / total_tests if total_tests > 0 else 0
                trends["failure_trend"]["data_points"].append(
                    {"date": date_key, "rate": failure_rate}
                )

                # Add duration data point
                avg_duration = total_duration / total_tests if total_tests > 0 else 0
                trends["duration_trend"]["data_points"].append(
                    {"date": date_key, "duration": avg_duration}
                )

            # Determine trend direction
            if len(trends["failure_trend"]["data_points"]) >= 2:
                first_rate = trends["failure_trend"]["data_points"][0]["rate"]
                last_rate = trends["failure_trend"]["data_points"][-1]["rate"]

                if last_rate > first_rate * 1.1:  # 10% increase
                    trends["failure_trend"]["direction"] = "increasing"
                    trends["failure_trend"]["significant"] = True
                elif last_rate < first_rate * 0.9:  # 10% decrease
                    trends["failure_trend"]["direction"] = "decreasing"
                    trends["failure_trend"]["significant"] = True

            if len(trends["duration_trend"]["data_points"]) >= 2:
                first_duration = trends["duration_trend"]["data_points"][0]["duration"]
                last_duration = trends["duration_trend"]["data_points"][-1]["duration"]

                if last_duration > first_duration * 1.1:  # 10% increase
                    trends["duration_trend"]["direction"] = "increasing"
                    trends["duration_trend"]["significant"] = True
                elif last_duration < first_duration * 0.9:  # 10% decrease
                    trends["duration_trend"]["direction"] = "decreasing"
                    trends["duration_trend"]["significant"] = True

            # Debug: Show raw trend data
            with st.expander("Debug: Raw Trend Data"):
                st.json(trends)
        except Exception as e:
            st.error(f"Error detecting trends: {e}")
            st.code(traceback.format_exc())
            trends = {}

        # Display trends in columns
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Failure Rate Trend")
            try:
                if "failure_trend" in trends and trends["failure_trend"]:
                    failure_data = trends["failure_trend"]

                    # Create DataFrame for plotting
                    dates = []
                    rates = []

                    for point in failure_data.get("data_points", []):
                        dates.append(point.get("date"))
                        rates.append(
                            point.get("rate", 0) * 100
                        )  # Convert to percentage

                    if dates and rates:
                        df = pd.DataFrame({"Date": dates, "Failure Rate (%)": rates})

                        # Create line chart
                        fig = px.line(df, x="Date", y="Failure Rate (%)", markers=True)
                        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                        st.plotly_chart(fig, use_container_width=True)

                        # Display trend information
                        trend_direction = failure_data.get("direction", "stable")
                        trend_significant = failure_data.get("significant", False)

                        if trend_significant:
                            if trend_direction == "increasing":
                                st.warning("⚠️ Failure rate is significantly increasing")
                            elif trend_direction == "decreasing":
                                st.success(
                                    "✅ Failure rate is significantly decreasing"
                                )
                        else:
                            st.info("ℹ️ Failure rate is stable")
                    else:
                        st.info("Insufficient data for failure trend analysis.")
                else:
                    st.info("No failure trend data available.")
            except Exception as e:
                st.error(f"Error displaying failure trend: {e}")
                st.code(traceback.format_exc())

        with col2:
            st.subheader("Duration Trend")
            try:
                if "duration_trend" in trends and trends["duration_trend"]:
                    duration_data = trends["duration_trend"]

                    # Create DataFrame for plotting
                    dates = []
                    durations = []

                    for point in duration_data.get("data_points", []):
                        dates.append(point.get("date"))
                        durations.append(point.get("duration", 0))

                    if dates and durations:
                        df = pd.DataFrame({"Date": dates, "Duration (s)": durations})

                        # Create line chart
                        fig = px.line(df, x="Date", y="Duration (s)", markers=True)
                        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                        st.plotly_chart(fig, use_container_width=True)

                        # Display trend information
                        trend_direction = duration_data.get("direction", "stable")
                        trend_significant = duration_data.get("significant", False)

                        if trend_significant:
                            if trend_direction == "increasing":
                                st.warning(
                                    "⚠️ Test duration is significantly increasing"
                                )
                            elif trend_direction == "decreasing":
                                st.success(
                                    "✅ Test duration is significantly decreasing"
                                )
                        else:
                            st.info("ℹ️ Test duration is stable")
                    else:
                        st.info("Insufficient data for duration trend analysis.")
                else:
                    st.info("No duration trend data available.")
            except Exception as e:
                st.error(f"Error displaying duration trend: {e}")
                st.code(traceback.format_exc())
    except Exception as e:
        st.error(f"Unexpected error in stability trends display: {e}")
        st.code(traceback.format_exc())


def display_predictive_insights(api: InsightAPI, sut: Optional[str], days: int):
    """Display predictive insights for the selected SUT and time range."""
    try:
        st.header("Predictive Insights")

        # Get sessions for the selected SUT and time range
        sessions = []
        try:
            query = api.query()
            if sut:
                query = query.for_sut(sut)
            result = query.execute()
            sessions = result.sessions
        except Exception as e:
            st.error(f"Error retrieving sessions: {e}")
            st.code(traceback.format_exc())
            return

        # Filter sessions by time range if needed
        if days and sessions:
            try:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                normalized_cutoff = NormalizedDatetime(cutoff)

                filtered_sessions = []
                for s in sessions:
                    if hasattr(s, "session_start_time") and s.session_start_time:
                        # Use NormalizedDatetime to handle timezone differences
                        if (
                            NormalizedDatetime(s.session_start_time)
                            >= normalized_cutoff
                        ):
                            filtered_sessions.append(s)

                sessions = filtered_sessions
            except Exception as e:
                st.error(f"Error filtering sessions by date: {e}")
                st.code(traceback.format_exc())

        if not sessions:
            st.warning("No test sessions found for the selected filters.")
            return

        # Create analysis with filtered sessions
        analyzer = api.analyze()
        analyzer._sessions = sessions

        # Get predictive insights
        try:
            # Create predictive analytics with the sessions
            predictive = api.predictive()

            # Make sure sessions are set in the predictive analytics object
            if hasattr(predictive, "_sessions") and predictive._sessions is None:
                predictive._sessions = sessions

            # Failure predictions
            st.subheader("Failure Predictions")
            try:
                predictions = predictive.failure_prediction()

                if (
                    predictions
                    and isinstance(predictions, dict)
                    and "predictions" in predictions
                ):
                    pred_data = predictions["predictions"]

                    if isinstance(pred_data, dict) and pred_data:
                        # Convert dictionary to list of dictionaries for display
                        pred_list = [
                            {"test": test, "probability": prob}
                            for test, prob in pred_data.items()
                        ]

                        # Sort by probability (descending)
                        pred_list = sorted(
                            pred_list, key=lambda x: x["probability"], reverse=True
                        )

                        # Create DataFrame for displaying predictions
                        df = pd.DataFrame(pred_list)

                        # Format probability as percentage
                        if "probability" in df.columns:
                            df["probability"] = df["probability"].apply(
                                lambda x: f"{x*100:.1f}%"
                            )

                        # Display as table
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No failure predictions available.")
                else:
                    st.info("No failure predictions available.")
            except Exception as e:
                st.error(f"Error generating failure predictions: {e}")
                st.code(traceback.format_exc())
                predictions = {}

            # Debug: Show raw prediction data
            with st.expander("Debug: Raw Prediction Data"):
                st.json(predictions)

            # Stability forecast
            st.subheader("Stability Forecast")
            try:
                forecast = predictive.stability_forecast()

                if (
                    forecast
                    and isinstance(forecast, dict)
                    and "forecasted_stability" in forecast
                ):
                    # Create a simple display of the forecast
                    current = forecast.get("current_stability")
                    forecasted = forecast.get("forecasted_stability")
                    trend = forecast.get("trend_direction")
                    factors = forecast.get("contributing_factors", [])

                    # Display current and forecasted stability
                    col1, col2 = st.columns(2)
                    with col1:
                        if current is not None:
                            st.metric("Current Stability", f"{current:.1f}%")
                    with col2:
                        if forecasted is not None:
                            delta = None
                            if current is not None:
                                delta = f"{forecasted - current:.1f}%"
                            st.metric(
                                "Forecasted Stability",
                                f"{forecasted:.1f}%",
                                delta=delta,
                            )

                    # Display trend direction
                    if trend:
                        st.info(f"Trend: {trend.capitalize()}")

                    # Display contributing factors
                    if factors:
                        st.subheader("Contributing Factors")
                        for factor in factors:
                            st.markdown(f"- {factor}")
                else:
                    st.info("No stability forecast available.")
            except Exception as e:
                st.error(f"Error generating stability forecast: {e}")
                st.code(traceback.format_exc())
                forecast = {}

            # Debug: Show raw forecast data
            with st.expander("Debug: Raw Forecast Data"):
                st.json(forecast)

            # Anomaly detection
            st.subheader("Detected Anomalies")
            try:
                anomalies = predictive.anomaly_detection()

                if (
                    anomalies
                    and isinstance(anomalies, dict)
                    and "anomalies" in anomalies
                ):
                    anomaly_list = anomalies.get("anomalies", [])

                    if anomaly_list:
                        # Create a simple table for anomalies
                        anomaly_data = []
                        for anomaly in anomaly_list:
                            if isinstance(anomaly, dict):
                                anomaly_data.append(anomaly)
                            elif isinstance(anomaly, str):
                                anomaly_data.append({"test": anomaly})

                        if anomaly_data:
                            df = pd.DataFrame(anomaly_data)
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("No anomalies detected.")
                    else:
                        st.info("No anomalies detected.")
                else:
                    st.info("No anomaly detection data available.")
            except Exception as e:
                st.error(f"Error detecting anomalies: {e}")
                st.code(traceback.format_exc())
                anomalies = {}

            # Debug: Show raw anomaly data
            with st.expander("Debug: Raw Anomaly Data"):
                st.json(anomalies)

        except Exception as e:
            st.error(f"Error generating predictive insights: {e}")
            st.code(traceback.format_exc())
    except Exception as e:
        st.error(f"Error in predictive insights display: {e}")
        st.code(traceback.format_exc())


def display_test_execution_trends(api: InsightAPI, sut: Optional[str], days: int):
    """Display detailed test execution trends over time.

    Shows historical pass/fail rates, execution time trends, and reliability-repeatability metrics.

    Args:
        api: InsightAPI instance
        sut: Optional system under test filter
        days: Number of days to include in the analysis
    """
    try:
        st.header("Test Execution Trends")

        # Get sessions for the selected SUT and time range
        sessions = []
        try:
            query = api.query()
            if sut:
                query = query.for_sut(sut)
            result = query.execute()
            sessions = result.sessions
        except Exception as e:
            st.error(f"Error retrieving sessions: {e}")
            st.code(traceback.format_exc())
            return

        # Filter sessions by time range if needed
        if days and sessions:
            try:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                normalized_cutoff = NormalizedDatetime(cutoff)

                filtered_sessions = []
                for s in sessions:
                    if hasattr(s, "session_start_time") and s.session_start_time:
                        # Use NormalizedDatetime to handle timezone differences
                        if (
                            NormalizedDatetime(s.session_start_time)
                            >= normalized_cutoff
                        ):
                            filtered_sessions.append(s)

                sessions = filtered_sessions
            except Exception as e:
                st.error(f"Error filtering sessions by date: {e}")
                st.code(traceback.format_exc())

        if not sessions:
            st.warning("No test sessions found for the selected filters.")
            return

        # Sort sessions by date
        try:
            sessions = sorted(
                sessions,
                key=lambda s: NormalizedDatetime(
                    getattr(s, "session_start_time", datetime.now(ZoneInfo("UTC")))
                ),
            )
        except Exception as e:
            st.error(f"Error sorting sessions: {e}")
            st.code(traceback.format_exc())
            return

        # Group sessions by date
        sessions_by_date = {}
        for session in sessions:
            if hasattr(session, "session_start_time") and session.session_start_time:
                # Get the date part only (without time)
                date_key = session.session_start_time.date().isoformat()
                if date_key not in sessions_by_date:
                    sessions_by_date[date_key] = []
                sessions_by_date[date_key].append(session)

        # Calculate metrics for each date
        dates = []
        pass_rates = []
        fail_rates = []
        avg_durations = []
        nonreliability_rates = []
        test_counts = []

        for date_key, date_sessions in sorted(sessions_by_date.items()):
            # Collect all test results for this date
            all_tests = []
            for session in date_sessions:
                if hasattr(session, "test_results") and session.test_results:
                    all_tests.extend(session.test_results)

            if not all_tests:
                continue

            # Calculate metrics
            total_tests = len(all_tests)
            passed_tests = sum(
                1
                for t in all_tests
                if hasattr(t, "outcome") and t.outcome == TestOutcome.PASSED
            )
            failed_tests = sum(
                1
                for t in all_tests
                if hasattr(t, "outcome") and t.outcome == TestOutcome.FAILED
            )

            # Calculate average duration
            durations = [
                t.duration
                for t in all_tests
                if hasattr(t, "duration") and t.duration is not None
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0

            # Calculate reliability-repeatability (tests that have both passed and failed on the same day)
            test_outcomes = {}
            for test in all_tests:
                if hasattr(test, "nodeid") and hasattr(test, "outcome"):
                    if test.nodeid not in test_outcomes:
                        test_outcomes[test.nodeid] = set()
                    test_outcomes[test.nodeid].add(test.outcome)

            unreliable_tests = sum(
                1 for outcomes in test_outcomes.values() if len(outcomes) > 1
            )
            nonreliability_rate = (
                unreliable_tests / len(test_outcomes) if test_outcomes else 0
            )

            # Store metrics
            dates.append(date_key)
            pass_rates.append(
                passed_tests / total_tests * 100 if total_tests > 0 else 0
            )
            fail_rates.append(
                failed_tests / total_tests * 100 if total_tests > 0 else 0
            )
            avg_durations.append(avg_duration)
            nonreliability_rates.append(
                nonreliability_rate * 100
            )  # Convert to percentage
            test_counts.append(total_tests)

        if not dates:
            st.warning("No test data available for the selected time range.")
            return

        # Create tabs for different trend visualizations
        tab1, tab2, tab3 = st.tabs(
            ["Pass/Fail Rates", "Execution Times", "reliability-repeatability Index"]
        )

        with tab1:
            st.subheader("Pass/Fail Rates Over Time")

            # Create DataFrame for plotting
            df_rates = pd.DataFrame(
                {
                    "Date": dates,
                    "Pass Rate (%)": pass_rates,
                    "Fail Rate (%)": fail_rates,
                    "Test Count": test_counts,
                }
            )

            # Create multi-line chart
            fig = px.line(
                df_rates,
                x="Date",
                y=["Pass Rate (%)", "Fail Rate (%)"],
                title="Test Pass/Fail Rates",
                markers=True,
            )

            # Add test count as a bar chart on secondary y-axis
            fig.add_trace(
                go.Bar(
                    x=df_rates["Date"],
                    y=df_rates["Test Count"],
                    name="Test Count",
                    opacity=0.3,
                    yaxis="y2",
                )
            )

            # Update layout for dual y-axis
            fig.update_layout(
                yaxis=dict(title="Rate (%)"),
                yaxis2=dict(title="Test Count", overlaying="y", side="right"),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                margin=dict(t=50, b=0, l=0, r=0),
                hovermode="x unified",
            )

            st.plotly_chart(fig, use_container_width=True)

            # Calculate trend
            if len(pass_rates) >= 2:
                first_pass_rate = pass_rates[0]
                last_pass_rate = pass_rates[-1]
                pass_rate_change = last_pass_rate - first_pass_rate

                if abs(pass_rate_change) < 1:
                    trend_message = "Pass rate has remained stable."
                elif pass_rate_change > 0:
                    trend_message = (
                        f"Pass rate has improved by {pass_rate_change:.1f}%."
                    )
                else:
                    trend_message = (
                        f"Pass rate has decreased by {abs(pass_rate_change):.1f}%."
                    )

                st.info(trend_message)

        with tab2:
            st.subheader("Test Execution Times")

            # Create DataFrame for plotting
            df_times = pd.DataFrame(
                {
                    "Date": dates,
                    "Average Duration (s)": avg_durations,
                    "Test Count": test_counts,
                }
            )

            # Create line chart
            fig = px.line(
                df_times,
                x="Date",
                y="Average Duration (s)",
                title="Average Test Execution Time",
                markers=True,
            )

            # Add test count as a bar chart on secondary y-axis
            fig.add_trace(
                go.Bar(
                    x=df_times["Date"],
                    y=df_times["Test Count"],
                    name="Test Count",
                    opacity=0.3,
                    yaxis="y2",
                )
            )

            # Update layout for dual y-axis
            fig.update_layout(
                yaxis=dict(title="Duration (seconds)"),
                yaxis2=dict(title="Test Count", overlaying="y", side="right"),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                margin=dict(t=50, b=0, l=0, r=0),
                hovermode="x unified",
            )

            st.plotly_chart(fig, use_container_width=True)

            # Calculate trend
            if len(avg_durations) >= 2:
                first_duration = avg_durations[0]
                last_duration = avg_durations[-1]

                if first_duration > 0:
                    duration_change_pct = (
                        (last_duration - first_duration) / first_duration * 100
                    )

                    if abs(duration_change_pct) < 5:
                        trend_message = "Test execution time has remained stable."
                    elif duration_change_pct > 0:
                        trend_message = f"Test execution time has increased by {duration_change_pct:.1f}%."
                    else:
                        trend_message = f"Test execution time has decreased by {abs(duration_change_pct):.1f}%."

                    st.info(trend_message)

        with tab3:
            st.subheader("Test reliability-repeatability Index")

            # Create DataFrame for plotting
            df_unreliable = pd.DataFrame(
                {
                    "Date": dates,
                    "reliability-repeatability (%)": nonreliability_rates,
                    "Test Count": test_counts,
                }
            )

            # Create line chart
            fig = px.line(
                df_unreliable,
                x="Date",
                y="reliability-repeatability (%)",
                title="Test reliability-repeatability Index",
                markers=True,
            )

            # Add test count as a bar chart on secondary y-axis
            fig.add_trace(
                go.Bar(
                    x=df_unreliable["Date"],
                    y=df_unreliable["Test Count"],
                    name="Test Count",
                    opacity=0.3,
                    yaxis="y2",
                )
            )

            # Update layout for dual y-axis
            fig.update_layout(
                yaxis=dict(title="reliability-repeatability (%)"),
                yaxis2=dict(title="Test Count", overlaying="y", side="right"),
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                margin=dict(t=50, b=0, l=0, r=0),
                hovermode="x unified",
            )

            st.plotly_chart(fig, use_container_width=True)

            # Calculate trend
            if len(nonreliability_rates) >= 2:
                first_unreliable = nonreliability_rates[0]
                last_unreliable = nonreliability_rates[-1]
                unreliable_change = last_unreliable - first_unreliable

                if abs(unreliable_change) < 1:
                    trend_message = (
                        "Test reliability-repeatability has remained stable."
                    )
                elif unreliable_change > 0:
                    trend_message = f"Test reliability-repeatability has increased by {unreliable_change:.1f}%."
                else:
                    trend_message = f"Test reliability-repeatability has decreased by {abs(unreliable_change):.1f}%."

                st.info(trend_message)

            # Add explanation of reliability-repeatability
            st.markdown(
                """
            **reliability-repeatability Index**: Percentage of tests that have inconsistent outcomes (both pass and fail)
            on the same day. low reliability indicates unstable tests that need attention.
            """
            )

    except Exception as e:
        st.error(f"Error displaying test execution trends: {e}")
        st.code(traceback.format_exc())


def display_test_impact_analysis(api: InsightAPI, sut: Optional[str], days: int):
    """Display test impact analysis to identify critical tests and failure patterns.

    Shows test criticality scores, failure correlations, and co-failing test groups.

    Args:
        api: InsightAPI instance
        sut: Optional system under test filter
        days: Number of days to include in the analysis
    """
    try:
        st.header("Test Impact Analysis")

        # Get sessions for the selected SUT and time range
        sessions = []
        try:
            query = api.query()
            if sut:
                query = query.for_sut(sut)
            result = query.execute()
            sessions = result.sessions
        except Exception as e:
            st.error(f"Error retrieving sessions: {e}")
            st.code(traceback.format_exc())
            return

        # Filter sessions by time range if needed
        if days and sessions:
            try:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                normalized_cutoff = NormalizedDatetime(cutoff)

                filtered_sessions = []
                for s in sessions:
                    if hasattr(s, "session_start_time") and s.session_start_time:
                        # Use NormalizedDatetime to handle timezone differences
                        if (
                            NormalizedDatetime(s.session_start_time)
                            >= normalized_cutoff
                        ):
                            filtered_sessions.append(s)

                sessions = filtered_sessions
            except Exception as e:
                st.error(f"Error filtering sessions by date: {e}")
                st.code(traceback.format_exc())

        if not sessions:
            st.warning("No test sessions found for the selected filters.")
            return

        # Create tabs for different impact analyses
        tab1, tab2, tab3 = st.tabs(
            ["Critical Tests", "Failure Correlations", "Co-Failing Tests"]
        )

        with tab1:
            st.subheader("Most Critical Tests")
            st.markdown(
                """
            Tests are ranked by a criticality score that considers:
            - Frequency of execution
            - Failure rate
            - Average execution time
            - Dependencies (tests that fail when this test fails)
            """
            )

            # Collect test statistics across all sessions
            test_stats = {}
            for session in sessions:
                if not hasattr(session, "test_results") or not session.test_results:
                    continue

                for test in session.test_results:
                    if not hasattr(test, "nodeid") or not test.nodeid:
                        continue

                    nodeid = test.nodeid
                    if nodeid not in test_stats:
                        test_stats[nodeid] = {
                            "count": 0,
                            "failures": 0,
                            "total_duration": 0,
                            "sessions": set(),
                        }

                    test_stats[nodeid]["count"] += 1

                    if hasattr(test, "outcome") and test.outcome == TestOutcome.FAILED:
                        test_stats[nodeid]["failures"] += 1

                    if hasattr(test, "duration") and test.duration is not None:
                        test_stats[nodeid]["total_duration"] += test.duration

                    if hasattr(session, "session_id") and session.session_id:
                        test_stats[nodeid]["sessions"].add(session.session_id)

            # Calculate failure correlations to identify dependencies
            session_failures = {}
            for session in sessions:
                if not hasattr(session, "session_id") or not session.session_id:
                    continue

                if not hasattr(session, "test_results") or not session.test_results:
                    continue

                session_id = session.session_id
                session_failures[session_id] = []

                for test in session.test_results:
                    if (
                        hasattr(test, "nodeid")
                        and hasattr(test, "outcome")
                        and test.outcome == TestOutcome.FAILED
                    ):
                        session_failures[session_id].append(test.nodeid)

            # Calculate dependency scores
            dependency_scores = {}
            for nodeid in test_stats:
                dependency_scores[nodeid] = 0

                # For each test, check how many other tests fail when it fails
                for session_id, failed_tests in session_failures.items():
                    if nodeid in failed_tests:
                        # This test failed in this session
                        # Count how many other tests failed in the same session
                        dependency_scores[nodeid] += len(failed_tests) - 1

            # Calculate criticality scores
            criticality_scores = []
            for nodeid, stats in test_stats.items():
                if stats["count"] == 0:
                    continue

                # Calculate metrics
                failure_rate = stats["failures"] / stats["count"]
                avg_duration = stats["total_duration"] / stats["count"]
                execution_frequency = stats["count"] / len(sessions)
                dependency_score = dependency_scores.get(nodeid, 0)

                # Normalize dependency score (0-1 range)
                max_dependency = (
                    max(dependency_scores.values()) if dependency_scores else 1
                )
                normalized_dependency = (
                    dependency_score / max_dependency if max_dependency > 0 else 0
                )

                # Calculate criticality score (weighted sum of factors)
                criticality = (
                    (failure_rate * 0.4)
                    + (normalized_dependency * 0.3)
                    + (execution_frequency * 0.2)
                    + (
                        min(1.0, avg_duration / 10) * 0.1
                    )  # Cap duration impact at 10 seconds
                )

                # Extract test name from nodeid for better display
                test_name = nodeid.split("::")[-1] if "::" in nodeid else nodeid

                criticality_scores.append(
                    {
                        "nodeid": nodeid,
                        "test_name": test_name,
                        "criticality": criticality * 100,  # Convert to percentage
                        "failure_rate": failure_rate * 100,
                        "avg_duration": avg_duration,
                        "execution_count": stats["count"],
                        "dependency_score": dependency_score,
                    }
                )

            # Sort by criticality score (descending)
            criticality_scores.sort(key=lambda x: x["criticality"], reverse=True)

            # Display top 10 most critical tests
            if criticality_scores:
                df = pd.DataFrame(criticality_scores[:10])

                # Format columns
                df["criticality"] = df["criticality"].apply(lambda x: f"{x:.1f}%")
                df["failure_rate"] = df["failure_rate"].apply(lambda x: f"{x:.1f}%")
                df["avg_duration"] = df["avg_duration"].apply(lambda x: f"{x:.2f}s")

                # Reorder and rename columns for display
                df = df[
                    [
                        "test_name",
                        "criticality",
                        "failure_rate",
                        "avg_duration",
                        "execution_count",
                        "dependency_score",
                    ]
                ]
                df.columns = [
                    "Test Name",
                    "Criticality Score",
                    "Failure Rate",
                    "Avg Duration",
                    "Execution Count",
                    "Dependency Score",
                ]

                st.dataframe(df, use_container_width=True)

                # Explain criticality score
                with st.expander("How is the Criticality Score calculated?"):
                    st.markdown(
                        """
                    The **Criticality Score** is a weighted combination of:

                    - **Failure Rate (40%)**: Tests that fail more often have higher impact
                    - **Dependency Score (30%)**: Tests that correlate with many other failures have higher impact
                    - **Execution Frequency (20%)**: Tests that run more often have higher impact
                    - **Duration (10%)**: Longer tests have higher impact (capped at 10 seconds)

                    Higher scores indicate tests that should be prioritized for maintenance and optimization.
                    """
                    )
            else:
                st.info("No test data available for criticality analysis.")

        with tab2:
            st.subheader("Failure Correlation Matrix")
            st.markdown(
                """
            This matrix shows how often tests fail together. Higher correlation values indicate
            tests that tend to fail in the same sessions, suggesting potential dependencies or
            shared failure causes.
            """
            )

            # Identify frequently failing tests
            failing_tests = []
            for nodeid, stats in test_stats.items():
                if (
                    stats["failures"] >= 2
                ):  # Only include tests that failed at least twice
                    failing_tests.append(nodeid)

            # Limit to top 15 most frequently failing tests to keep matrix readable
            if len(failing_tests) > 15:
                # Sort by failure count
                failing_tests = sorted(
                    failing_tests, key=lambda x: test_stats[x]["failures"], reverse=True
                )[:15]

            if failing_tests:
                # Create correlation matrix
                correlation_matrix = {}
                for test1 in failing_tests:
                    correlation_matrix[test1] = {}
                    for test2 in failing_tests:
                        correlation_matrix[test1][test2] = 0

                # Calculate co-failures
                for session_id, failed_tests in session_failures.items():
                    for test1 in failing_tests:
                        if test1 in failed_tests:
                            for test2 in failing_tests:
                                if test2 in failed_tests and test1 != test2:
                                    correlation_matrix[test1][test2] += 1

                # Convert to correlation coefficients (normalize by failure counts)
                for test1 in failing_tests:
                    for test2 in failing_tests:
                        if test1 != test2:
                            failures1 = test_stats[test1]["failures"]
                            failures2 = test_stats[test2]["failures"]
                            co_failures = correlation_matrix[test1][test2]

                            # Calculate correlation coefficient (0-1)
                            if failures1 > 0 and failures2 > 0:
                                correlation_matrix[test1][test2] = co_failures / min(
                                    failures1, failures2
                                )
                            else:
                                correlation_matrix[test1][test2] = 0

                # Extract test names for better display
                test_names = [
                    nodeid.split("::")[-1] if "::" in nodeid else nodeid
                    for nodeid in failing_tests
                ]

                # Create heatmap data
                heatmap_data = []
                for i, test1 in enumerate(failing_tests):
                    row = []
                    for j, test2 in enumerate(failing_tests):
                        if test1 == test2:
                            row.append(1.0)  # Self-correlation is always 1
                        else:
                            row.append(correlation_matrix[test1][test2])
                    heatmap_data.append(row)

                # Create heatmap
                fig = go.Figure(
                    data=go.Heatmap(
                        z=heatmap_data,
                        x=test_names,
                        y=test_names,
                        colorscale="Viridis",
                        zmin=0,
                        zmax=1,
                    )
                )

                fig.update_layout(
                    title="Test Failure Correlation Matrix",
                    xaxis_title="Test Name",
                    yaxis_title="Test Name",
                    height=600,
                    margin=dict(t=50, b=0, l=0, r=0),
                )

                st.plotly_chart(fig, use_container_width=True)

                # Explain correlation matrix
                with st.expander("How to interpret the Correlation Matrix"):
                    st.markdown(
                        """
                    - **Darker colors** indicate stronger correlations (tests that fail together more often)
                    - **Diagonal** (top-left to bottom-right) always shows 1.0 (self-correlation)
                    - **High correlation** between tests suggests they might:
                      - Share dependencies
                      - Test related functionality
                      - Be affected by the same underlying issues

                    This information can help identify clusters of related tests and potential common failure points.
                    """
                    )
            else:
                st.info("Not enough failing tests for correlation analysis.")

        with tab3:
            st.subheader("Co-Failing Test Groups")
            st.markdown(
                """
            These are clusters of tests that frequently fail together, suggesting they might
            be related or affected by the same underlying issues.

            Understanding co-failing test patterns can help prioritize fixes and identify root causes.
            """
            )

            # Identify co-failing test groups
            co_failing_groups = []

            # Track which tests have been assigned to groups
            assigned_tests = set()

            # For each session with failures, check if it forms a recurring pattern
            session_failure_patterns = {}
            for session_id, failed_tests in session_failures.items():
                if (
                    len(failed_tests) >= 2
                ):  # Only consider sessions with multiple failures
                    # Create a frozen set of failed tests to use as a dictionary key
                    pattern = frozenset(failed_tests)
                    if pattern not in session_failure_patterns:
                        session_failure_patterns[pattern] = 1
                    else:
                        session_failure_patterns[pattern] += 1

            # Find recurring patterns (groups of tests that fail together in multiple sessions)
            recurring_patterns = []
            for pattern, count in session_failure_patterns.items():
                if count >= 2:  # Pattern appears in at least 2 sessions
                    recurring_patterns.append((pattern, count))

            # Sort patterns by frequency (descending)
            recurring_patterns.sort(key=lambda x: x[1], reverse=True)

            # Convert patterns to group information
            for pattern, count in recurring_patterns:
                # Skip if all tests in this pattern are already in groups
                if all(test in assigned_tests for test in pattern):
                    continue

                # Create a new group
                group = {
                    "tests": [test for test in pattern if test not in assigned_tests],
                    "count": count,
                    "test_names": [
                        test.split("::")[-1] if "::" in test else test
                        for test in pattern
                        if test not in assigned_tests
                    ],
                }

                if group["tests"]:
                    co_failing_groups.append(group)
                    assigned_tests.update(group["tests"])

            # Create a matrix to track co-failures for visualization
            test_nodeids = list(test_stats.keys())
            co_failures = {}

            # Initialize the co-failure matrix
            for test_id in test_nodeids:
                co_failures[test_id] = {}
                for other_id in test_nodeids:
                    if test_id != other_id:
                        co_failures[test_id][other_id] = 0

            # Fill the co-failure matrix by analyzing session failures
            for session_id, failed_tests in session_failures.items():
                if (
                    len(failed_tests) > 1
                ):  # Only consider sessions with multiple failures
                    for i, test1 in enumerate(failed_tests):
                        for test2 in failed_tests[i + 1 :]:
                            if test1 in co_failures and test2 in co_failures[test1]:
                                co_failures[test1][test2] += 1
                            if test2 in co_failures and test1 in co_failures[test2]:
                                co_failures[test2][test1] += 1

            # Identify significant co-failure relationships
            significant_co_failures = []
            for test1, others in co_failures.items():
                for test2, count in others.items():
                    if count > 0:
                        # Calculate correlation strength as a percentage of failures
                        test1_failures = test_stats[test1]["failures"]
                        test2_failures = test_stats[test2]["failures"]

                        if test1_failures > 0 and test2_failures > 0:
                            correlation_pct1 = (count / test1_failures) * 100
                            correlation_pct2 = (count / test2_failures) * 100
                            avg_correlation = (correlation_pct1 + correlation_pct2) / 2

                            significant_co_failures.append(
                                {
                                    "test1": test1,
                                    "test2": test2,
                                    "co_failures": count,
                                    "test1_failures": test1_failures,
                                    "test2_failures": test2_failures,
                                    "correlation_pct": avg_correlation,
                                }
                            )

            # Sort by correlation percentage
            significant_co_failures.sort(
                key=lambda x: x["correlation_pct"], reverse=True
            )

            # Display co-failing groups
            if co_failing_groups:
                # Create tabs for different visualizations
                subtab1, subtab2, subtab3 = st.tabs(
                    ["Group View", "Correlation Table", "Network Graph"]
                )

                with subtab1:
                    for i, group in enumerate(
                        co_failing_groups[:5]
                    ):  # Show top 5 groups
                        with st.expander(
                            f"Group {i+1}: {len(group['tests'])} tests, failed together {group['count']} times"
                        ):
                            st.markdown("**Tests in this group:**")
                            for test_name in group["test_names"]:
                                st.markdown(f"- `{test_name}`")

                            st.markdown(
                                f"**Failure frequency:** {group['count']} sessions"
                            )

                            # Calculate potential root causes based on test names
                            common_words = set()
                            for test_name in group["test_names"]:
                                words = set(re.findall(r"[a-zA-Z]+", test_name.lower()))
                                if not common_words:
                                    common_words = words
                                else:
                                    common_words &= words

                            if common_words:
                                st.markdown("**Potential common elements:**")
                                st.markdown(
                                    ", ".join(f"`{word}`" for word in common_words)
                                )

                with subtab2:
                    # Display co-failing test pairs in a table
                    if significant_co_failures:
                        # Create a DataFrame for the table
                        co_failure_df = pd.DataFrame(significant_co_failures)

                        # Simplify nodeids for display
                        co_failure_df["test1_short"] = co_failure_df["test1"].apply(
                            lambda x: x.split("::")[-1] if "::" in x else x
                        )
                        co_failure_df["test2_short"] = co_failure_df["test2"].apply(
                            lambda x: x.split("::")[-1] if "::" in x else x
                        )

                        # Format the table
                        display_df = co_failure_df[
                            [
                                "test1_short",
                                "test2_short",
                                "co_failures",
                                "correlation_pct",
                            ]
                        ].copy()
                        display_df.columns = [
                            "Test 1",
                            "Test 2",
                            "Co-Failures",
                            "Correlation %",
                        ]
                        display_df["Correlation %"] = (
                            display_df["Correlation %"].round(1).astype(str) + "%"
                        )

                        # Show the table with the most significant correlations
                        st.dataframe(display_df.head(20), use_container_width=True)
                    else:
                        st.info("No significant co-failing test pairs detected.")

                with subtab3:
                    # Create a network graph of co-failing tests
                    st.subheader("Co-Failure Network Graph")
                    st.markdown(
                        "This graph shows the relationships between tests that fail together. Larger nodes indicate tests that fail more frequently, and thicker edges indicate stronger co-failure relationships."
                    )

                    # Prepare data for the network graph
                    # Only include the top correlations to avoid cluttering the graph
                    top_correlations = significant_co_failures[
                        : min(30, len(significant_co_failures))
                    ]

                    if top_correlations:
                        # Create nodes and edges for the network graph
                        nodes = set()
                        edges = []

                        for corr in top_correlations:
                            test1_short = (
                                corr["test1"].split("::")[-1]
                                if "::" in corr["test1"]
                                else corr["test1"]
                            )
                            test2_short = (
                                corr["test2"].split("::")[-1]
                                if "::" in corr["test2"]
                                else corr["test2"]
                            )

                            nodes.add(test1_short)
                            nodes.add(test2_short)

                            edges.append(
                                (test1_short, test2_short, corr["correlation_pct"])
                            )

                        # Create node list with failure counts as size
                        node_sizes = {}
                        for node in nodes:
                            # Find the original nodeid
                            for nodeid in test_nodeids:
                                if node == nodeid.split("::")[-1]:
                                    node_sizes[node] = test_stats[nodeid]["failures"]
                                    break

                        # Create the network graph
                        if len(nodes) > 1:
                            try:
                                # Create node and edge dataframes for plotly
                                node_df = pd.DataFrame(
                                    {
                                        "id": list(nodes),
                                        "size": [
                                            node_sizes.get(node, 1) for node in nodes
                                        ],
                                        "failures": [
                                            node_sizes.get(node, 1) for node in nodes
                                        ],
                                    }
                                )

                                edge_df = pd.DataFrame(
                                    edges, columns=["source", "target", "weight"]
                                )

                                # Create the network graph
                                import networkx as nx

                                # Create a graph
                                G = nx.Graph()

                                # Add nodes
                                for _, row in node_df.iterrows():
                                    G.add_node(
                                        row["id"],
                                        size=row["size"],
                                        failures=row["failures"],
                                    )

                                # Add edges
                                for _, row in edge_df.iterrows():
                                    G.add_edge(
                                        row["source"],
                                        row["target"],
                                        weight=row["weight"],
                                    )

                                # Use a layout algorithm to position nodes
                                pos = nx.spring_layout(G, seed=42)

                                # Create the plotly figure
                                edge_trace = []

                                # Add edges
                                for edge in G.edges(data=True):
                                    x0, y0 = pos[edge[0]]
                                    x1, y1 = pos[edge[1]]
                                    weight = edge[2]["weight"]

                                    # Scale line width based on correlation strength
                                    width = 1 + (weight / 20)

                                    edge_trace.append(
                                        go.Scatter(
                                            x=[x0, x1, None],
                                            y=[y0, y1, None],
                                            line=dict(
                                                width=width,
                                                color="rgba(150,150,150,0.7)",
                                            ),
                                            hoverinfo="none",
                                            mode="lines",
                                        )
                                    )

                                # Create node trace
                                node_trace = go.Scatter(
                                    x=[pos[node][0] for node in G.nodes()],
                                    y=[pos[node][1] for node in G.nodes()],
                                    mode="markers",
                                    hoverinfo="text",
                                    marker=dict(
                                        showscale=True,
                                        colorscale="YlOrRd",
                                        color=[
                                            G.nodes[node]["failures"]
                                            for node in G.nodes()
                                        ],
                                        size=[
                                            10 + G.nodes[node]["failures"] * 2
                                            for node in G.nodes()
                                        ],
                                        colorbar=dict(
                                            thickness=15,
                                            title="Failures",
                                            xanchor="left",
                                            titleside="right",
                                        ),
                                        line=dict(width=2),
                                    ),
                                    text=[
                                        f"{node}<br>Failures: {G.nodes[node]['failures']}"
                                        for node in G.nodes()
                                    ],
                                )

                                # Create the figure
                                fig = go.Figure(
                                    data=edge_trace + [node_trace],
                                    layout=go.Layout(
                                        showlegend=False,
                                        hovermode="closest",
                                        margin=dict(b=20, l=5, r=5, t=40),
                                        xaxis=dict(
                                            showgrid=False,
                                            zeroline=False,
                                            showticklabels=False,
                                        ),
                                        yaxis=dict(
                                            showgrid=False,
                                            zeroline=False,
                                            showticklabels=False,
                                        ),
                                        height=600,
                                        title="Co-Failing Test Network",
                                    ),
                                )

                                st.plotly_chart(fig, use_container_width=True)

                                # Add explanation of how to interpret the graph
                                st.info(
                                    """
                                **How to interpret this graph:**
                                - **Nodes (circles)**: Each node represents a test. Larger and darker nodes indicate tests that fail more frequently.
                                - **Edges (lines)**: Connections between tests that fail together. Thicker lines indicate stronger correlations.
                                - **Clusters**: Groups of connected tests often indicate related functionality or shared dependencies.
                                """
                                )
                            except Exception as e:
                                st.error(f"Error creating network graph: {e}")
                                st.code(traceback.format_exc())
                        else:
                            st.info(
                                "Not enough co-failing tests to create a network graph."
                            )
                    else:
                        st.info(
                            "No significant co-failing test patterns detected in the selected time period."
                        )
            else:
                st.info("No recurring co-failing test groups identified.")
    except Exception as e:
        st.error(f"Error displaying test impact analysis: {e}")
        st.code(traceback.format_exc())


def display_failure_pattern_analysis(api: InsightAPI, sut: Optional[str], days: int):
    """Display failure pattern analysis to identify common error patterns and root causes.

    Shows error message clustering, stack trace analysis, and temporal patterns in failures.

    Args:
        api: InsightAPI instance
        sut: Optional system under test filter
        days: Number of days to include in the analysis
    """
    try:
        st.header("Failure Pattern Analysis")

        # Get sessions for the selected SUT and time range
        sessions = []
        try:
            query = api.query()
            if sut:
                query = query.for_sut(sut)
            result = query.execute()
            sessions = result.sessions
        except Exception as e:
            st.error(f"Error retrieving sessions: {e}")
            st.code(traceback.format_exc())
            return

        # Filter sessions by time range if needed
        if days and sessions:
            try:
                cutoff = datetime.now(ZoneInfo("UTC")) - timedelta(days=days)
                normalized_cutoff = NormalizedDatetime(cutoff)

                filtered_sessions = []
                for s in sessions:
                    if hasattr(s, "session_start_time") and s.session_start_time:
                        # Use NormalizedDatetime to handle timezone differences
                        if (
                            NormalizedDatetime(s.session_start_time)
                            >= normalized_cutoff
                        ):
                            filtered_sessions.append(s)

                sessions = filtered_sessions
            except Exception as e:
                st.error(f"Error filtering sessions by date: {e}")
                st.code(traceback.format_exc())

        if not sessions:
            st.warning("No test sessions found for the selected filters.")
            return

        # Create tabs for different failure pattern analyses
        tab1, tab2, tab3 = st.tabs(
            ["Error Message Patterns", "Stack Trace Analysis", "Temporal Patterns"]
        )

        # Extract all failed tests with error messages
        failed_tests = []
        for session in sessions:
            if not hasattr(session, "test_results") or not session.test_results:
                continue

            session_time = None
            if hasattr(session, "session_start_time") and session.session_start_time:
                session_time = session.session_start_time

            for test in session.test_results:
                if (
                    hasattr(test, "outcome")
                    and test.outcome == TestOutcome.FAILED
                    and hasattr(test, "longrepr")
                    and test.longrepr
                ):
                    # Extract error message and stack trace if available
                    error_message = None
                    stack_trace = None

                    if hasattr(test, "longrepr") and test.longrepr:
                        # Try to extract error message from longrepr
                        longrepr = test.longrepr

                        # Handle different formats of longrepr
                        if isinstance(longrepr, str):
                            # Simple string representation
                            error_message = longrepr.strip()

                            # Try to extract the first line as the main error message
                            lines = error_message.split("\n")
                            if lines:
                                error_message = lines[0].strip()
                                stack_trace = (
                                    "\n".join(lines[1:]).strip()
                                    if len(lines) > 1
                                    else None
                                )
                        elif isinstance(longrepr, dict):
                            # Dictionary representation
                            if "message" in longrepr:
                                error_message = longrepr["message"]
                            if "traceback" in longrepr:
                                stack_trace = longrepr["traceback"]

                    # Get session ID
                    session_id = session.session_id

                    # Add to failed tests list
                    failed_tests.append(
                        {
                            "nodeid": (
                                test.nodeid if hasattr(test, "nodeid") else "Unknown"
                            ),
                            "test_name": (
                                test.nodeid.split("::")[-1]
                                if hasattr(test, "nodeid") and "::" in test.nodeid
                                else "Unknown"
                            ),
                            "error_message": error_message,
                            "stack_trace": stack_trace,
                            "session_id": session_id,
                            "session_time": session_time,
                        }
                    )

        if not failed_tests:
            with tab1:
                st.info("No failed tests found for the selected filters.")
                st.markdown(
                    """
                ### Why am I not seeing any data?

                The Failure Pattern Analysis requires tests with failure information. Here are some possible reasons you're not seeing data:

                1. **No failed tests**: Your test suite might have no failures in the selected time period
                2. **Missing error information**: The test failures might not include detailed error messages
                3. **Data format**: The error messages might be in a format that's not being recognized

                Try the following:
                - Increase the time range in the sidebar
                - Select a different System Under Test
                - Run some tests with failures to generate data
                """
                )

                # Add option to show sample data
                if st.button("Show Sample Data", key="sample_failure_data"):
                    st.markdown("### Sample Error Message Patterns")

                    # Create sample error patterns
                    sample_patterns = {
                        "AssertionError: assert 10 == 20": {
                            "count": 15,
                            "tests": [
                                "test_calculation",
                                "test_math_functions",
                                "test_validation",
                            ],
                            "first_seen": "2 days ago",
                            "last_seen": "2 hours ago",
                        },
                        "ImportError: No module named 'missing_dependency'": {
                            "count": 8,
                            "tests": ["test_imports", "test_dependencies"],
                            "first_seen": "5 days ago",
                            "last_seen": "1 day ago",
                        },
                        "TypeError: cannot convert 'NoneType' object to int": {
                            "count": 12,
                            "tests": ["test_conversion", "test_data_processing"],
                            "first_seen": "3 days ago",
                            "last_seen": "6 hours ago",
                        },
                    }

                    # Display sample data
                    for pattern, details in sample_patterns.items():
                        with st.expander(f"{pattern} ({details['count']} occurrences)"):
                            st.markdown(
                                f"**Affected Tests:** {', '.join(details['tests'])}"
                            )
                            st.markdown(f"**First Seen:** {details['first_seen']}")
                            st.markdown(f"**Last Seen:** {details['last_seen']}")
                            st.markdown("**Potential Root Causes:**")
                            if "AssertionError" in pattern:
                                st.markdown("- Calculation logic error")
                                st.markdown("- Test expectations need updating")
                            elif "ImportError" in pattern:
                                st.markdown("- Missing dependency")
                                st.markdown("- Environment configuration issue")
                            elif "TypeError" in pattern:
                                st.markdown("- Null value handling issue")
                                st.markdown("- Data validation missing")

            with tab2:
                st.info("No stack trace data available for analysis.")
                st.markdown(
                    """
                ### Why am I not seeing any data?

                The Stack Trace Analysis requires tests with detailed failure information including stack traces. Here are some possible reasons you're not seeing data:

                1. **No stack traces**: Your test failures might not include stack trace information
                2. **Parse errors**: The stack traces might be in a format that can't be parsed
                3. **Missing line information**: The stack traces might not include file and line information

                Try the following:
                - Increase the time range in the sidebar
                - Select a different System Under Test
                - Run tests with assertion failures that generate stack traces
                - Ensure your test runner is capturing and storing stack traces
                """
                )

            with tab3:
                st.info("No temporal failure data available for analysis.")
                st.markdown(
                    """
                ### Why am I not seeing any data?

                The Temporal Patterns analysis requires tests with timestamps to analyze failure patterns over time. Here are some possible reasons you're not seeing data:

                1. **No timestamps**: Your test sessions might not include timestamp information
                2. **Single session**: You might only have one test session in the selected time range
                3. **No failures**: There might not be any failures to analyze temporal patterns

                Try the following:
                - Increase the time range in the sidebar to include more test sessions
                - Select a different System Under Test
                - Run tests across multiple days/times to generate temporal data
                - Ensure your test runner is capturing and storing session timestamps
                """
                )

            return
        else:
            with tab1:
                st.markdown("### Error Message Patterns")
                st.markdown(
                    """
                This analysis groups similar error messages to identify common failure patterns.
                Understanding these patterns can help prioritize fixes and identify systemic issues.
                """
                )

                # Group error messages by similarity
                error_patterns = {}

                for test in failed_tests:
                    if not test["error_message"]:
                        continue

                    # Normalize error message to create a pattern key
                    # Remove specific values like line numbers, memory addresses, etc.
                    pattern_key = test["error_message"]

                    # Remove specific file paths
                    pattern_key = re.sub(r'File ".*?"', 'File "..."', pattern_key)

                    # Remove line numbers
                    pattern_key = re.sub(r"line \d+", "line XXX", pattern_key)

                    # Remove specific values in error messages
                    pattern_key = re.sub(r"'[^']*'", "'...'", pattern_key)

                    # Remove memory addresses
                    pattern_key = re.sub(r"0x[0-9a-fA-F]+", "0xXXX", pattern_key)

                    # Remove specific numbers
                    pattern_key = re.sub(r"\b\d+\b", "XXX", pattern_key)

                    if pattern_key not in error_patterns:
                        error_patterns[pattern_key] = {
                            "count": 0,
                            "examples": [],
                            "tests": set(),
                        }

                    error_patterns[pattern_key]["count"] += 1
                    error_patterns[pattern_key]["tests"].add(test["nodeid"])

                    # Store up to 3 examples of each pattern
                    if len(error_patterns[pattern_key]["examples"]) < 3:
                        error_patterns[pattern_key]["examples"].append(
                            {
                                "test_name": test["test_name"],
                                "error_message": test["error_message"],
                            }
                        )

                # Convert to list and sort by frequency
                pattern_list = [
                    {
                        "pattern": pattern,
                        "count": data["count"],
                        "examples": data["examples"],
                        "tests": list(data["tests"]),
                        "test_count": len(data["tests"]),
                    }
                    for pattern, data in error_patterns.items()
                ]

                pattern_list.sort(key=lambda x: x["count"], reverse=True)

                # Display error patterns
                if pattern_list:
                    st.write("Common error messages across test failures")

                    for i, pattern in enumerate(
                        pattern_list[:10]
                    ):  # Show top 10 patterns
                        with st.expander(
                            f"{pattern['pattern']} ({pattern['count']} occurrences)"
                        ):
                            st.markdown(
                                f"**Affected Tests:** {', '.join(pattern['tests'])}"
                            )
                            st.markdown("**Example Errors:**")
                            for example in pattern["examples"]:
                                st.markdown(f"- In test `{example['test_name']}`:")
                                st.code(example["error_message"])

                            # Suggest potential root causes
                            st.markdown("**Potential Root Causes:**")

                            # Look for common keywords in the error pattern
                            if "AssertionError" in pattern["pattern"]:
                                st.markdown("- Calculation logic error")
                                st.markdown("- Test expectations need updating")
                            elif (
                                "ImportError" in pattern["pattern"]
                                or "ModuleNotFoundError" in pattern["pattern"]
                            ):
                                st.markdown("- Missing dependency")
                                st.markdown("- Environment configuration issue")
                            elif "AttributeError" in pattern["pattern"]:
                                st.markdown(
                                    "- Missing Attribute: Attempting to access a property or method that doesn't exist"
                                )
                            elif "TypeError" in pattern["pattern"]:
                                st.markdown(
                                    "- Type Mismatch: Function received an incompatible argument type"
                                )
                            elif "ValueError" in pattern["pattern"]:
                                st.markdown(
                                    "- Invalid Value: Function received a value that is the right type but inappropriate"
                                )
                            elif "KeyError" in pattern["pattern"]:
                                st.markdown(
                                    "- Missing Key: Attempted to access a dictionary with a key that doesn't exist"
                                )
                            elif "IndexError" in pattern["pattern"]:
                                st.markdown(
                                    "- Index Out of Range: Attempted to access a list element that doesn't exist"
                                )
                            elif "FileNotFoundError" in pattern["pattern"]:
                                st.markdown(
                                    "- Missing File: Required file doesn't exist at the expected location"
                                )
                            elif "PermissionError" in pattern["pattern"]:
                                st.markdown(
                                    "- Permission Issue: Insufficient permissions to access a resource"
                                )
                            elif (
                                "TimeoutError" in pattern["pattern"]
                                or "timeout" in pattern["pattern"].lower()
                            ):
                                st.markdown(
                                    "- Timeout: Operation took too long to complete"
                                )
                            else:
                                st.markdown(
                                    "- Examine the error message and stack trace for more specific information"
                                )
                else:
                    st.info(
                        "No error patterns could be identified from the failed tests."
                    )

            with tab2:
                st.subheader("Stack Trace Analysis")
                st.markdown(
                    """
                This analysis examines stack traces to identify common failure locations in the code.
                Frequent failures in specific modules or functions may indicate problematic code areas.
                """
                )

                # Extract stack frames from stack traces
                stack_frames = []

                for test in failed_tests:
                    if not test["stack_trace"]:
                        continue

                    # Parse stack trace to extract file and line information
                    trace_lines = test["stack_trace"].split("\n")
                    for line in trace_lines:
                        # Look for lines with file paths and line numbers
                        file_match = re.search(r'File "([^"]+)", line (\d+)', line)
                        if file_match:
                            file_path = file_match.group(1)
                            line_number = file_match.group(2)

                            # Extract function name if available (usually in the next line)
                            func_name = "unknown"
                            if trace_lines.index(line) + 1 < len(trace_lines):
                                next_line = trace_lines[
                                    trace_lines.index(line) + 1
                                ].strip()
                                if next_line.startswith("in "):
                                    func_name = next_line[3:].strip()

                            # Normalize path to just the filename
                            file_name = os.path.basename(file_path)

                            stack_frames.append(
                                {
                                    "file_path": file_path,
                                    "file_name": file_name,
                                    "line_number": line_number,
                                    "func_name": func_name,
                                    "test_nodeid": test["nodeid"],
                                }
                            )

                # Group stack frames by file and function
                frame_groups = {}

                for frame in stack_frames:
                    key = f"{frame['file_name']}:{frame['func_name']}"

                    if key not in frame_groups:
                        frame_groups[key] = {
                            "count": 0,
                            "file_name": frame["file_name"],
                            "func_name": frame["func_name"],
                            "tests": set(),
                            "line_numbers": set(),
                        }

                    frame_groups[key]["count"] += 1
                    frame_groups[key]["tests"].add(frame["test_nodeid"])
                    frame_groups[key]["line_numbers"].add(frame["line_number"])

                # Convert to list and sort by frequency
                frame_list = [
                    {
                        "key": key,
                        "count": data["count"],
                        "file_name": data["file_name"],
                        "func_name": data["func_name"],
                        "tests": list(data["tests"]),
                        "test_count": len(data["tests"]),
                        "line_numbers": sorted(list(data["line_numbers"])),
                    }
                    for key, data in frame_groups.items()
                ]

                frame_list.sort(key=lambda x: x["count"], reverse=True)

                # Display stack frame analysis
                if frame_list:
                    st.write(
                        f"Found {len(frame_list)} distinct failure locations in the code"
                    )

                    # Create a bar chart of top failure locations
                    top_frames = frame_list[:10]  # Top 10 failure locations

                    fig = go.Figure()
                    fig.add_trace(
                        go.Bar(
                            x=[
                                f"{frame['file_name']}:{frame['func_name']}"
                                for frame in top_frames
                            ],
                            y=[frame["count"] for frame in top_frames],
                            marker_color="indianred",
                        )
                    )

                    fig.update_layout(
                        title="Top Failure Locations in Code",
                        xaxis_title="File:Function",
                        yaxis_title="Failure Count",
                        height=400,
                        margin=dict(t=50, b=0, l=0, r=0),
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Show detailed information for each failure location
                    for i, frame in enumerate(top_frames):
                        with st.expander(
                            f"{frame['file_name']}:{frame['func_name']} - {frame['count']} failures"
                        ):
                            st.markdown(f"**File:** `{frame['file_name']}`")
                            st.markdown(f"**Function:** `{frame['func_name']}`")
                            st.markdown(
                                f"**Line Numbers:** {', '.join(frame['line_numbers'])}"
                            )
                            st.markdown(f"**Failed Tests:** {frame['test_count']}")

                            # Show a sample of failed tests
                            if frame["tests"]:
                                st.markdown("**Sample Failed Tests:**")
                                for test in frame["tests"][:5]:  # Show up to 5 tests
                                    test_name = (
                                        test.split("::")[-1] if "::" in test else test
                                    )
                                    st.markdown(f"- `{test_name}`")
                else:
                    st.info(
                        "No stack trace information could be extracted from the failed tests."
                    )

            with tab3:
                st.subheader("Temporal Failure Patterns")
                st.markdown(
                    """
                This analysis examines how failures occur over time to identify temporal patterns.
                Patterns may include time-of-day dependencies, gradual degradation, or sudden spikes.
                """
                )

                # Group failures by date
                date_failures = {}

                for test in failed_tests:
                    if not test["session_time"]:
                        continue

                    # Extract date from session time
                    session_date = (
                        test["session_time"].date()
                        if hasattr(test["session_time"], "date")
                        else None
                    )
                    if not session_date:
                        continue

                    if session_date not in date_failures:
                        date_failures[session_date] = {"count": 0, "tests": set()}

                    date_failures[session_date]["count"] += 1
                    date_failures[session_date]["tests"].add(test["nodeid"])

                # Group failures by hour of day
                hour_failures = {}

                for test in failed_tests:
                    if not test["session_time"]:
                        continue

                    # Extract hour from session time
                    session_hour = (
                        test["session_time"].hour
                        if hasattr(test["session_time"], "hour")
                        else None
                    )
                    if session_hour is None:
                        continue

                    if session_hour not in hour_failures:
                        hour_failures[session_hour] = {"count": 0, "tests": set()}

                    hour_failures[session_hour]["count"] += 1
                    hour_failures[session_hour]["tests"].add(test["nodeid"])

                # Create time series data
                if date_failures:
                    dates = sorted(date_failures.keys())
                    failure_counts = [date_failures[date]["count"] for date in dates]
                    unique_test_counts = [
                        len(date_failures[date]["tests"]) for date in dates
                    ]

                    # Create time series chart
                    fig = go.Figure()

                    fig.add_trace(
                        go.Scatter(
                            x=dates,
                            y=failure_counts,
                            mode="lines+markers",
                            name="Total Failures",
                            line=dict(color="indianred", width=2),
                        )
                    )

                    fig.add_trace(
                        go.Scatter(
                            x=dates,
                            y=unique_test_counts,
                            mode="lines+markers",
                            name="Unique Failed Tests",
                            line=dict(color="royalblue", width=2),
                        )
                    )

                    fig.update_layout(
                        title="Failures Over Time",
                        xaxis_title="Date",
                        yaxis_title="Count",
                        height=400,
                        margin=dict(t=50, b=0, l=0, r=0),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1,
                        ),
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Check for trends
                    if len(dates) >= 3:
                        # Simple trend detection
                        first_half = sum(failure_counts[: len(failure_counts) // 2]) / (
                            len(failure_counts) // 2
                        )
                        second_half = sum(
                            failure_counts[len(failure_counts) // 2 :]
                        ) / (len(failure_counts) - len(failure_counts) // 2)

                        trend_percentage = (
                            ((second_half - first_half) / first_half * 100)
                            if first_half > 0
                            else 0
                        )

                        if abs(trend_percentage) >= 10:  # 10% change threshold
                            if trend_percentage > 0:
                                st.warning(
                                    f"⚠️ Failures are increasing over time (up {trend_percentage:.1f}% on average)"
                                )
                            else:
                                st.success(
                                    f"✅ Failures are decreasing over time (down {abs(trend_percentage):.1f}% on average)"
                                )

                # Create hour of day distribution
                if hour_failures:
                    all_hours = list(range(24))

                    # Fill in missing hours with zeros
                    all_hourly_counts = [
                        hour_failures.get(hour, {"count": 0})["count"]
                        for hour in all_hours
                    ]

                    # Create hour distribution chart
                    fig = go.Figure()

                    fig.add_trace(
                        go.Bar(
                            x=all_hours, y=all_hourly_counts, marker_color="indianred"
                        )
                    )

                    fig.update_layout(
                        title="Failures by Hour of Day",
                        xaxis_title="Hour (24-hour format)",
                        yaxis_title="Failure Count",
                        height=400,
                        margin=dict(t=50, b=0, l=0, r=0),
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # Check for time-of-day patterns
                    max_hour = all_hours[
                        all_hourly_counts.index(max(all_hourly_counts))
                    ]
                    max_count = max(all_hourly_counts)
                    avg_count = (
                        sum(all_hourly_counts)
                        / len([c for c in all_hourly_counts if c > 0])
                        if any(all_hourly_counts)
                        else 0
                    )

                    if max_count > 2 * avg_count:  # Significant spike
                        st.warning(
                            f"⚠️ Significant spike in failures at hour {max_hour}:00 (UTC)"
                        )

                        # Categorize time periods
                        if 0 <= max_hour < 6:
                            period = "night/early morning"
                        elif 6 <= max_hour < 12:
                            period = "morning"
                        elif 12 <= max_hour < 18:
                            period = "afternoon"
                        else:
                            period = "evening"

                        st.markdown(
                            """
                        **Potential causes for time-of-day patterns:**
                        - Scheduled jobs or maintenance during """
                            + period
                            + """ hours
                        - Resource contention with other processes
                        - Time-dependent test data or configurations
                        - Database or service maintenance windows
                        """
                        )

            if not date_failures and not hour_failures:
                st.info(
                    "Not enough temporal data to analyze failure patterns over time."
                )

    except Exception as e:
        st.error(f"Error displaying failure pattern analysis: {e}")
        st.code(traceback.format_exc())


def get_available_suts(api: InsightAPI) -> List[str]:
    """Get a list of available SUTs from all sessions in storage.

    Args:
        api: InsightAPI instance

    Returns:
        List of unique SUTs
    """
    try:
        # Get all sessions from storage
        sessions = api.query().execute().sessions

        # Extract unique SUTs
        suts = set()
        for session in sessions:
            if hasattr(session, "sut_name") and session.sut_name:
                suts.add(session.sut_name)

        # Return sorted list
        return sorted(list(suts))
    except Exception as e:
        # Log the error and return empty list
        st.sidebar.error(f"Error getting SUTs: {e}")
        st.sidebar.code(traceback.format_exc())
        return []


def main():
    """Main entry point for the dashboard."""
    try:
        # Set up the page
        setup_page()

        # Select profile
        profile_name = select_profile()

        # Initialize API with the selected profile
        api = InsightAPI(profile_name=profile_name)

        # Sidebar controls
        st.sidebar.header("Filters")

        # SUT selection
        sut_options = ["All SUTs"] + get_available_suts(api)
        selected_sut = st.sidebar.selectbox(
            "System Under Test",
            options=sut_options,
            index=0,
            help="Filter data by System Under Test",
        )

        # Convert "All SUTs" to None for API calls
        if selected_sut == "All SUTs":
            sut = None
        else:
            sut = selected_sut

        # Time range selection
        days = st.sidebar.slider(
            "Time Range (days)",
            min_value=1,
            max_value=90,
            value=30,
            step=1,
            help="Number of days to include in the analysis",
        )

        # HTML Report Generation Section
        st.sidebar.header("Export & Reports")

        # Add HTML report generation section
        with st.sidebar.expander("Generate HTML Report", expanded=False):
            st.markdown(
                "Generate a standalone HTML report with all test results and visualizations."
            )

            report_title = st.text_input(
                "Report Title",
                value="Test Report - "
                + selected_sut
                + " - "
                + datetime.now().strftime("%Y-%m-%d"),
                help="Custom title for the HTML report",
            )

            # Create command string for the user to run
            report_cmd = "insight report generate"
            if profile_name:
                report_cmd += ' --profile "' + profile_name + '"'
            if days:
                report_cmd += " --days " + str(days)
            if selected_sut != "All SUTs":
                report_cmd += ' --title "' + report_title + '"'

            st.code(report_cmd, language="bash")

            if st.button("Generate Report", key="generate_report"):
                try:
                    import subprocess
                    import tempfile

                    # Create a temporary file for the report
                    with tempfile.NamedTemporaryFile(
                        suffix=".html", delete=False
                    ) as tmp:
                        report_path = tmp.name

                    # Build the command
                    cmd = ["insight", "report", "generate", "--output", report_path]
                    if profile_name:
                        cmd.extend(["--profile", profile_name])
                    if days:
                        cmd.extend(["--days", str(days)])
                    if report_title:
                        cmd.extend(["--title", report_title])

                    # Run the command
                    process = subprocess.run(cmd, capture_output=True, text=True)

                    if process.returncode == 0:
                        # Success - provide download link
                        with open(report_path, "r") as f:
                            report_content = f.read()

                        st.download_button(
                            label="Download HTML Report",
                            data=report_content,
                            file_name="pytest_insight_report_"
                            + datetime.now().strftime("%Y%m%d_%H%M%S")
                            + ".html",
                            mime="text/html",
                        )
                        st.success(
                            "Report generated successfully! Click the button above to download."
                        )
                    else:
                        # Error
                        st.error("Error generating report: " + process.stderr)

                except Exception as e:
                    st.error("Error generating report: " + str(e))
                    st.code(traceback.format_exc())

        # Add dashboard control section
        st.sidebar.header("Dashboard Controls")

        # Add shutdown button
        if st.sidebar.button(
            "Shutdown Dashboard", type="primary", use_container_width=True
        ):
            st.sidebar.warning("Shutting down dashboard server...")
            # Create a flag file that will be checked by the dashboard launcher
            shutdown_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "shutdown_dashboard.flag"
            )
            with open(shutdown_file, "w") as f:
                f.write(str(datetime.now()))

            # Show a message to the user
            st.sidebar.success("Shutdown signal sent. You can close this browser tab.")

            # Use JavaScript to close the browser tab after a short delay
            st.sidebar.markdown(
                """
            <script>
                setTimeout(function() {
                    window.close();
                }, 3000);
            </script>
            """,
                unsafe_allow_html=True,
            )

        # Display tabs for different dashboards
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "Health Metrics",
                "Stability Trends",
                "Predictive Insights",
                "Test Execution Trends",
                "Test Impact Analysis",
                "Failure Pattern Analysis",
            ]
        )

        with tab1:
            display_health_metrics(api, sut, days)

        with tab2:
            display_stability_trends(api, sut, days)

        with tab3:
            display_predictive_insights(api, sut, days)

        with tab4:
            display_test_execution_trends(api, sut, days)

        with tab5:
            display_test_impact_analysis(api, sut, days)

        with tab6:
            display_failure_pattern_analysis(api, sut, days)
    except Exception as e:
        st.error(f"Unexpected error in dashboard: {e}")
        st.code(traceback.format_exc())
        # Also print to console for terminal visibility
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc()


if __name__ == "__main__":
    main()
