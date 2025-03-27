"""Main entry point for pytest-insight API.

This module provides the top-level API for interacting with pytest-insight.
It follows a fluent interface design with three main operations:
1. Query - Find and filter test sessions
2. Compare - Compare between versions/times
3. Analyze - Extract insights and metrics
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from statistics import mean, stdev
from collections import defaultdict
import datetime as dt_module  # Import for datetime operations
import logging

from fastapi import FastAPI, HTTPException, Query as FastAPIQuery, Body, Path as FastAPIPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from pytest_insight.analysis import Analysis  # Import Analysis class
from pytest_insight.comparison import Comparison
from pytest_insight.models import TestOutcome, TestSession
from pytest_insight.query import Query
from pytest_insight.storage import BaseStorage, get_storage_instance


# Create FastAPI app for metrics visualization and REST API
app = FastAPI(
    title="pytest-insight API",
    description="API for interacting with pytest-insight and visualizing metrics",
    version="0.1.0",
    docs_url=None,  # Disable default docs to customize
    redoc_url=None,  # Disable default redoc to customize
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom Swagger UI endpoint
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Serve custom Swagger UI."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="pytest-insight API",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    """Serve OpenAPI schema."""
    return JSONResponse(
        get_openapi(
            title="pytest-insight API",
            version="0.1.0",
            description="API for interacting with pytest-insight and visualizing metrics",
            routes=app.routes,
        )
    )


# Models for API responses
class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class TimeSeriesPoint(BaseModel):
    target: str
    datapoints: List[List[float]]


class TestSessionResponse(BaseModel):
    """Model for test session response."""
    id: str
    sut_name: str
    session_start_time: datetime
    session_duration: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    xfailed_tests: int
    xpassed_tests: int
    error_tests: int
    test_results: List[Dict[str, Any]] = Field(..., description="List of test results")


class TestResultResponse(BaseModel):
    """Model for test result response."""
    id: str
    name: str
    outcome: str
    duration: float
    nodeid: str
    markers: List[str] = Field(default_factory=list)
    reruns: int = Field(default=0)
    error_message: Optional[str] = None


class HealthReportResponse(BaseModel):
    """Model for health report response."""
    health_score: Dict[str, Any]
    session_metrics: Dict[str, Any]
    trends: Dict[str, Any]
    timestamp: datetime


class StabilityReportResponse(BaseModel):
    """Model for stability report response."""
    flaky_tests: List[Dict[str, Any]]
    consistent_failures: List[Dict[str, Any]]
    outcome_patterns: Dict[str, Any]
    timestamp: datetime


class PerformanceReportResponse(BaseModel):
    """Model for performance report response."""
    slow_tests: List[Dict[str, Any]]
    duration_trends: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    timestamp: datetime


class ComparisonResponse(BaseModel):
    """Model for comparison response."""
    sut1: str
    sut2: str
    added_tests: List[Dict[str, Any]]
    removed_tests: List[Dict[str, Any]]
    changed_outcomes: List[Dict[str, Any]]
    performance_changes: List[Dict[str, Any]]
    metrics_comparison: Dict[str, Any]
    timestamp: datetime


class SUTsResponse(BaseModel):
    suts: List[str] = Field(..., description="List of available Systems Under Test")
    count: int = Field(..., description="Number of available SUTs")


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.now(),
    }


# Grafana Simple JSON datasource endpoint
@app.post("/search", tags=["Grafana"])
async def search():
    """Return available metrics for Grafana."""
    return [
        "health_score",
        "stability_score",
        "performance_score",
        "pass_rate",
        "failure_rate",
        "flaky_tests_count",
        "avg_test_duration",
        "test_count_by_outcome",
    ]


class GrafanaQuery(BaseModel):
    """Model for Grafana SimpleJSON/Infinity query request."""
    panelId: Optional[int] = None
    range: Optional[Dict[str, Any]] = None
    rangeRaw: Optional[Dict[str, Any]] = None
    interval: Optional[str] = None
    intervalMs: Optional[int] = None
    targets: List[Dict[str, Any]]
    maxDataPoints: Optional[int] = None
    scopedVars: Optional[Dict[str, Any]] = None
    adhocFilters: Optional[List[Dict[str, Any]]] = None


@app.post("/query", tags=["Grafana"])
async def query(query_request: GrafanaQuery):
    """Query metrics for Grafana.

    This endpoint handles Grafana SimpleJSON datasource queries.
    """
    # Default to 7 days if no range is provided
    days = 7
    if query_request.range and query_request.range.get("from"):
        try:
            from_str = query_request.range.get("from")
            from_dt = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
            days = (datetime.now() - from_dt).days + 1
        except (ValueError, TypeError):
            # If we can't parse the date, default to 7 days
            days = 7

    # Load sessions from storage
    storage = get_storage_instance()
    all_sessions = storage.load_sessions()

    # Apply time filter
    cutoff = datetime.now() - timedelta(days=days)
    sessions = [s for s in all_sessions if s.session_start_time >= cutoff]

    if not sessions:
        return []

    # Create analysis instance
    analysis = Analysis(sessions=sessions)

    # Group sessions by day for time series
    sessions_by_day = {}
    for session in sorted(sessions, key=lambda s: s.session_start_time):
        day = session.session_start_time.date()
        if day not in sessions_by_day:
            sessions_by_day[day] = []
        sessions_by_day[day].append(session)

    # Process each target in the request
    results = []
    for target_obj in query_request.targets:
        target = target_obj.get("target")
        # Extract SUT filter if provided in the target
        sut = None
        if isinstance(target, str) and ":" in target:
            target, sut = target.split(":", 1)

        # Apply SUT filter if specified
        filtered_sessions = sessions
        if sut:
            filtered_sessions = [s for s in filtered_sessions if s.sut_name == sut]

        if not filtered_sessions:
            continue

        # Generate metrics based on target
        if target == "health_score":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                day_analysis = Analysis(sessions=day_sessions)
                health_report = day_analysis.health_report()
                score = health_report["health_score"]["overall_score"]
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([score, timestamp])
            results.append({"target": "Health Score", "datapoints": datapoints})

        elif target == "stability_score":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                day_analysis = Analysis(sessions=day_sessions)
                health_report = day_analysis.health_report()
                score = health_report["health_score"].get("stability_score", 0)
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([score, timestamp])
            results.append({"target": "Stability Score", "datapoints": datapoints})

        elif target == "performance_score":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                day_analysis = Analysis(sessions=day_sessions)
                health_report = day_analysis.health_report()
                score = health_report["health_score"].get("performance_score", 0)
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([score, timestamp])
            results.append({"target": "Performance Score", "datapoints": datapoints})

        elif target == "pass_rate":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                passed = 0
                total = 0
                for session in day_sessions:
                    for test in session.test_results:
                        total += 1
                        if test.outcome == TestOutcome.PASSED:
                            passed += 1
                pass_rate = (passed / total * 100) if total > 0 else 0
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([pass_rate, timestamp])
            results.append({"target": "Pass Rate (%)", "datapoints": datapoints})

        elif target == "failure_rate":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                failed = 0
                total = 0
                for session in day_sessions:
                    for test in session.test_results:
                        total += 1
                        if test.outcome == TestOutcome.FAILED:
                            failed += 1
                failure_rate = (failed / total * 100) if total > 0 else 0
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([failure_rate, timestamp])
            results.append({"target": "Failure Rate (%)", "datapoints": datapoints})

        elif target == "flaky_tests_count":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                day_analysis = Analysis(sessions=day_sessions)
                flaky_tests = day_analysis.find_flaky_tests()
                count = len(flaky_tests)
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([count, timestamp])
            results.append({"target": "Flaky Tests Count", "datapoints": datapoints})

        elif target == "avg_test_duration":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                durations = []
                for session in day_sessions:
                    for test in session.test_results:
                        durations.append(test.duration)
                avg_duration = sum(durations) / len(durations) if durations else 0
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([avg_duration, timestamp])
            results.append({"target": "Average Test Duration (s)", "datapoints": datapoints})

        elif target == "test_count_by_outcome":
            # Create a series for each outcome
            outcome_series = {outcome.name: [] for outcome in TestOutcome}

            for day, day_sessions in sessions_by_day.items():
                outcome_counts = {outcome.name: 0 for outcome in TestOutcome}
                for session in day_sessions:
                    for test in session.test_results:
                        outcome_name = test.outcome.name if hasattr(test.outcome, 'name') else str(test.outcome)
                        outcome_counts[outcome_name] = outcome_counts.get(outcome_name, 0) + 1

                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                for outcome, count in outcome_counts.items():
                    if outcome not in outcome_series:
                        outcome_series[outcome] = []
                    outcome_series[outcome].append([count, timestamp])

            # Add a series for each outcome
            for outcome, datapoints in outcome_series.items():
                if datapoints:  # Only include non-empty series
                    results.append({"target": f"Tests {outcome}", "datapoints": datapoints})

    return results


@app.post("/annotations", tags=["Grafana"])
async def annotations():
    """Return annotations for Grafana."""
    # This would be used to mark important events on the timeline
    # For now, return an empty list
    return []


# Helper function to convert sessions to time series
def sessions_to_timeseries(sessions, metric_fn, metric_name):
    """Convert sessions to time series data for Grafana."""
    # Group sessions by day
    sessions_by_day = {}
    for session in sorted(sessions, key=lambda s: s.session_start_time):
        day = session.session_start_time.date()
        if day not in sessions_by_day:
            sessions_by_day[day] = []
        sessions_by_day[day].append(session)

    # Calculate metric for each day
    datapoints = []
    for day, day_sessions in sessions_by_day.items():
        value = metric_fn(day_sessions)
        timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
        datapoints.append([value, timestamp])

    return [{"target": metric_name, "datapoints": datapoints}]


# REST API Endpoints for pytest-insight core functionality

# Query Endpoints
@app.get("/api/sessions", response_model=List[TestSessionResponse], tags=["Query"])
async def get_sessions(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    limit: int = FastAPIQuery(100, description="Maximum number of sessions to return"),
):
    """Get test sessions filtered by SUT and time range."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    # Convert to response format
    results = []
    # QueryResult is not subscriptable, but it is iterable
    # Use list() to convert it to a list, then apply the limit
    session_list = list(sessions.sessions)[:limit]

    for session in session_list:
        results.append({
            "id": session.session_id,
            "sut_name": session.sut_name,
            "session_start_time": session.session_start_time,
            "session_duration": session.session_duration,
            "total_tests": len(session.test_results),
            "passed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.PASSED),
            "failed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.FAILED),
            "skipped_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.SKIPPED),
            "xfailed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.XFAILED),
            "xpassed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.XPASSED),
            "error_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.ERROR),
            "test_results": [
                {
                    "id": test.nodeid,  # Use nodeid as id
                    "name": test.nodeid.split("::")[-1] if "::" in test.nodeid else test.nodeid,  # Extract name from nodeid
                    "outcome": test.outcome.value if hasattr(test.outcome, 'value') else str(test.outcome),
                    "duration": test.duration,
                    "nodeid": test.nodeid,
                    "markers": [],  # TestResult doesn't have markers
                    "reruns": 0,    # TestResult doesn't have reruns
                    "error_message": test.longreprtext,  # Use longreprtext as error message
                }
                for test in session.test_results
            ],
        })

    return results


