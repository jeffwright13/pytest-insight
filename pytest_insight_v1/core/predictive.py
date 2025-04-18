"""Predictive analytics module for pytest-insight.

This module provides classes and functions for predictive analytics on test data,
including time-series analysis, anomaly detection, and trend prediction.
"""

from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
from pytest_insight.core.analysis import Analysis
from pytest_insight.core.models import TestOutcome
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression


class PredictiveAnalytics:
    """Predictive analytics for test data.

    This class provides methods for predicting future test behavior based on
    historical data, detecting anomalies, and identifying trends.
    """

    def __init__(self, analysis: Analysis):
        """Initialize with an Analysis instance.

        Args:
            analysis: Analysis instance to use for predictions
        """
        self.analysis = analysis
        self._sessions = analysis._sessions

    def failure_prediction(self, days_ahead: int = 7) -> Dict[str, Any]:
        """Predict test failures for the coming days.

        Uses time-series analysis to predict which tests are likely to fail
        in the near future based on historical patterns.

        Args:
            days_ahead: Number of days to predict ahead

        Returns:
            Dict containing:
            - predictions: Dict mapping test nodeids to failure probabilities
            - confidence: Overall confidence in the predictions (0-1)
            - high_risk_tests: List of tests with high failure probability
        """
        # Sort sessions by date
        sorted_sessions = sorted(
            self._sessions,
            key=lambda s: getattr(s, "session_start_time", datetime.now()),
        )

        if len(sorted_sessions) < 5:
            return {
                "predictions": {},
                "confidence": 0,
                "high_risk_tests": [],
                "error": "Insufficient data for prediction (need at least 5 sessions)",
            }

        # Build time series data for each test
        test_time_series = {}
        for session in sorted_sessions:
            session_date = getattr(session, "session_start_time", datetime.now())
            for test in session.test_results:
                if test.nodeid not in test_time_series:
                    test_time_series[test.nodeid] = []

                # 1 for failure, 0 for pass
                outcome_value = 1 if test.outcome == TestOutcome.FAILED else 0
                test_time_series[test.nodeid].append((session_date, outcome_value))

        # Only analyze tests with sufficient history
        predictions = {}
        high_risk_tests = []

        for nodeid, time_series in test_time_series.items():
            if len(time_series) < 5:
                continue

            # Extract dates and outcomes
            dates = [ts[0] for ts in time_series]
            outcomes = [ts[1] for ts in time_series]

            # Simple linear trend for demonstration
            # In a real implementation, use more sophisticated time series models
            x = np.array([(d - dates[0]).total_seconds() / 86400 for d in dates]).reshape(-1, 1)
            y = np.array(outcomes)

            model = LinearRegression()
            model.fit(x, y)

            # Predict for future days
            future_days = np.array([len(dates) + i for i in range(1, days_ahead + 1)]).reshape(-1, 1)
            predicted_values = model.predict(future_days)

            # Calculate average failure probability over the prediction period
            avg_probability = float(np.mean(predicted_values))

            # Clip to valid probability range
            avg_probability = max(0, min(1, avg_probability))

            predictions[nodeid] = avg_probability

            # High risk if probability > 0.7
            if avg_probability > 0.7:
                high_risk_tests.append(
                    {
                        "nodeid": nodeid,
                        "probability": avg_probability,
                        "recent_failures": sum(outcomes[-3:]),  # Count of failures in last 3 runs
                    }
                )

        # Sort high risk tests by probability
        high_risk_tests = sorted(high_risk_tests, key=lambda x: x["probability"], reverse=True)

        # Calculate overall confidence based on data quantity and quality
        confidence = min(1.0, len(sorted_sessions) / 20)  # More sessions = higher confidence

        return {
            "predictions": predictions,
            "confidence": confidence,
            "high_risk_tests": high_risk_tests,
        }

    def anomaly_detection(self) -> Dict[str, Any]:
        """Detect anomalous test behavior.

        Uses machine learning to identify tests that are behaving unusually
        compared to their historical patterns or other tests.

        Returns:
            Dict containing:
            - anomalies: List of tests with anomalous behavior
            - anomaly_scores: Dict mapping test nodeids to anomaly scores
            - detection_confidence: Overall confidence in the anomaly detection
        """
        if len(self._sessions) < 10:
            return {
                "anomalies": [],
                "anomaly_scores": {},
                "detection_confidence": 0,
                "error": "Insufficient data for anomaly detection (need at least 10 sessions)",
            }

        # Extract features for each test
        test_features = {}
        for session in self._sessions:
            for test in session.test_results:
                if test.nodeid not in test_features:
                    test_features[test.nodeid] = {
                        "durations": [],
                        "outcomes": [],
                        "reruns": [],
                    }

                # Add test features
                test_features[test.nodeid]["durations"].append(test.duration)
                test_features[test.nodeid]["outcomes"].append(1 if test.outcome == TestOutcome.FAILED else 0)

                # Count reruns if available
                rerun_count = 0
                if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                    for rerun_group in session.rerun_test_groups:
                        if rerun_group.nodeid == test.nodeid:
                            rerun_count = len(rerun_group.tests) - 1
                            break

                test_features[test.nodeid]["reruns"].append(rerun_count)

        # Prepare feature matrix for anomaly detection
        feature_matrix = []
        test_nodeids = []

        for nodeid, features in test_features.items():
            if len(features["durations"]) < 5:
                continue

            # Calculate statistical features
            feature_vector = [
                np.mean(features["durations"]),
                np.std(features["durations"]),
                np.mean(features["outcomes"]),
                np.mean(features["reruns"]),
                np.max(features["durations"]) / (np.mean(features["durations"]) or 1),
            ]

            feature_matrix.append(feature_vector)
            test_nodeids.append(nodeid)

        if not feature_matrix:
            return {
                "anomalies": [],
                "anomaly_scores": {},
                "detection_confidence": 0,
                "error": "No tests with sufficient data for anomaly detection",
            }

        # Use Isolation Forest for anomaly detection
        model = IsolationForest(contamination=0.1, random_state=42)
        model.fit(feature_matrix)

        # Get anomaly scores (-1 for anomalies, 1 for normal)
        scores = model.decision_function(feature_matrix)

        # Convert to anomaly score (0-1, higher = more anomalous)
        anomaly_scores = {nodeid: 1 - (score + 1) / 2 for nodeid, score in zip(test_nodeids, scores)}

        # Identify anomalies (tests with negative scores in isolation forest)
        anomalies = [
            {
                "nodeid": nodeid,
                "score": anomaly_scores[nodeid],
                "features": {
                    "mean_duration": np.mean(test_features[nodeid]["durations"]),
                    "failure_rate": np.mean(test_features[nodeid]["outcomes"]),
                    "rerun_rate": np.mean(test_features[nodeid]["reruns"]),
                },
            }
            for nodeid, score in anomaly_scores.items()
            if score > 0.7  # High anomaly score threshold
        ]

        # Sort anomalies by score
        anomalies = sorted(anomalies, key=lambda x: x["score"], reverse=True)

        # Calculate detection confidence based on data quantity
        detection_confidence = min(1.0, len(self._sessions) / 30)

        return {
            "anomalies": anomalies,
            "anomaly_scores": anomaly_scores,
            "detection_confidence": detection_confidence,
        }

    def stability_forecast(self) -> Dict[str, Any]:
        """Forecast test stability trends.

        Analyzes historical stability patterns to forecast how test stability
        will evolve in the near future.

        Returns:
            Dict containing:
            - current_stability: Current overall test stability score (0-100)
            - forecasted_stability: Forecasted stability score
            - trend_direction: Whether stability is improving, declining, or stable
            - contributing_factors: Factors contributing to the forecast
        """
        if len(self._sessions) < 7:
            return {
                "current_stability": None,
                "forecasted_stability": None,
                "trend_direction": "unknown",
                "contributing_factors": [],
                "error": "Insufficient data for stability forecast (need at least 7 sessions)",
            }

        # Calculate stability scores for each day
        daily_stability = {}

        for session in self._sessions:
            session_date = getattr(session, "session_start_time", datetime.now())
            date_key = session_date.date().isoformat()

            if date_key not in daily_stability:
                daily_stability[date_key] = {
                    "total_tests": 0,
                    "passed_tests": 0,
                    "unreliable_tests": 0,
                }

            # Count tests
            daily_stability[date_key]["total_tests"] += len(session.test_results)
            daily_stability[date_key]["passed_tests"] += sum(
                1 for t in session.test_results if t.outcome == TestOutcome.PASSED
            )

            # Count unreliable tests
            if hasattr(session, "rerun_test_groups") and session.rerun_test_groups:
                daily_stability[date_key]["unreliable_tests"] += sum(
                    1 for g in session.rerun_test_groups if g.final_outcome == TestOutcome.PASSED and len(g.tests) > 1
                )

        # Calculate daily stability scores
        dates = []
        stability_scores = []

        for date_key, metrics in sorted(daily_stability.items()):
            if metrics["total_tests"] == 0:
                continue

            # Calculate stability score (0-100)
            pass_rate = metrics["passed_tests"] / metrics["total_tests"]
            nonreliability_rate = (
                metrics["unreliable_tests"] / metrics["total_tests"] if metrics["total_tests"] > 0 else 0
            )

            # Weighted score: 70% pass rate, 30% non-repeatability
            stability_score = (pass_rate * 70) + ((1 - nonreliability_rate) * 30)

            dates.append(datetime.fromisoformat(date_key))
            stability_scores.append(stability_score)

        if len(stability_scores) < 5:
            return {
                "current_stability": (np.mean(stability_scores) if stability_scores else None),
                "forecasted_stability": None,
                "trend_direction": "unknown",
                "contributing_factors": [],
                "error": "Insufficient daily data for stability forecast",
            }

        # Current stability is the average of the last 3 days
        current_stability = np.mean(stability_scores[-3:])

        # Fit linear regression to predict trend
        x = np.array([(d - dates[0]).total_seconds() / 86400 for d in dates]).reshape(-1, 1)
        y = np.array(stability_scores)

        model = LinearRegression()
        model.fit(x, y)

        # Predict stability for next 7 days
        future_days = np.array([len(dates) + i for i in range(1, 8)]).reshape(-1, 1)
        predicted_values = model.predict(future_days)

        # Forecasted stability is the average of the predicted values
        forecasted_stability = float(np.mean(predicted_values))

        # Determine trend direction
        if forecasted_stability > current_stability + 5:
            trend_direction = "improving"
        elif forecasted_stability < current_stability - 5:
            trend_direction = "declining"
        else:
            trend_direction = "stable"

        # Identify contributing factors
        contributing_factors = []

        # Check pass rate trend
        pass_rates = [
            metrics["passed_tests"] / metrics["total_tests"]
            for _, metrics in sorted(daily_stability.items())
            if metrics["total_tests"] > 0
        ]

        if len(pass_rates) >= 5:
            pass_rate_slope, _, _, _, _ = stats.linregress(range(len(pass_rates)), pass_rates)
            if abs(pass_rate_slope) > 0.01:
                direction = "increasing" if pass_rate_slope > 0 else "decreasing"
                contributing_factors.append(f"Pass rate is {direction}")

        # Check reliability/repeatability trend
        nonreliability_rates = [
            metrics["unreliable_tests"] / metrics["total_tests"]
            for _, metrics in sorted(daily_stability.items())
            if metrics["total_tests"] > 0
        ]

        if len(nonreliability_rates) >= 5:
            nonreliability_rate_slope, _, _, _, _ = stats.linregress(
                range(len(nonreliability_rates)), nonreliability_rates
            )
            if abs(nonreliability_rate_slope) > 0.01:
                direction = "increasing" if nonreliability_rate_slope > 0 else "decreasing"
                contributing_factors.append(f"Test reliability/repeatability is {direction}")

        return {
            "current_stability": current_stability,
            "forecasted_stability": forecasted_stability,
            "trend_direction": trend_direction,
            "contributing_factors": contributing_factors,
        }


# Helper function to create a PredictiveAnalytics instance
def predictive_analytics(analysis: Optional[Analysis] = None) -> PredictiveAnalytics:
    """Create a new PredictiveAnalytics instance.

    Args:
        analysis: Optional Analysis instance to use

    Returns:
        PredictiveAnalytics instance
    """
    if analysis is None:
        from pytest_insight.core.analysis import analysis as create_analysis

        analysis = create_analysis()

    return PredictiveAnalytics(analysis)
