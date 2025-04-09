#!/usr/bin/env python
"""Streamlit dashboard for pytest-insight."""

import sys
import traceback
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from zoneinfo import ZoneInfo

from pytest_insight.core.core_api import InsightAPI
from pytest_insight.core.models import TestOutcome
from pytest_insight.core.storage import get_active_profile, list_profiles
from pytest_insight.utils.utils import NormalizedDatetime
import re

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
    # Get available profiles
    profiles = list_profiles()
    active_profile = get_active_profile()
    
    # Check if profiles is a dict (old format) or list (new format)
    if isinstance(profiles, dict):
        profile_options = list(profiles.keys())
    else:
        profile_options = profiles
    
    # Default to active profile
    default_index = 0
    if active_profile:
        if isinstance(active_profile, dict) and 'name' in active_profile:
            active_name = active_profile['name']
        elif hasattr(active_profile, 'name'):
            active_name = active_profile.name
        else:
            active_name = str(active_profile)
            
        if active_name in profile_options:
            default_index = profile_options.index(active_name)
    
    # Let user select profile
    profile_name = st.sidebar.selectbox(
        "Storage Profile",
        options=profile_options,
        index=default_index,
        help="Select a storage profile to use",
    )
    
    return profile_name


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
                        if NormalizedDatetime(s.session_start_time) >= normalized_cutoff:
                            filtered_sessions.append(s)
                
                sessions = filtered_sessions
                st.sidebar.info(f"Filtered to {len(sessions)} sessions in last {days} days")
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
        
        # Display metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            try:
                pass_rate = health_report.get('pass_rate', 0)
                if isinstance(pass_rate, float) and pass_rate <= 1.0:
                    # Convert from decimal to percentage if needed
                    pass_rate = pass_rate * 100
                
                pass_rate_trend = health_report.get('pass_rate_trend', 0)
                if isinstance(pass_rate_trend, float) and pass_rate_trend <= 1.0:
                    pass_rate_trend = pass_rate_trend * 100
                    
                st.metric(
                    "Pass Rate",
                    f"{float(pass_rate):.1f}%",
                    delta=f"{float(pass_rate_trend):.1f}%",
                    delta_color="normal",
                )
            except Exception as e:
                st.metric("Pass Rate", "N/A")
                st.error(f"Error displaying pass rate: {e}")
        
        with col2:
            try:
                flaky_rate = health_report.get('flaky_rate', 0)
                if isinstance(flaky_rate, float) and flaky_rate <= 1.0:
                    # Convert from decimal to percentage if needed
                    flaky_rate = flaky_rate * 100
                
                flaky_rate_trend = health_report.get('flaky_rate_trend', 0)
                if isinstance(flaky_rate_trend, float) and flaky_rate_trend <= 1.0:
                    flaky_rate_trend = flaky_rate_trend * 100
                    
                st.metric(
                    "Flaky Rate",
                    f"{float(flaky_rate):.1f}%",
                    delta=f"{-float(flaky_rate_trend):.1f}%",
                    delta_color="inverse",
                )
            except Exception as e:
                st.metric("Flaky Rate", "N/A")
                st.error(f"Error displaying flaky rate: {e}")
        
        with col3:
            try:
                avg_duration = health_report.get('avg_duration', 0)
                duration_trend = health_report.get('duration_trend', 0)
                
                st.metric(
                    "Avg Duration",
                    f"{float(avg_duration):.2f}s",
                    delta=f"{-float(duration_trend):.2f}s",
                    delta_color="inverse",
                )
            except Exception as e:
                st.metric("Avg Duration", "N/A")
                st.error(f"Error displaying duration: {e}")
        
        with col4:
            try:
                health_score = health_report.get('health_score', 0)
                # Handle different types of health score values
                if isinstance(health_score, dict):
                    # If health_score is a dictionary, extract the overall score
                    score_value = health_score.get('overall', 0)
                elif isinstance(health_score, (int, float)):
                    score_value = health_score
                else:
                    # Default fallback
                    score_value = 0
                    
                # Also handle health_score_trend
                health_trend = health_report.get('health_score_trend', 0)
                if isinstance(health_trend, dict):
                    trend_value = health_trend.get('overall', 0)
                elif isinstance(health_trend, (int, float)):
                    trend_value = health_trend
                else:
                    trend_value = 0
                    
                st.metric(
                    "Health Score",
                    f"{float(score_value):.1f}/10",
                    delta=f"{float(trend_value):.1f}",
                    delta_color="normal",
                )
            except Exception as e:
                st.metric("Health Score", "N/A")
                st.error(f"Error displaying health score: {e}")
        
        # Display test outcome breakdown
        st.subheader("Test Outcome Distribution")
        
        # Calculate outcome counts
        outcome_counts = {}
        try:
            # First try to get from health report if available
            if 'outcome_distribution' in health_report:
                outcome_counts = health_report['outcome_distribution']
            else:
                # Otherwise calculate from sessions
                for session in sessions:
                    if hasattr(session, "test_results") and session.test_results:
                        for test in session.test_results:
                            if hasattr(test, "outcome") and test.outcome:
                                outcome = test.outcome
                                if isinstance(outcome, TestOutcome):
                                    outcome = outcome.value.lower()
                                outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
            
            if outcome_counts:
                # Create DataFrame for plotting
                df = pd.DataFrame({
                    'Outcome': list(outcome_counts.keys()),
                    'Count': list(outcome_counts.values())
                })
                
                # Create pie chart
                fig = px.pie(
                    df, 
                    values='Count', 
                    names='Outcome',
                    color='Outcome',
                    color_discrete_map={
                        'passed': 'green',
                        'failed': 'red',
                        'skipped': 'gray',
                        'error': 'darkred',
                        'xfailed': 'orange',
                        'xpassed': 'lightgreen'
                    }
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
                        if NormalizedDatetime(s.session_start_time) >= normalized_cutoff:
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
                    "data_points": []
                },
                "duration_trend": {
                    "direction": "stable",
                    "significant": False,
                    "data_points": []
                }
            }
            
            # Group sessions by date
            sessions_by_date = {}
            for session in sessions:
                if hasattr(session, "session_start_time") and session.session_start_time:
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
                        if hasattr(test, "outcome") and test.outcome == TestOutcome.FAILED:
                            failed_tests += 1
                        if hasattr(test, "duration") and test.duration:
                            total_duration += test.duration
                
                # Add failure rate data point
                failure_rate = failed_tests / total_tests if total_tests > 0 else 0
                trends["failure_trend"]["data_points"].append({
                    "date": date_key,
                    "rate": failure_rate
                })
                
                # Add duration data point
                avg_duration = total_duration / total_tests if total_tests > 0 else 0
                trends["duration_trend"]["data_points"].append({
                    "date": date_key,
                    "duration": avg_duration
                })
            
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
                if 'failure_trend' in trends and trends['failure_trend']:
                    failure_data = trends['failure_trend']
                    
                    # Create DataFrame for plotting
                    dates = []
                    rates = []
                    
                    for point in failure_data.get('data_points', []):
                        dates.append(point.get('date'))
                        rates.append(point.get('rate', 0) * 100)  # Convert to percentage
                    
                    if dates and rates:
                        df = pd.DataFrame({
                            'Date': dates,
                            'Failure Rate (%)': rates
                        })
                        
                        # Create line chart
                        fig = px.line(
                            df, 
                            x='Date', 
                            y='Failure Rate (%)',
                            markers=True
                        )
                        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Display trend information
                        trend_direction = failure_data.get('direction', 'stable')
                        trend_significant = failure_data.get('significant', False)
                        
                        if trend_significant:
                            if trend_direction == 'increasing':
                                st.warning(f"⚠️ Failure rate is significantly increasing")
                            elif trend_direction == 'decreasing':
                                st.success(f"✅ Failure rate is significantly decreasing")
                        else:
                            st.info(f"ℹ️ Failure rate is stable")
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
                if 'duration_trend' in trends and trends['duration_trend']:
                    duration_data = trends['duration_trend']
                    
                    # Create DataFrame for plotting
                    dates = []
                    durations = []
                    
                    for point in duration_data.get('data_points', []):
                        dates.append(point.get('date'))
                        durations.append(point.get('duration', 0))
                    
                    if dates and durations:
                        df = pd.DataFrame({
                            'Date': dates,
                            'Duration (s)': durations
                        })
                        
                        # Create line chart
                        fig = px.line(
                            df, 
                            x='Date', 
                            y='Duration (s)',
                            markers=True
                        )
                        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Display trend information
                        trend_direction = duration_data.get('direction', 'stable')
                        trend_significant = duration_data.get('significant', False)
                        
                        if trend_significant:
                            if trend_direction == 'increasing':
                                st.warning(f"⚠️ Test duration is significantly increasing")
                            elif trend_direction == 'decreasing':
                                st.success(f"✅ Test duration is significantly decreasing")
                        else:
                            st.info(f"ℹ️ Test duration is stable")
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
                        if NormalizedDatetime(s.session_start_time) >= normalized_cutoff:
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
                
                if predictions and isinstance(predictions, dict) and 'predictions' in predictions:
                    pred_data = predictions['predictions']
                    
                    if isinstance(pred_data, dict) and pred_data:
                        # Convert dictionary to list of dictionaries for display
                        pred_list = [{"test": test, "probability": prob} 
                                    for test, prob in pred_data.items()]
                        
                        # Sort by probability (descending)
                        pred_list = sorted(pred_list, key=lambda x: x["probability"], reverse=True)
                        
                        # Create DataFrame for displaying predictions
                        df = pd.DataFrame(pred_list)
                        
                        # Format probability as percentage
                        if 'probability' in df.columns:
                            df['probability'] = df['probability'].apply(lambda x: f"{x*100:.1f}%")
                        
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
                
                if forecast and isinstance(forecast, dict) and 'forecasted_stability' in forecast:
                    # Create a simple display of the forecast
                    current = forecast.get('current_stability')
                    forecasted = forecast.get('forecasted_stability')
                    trend = forecast.get('trend_direction')
                    factors = forecast.get('contributing_factors', [])
                    
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
                            st.metric("Forecasted Stability", f"{forecasted:.1f}%", delta=delta)
                    
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
                
                if anomalies and isinstance(anomalies, dict) and 'anomalies' in anomalies:
                    anomaly_list = anomalies.get('anomalies', [])
                    
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
    
    Shows historical pass/fail rates, execution time trends, and flakiness metrics.
    
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
                        if NormalizedDatetime(s.session_start_time) >= normalized_cutoff:
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
                key=lambda s: getattr(s, "session_start_time", datetime.now(ZoneInfo("UTC")))
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
        flaky_rates = []
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
            passed_tests = sum(1 for t in all_tests if hasattr(t, "outcome") and t.outcome == TestOutcome.PASSED)
            failed_tests = sum(1 for t in all_tests if hasattr(t, "outcome") and t.outcome == TestOutcome.FAILED)
            
            # Calculate average duration
            durations = [t.duration for t in all_tests if hasattr(t, "duration") and t.duration is not None]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # Calculate flakiness (tests that have both passed and failed on the same day)
            test_outcomes = {}
            for test in all_tests:
                if hasattr(test, "nodeid") and hasattr(test, "outcome"):
                    if test.nodeid not in test_outcomes:
                        test_outcomes[test.nodeid] = set()
                    test_outcomes[test.nodeid].add(test.outcome)
            
            flaky_tests = sum(1 for outcomes in test_outcomes.values() if len(outcomes) > 1)
            flaky_rate = flaky_tests / len(test_outcomes) if test_outcomes else 0
            
            # Store metrics
            dates.append(date_key)
            pass_rates.append(passed_tests / total_tests * 100 if total_tests > 0 else 0)
            fail_rates.append(failed_tests / total_tests * 100 if total_tests > 0 else 0)
            avg_durations.append(avg_duration)
            flaky_rates.append(flaky_rate * 100)  # Convert to percentage
            test_counts.append(total_tests)
        
        if not dates:
            st.warning("No test data available for the selected time range.")
            return
        
        # Create tabs for different trend visualizations
        tab1, tab2, tab3 = st.tabs(["Pass/Fail Rates", "Execution Times", "Flakiness Index"])
        
        with tab1:
            st.subheader("Pass/Fail Rates Over Time")
            
            # Create DataFrame for plotting
            df_rates = pd.DataFrame({
                "Date": dates,
                "Pass Rate (%)": pass_rates,
                "Fail Rate (%)": fail_rates,
                "Test Count": test_counts
            })
            
            # Create multi-line chart
            fig = px.line(
                df_rates, 
                x="Date", 
                y=["Pass Rate (%)", "Fail Rate (%)"],
                title="Test Pass/Fail Rates",
                markers=True
            )
            
            # Add test count as a bar chart on secondary y-axis
            fig.add_trace(
                go.Bar(
                    x=df_rates["Date"],
                    y=df_rates["Test Count"],
                    name="Test Count",
                    opacity=0.3,
                    yaxis="y2"
                )
            )
            
            # Update layout for dual y-axis
            fig.update_layout(
                yaxis=dict(title="Rate (%)"),
                yaxis2=dict(
                    title="Test Count",
                    overlaying="y",
                    side="right"
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=50, b=0, l=0, r=0),
                hovermode="x unified"
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
                    trend_message = f"Pass rate has improved by {pass_rate_change:.1f}%."
                else:
                    trend_message = f"Pass rate has decreased by {abs(pass_rate_change):.1f}%."
                
                st.info(trend_message)
        
        with tab2:
            st.subheader("Test Execution Times")
            
            # Create DataFrame for plotting
            df_times = pd.DataFrame({
                "Date": dates,
                "Average Duration (s)": avg_durations,
                "Test Count": test_counts
            })
            
            # Create line chart
            fig = px.line(
                df_times, 
                x="Date", 
                y="Average Duration (s)",
                title="Average Test Execution Time",
                markers=True
            )
            
            # Add test count as a bar chart on secondary y-axis
            fig.add_trace(
                go.Bar(
                    x=df_times["Date"],
                    y=df_times["Test Count"],
                    name="Test Count",
                    opacity=0.3,
                    yaxis="y2"
                )
            )
            
            # Update layout for dual y-axis
            fig.update_layout(
                yaxis=dict(title="Duration (seconds)"),
                yaxis2=dict(
                    title="Test Count",
                    overlaying="y",
                    side="right"
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=50, b=0, l=0, r=0),
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Calculate trend
            if len(avg_durations) >= 2:
                first_duration = avg_durations[0]
                last_duration = avg_durations[-1]
                
                if first_duration > 0:
                    duration_change_pct = (last_duration - first_duration) / first_duration * 100
                    
                    if abs(duration_change_pct) < 5:
                        trend_message = "Test execution time has remained stable."
                    elif duration_change_pct > 0:
                        trend_message = f"Test execution time has increased by {duration_change_pct:.1f}%."
                    else:
                        trend_message = f"Test execution time has decreased by {abs(duration_change_pct):.1f}%."
                    
                    st.info(trend_message)
        
        with tab3:
            st.subheader("Test Flakiness Index")
            
            # Create DataFrame for plotting
            df_flaky = pd.DataFrame({
                "Date": dates,
                "Flakiness (%)": flaky_rates,
                "Test Count": test_counts
            })
            
            # Create line chart
            fig = px.line(
                df_flaky, 
                x="Date", 
                y="Flakiness (%)",
                title="Test Flakiness Index",
                markers=True
            )
            
            # Add test count as a bar chart on secondary y-axis
            fig.add_trace(
                go.Bar(
                    x=df_flaky["Date"],
                    y=df_flaky["Test Count"],
                    name="Test Count",
                    opacity=0.3,
                    yaxis="y2"
                )
            )
            
            # Update layout for dual y-axis
            fig.update_layout(
                yaxis=dict(title="Flakiness (%)"),
                yaxis2=dict(
                    title="Test Count",
                    overlaying="y",
                    side="right"
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=50, b=0, l=0, r=0),
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Calculate trend
            if len(flaky_rates) >= 2:
                first_flaky = flaky_rates[0]
                last_flaky = flaky_rates[-1]
                flaky_change = last_flaky - first_flaky
                
                if abs(flaky_change) < 1:
                    trend_message = "Test flakiness has remained stable."
                elif flaky_change > 0:
                    trend_message = f"Test flakiness has increased by {flaky_change:.1f}%."
                else:
                    trend_message = f"Test flakiness has decreased by {abs(flaky_change):.1f}%."
                
                st.info(trend_message)
                
            # Add explanation of flakiness
            st.markdown("""
            **Flakiness Index**: Percentage of tests that have inconsistent outcomes (both pass and fail) 
            on the same day. High flakiness indicates unstable tests that need attention.
            """)
            
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
                        if NormalizedDatetime(s.session_start_time) >= normalized_cutoff:
                            filtered_sessions.append(s)
                
                sessions = filtered_sessions
            except Exception as e:
                st.error(f"Error filtering sessions by date: {e}")
                st.code(traceback.format_exc())
        
        if not sessions:
            st.warning("No test sessions found for the selected filters.")
            return
        
        # Create tabs for different impact analyses
        tab1, tab2, tab3 = st.tabs(["Critical Tests", "Failure Correlations", "Co-Failing Tests"])
        
        with tab1:
            st.subheader("Most Critical Tests")
            st.markdown("""
            Tests are ranked by a criticality score that considers:
            - Frequency of execution
            - Failure rate
            - Average execution time
            - Dependencies (tests that fail when this test fails)
            """)
            
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
                            "sessions": set()
                        }
                    
                    test_stats[nodeid]["count"] += 1
                    
                    if hasattr(test, "outcome") and test.outcome == TestOutcome.FAILED:
                        test_stats[nodeid]["failures"] += 1
                    
                    if hasattr(test, "duration") and test.duration is not None:
                        test_stats[nodeid]["total_duration"] += test.duration
                    
                    if hasattr(session, "id") and session.id:
                        test_stats[nodeid]["sessions"].add(session.id)
            
            # Calculate failure correlations to identify dependencies
            session_failures = {}
            for session in sessions:
                if not hasattr(session, "id") or not session.id:
                    continue
                
                if not hasattr(session, "test_results") or not session.test_results:
                    continue
                
                session_id = session.id
                session_failures[session_id] = []
                
                for test in session.test_results:
                    if hasattr(test, "nodeid") and hasattr(test, "outcome") and test.outcome == TestOutcome.FAILED:
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
                max_dependency = max(dependency_scores.values()) if dependency_scores else 1
                normalized_dependency = dependency_score / max_dependency if max_dependency > 0 else 0
                
                # Calculate criticality score (weighted sum of factors)
                criticality = (
                    (failure_rate * 0.4) +
                    (normalized_dependency * 0.3) +
                    (execution_frequency * 0.2) +
                    (min(1.0, avg_duration / 10) * 0.1)  # Cap duration impact at 10 seconds
                )
                
                # Extract test name from nodeid for better display
                test_name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
                
                criticality_scores.append({
                    "nodeid": nodeid,
                    "test_name": test_name,
                    "criticality": criticality * 100,  # Convert to percentage
                    "failure_rate": failure_rate * 100,
                    "avg_duration": avg_duration,
                    "execution_count": stats["count"],
                    "dependency_score": dependency_score
                })
            
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
                df = df[["test_name", "criticality", "failure_rate", "avg_duration", 
                         "execution_count", "dependency_score"]]
                df.columns = ["Test Name", "Criticality Score", "Failure Rate", 
                              "Avg Duration", "Execution Count", "Dependency Score"]
                
                st.dataframe(df, use_container_width=True)
                
                # Explain criticality score
                with st.expander("How is the Criticality Score calculated?"):
                    st.markdown("""
                    The **Criticality Score** is a weighted combination of:
                    
                    - **Failure Rate (40%)**: Tests that fail more often have higher impact
                    - **Dependency Score (30%)**: Tests that correlate with many other failures have higher impact
                    - **Execution Frequency (20%)**: Tests that run more often have higher impact
                    - **Duration (10%)**: Longer tests have higher impact (capped at 10 seconds)
                    
                    Higher scores indicate tests that should be prioritized for maintenance and optimization.
                    """)
            else:
                st.info("No test data available for criticality analysis.")
        
        with tab2:
            st.subheader("Failure Correlation Matrix")
            st.markdown("""
            This matrix shows how often tests fail together. Higher correlation values indicate 
            tests that tend to fail in the same sessions, suggesting potential dependencies or 
            shared failure causes.
            """)
            
            # Identify frequently failing tests
            failing_tests = []
            for nodeid, stats in test_stats.items():
                if stats["failures"] >= 2:  # Only include tests that failed at least twice
                    failing_tests.append(nodeid)
            
            # Limit to top 15 most frequently failing tests to keep matrix readable
            if len(failing_tests) > 15:
                # Sort by failure count
                failing_tests = sorted(
                    failing_tests, 
                    key=lambda x: test_stats[x]["failures"],
                    reverse=True
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
                                correlation_matrix[test1][test2] = co_failures / min(failures1, failures2)
                            else:
                                correlation_matrix[test1][test2] = 0
                
                # Extract test names for better display
                test_names = [nodeid.split("::")[-1] if "::" in nodeid else nodeid for nodeid in failing_tests]
                
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
                fig = go.Figure(data=go.Heatmap(
                    z=heatmap_data,
                    x=test_names,
                    y=test_names,
                    colorscale='Viridis',
                    zmin=0,
                    zmax=1
                ))
                
                fig.update_layout(
                    title="Test Failure Correlation Matrix",
                    xaxis=dict(title="Test Name"),
                    yaxis=dict(title="Test Name"),
                    height=600,
                    margin=dict(t=50, b=0, l=0, r=0)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Explain correlation matrix
                with st.expander("How to interpret the Correlation Matrix"):
                    st.markdown("""
                    - **Darker colors** indicate stronger correlations (tests that fail together more often)
                    - **Diagonal** (top-left to bottom-right) always shows 1.0 (self-correlation)
                    - **High correlation** between tests suggests they might:
                      - Share dependencies
                      - Test related functionality
                      - Be affected by the same underlying issues
                    
                    This information can help identify clusters of related tests and potential common failure points.
                    """)
            else:
                st.info("Not enough failing tests for correlation analysis.")
        
        with tab3:
            st.subheader("Co-Failing Test Groups")
            st.markdown("""
            These are clusters of tests that frequently fail together, suggesting they might 
            be related or affected by the same underlying issues.
            """)
            
            # Identify co-failing test groups
            co_failing_groups = []
            
            # Track which tests have been assigned to groups
            assigned_tests = set()
            
            # For each session with failures, check if it forms a recurring pattern
            session_failure_patterns = {}
            for session_id, failed_tests in session_failures.items():
                if len(failed_tests) < 2:
                    continue  # Skip sessions with only one failure
                
                # Create a sorted tuple of failed tests as a pattern key
                pattern = tuple(sorted(failed_tests))
                
                if pattern not in session_failure_patterns:
                    session_failure_patterns[pattern] = 0
                
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
                        for test in pattern if test not in assigned_tests
                    ]
                }
                
                if group["tests"]:
                    co_failing_groups.append(group)
                    assigned_tests.update(group["tests"])
            
            # Display co-failing groups
            if co_failing_groups:
                for i, group in enumerate(co_failing_groups[:5]):  # Show top 5 groups
                    with st.expander(f"Group {i+1}: {len(group['tests'])} tests, failed together {group['count']} times"):
                        st.markdown(f"**Tests in this group:**")
                        for test_name in group["test_names"]:
                            st.markdown(f"- `{test_name}`")
                        
                        st.markdown("**Failure frequency:** {group['count']} sessions".format(group=group))
                        
                        # Calculate potential root causes based on test names
                        common_words = set()
                        for test_name in group["test_names"]:
                            words = set(re.findall(r'[a-zA-Z]+', test_name.lower()))
                            if not common_words:
                                common_words = words
                            else:
                                common_words &= words
                        
                        if common_words:
                            st.markdown("**Potential common elements:**")
                            st.markdown(", ".join(f"`{word}`" for word in common_words))
            else:
                st.info("No recurring co-failing test groups identified.")
            
    except Exception as e:
        st.error(f"Error displaying test impact analysis: {e}")
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
            if hasattr(session, "sut") and session.sut:
                suts.add(session.sut)
            # Also check for sut_name which is used in some models
            elif hasattr(session, "sut_name") and session.sut_name:
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
        sut = None if selected_sut == "All SUTs" else selected_sut
        
        # Time range selection
        days = st.sidebar.slider(
            "Time Range (days)",
            min_value=1,
            max_value=90,
            value=30,
            step=1,
            help="Number of days to include in the analysis",
        )
        
        # Display tabs for different dashboards
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Health Metrics", "Stability Trends", "Predictive Insights", "Test Execution Trends", "Test Impact Analysis"])
        
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
    except Exception as e:
        st.error(f"Unexpected error in dashboard: {e}")
        st.code(traceback.format_exc())
        # Also print to console for terminal visibility
        print(f"ERROR: {e}", file=sys.stderr)
        traceback.print_exc()


if __name__ == "__main__":
    main()