@app.get("/api/sessions/{session_id}", response_model=TestSessionResponse, tags=["Query"])
async def get_session(
    session_id: str = FastAPIPath(..., description="Session ID"),
):
    """Get a specific test session by ID."""
    api = InsightAPI()
    storage = api.storage
    sessions = storage.load_sessions()

    # Find the session with the matching ID
    session = next((s for s in sessions if s.id == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found")

    # Convert to response format
    return {
        "id": session.id,
        "sut_name": session.sut_name,
        "session_start_time": session.session_start_time,
        "session_duration": session.session_duration,
        "total_tests": len(session.test_results),
        "passed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.PASSED),
        "failed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.FAILED),
        "skipped_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.SKIPPED),
        "xfailed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.XFAILED),
        "xpassed_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.XPASSED),
        "error_tests": sum(1 for t in session.test_results if t.outcome == TestOutcome.ERROR),
        "test_results": [
            {
                "id": test.id,
                "name": test.name,
                "outcome": test.outcome.name if hasattr(test.outcome, 'name') else str(test.outcome),
                "duration": test.duration,
                "nodeid": test.nodeid,
                "markers": test.markers,
                "reruns": test.reruns,
                "error_message": test.error_message,
            }
            for test in session.test_results
        ],
    }


@app.get("/api/tests", response_model=List[TestResultResponse], tags=["Query"])
async def get_tests(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    pattern: Optional[str] = FastAPIQuery(None, description="Test name pattern to match"),
    outcome: Optional[str] = FastAPIQuery(None, description="Filter by test outcome"),
    min_duration: Optional[float] = FastAPIQuery(None, description="Minimum test duration"),
    max_duration: Optional[float] = FastAPIQuery(None, description="Maximum test duration"),
    limit: int = FastAPIQuery(100, description="Maximum number of tests to return"),
):
    """Get test results filtered by various criteria."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)

    # Apply test-level filters if specified
    if pattern or outcome or min_duration is not None or max_duration is not None:
        query = query.filter_by_test()

        if pattern:
            query = query.with_pattern(pattern)

        if outcome:
            try:
                outcome_enum = TestOutcome[outcome.upper()]
                query = query.with_outcome(outcome_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid outcome: {outcome}")

        if min_duration is not None or max_duration is not None:
            min_val = min_duration if min_duration is not None else 0
            max_val = max_duration if max_duration is not None else float("inf")
            query = query.with_duration(min_val, max_val)

        query = query.apply()

    sessions = query.execute()

    # Extract and flatten test results
    results = []
    for session in sessions:
        for test in session.test_results:
            # Skip tests that don't match the filters
            if pattern and pattern.lower() not in test.name.lower():
                continue

            if outcome and (not hasattr(test.outcome, 'name') or test.outcome.name != outcome.upper()):
                continue

            if min_duration is not None and test.duration < min_duration:
                continue

            if max_duration is not None and test.duration > max_duration:
                continue

            results.append({
                "id": test.id,
                "name": test.name,
                "outcome": test.outcome.name if hasattr(test.outcome, 'name') else str(test.outcome),
                "duration": test.duration,
                "nodeid": test.nodeid,
                "markers": test.markers,
                "reruns": test.reruns,
                "error_message": test.error_message,
            })

            if len(results) >= limit:
                break

        if len(results) >= limit:
            break

    return results


# Analysis Endpoints
@app.get("/api/analysis/health", response_model=HealthReportResponse, tags=["Analysis"])
async def get_health_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    include_trends: bool = FastAPIQuery(True, description="Include trend analysis in the report"),
    include_recommendations: bool = FastAPIQuery(True, description="Include improvement recommendations"),
    min_score_threshold: Optional[float] = FastAPIQuery(None, description="Only return results if health score is below this threshold"),
):
    """Get health report for test sessions with enhanced parametrization."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    analysis = api.analyze().sessions(sessions)
    health_report = analysis.health_report()

    # Filter based on parameters
    if not include_trends and "trends" in health_report:
        del health_report["trends"]

    if not include_recommendations and "health_score" in health_report and "recommendations" in health_report["health_score"]:
        del health_report["health_score"]["recommendations"]

    # Check threshold if specified
    if min_score_threshold is not None and health_report["health_score"]["overall_score"] > min_score_threshold:
        raise HTTPException(status_code=404, detail=f"Health score {health_report['health_score']['overall_score']} is above threshold {min_score_threshold}")

    return health_report


@app.get("/api/analysis/stability", response_model=StabilityReportResponse, tags=["Analysis"])
async def get_stability_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    min_flaky_rate: float = FastAPIQuery(0.0, description="Minimum flakiness rate to include a test (0.0-1.0)"),
    max_tests: int = FastAPIQuery(100, description="Maximum number of tests to include in each category"),
    include_patterns: bool = FastAPIQuery(True, description="Include outcome patterns in the report"),
):
    """Get stability report for test sessions with enhanced parametrization."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    # Initialize Analysis with the sessions
    analysis = api.analyze()
    analysis._sessions = sessions  # Set the sessions directly

    # Get stability report from the tests component
    stability = analysis.tests.stability()

    # Get flaky tests with filtering
    flaky_tests = [
        test for test in stability.get("flaky_tests", [])
        if test.get("flaky_rate", 0) >= min_flaky_rate
    ][:max_tests]

    # Get consistent failures with limit
    consistent_failures = stability.get("unstable_tests", [])[:max_tests]

    # Get outcome patterns conditionally
    outcome_patterns = stability.get("outcome_patterns", {}) if include_patterns else {}

    return {
        "flaky_tests": flaky_tests,
        "consistent_failures": consistent_failures,
        "outcome_patterns": outcome_patterns,
        "timestamp": datetime.now(),
    }


@app.get("/api/analysis/performance", response_model=PerformanceReportResponse, tags=["Analysis"])
async def get_performance_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    min_duration: float = FastAPIQuery(0.0, description="Minimum test duration to include (seconds)"),
    max_tests: int = FastAPIQuery(100, description="Maximum number of tests to include"),
    include_trends: bool = FastAPIQuery(True, description="Include duration trends in the report"),
):
    """Get performance report for test sessions with enhanced parametrization."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    analysis = api.analyze().sessions(sessions)

    # Get slow tests with filtering
    slow_tests = [
        test for test in analysis.find_slow_tests()
        if test.get("duration", 0) >= min_duration
    ][:max_tests]

    # Get duration trends conditionally
    duration_trends = analysis.duration_trends() if include_trends else {}

    # Get performance metrics
    performance_metrics = analysis.performance_metrics()

    return {
        "slow_tests": slow_tests,
        "duration_trends": duration_trends if include_trends else {},
        "performance_metrics": performance_metrics,
        "timestamp": datetime.now(),
    }


# New Canned Reports
class TrendReportResponse(BaseModel):
    """Model for trend report response."""
    duration_trends: Dict[str, Any]
    failure_trends: Dict[str, Any]
    pass_rate_trend: List[Dict[str, Any]]
    test_count_trend: List[Dict[str, Any]]
    timestamp: datetime


@app.get("/api/analysis/trends", response_model=TrendReportResponse, tags=["Analysis"])
async def get_trend_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(30, description="Number of days to include"),
    interval: str = FastAPIQuery("day", description="Trend interval (day, week, month)"),
):
    """Get comprehensive trend report showing how metrics change over time."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    analysis = api.analyze().sessions(sessions)

    # Get trends by time interval
    duration_trends = analysis.duration_trends(interval=interval)
    failure_trends = analysis.failure_trends(interval=interval)

    # Calculate pass rate trend
    pass_rate_trend = []
    test_count_trend = []

    # Group sessions by interval
    interval_sessions = defaultdict(list)
    for session in sessions:
        if interval == "day":
            key = session.session_start_time.strftime("%Y-%m-%d")
        elif interval == "week":
            key = f"{session.session_start_time.year}-W{session.session_start_time.isocalendar()[1]}"
        else:  # month
            key = session.session_start_time.strftime("%Y-%m")
        interval_sessions[key].append(session)

    # Calculate metrics for each interval
    for interval_key, interval_sessions_list in sorted(interval_sessions.items()):
        total_tests = sum(len(s.test_results) for s in interval_sessions_list)
        passed_tests = sum(
            sum(1 for t in s.test_results if t.outcome == TestOutcome.PASSED)
            for s in interval_sessions_list
        )
        pass_rate = passed_tests / total_tests if total_tests > 0 else 0

        pass_rate_trend.append({
            "interval": interval_key,
            "pass_rate": pass_rate,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
        })

        test_count_trend.append({
            "interval": interval_key,
            "total_tests": total_tests,
            "unique_tests": len(set(t.nodeid for s in interval_sessions_list for t in s.test_results)),
        })

    return {
        "duration_trends": duration_trends,
        "failure_trends": failure_trends,
        "pass_rate_trend": pass_rate_trend,
        "test_count_trend": test_count_trend,
        "timestamp": datetime.now(),
    }


class TestCoverageResponse(BaseModel):
    """Model for test coverage response."""
    total_tests: int
    coverage_by_module: Dict[str, Any]
    coverage_by_marker: Dict[str, Any]
    uncovered_areas: List[str]
    timestamp: datetime


@app.get("/api/analysis/coverage", response_model=TestCoverageResponse, tags=["Analysis"])
async def get_coverage_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    group_by: str = FastAPIQuery("module", description="How to group coverage (module, package, directory)"),
):
    """Get test coverage report showing distribution of tests across modules."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    # Extract all unique tests
    all_tests = {}
    for session in sessions:
        for test in session.test_results:
            all_tests[test.nodeid] = test

    # Group by module/package
    coverage_by_module = defaultdict(list)
    for test in all_tests.values():
        if group_by == "module":
            # Extract module from nodeid (e.g., "test_file.py::test_func" -> "test_file.py")
            module = test.nodeid.split("::")[0]
        elif group_by == "package":
            # Extract package from nodeid if available
            parts = test.nodeid.split("/")
            module = parts[0] if len(parts) > 1 else "root"
        else:  # directory
            # Extract directory from nodeid if available
            parts = test.nodeid.split("/")
            module = "/".join(parts[:-1]) if len(parts) > 1 else "root"

        coverage_by_module[module].append(test)

    # Convert to counts and percentages
    total_tests = len(all_tests)
    coverage_summary = {}
    for module, tests in coverage_by_module.items():
        coverage_summary[module] = {
            "test_count": len(tests),
            "percentage": len(tests) / total_tests if total_tests > 0 else 0,
        }

    # Group by marker
    coverage_by_marker = defaultdict(list)
    for test in all_tests.values():
        if not test.markers:
            coverage_by_marker["no_marker"].append(test)
        else:
            for marker in test.markers:
                coverage_by_marker[marker].append(test)

    # Convert marker coverage to summary
    marker_summary = {}
    for marker, tests in coverage_by_marker.items():
        marker_summary[marker] = {
            "test_count": len(tests),
            "percentage": len(tests) / total_tests if total_tests > 0 else 0,
        }

    # Identify potentially uncovered areas (modules with few tests)
    uncovered_areas = [
        module for module, data in coverage_summary.items()
        if data["percentage"] < 0.01  # Less than 1% of tests
    ]

    return {
        "total_tests": total_tests,
        "coverage_by_module": coverage_summary,
        "coverage_by_marker": marker_summary,
        "uncovered_areas": uncovered_areas,
        "timestamp": datetime.now(),
    }


class TestRegressionResponse(BaseModel):
    """Model for test regression response."""
    new_failures: List[Dict[str, Any]]
    fixed_tests: List[Dict[str, Any]]
    performance_regressions: List[Dict[str, Any]]
    performance_improvements: List[Dict[str, Any]]
    overall_assessment: str
    timestamp: datetime


@app.get("/api/analysis/regression", response_model=TestRegressionResponse, tags=["Analysis"])
async def get_regression_report(
    sut: str = FastAPIQuery(..., description="System Under Test name"),
    baseline_days: int = FastAPIQuery(14, description="Number of days to include for baseline"),
    recent_days: int = FastAPIQuery(7, description="Number of days to include for recent tests"),
    min_duration_change: float = FastAPIQuery(0.5, description="Minimum duration change to consider significant (seconds)"),
):
    """Get regression report comparing recent test runs to a baseline period."""
    api = InsightAPI()

    # Get baseline sessions (older period)
    now = dt_module.datetime.now(dt_module.timezone.utc)
    baseline_start = now - dt_module.timedelta(days=baseline_days + recent_days)
    baseline_end = now - dt_module.timedelta(days=recent_days)
    baseline_query = api.query().for_sut(sut).date_range(baseline_start, baseline_end)
    baseline_sessions = baseline_query.execute()

    # Get recent sessions
    recent_query = api.query().for_sut(sut).in_last_days(recent_days)
    recent_sessions = recent_query.execute()

    if not baseline_sessions or not recent_sessions:
        raise HTTPException(status_code=404, detail="Insufficient data for baseline or recent period")

    # Extract test results by nodeid
    baseline_tests = {}
    for session in baseline_sessions:
        for test in session.test_results:
            baseline_tests[test.nodeid] = test

    recent_tests = {}
    for session in recent_sessions:
        for test in session.test_results:
            recent_tests[test.nodeid] = test

    # Find new failures (passed in baseline, failed in recent)
    new_failures = []
    for nodeid, test in recent_tests.items():
        if (nodeid in baseline_tests and
            baseline_tests[nodeid].outcome == TestOutcome.PASSED and
            test.outcome == TestOutcome.FAILED):
            new_failures.append({
                "nodeid": nodeid,
                "name": test.name,
                "error_message": test.error_message,
            })

    # Find fixed tests (failed in baseline, passed in recent)
    fixed_tests = []
    for nodeid, test in recent_tests.items():
        if (nodeid in baseline_tests and
            baseline_tests[nodeid].outcome == TestOutcome.FAILED and
            test.outcome == TestOutcome.PASSED):
            fixed_tests.append({
                "nodeid": nodeid,
                "name": test.name,
            })

    # Find performance regressions (slower in recent)
    performance_regressions = []
    for nodeid, test in recent_tests.items():
        if nodeid in baseline_tests:
            duration_change = test.duration - baseline_tests[nodeid].duration
            if duration_change > min_duration_change:
                performance_regressions.append({
                    "nodeid": nodeid,
                    "name": test.name,
                    "baseline_duration": baseline_tests[nodeid].duration,
                    "recent_duration": test.duration,
                    "change": duration_change,
                    "percent_change": (duration_change / baseline_tests[nodeid].duration) * 100 if baseline_tests[nodeid].duration > 0 else 0,
                })

    # Find performance improvements (faster in recent)
    performance_improvements = []
    for nodeid, test in recent_tests.items():
        if nodeid in baseline_tests:
            duration_change = baseline_tests[nodeid].duration - test.duration
            if duration_change > min_duration_change:
                performance_improvements.append({
                    "nodeid": nodeid,
                    "name": test.name,
                    "baseline_duration": baseline_tests[nodeid].duration,
                    "recent_duration": test.duration,
                    "change": duration_change,
                    "percent_change": (duration_change / baseline_tests[nodeid].duration) * 100 if baseline_tests[nodeid].duration > 0 else 0,
                })

    # Overall assessment
    if len(new_failures) > len(fixed_tests):
        assessment = "Regression detected"
    elif len(fixed_tests) > len(new_failures):
        assessment = "Improvement detected"
    elif len(performance_regressions) > len(performance_improvements):
        assessment = "Performance regression detected"
    elif len(performance_improvements) > len(performance_regressions):
        assessment = "Performance improvement detected"
    else:
        assessment = "No significant change detected"

    return {
        "new_failures": new_failures,
        "fixed_tests": fixed_tests,
        "performance_regressions": performance_regressions,
        "performance_improvements": performance_improvements,
        "overall_assessment": assessment,
        "timestamp": datetime.now(),
    }


class TestSuiteQualityResponse(BaseModel):
    """Model for test suite quality response."""
    quality_score: float
    test_distribution: Dict[str, Any]
    test_complexity: Dict[str, Any]
    test_isolation: Dict[str, Any]
    recommendations: List[str]
    timestamp: datetime


@app.get("/api/analysis/quality", response_model=TestSuiteQualityResponse, tags=["Analysis"])
async def get_quality_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(30, description="Number of days to include"),
):
    """Get test suite quality report analyzing test design and organization."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    # Extract all unique tests
    all_tests = {}
    for session in sessions:
        for test in session.test_results:
            all_tests[test.nodeid] = test

    # Analyze test distribution (by module, outcome, duration)
    test_by_module = defaultdict(list)
    test_by_outcome = defaultdict(list)
    test_by_duration = {
        "fast": [],    # < 0.1s
        "medium": [],  # 0.1s - 1s
        "slow": [],    # 1s - 5s
        "very_slow": [] # > 5s
    }

    for test in all_tests.values():
        # Module
        module = test.nodeid.split("::")[0]
        test_by_module[module].append(test)

        # Outcome
        outcome = test.outcome.name if hasattr(test.outcome, 'name') else str(test.outcome)
        test_by_outcome[outcome].append(test)

        # Duration
        if test.duration < 0.1:
            test_by_duration["fast"].append(test)
        elif test.duration < 1.0:
            test_by_duration["medium"].append(test)
        elif test.duration < 5.0:
            test_by_duration["slow"].append(test)
        else:
            test_by_duration["very_slow"].append(test)

    # Calculate distribution percentages
    total_tests = len(all_tests)

    module_distribution = {
        module: len(tests) / total_tests
        for module, tests in test_by_module.items()
    }

    outcome_distribution = {
        outcome: len(tests) / total_tests
        for outcome, tests in test_by_outcome.items()
    }

    duration_distribution = {
        category: len(tests) / total_tests
        for category, tests in test_by_duration.items()
    }

    # Analyze test complexity (based on duration variance and failure patterns)
    duration_stats = {
        module: {
            "mean": mean([t.duration for t in tests]) if tests else 0,
            "variance": stdev([t.duration for t in tests]) if len(tests) > 1 else 0,
            "max": max([t.duration for t in tests]) if tests else 0,
        }
        for module, tests in test_by_module.items()
    }

    # Analyze test isolation (based on flaky tests and outcome consistency)
    # A proxy for isolation issues is flakiness
    flaky_tests = []
    for nodeid, test in all_tests.items():
        # Check if this test has different outcomes across sessions
        outcomes = set()
        for session in sessions:
            for session_test in session.test_results:
                if session_test.nodeid == nodeid:
                    outcomes.add(session_test.outcome.name if hasattr(session_test.outcome, 'name') else str(session_test.outcome))

        if len(outcomes) > 1:
            flaky_tests.append(test)

    isolation_score = 1.0 - (len(flaky_tests) / total_tests if total_tests > 0 else 0)

    # Generate quality score (weighted average of various factors)
    # - Distribution score: How well distributed tests are (higher is better)
    # - Complexity score: How complex tests are (lower variance is better)
    # - Isolation score: How isolated tests are (higher is better)

    # Distribution score: Penalize if tests are concentrated in few modules
    distribution_score = 1.0 - max(module_distribution.values()) if module_distribution else 0

    # Complexity score: Penalize high variance in test duration
    complexity_values = [stats["variance"] for stats in duration_stats.values() if stats["variance"] > 0]
    complexity_score = 1.0 - (mean(complexity_values) / 10 if complexity_values else 0)
    complexity_score = max(0, min(1, complexity_score))  # Clamp between 0 and 1

    # Calculate overall quality score
    quality_score = (0.4 * distribution_score + 0.3 * complexity_score + 0.3 * isolation_score) * 100

    # Generate recommendations
    recommendations = []

    if distribution_score < 0.5:
        recommendations.append("Tests are concentrated in too few modules. Consider more even test distribution.")

    if complexity_score < 0.5:
        recommendations.append("High variance in test duration suggests complex tests. Consider simplifying tests.")

    if isolation_score < 0.8:
        recommendations.append("Many flaky tests suggest isolation issues. Review test dependencies.")

    if duration_distribution.get("very_slow", 0) > 0.2:
        recommendations.append("Too many slow tests (>5s). Consider optimizing or parallelizing.")

    return {
        "quality_score": quality_score,
        "test_distribution": {
            "by_module": module_distribution,
            "by_outcome": outcome_distribution,
            "by_duration": duration_distribution,
        },
        "test_complexity": {
            "duration_stats": duration_stats,
            "complexity_score": complexity_score * 100,
        },
        "test_isolation": {
            "flaky_test_count": len(flaky_tests),
            "isolation_score": isolation_score * 100,
        },
        "recommendations": recommendations,
        "timestamp": datetime.now(),
    }


# Enhanced Comparison Endpoint
@app.get("/api/compare", response_model=ComparisonResponse, tags=["Comparison"])
async def compare_suts(
    sut1: str = FastAPIQuery(..., description="First SUT to compare"),
    sut2: str = FastAPIQuery(..., description="Second SUT to compare"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    include_tests: bool = FastAPIQuery(True, description="Include detailed test results"),
    min_duration_change: float = FastAPIQuery(0.1, description="Minimum duration change to consider significant (seconds)"),
    include_metrics: bool = FastAPIQuery(True, description="Include aggregated metrics comparison"),
):
    """Compare two SUTs and return the differences with enhanced parametrization."""
    api = InsightAPI()
    comparison = api.compare().between_suts(sut1, sut2).in_last_days(days)
    result = comparison.execute()

    if not result:
        raise HTTPException(status_code=404, detail="No comparison data available for the specified SUTs")

    # Extract comparison data
    added_tests = result.get("added_tests", [])
    removed_tests = result.get("removed_tests", [])

    # Filter performance changes based on threshold
    performance_changes = [
        change for change in result.get("performance_changes", [])
        if abs(change.get("duration_change", 0)) >= min_duration_change
    ]

    # Include or exclude detailed test results
    if not include_tests:
        added_tests = [{"name": test["name"], "nodeid": test["nodeid"]} for test in added_tests]
        removed_tests = [{"name": test["name"], "nodeid": test["nodeid"]} for test in removed_tests]

    # Include aggregated metrics if requested
    metrics_comparison = {}
    if include_metrics:
        # Get sessions for each SUT
        sut1_sessions = api.query().for_sut(sut1).in_last_days(days).execute()
        sut2_sessions = api.query().for_sut(sut2).in_last_days(days).execute()

        # Calculate metrics for each SUT
        if sut1_sessions and sut2_sessions:
            sut1_analysis = api.analyze().sessions(sut1_sessions)
            sut2_analysis = api.analyze().sessions(sut2_sessions)

            sut1_health = sut1_analysis.health_report()
            sut2_health = sut2_analysis.health_report()

            metrics_comparison = {
                "pass_rate": {
                    "sut1": sut1_health["session_metrics"]["pass_rate"] if "session_metrics" in sut1_health else 0,
                    "sut2": sut2_health["session_metrics"]["pass_rate"] if "session_metrics" in sut2_health else 0,
                    "difference": (sut2_health["session_metrics"]["pass_rate"] - sut1_health["session_metrics"]["pass_rate"])
                              if ("session_metrics" in sut1_health and "session_metrics" in sut2_health) else 0
                },
                "avg_duration": {
                    "sut1": sut1_health["session_metrics"]["avg_duration"] if "session_metrics" in sut1_health else 0,
                    "sut2": sut2_health["session_metrics"]["avg_duration"] if "session_metrics" in sut2_health else 0,
                    "difference": (sut2_health["session_metrics"]["avg_duration"] - sut1_health["session_metrics"]["avg_duration"])
                                if ("session_metrics" in sut1_health and "session_metrics" in sut2_health) else 0
                },
                "health_score": {
                    "sut1": sut1_health["health_score"]["overall_score"] if "health_score" in sut1_health else 0,
                    "sut2": sut2_health["health_score"]["overall_score"] if "health_score" in sut2_health else 0,
                    "difference": (sut2_health["health_score"]["overall_score"] - sut1_health["health_score"]["overall_score"])
                               if ("health_score" in sut1_health and "health_score" in sut2_health) else 0
                }
            }

    response = {
        "sut1": sut1,
        "sut2": sut2,
        "added_tests": added_tests,
        "removed_tests": removed_tests,
        "changed_outcomes": result.get("changed_outcomes", []),
        "performance_changes": performance_changes,
        "metrics_comparison": metrics_comparison if include_metrics else {},
        "timestamp": datetime.now(),
    }

    return response


@app.get("/api/suts", response_model=SUTsResponse, tags=["Discovery"])
async def get_available_suts():
    """Get a list of all available Systems Under Test (SUTs).

    This endpoint helps users discover what SUTs are available in the system
    without needing to know them in advance.

    Returns:
        A list of all unique SUT names found in the test sessions.
    """
    api = InsightAPI()

    try:
        # Get all sessions using the query system
        all_sessions = api.query().execute()

        # Extract unique SUTs
        suts = sorted(list({session.sut_name for session in all_sessions.sessions if session.sut_name}))

        return {
            "suts": suts,
            "count": len(suts)
        }
    except Exception as e:
        # Log the error but return an empty list rather than failing
        logging.warning(f"Error retrieving SUTs: {str(e)}")
        return {
            "suts": [],
            "count": 0
        }


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

    def analyze(self) -> Analysis:
        """Build and execute analysis of test patterns and health.

        Returns:
            Analysis instance for extracting insights.

        Example:
            api.analyze()
               .tests()
               .stability()
        """
        return Analysis(storage=self.storage)
