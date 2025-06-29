"""Main entry point for pytest-insight API.

This module provides the top-level API for interacting with pytest-insight.
It follows a fluent interface design with three main operations:
1. Query - Find and filter test sessions
2. Compare - Compare between versions/times
3. Analyze - Extract insights and metrics
"""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi import Path as FastAPIPath
from fastapi import Query as FastAPIQuery
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from pytest_insight.core.analysis import Analysis
from pytest_insight.core.comparison import ComparisonError
from pytest_insight.core.core_api import InsightAPI
from pytest_insight.core.models import (
    TestOutcome,
)
from pytest_insight.core.storage import (
    create_profile,
    get_profile_manager,
    get_storage_instance,
)

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
    openapi_schema = get_openapi(
        title="pytest-insight API",
        version="0.2.0",
        description="""API for interacting with pytest-insight and visualizing metrics.

        ## Core Components

        pytest-insight is built around four primary operations:

        1. **Query** - Finding and filtering test sessions
        2. **Compare** - Comparing between versions/times
        3. **Analyze** - Extracting insights and metrics
        4. **Insights** - Consolidated views with health scores and recommendations

        Each component follows a fluent interface design pattern for intuitive and chainable operations.

        ## Storage Profiles

        The API now supports storage profiles, allowing you to:

        - Create and manage multiple storage configurations
        - Switch between profiles for different environments
        - Compare data across profiles

        Use the /api/insights/profiles endpoint to see available profiles.
        """,
        routes=app.routes,
    )

    openapi_schema["tags"] = [
        {
            "name": "health",
            "description": "Health check and system status",
        },
        {
            "name": "insights",
            "description": "Operations related to the Insights module: consolidated analytics and health scores",
        },
        {
            "name": "profiles",
            "description": "Operations for managing storage profiles",
        },
        {
            "name": "analysis",
            "description": "Operations for analyzing test patterns and health",
        },
        {
            "name": "comparison",
            "description": "Operations for comparing test sessions across versions or time periods",
        },
        {
            "name": "query",
            "description": "Operations for finding and filtering test sessions",
        },
        {
            "name": "grafana",
            "description": "Grafana SimpleJSON datasource endpoints for metrics visualization",
        },
        {
            "name": "settings",
            "description": "Operations for managing global settings",
        },
        {
            "name": "debug",
            "description": "Debug endpoints for troubleshooting and testing",
        },
    ]

    return JSONResponse(openapi_schema)


# Custom docs page with selector link
@app.get("/api-docs", include_in_schema=False)
async def api_docs_with_selector():
    """Serve a custom docs page with a link to the selector."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>pytest-insight API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
            }
            .header {
                background-color: #f8f9fa;
                padding: 10px 20px;
                border-bottom: 1px solid #dee2e6;
            }
            .header a {
                display: inline-block;
                margin-right: 15px;
                color: #0d6efd;
                text-decoration: none;
            }
            .header a:hover {
                text-decoration: underline;
            }
            iframe {
                width: 100%;
                height: calc(100vh - 50px);
                border: none;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <strong>pytest-insight:</strong>
            <a href="/">Home</a>
            <a href="/selector">Configure Profile & SUT</a>
            <a href="/docs" target="api-frame">API Documentation</a>
        </div>
        <iframe name="api-frame" src="/docs"></iframe>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


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

    reliability_tests: List[Dict[str, Any]]
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
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "0.2.0",
        "timestamp": datetime.now(),
    }


# Grafana Simple JSON datasource endpoint
@app.post("/search", tags=["grafana"])
async def search():
    """Return available metrics for Grafana."""
    return [
        "health_score",
        "stability_score",
        "performance_score",
        "pass_rate",
        "failure_rate",
        "unreliable_tests_count",
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


@app.post("/query", tags=["grafana"])
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
    Analysis(sessions=sessions)

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

        elif target == "unreliable_tests_count":
            datapoints = []
            for day, day_sessions in sessions_by_day.items():
                day_analysis = Analysis(sessions=day_sessions)
                unreliable_tests = day_analysis.find_unreliable_tests()
                count = len(unreliable_tests)
                timestamp = int(datetime.combine(day, datetime.min.time()).timestamp() * 1000)
                datapoints.append([count, timestamp])
            results.append({"target": "Unreliable Tests Count", "datapoints": datapoints})

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
                        outcome_name = test.outcome.name if hasattr(test.outcome, "name") else str(test.outcome)
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


@app.post("/annotations", tags=["grafana"])
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
@app.get("/api/sessions", response_model=List[TestSessionResponse], tags=["query"])
async def get_sessions(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    limit: int = FastAPIQuery(100, description="Maximum number of sessions to return"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get test sessions filtered by SUT and time range."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)
    sessions = query.get_sessions()

    # Convert to response format
    results = []
    for session in sessions[:limit]:
        results.append(
            {
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
                        "name": test.name,
                        "outcome": (test.outcome.name if hasattr(test.outcome, "name") else str(test.outcome)),
                        "duration": test.duration,
                        "nodeid": test.nodeid,
                        "markers": test.markers,
                        "reruns": test.reruns,
                        "error_message": test.error_message,
                    }
                    for test in session.test_results
                ],
            }
        )

    return results


@app.get("/api/sessions/{session_id}", response_model=TestSessionResponse, tags=["query"])
async def get_session(
    session_id: str = FastAPIPath(..., description="Session ID"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get a specific test session by ID."""
    api = InsightAPI(profile_name=profile)
    storage = api.storage
    sessions = storage.load_sessions()

    # Find the session with the matching ID
    session = next((s for s in sessions if s.id == session_id), None)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

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
                "name": test.name,
                "outcome": (test.outcome.name if hasattr(test.outcome, "name") else str(test.outcome)),
                "duration": test.duration,
                "nodeid": test.nodeid,
                "markers": test.markers,
                "reruns": test.reruns,
                "error_message": test.error_message,
            }
            for test in session.test_results
        ],
    }


@app.get("/api/tests", response_model=List[TestResultResponse], tags=["query"])
async def get_tests(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    pattern: Optional[str] = FastAPIQuery(None, description="Test name pattern to match"),
    outcome: Optional[str] = FastAPIQuery(None, description="Filter by test outcome"),
    min_duration: Optional[float] = FastAPIQuery(None, description="Minimum test duration"),
    max_duration: Optional[float] = FastAPIQuery(None, description="Maximum test duration"),
    limit: int = FastAPIQuery(100, description="Maximum number of tests to return"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get test results filtered by various criteria."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)

    # Apply test-level filters if specified
    if pattern or outcome or min_duration is not None or max_duration is not None:
        query = query.filter_by_test()

        if pattern:
            query = query.with_nodeid_containing(pattern)

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

    sessions = query.get_sessions()

    # Extract and flatten test results
    results = []
    for session in sessions:
        for test in session.test_results:
            # Skip tests that don't match the filters
            if pattern and pattern.lower() not in test.nodeid.lower():
                continue

            if outcome and (not hasattr(test.outcome, "name") or test.outcome.name != outcome.upper()):
                continue

            if min_duration is not None and test.duration < min_duration:
                continue

            if max_duration is not None and test.duration > max_duration:
                continue

            results.append(
                {
                    "name": test.name,
                    "outcome": (test.outcome.name if hasattr(test.outcome, "name") else str(test.outcome)),
                    "duration": test.duration,
                    "nodeid": test.nodeid,
                    "markers": test.markers,
                    "reruns": test.reruns,
                    "error_message": test.error_message,
                }
            )

            if len(results) >= limit:
                break

        if len(results) >= limit:
            break

    return results


# Analysis Endpoints
@app.get("/api/analysis/health", response_model=HealthReportResponse, tags=["analysis"])
async def get_health_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    include_trends: bool = FastAPIQuery(True, description="Include trend analysis in the report"),
    include_recommendations: bool = FastAPIQuery(True, description="Include improvement recommendations"),
    min_score_threshold: Optional[float] = FastAPIQuery(
        None, description="Only return results if health score is below this threshold"
    ),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get health report for test sessions with enhanced parametrization."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)
    analysis = query.analyze()
    health_report = analysis.get_health_report(include_trends=include_trends)

    # Filter based on parameters
    if not include_trends and "trends" in health_report:
        del health_report["trends"]

    if (
        not include_recommendations
        and "health_score" in health_report
        and "recommendations" in health_report["health_score"]
    ):
        del health_report["health_score"]["recommendations"]

    # Check threshold if specified
    if min_score_threshold is not None and health_report["health_score"]["overall_score"] > min_score_threshold:
        raise HTTPException(
            status_code=404,
            detail=f"Health score {health_report['health_score']['overall_score']} is above threshold {min_score_threshold}",
        )

    return health_report


@app.get("/api/analysis/stability", response_model=StabilityReportResponse, tags=["analysis"])
async def get_stability_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    min_reliability_rate: float = FastAPIQuery(
        0.0,
        description="Minimum reliability/repeatability rate to include a test (0.0-1.0)",
    ),
    max_tests: int = FastAPIQuery(100, description="Maximum number of tests to include in each category"),
    include_patterns: bool = FastAPIQuery(True, description="Include outcome patterns in the report"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get stability report for test sessions with enhanced parametrization."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)
    analysis = query.analyze()
    stability = analysis.get_stability_report()

    # Get reliability tests with filtering
    reliability_tests = [
        test
        for test in stability.get("reliability_tests", [])
        if test.get("reliability_rate", 1) <= min_reliability_rate
    ][:max_tests]

    # Get consistent failures with limit
    consistent_failures = stability.get("unstable_tests", [])[:max_tests]

    # Get outcome patterns conditionally
    outcome_patterns = stability.get("outcome_patterns", {}) if include_patterns else {}

    return {
        "reliability_tests": reliability_tests,
        "consistent_failures": consistent_failures,
        "outcome_patterns": outcome_patterns,
        "timestamp": datetime.now(),
    }


@app.get(
    "/api/analysis/performance",
    response_model=PerformanceReportResponse,
    tags=["analysis"],
)
async def get_performance_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    min_duration: float = FastAPIQuery(0.0, description="Minimum test duration to include (seconds)"),
    max_tests: int = FastAPIQuery(100, description="Maximum number of tests to include"),
    include_trends: bool = FastAPIQuery(True, description="Include duration trends in the report"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get performance report for test sessions with enhanced parametrization."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)
    analysis = query.analyze()
    performance_report = analysis.get_performance_report(include_trends=include_trends)

    # Extract and filter the data from the report
    slow_tests = [
        test
        for test in performance_report.get("performance", {}).get("slow_tests", [])
        if test.get("duration", 0) >= min_duration
    ][:max_tests]

    # Get performance metrics from the report
    performance_metrics = performance_report.get("session_metrics", {})

    # Duration trends will be empty if not requested
    duration_trends = {} if not include_trends else performance_report.get("performance", {}).get("duration_trends", {})

    return {
        "slow_tests": slow_tests,
        "duration_trends": duration_trends,
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


@app.get("/api/analysis/trends", response_model=TrendReportResponse, tags=["analysis"])
async def get_trend_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(30, description="Number of days to include"),
    interval: str = FastAPIQuery("day", description="Trend interval (day, week, month)"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get comprehensive trend report showing how metrics change over time."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)
    sessions = query.get_sessions()

    # Group sessions by interval
    sessions_by_interval = defaultdict(list)
    for session in sessions:
        if interval == "day":
            interval_key = session.start_time.date().isoformat()
        elif interval == "week":
            # Get the start of the week (Monday)
            start_of_week = session.start_time.date() - timedelta(days=session.start_time.weekday())
            interval_key = start_of_week.isoformat()
        elif interval == "month":
            interval_key = f"{session.start_time.year}-{session.start_time.month:02d}"
        else:
            interval_key = session.start_time.date().isoformat()

        sessions_by_interval[interval_key].append(session)

    # Calculate metrics for each interval
    duration_trends = []
    failure_trends = []
    pass_rate_trend = []
    test_count_trend = []

    for interval_key, interval_sessions_list in sorted(sessions_by_interval.items()):
        # Duration trend
        durations = [s.duration for s in interval_sessions_list if s.duration]
        avg_duration = mean(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        std_dev = stdev(durations) if len(durations) > 1 else 0

        duration_trends.append(
            {
                "interval": interval_key,
                "avg_duration": avg_duration,
                "max_duration": max_duration,
                "min_duration": min_duration,
                "std_dev": std_dev,
            }
        )

        # Failure trend
        total_failures = sum(
            1 for s in interval_sessions_list for t in s.test_results if t.outcome == TestOutcome.FAILED
        )
        total_tests = sum(len(s.test_results) for s in interval_sessions_list)

        failure_trends.append(
            {
                "interval": interval_key,
                "failure_count": total_failures,
                "total_tests": total_tests,
                "failure_rate": ((total_failures / total_tests * 100) if total_tests > 0 else 0),
            }
        )

        # Pass rate trend
        passed_tests = sum(1 for s in interval_sessions_list for t in s.test_results if t.outcome == TestOutcome.PASSED)

        pass_rate_trend.append(
            {
                "interval": interval_key,
                "pass_rate": ((passed_tests / total_tests * 100) if total_tests > 0 else 0),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
            }
        )

        test_count_trend.append(
            {
                "interval": interval_key,
                "total_tests": total_tests,
                "unique_tests": len(set(t.nodeid for s in interval_sessions_list for t in s.test_results)),
            }
        )

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


@app.get("/api/coverage", response_model=TestCoverageResponse, tags=["analysis"])
async def get_coverage_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get a report on test coverage across modules and markers."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)
    sessions = query.get_sessions()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    # Extract all unique tests
    all_tests = {}
    for session in sessions:
        for test in session.test_results:
            if test.nodeid not in all_tests:
                all_tests[test.nodeid] = test

    # Count tests by module
    coverage_by_module = defaultdict(int)
    for test in all_tests.values():
        # Extract module from nodeid (format: path/to/module.py::TestClass::test_name)
        parts = test.nodeid.split("::")
        if len(parts) > 0:
            module = parts[0]
            coverage_by_module[module] += 1

    # Count tests by marker
    coverage_by_marker = defaultdict(int)
    for test in all_tests.values():
        for marker in test.markers:
            coverage_by_marker[marker] += 1

    # Find potential uncovered areas (this is a placeholder - in a real implementation,
    # you would compare against a known list of modules or functions)
    uncovered_areas = []

    # Create coverage summary
    test_coverage = {
        "total_tests": len(all_tests),
        "coverage_by_module": dict(coverage_by_module),
        "coverage_by_marker": dict(coverage_by_marker),
        "uncovered_areas": uncovered_areas,
        "timestamp": datetime.now(),
    }

    return test_coverage


class TestRegressionResponse(BaseModel):
    """Model for test regression response."""

    new_failures: List[Dict[str, Any]]
    fixed_tests: List[Dict[str, Any]]
    performance_regressions: List[Dict[str, Any]]
    performance_improvements: List[Dict[str, Any]]
    overall_assessment: str
    timestamp: datetime


@app.get("/api/analysis/regression", response_model=TestRegressionResponse, tags=["analysis"])
async def get_regression_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    baseline_days: int = FastAPIQuery(14, description="Number of days to include for baseline"),
    recent_days: int = FastAPIQuery(7, description="Number of days to include for recent tests"),
    min_duration_change: float = FastAPIQuery(
        0.5, description="Minimum duration change to consider significant (seconds)"
    ),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get regression report comparing recent test runs to a baseline period."""
    api = InsightAPI(profile_name=profile)

    # Get baseline sessions (older period)
    now = datetime.now()
    baseline_start = now - timedelta(days=baseline_days + recent_days)
    baseline_end = now - timedelta(days=recent_days)
    baseline_query = api.query().filter_by_date_range(baseline_start, baseline_end)
    if sut:
        baseline_query = baseline_query.filter_by_sut(sut)
    baseline_sessions = baseline_query.get_sessions()

    # Get recent sessions
    recent_query = api.query().filter_by_date_range(recent_days)
    if sut:
        recent_query = recent_query.filter_by_sut(sut)
    recent_sessions = recent_query.get_sessions()

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
        if (
            nodeid in baseline_tests
            and baseline_tests[nodeid].outcome == TestOutcome.PASSED
            and test.outcome == TestOutcome.FAILED
        ):
            new_failures.append(
                {
                    "nodeid": nodeid,
                    "name": test.name,
                    "error_message": test.error_message,
                }
            )

    # Find fixed tests (failed in baseline, passed in recent)
    fixed_tests = []
    for nodeid, test in recent_tests.items():
        if (
            nodeid in baseline_tests
            and baseline_tests[nodeid].outcome == TestOutcome.FAILED
            and test.outcome == TestOutcome.PASSED
        ):
            fixed_tests.append(
                {
                    "nodeid": nodeid,
                    "name": test.name,
                }
            )

    # Find performance regressions (slower in recent)
    performance_regressions = []
    for nodeid, test in recent_tests.items():
        if nodeid in baseline_tests:
            duration_change = test.duration - baseline_tests[nodeid].duration
            if duration_change > min_duration_change:
                performance_regressions.append(
                    {
                        "nodeid": nodeid,
                        "name": test.name,
                        "baseline_duration": baseline_tests[nodeid].duration,
                        "recent_duration": test.duration,
                        "change": duration_change,
                        "percent_change": (
                            (duration_change / baseline_tests[nodeid].duration) * 100
                            if baseline_tests[nodeid].duration > 0
                            else 0
                        ),
                    }
                )

    # Find performance improvements (faster in recent)
    performance_improvements = []
    for nodeid, test in recent_tests.items():
        if nodeid in baseline_tests:
            duration_change = baseline_tests[nodeid].duration - test.duration
            if duration_change > min_duration_change:
                performance_improvements.append(
                    {
                        "nodeid": nodeid,
                        "name": test.name,
                        "baseline_duration": baseline_tests[nodeid].duration,
                        "recent_duration": test.duration,
                        "change": duration_change,
                        "percent_change": (
                            (duration_change / baseline_tests[nodeid].duration) * 100
                            if baseline_tests[nodeid].duration > 0
                            else 0
                        ),
                    }
                )

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


@app.get("/api/analysis/quality", response_model=TestSuiteQualityResponse, tags=["analysis"])
async def get_quality_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(30, description="Number of days to include"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get test suite quality report analyzing test design and organization."""
    api = InsightAPI(profile_name=profile)
    query = api.query()

    if sut:
        query = query.filter_by_sut(sut)

    query = query.filter_by_date_range(days=days)
    sessions = query.get_sessions()

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
        "fast": [],  # < 0.1s
        "medium": [],  # 0.1s - 1s
        "slow": [],  # 1s - 5s
        "very_slow": [],  # > 5s
    }

    for test in all_tests.values():
        # Module
        module = test.nodeid.split("::")[0]
        test_by_module[module].append(test)

        # Outcome
        outcome = test.outcome.name if hasattr(test.outcome, "name") else str(test.outcome)
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

    module_distribution = {module: len(tests) / total_tests for module, tests in test_by_module.items()}

    outcome_distribution = {outcome: len(tests) / total_tests for outcome, tests in test_by_outcome.items()}

    duration_distribution = {category: len(tests) / total_tests for category, tests in test_by_duration.items()}

    # Analyze test complexity (based on duration variance and failure patterns)
    duration_stats = {
        module: {
            "mean": mean([t.duration for t in tests]) if tests else 0,
            "variance": stdev([t.duration for t in tests]) if len(tests) > 1 else 0,
            "max": max([t.duration for t in tests]) if tests else 0,
        }
        for module, tests in test_by_module.items()
    }

    # Analyze test isolation (based on unreliable tests and outcome consistency)
    unreliable_tests = []
    for nodeid, test in all_tests.items():
        # Check if this test has different outcomes across sessions
        outcomes = set()
        for session in sessions:
            for session_test in session.test_results:
                if session_test.nodeid == nodeid:
                    outcomes.add(
                        session_test.outcome.name
                        if hasattr(session_test.outcome, "name")
                        else str(session_test.outcome)
                    )

        if len(outcomes) > 1:
            unreliable_tests.append(test)

    isolation_score = 1.0 - (len(unreliable_tests) / total_tests if total_tests > 0 else 0)

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
        recommendations.append("Many unreliable tests suggest isolation issues. Review test dependencies.")

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
            "unreliable_test_count": len(unreliable_tests),
            "isolation_score": isolation_score * 100,
        },
        "recommendations": recommendations,
        "timestamp": datetime.now(),
    }


# Enhanced Comparison Endpoint
@app.get("/api/compare", response_model=ComparisonResponse, tags=["comparison"])
async def compare_suts(
    sut1: str = FastAPIQuery(..., description="First SUT to compare"),
    sut2: str = FastAPIQuery(..., description="Second SUT to compare"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    include_tests: bool = FastAPIQuery(True, description="Include detailed test results"),
    min_duration_change: float = FastAPIQuery(
        0.1, description="Minimum duration change to consider significant (seconds)"
    ),
    include_metrics: bool = FastAPIQuery(True, description="Include aggregated metrics comparison"),
    profile: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Compare two SUTs and return the differences with enhanced parametrization."""
    try:
        api = InsightAPI(profile_name=profile)
        query = api.query()
        query = query.filter_by_date_range(days=days)

        # Get the most recent session for each SUT
        base_sessions = query.filter_by_sut(sut1).get_sessions()
        target_sessions = query.filter_by_sut(sut2).get_sessions()

        if not base_sessions:
            raise HTTPException(status_code=404, detail=f"No sessions found for SUT '{sut1}'")

        if not target_sessions:
            raise HTTPException(status_code=404, detail=f"No sessions found for SUT '{sut2}'")

        # Sort by start time (newest first) and take the first one
        base_session = sorted(base_sessions, key=lambda s: s.start_time, reverse=True)[0]
        target_session = sorted(target_sessions, key=lambda s: s.start_time, reverse=True)[0]

        # Compare the sessions
        comparison = api.compare()
        result = comparison.compare_sessions(base_session, target_session)

        # Extract metrics for both sessions
        if include_tests:
            # Include test-level changes
            outcome_changes = [
                {
                    "nodeid": change.nodeid,
                    "base_outcome": str(change.base_outcome),
                    "target_outcome": str(change.target_outcome),
                    "base_duration": change.base_duration,
                    "target_duration": change.target_duration,
                    "duration_change": change.duration_change,
                    "duration_change_percent": change.duration_change_percent,
                }
                for change in result.outcome_changes
                if abs(change.duration_change) >= min_duration_change
            ]

            # Include duration changes for tests with the same outcome
            duration_changes = [
                {
                    "nodeid": change.nodeid,
                    "outcome": str(change.outcome),
                    "base_duration": change.base_duration,
                    "target_duration": change.target_duration,
                    "duration_change": change.duration_change,
                    "duration_change_percent": change.duration_change_percent,
                }
                for change in result.duration_changes
                if abs(change.duration_change) >= min_duration_change
            ]

            # Include new and removed tests
            new_tests = [
                {
                    "nodeid": test.nodeid,
                    "outcome": str(test.outcome),
                    "duration": test.duration,
                }
                for test in result.new_tests
            ]
            removed_tests = [
                {
                    "nodeid": test.nodeid,
                    "outcome": str(test.outcome),
                    "duration": test.duration,
                }
                for test in result.removed_tests
            ]
        else:
            # Just include counts
            outcome_changes = []
            duration_changes = []
            new_tests = []
            removed_tests = []

        # Calculate session-level metrics
        base_metrics = {
            "total_tests": len(result.base_session.test_results),
            "passed_tests": sum(1 for t in result.base_session.test_results if t.outcome == TestOutcome.PASSED),
            "failed_tests": sum(1 for t in result.base_session.test_results if t.outcome == TestOutcome.FAILED),
            "skipped_tests": sum(1 for t in result.base_session.test_results if t.outcome == TestOutcome.SKIPPED),
            "avg_duration": (
                mean([t.duration for t in result.base_session.test_results if t.duration])
                if result.base_session.test_results
                else 0
            ),
        }

        target_metrics = {
            "total_tests": len(result.target_session.test_results),
            "passed_tests": sum(1 for t in result.target_session.test_results if t.outcome == TestOutcome.PASSED),
            "failed_tests": sum(1 for t in result.target_session.test_results if t.outcome == TestOutcome.FAILED),
            "skipped_tests": sum(1 for t in result.target_session.test_results if t.outcome == TestOutcome.SKIPPED),
            "avg_duration": (
                mean([t.duration for t in result.target_session.test_results if t.duration])
                if result.target_session.test_results
                else 0
            ),
        }

        metrics_comparison = {
            "base": base_metrics,
            "target": target_metrics,
        }

        # Create changed outcomes from outcome_changes
        changed_outcomes = [
            {
                "nodeid": change["nodeid"],
                "base": change["base_outcome"],
                "target": change["target_outcome"],
            }
            for change in outcome_changes
        ]

        return {
            "base_sut": sut1,
            "target_sut": sut2,
            "base_session_id": base_session.id,
            "target_session_id": target_session.id,
            "base_session_time": base_session.start_time,
            "target_session_time": target_session.start_time,
            "metrics_comparison": metrics_comparison,
            "outcome_changes": outcome_changes,
            "duration_changes": duration_changes,
            "new_tests": new_tests,
            "removed_tests": removed_tests,
            "changed_outcomes": changed_outcomes,
            "timestamp": datetime.now(),
        }

    except ComparisonError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("Error comparing SUTs")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/suts", response_model=SUTsResponse, tags=["query"])
async def get_available_suts(
    all_profiles: bool = FastAPIQuery(False, description="Get SUTs from all profiles"),
    profile: Optional[str] = FastAPIQuery(None, description="Specific profile to query"),
):
    """Get a list of all available Systems Under Test (SUTs).

    This endpoint helps users discover what SUTs are available in the system
    without needing to know them in advance.

    Args:
        all_profiles: If True, return SUTs from all defined profiles.
                     If False (default), only return SUTs from the active profile.

    Returns:
        A list of all unique SUT names found in the test sessions.
    """
    # Get profile information
    profile_manager = get_profile_manager()
    active_profile = profile_manager.get_active_profile()

    # Log active profile for debugging
    logging.info(f"Active profile: {active_profile.name}, all_profiles={all_profiles}")

    # Collect SUTs
    all_suts = set()

    # Function to extract SUTs directly from storage file
    def get_suts_from_file(profile_name):
        file_suts = set()
        try:
            profile_obj = profile_manager.get_profile(profile_name)
            if profile_obj and profile_obj.file_path:
                logging.info(f"Checking file path for profile {profile_name}: {profile_obj.file_path}")
                if os.path.exists(profile_obj.file_path):
                    try:
                        with open(profile_obj.file_path, "r") as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                for session in data:
                                    if isinstance(session, dict) and "sut_name" in session and session["sut_name"]:
                                        file_suts.add(session["sut_name"])
                        logging.info(f"SUTs found in profile {profile_name} via file: {file_suts}")
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid JSON format in {profile_obj.file_path}")
                    except Exception as e:
                        logging.warning(f"Error reading {profile_obj.file_path}: {str(e)}")
                else:
                    logging.warning(f"File does not exist: {profile_obj.file_path}")
            else:
                logging.warning(f"Profile {profile_name} has no valid file path")
        except Exception as ex:
            logging.warning(f"Error accessing profile {profile_name}: {str(ex)}")

        return file_suts

    # Function to extract SUTs from a profile using API
    def get_suts_from_api(profile_name):
        api_suts = set()
        api_error = False

        try:
            # Create a new InsightAPI instance for each profile
            api = InsightAPI(profile_name=profile_name)

            # Only call with_profile if not using the active profile
            if profile_name != active_profile.name:
                api = api.with_profile(profile_name)

            query_result = api.query().execute()
            api_suts = {session.sut_name for session in query_result.sessions if session.sut_name}
            logging.info(f"SUTs found in profile {profile_name} via API: {api_suts}")
        except Exception as e:
            logging.warning(f"Error retrieving SUTs from profile {profile_name} via API: {str(e)}")
            api_error = True

        return api_suts, api_error

    # Process profiles based on the all_profiles flag
    if all_profiles:
        # Get SUTs from all defined profiles
        profiles_dict = profile_manager.list_profiles()
        for profile_name in profiles_dict.keys():
            # Try API first
            api_suts, api_error = get_suts_from_api(profile_name)

            # Always check file SUTs, especially if API had an error
            file_suts = get_suts_from_file(profile_name)

            # If API had an error, prioritize file SUTs
            if api_error and file_suts:
                all_suts.update(file_suts)
            else:
                # Otherwise combine results from both sources
                all_suts.update(api_suts)
                all_suts.update(file_suts)
    else:
        # Get SUTs from the active profile - try both API and file
        active_api_suts, active_api_error = get_suts_from_api(active_profile.name)
        active_file_suts = get_suts_from_file(active_profile.name)

        # If API had an error, prioritize file SUTs
        if active_api_error and active_file_suts:
            all_suts.update(active_file_suts)
        else:
            # Otherwise combine results from both sources
            all_suts.update(active_api_suts)
            all_suts.update(active_file_suts)

        # Also check environment variable override if it exists
        env_profile = os.environ.get("PYTEST_INSIGHT_PROFILE")
        if env_profile and env_profile != active_profile.name:
            logging.info(f"Checking environment profile: {env_profile}")

            # Try both API and file for env profile
            env_api_suts, env_api_error = get_suts_from_api(env_profile)
            env_file_suts = get_suts_from_file(env_profile)

            # If API had an error, prioritize file SUTs
            if env_api_error and env_file_suts:
                all_suts.update(env_file_suts)
            else:
                # Otherwise combine results from both sources
                all_suts.update(env_api_suts)
                all_suts.update(env_file_suts)

    # Convert to sorted list
    suts = sorted(list(all_suts))

    # Log final list of SUTs
    logging.info(f"Final list of SUTs: {suts}")

    # If no SUTs found, provide a default example
    if not suts:
        suts = ["example-sut"]

    return {"suts": suts, "count": len(suts)}


class InsightsResponse(BaseModel):
    """Model for insights response."""

    health_score: Dict[str, Any]
    stability_score: Dict[str, Any]
    performance_score: Dict[str, Any]
    warning_score: Dict[str, Any]
    failure_rate: float
    warning_rate: float
    avg_duration: float
    outcome_distribution: Dict[str, Any]
    slowest_tests: List[Dict[str, Any]]
    failure_trend: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


@app.get("/api/insights", response_model=InsightsResponse, tags=["insights"])
def get_insights(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
    profile_name: Optional[str] = FastAPIQuery(None, description="Storage profile to use"),
):
    """Get insights summary for test sessions.

    This endpoint provides a consolidated view of test health, stability,
    performance, and trends using the Insights module.

    Args:
        sut: Optional SUT name to filter by
        days: Number of days of data to include
        profile_name: Storage profile to use

    Returns:
        A comprehensive insights summary with health scores and key metrics
    """
    try:
        # Use the insights convenience function with profile if specified
        from pytest_insight.core.insights import insights, insights_with_profile

        if profile_name:
            insight = insights_with_profile(profile_name)
        else:
            insight = insights()

        # Apply query if SUT or days are specified
        if sut or days:

            def query_filter(q):
                query_obj = q
                if sut:
                    query_obj = query_obj.filter_by_sut(sut)
                return query_obj.filter_by_date_range(days=days)

            insight = insight.with_query(query_filter)

        # Get the console summary
        summary = insight.console_summary()

        # Transform the data to match the expected response model
        transformed_summary = {
            "health_score": {"overall": summary.get("health_score", 0)},
            "stability_score": {"overall": summary.get("stability_score", 0)},
            "performance_score": {"overall": summary.get("performance_score", 0)},
            "warning_score": {"overall": summary.get("warning_score", 0)},
            "failure_rate": summary.get("failure_rate", 0),
            "warning_rate": summary.get("warning_rate", 0),
            "avg_duration": summary.get("avg_duration", 0),
            "outcome_distribution": {
                str(outcome): {"count": count} for outcome, count in summary.get("outcome_distribution", [])
            },
            "slowest_tests": [
                {"nodeid": nodeid, "duration": duration} for nodeid, duration in summary.get("slowest_tests", [])
            ],
            "failure_trend": summary.get("failure_trend", {}),
            "timestamp": datetime.now(),
        }

        return transformed_summary

    except Exception as e:
        logging.exception("Error generating insights")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/profiles", response_model=List[str], tags=["profiles"])
def get_available_profiles():
    """Get a list of all available storage profiles.

    This endpoint helps users discover what storage profiles are available
    without needing to know them in advance.

    Returns:
        A list of all profile names in the system.
    """
    try:
        from pytest_insight.core.storage import get_profile_manager

        profile_manager = get_profile_manager()
        profiles = list(profile_manager.list_profiles().keys())

        # If no profiles exist, return a default one
        if not profiles:
            profiles = ["default"]

        return profiles

    except Exception as e:
        logging.exception("Error retrieving profiles")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/{profile_name}", response_model=InsightsResponse, tags=["insights"])
def get_insights_with_profile(
    profile_name: str = FastAPIPath(..., description="Storage profile name"),
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
):
    """Get insights summary using a specific storage profile.

    This endpoint provides insights using a named storage profile.

    Args:
        profile_name: Name of the profile to use
        sut: Optional SUT name to filter by
        days: Number of days of data to include

    Returns:
        A comprehensive insights summary with health scores and key metrics
    """
    try:
        # Use the insights_with_profile convenience function
        from pytest_insight.core.insights import insights_with_profile

        insight = insights_with_profile(profile_name)

        # Apply query if SUT or days are specified
        if sut or days:

            def query_filter(q):
                query_obj = q
                if sut:
                    query_obj = query_obj.filter_by_sut(sut)
                return query_obj.filter_by_date_range(days=days)

            insight = insight.with_query(query_filter)

        # Get the console summary
        summary = insight.console_summary()

        # Transform the data to match the expected response model
        transformed_summary = {
            "health_score": {"overall": summary.get("health_score", 0)},
            "stability_score": {"overall": summary.get("stability_score", 0)},
            "performance_score": {"overall": summary.get("performance_score", 0)},
            "warning_score": {"overall": summary.get("warning_score", 0)},
            "failure_rate": summary.get("failure_rate", 0),
            "warning_rate": summary.get("warning_rate", 0),
            "avg_duration": summary.get("avg_duration", 0),
            "outcome_distribution": {
                str(outcome): {"count": count} for outcome, count in summary.get("outcome_distribution", [])
            },
            "slowest_tests": [
                {"nodeid": nodeid, "duration": duration} for nodeid, duration in summary.get("slowest_tests", [])
            ],
            "failure_trend": summary.get("failure_trend", {}),
            "timestamp": datetime.now(),
        }

        return transformed_summary

    except Exception as e:
        logging.exception(f"Error generating insights with profile {profile_name}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profiles", response_model=Dict[str, Any], tags=["profiles"])
def create_profile_endpoint(
    name: str = FastAPIQuery(..., description="Profile name"),
    storage_type: str = FastAPIQuery("json", description="Storage type (json, sqlite, etc.)"),
    file_path: Optional[str] = FastAPIQuery(None, description="Path to storage file"),
):
    """Create a new storage profile.

    Args:
        name: Name for the new profile
        storage_type: Type of storage (json, sqlite, etc.), defaults to 'json'
        file_path: Optional path to the storage file

    Returns:
        The created profile information
    """
    try:
        profile = create_profile(name, storage_type=storage_type, file_path=file_path)

        return {
            "name": profile.name,
            "storage_type": profile.storage_type,
            "file_path": profile.file_path,
            "created": True,
        }

    except Exception as e:
        logging.exception(f"Error creating profile {name}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/profiles/{profile_name}", response_model=Dict[str, Any], tags=["profiles"])
def delete_profile(
    profile_name: str = FastAPIPath(..., description="Profile name to delete"),
):
    """Delete a storage profile.

    Args:
        profile_name: Name of the profile to delete

    Returns:
        Confirmation of deletion
    """
    try:
        from pytest_insight.core.storage import get_profile_manager

        profile_manager = get_profile_manager()
        success = profile_manager.delete_profile(profile_name)

        if not success:
            raise HTTPException(status_code=404, detail=f"Profile {profile_name} not found")

        return {"name": profile_name, "deleted": True}

    except Exception as e:
        logging.exception(f"Error deleting profile {profile_name}")
        raise HTTPException(status_code=500, detail=str(e))


# Global selector UI
@app.get("/selector", response_class=HTMLResponse, include_in_schema=False)
async def global_selector():
    """Provide a UI for selecting global profile and SUT."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>pytest-insight Global Selector</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                margin-top: 0;
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            select, input {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #45a049;
            }
            .status {
                margin-top: 20px;
                padding: 10px;
                border-radius: 4px;
            }
            .success {
                background-color: #dff0d8;
                color: #3c763d;
            }
            .error {
                background-color: #f2dede;
                color: #a94442;
            }
            .nav-links {
                margin-top: 20px;
                padding-top: 15px;
                border-top: 1px solid #eee;
            }
            .nav-links a {
                display: inline-block;
                margin-right: 15px;
                color: #0d6efd;
                text-decoration: none;
            }
            .nav-links a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>pytest-insight Global Selector</h1>
            <p>Set the global profile and SUT for all API calls. These settings will be used as defaults when specific values are not provided.</p>

            <div class="form-group">
                <label for="profile">Storage Profile:</label>
                <select id="profile">
                    <option value="">Loading profiles...</option>
                </select>
            </div>

            <div class="form-group">
                <label for="sut">System Under Test (SUT):</label>
                <select id="sut">
                    <option value="">Loading SUTs...</option>
                </select>
            </div>

            <button id="saveBtn">Save Settings</button>

            <div id="status" class="status" style="display: none;"></div>

            <div class="nav-links">
                <a href="/docs">API Documentation</a>
                <a href="/">Home</a>
            </div>
        </div>

        <script>
            // Fetch available profiles
            fetch('/api/insights/profiles')
                .then(response => response.json())
                .then(profiles => {
                    const profileSelect = document.getElementById('profile');
                    profileSelect.innerHTML = '<option value="">Select a profile</option>';

                    profiles.forEach(profile => {
                        const option = document.createElement('option');
                        option.value = profile;
                        option.textContent = profile;
                        profileSelect.appendChild(option);
                    });

                    // Set current value if available
                    fetch('/api/settings/current')
                        .then(response => response.json())
                        .then(settings => {
                            if (settings.profile) {
                                profileSelect.value = settings.profile;
                            }
                        });
                })
                .catch(error => console.error('Error loading profiles:', error));

            // Fetch available SUTs
            fetch('/api/suts')
                .then(response => response.json())
                .then(data => {
                    const sutSelect = document.getElementById('sut');
                    sutSelect.innerHTML = '<option value="">Select a SUT</option>';

                    data.suts.forEach(sut => {
                        const option = document.createElement('option');
                        option.value = sut;
                        option.textContent = sut;
                        sutSelect.appendChild(option);
                    });

                    // Set current value if available
                    fetch('/api/settings/current')
                        .then(response => response.json())
                        .then(settings => {
                            if (settings.sut) {
                                sutSelect.value = settings.sut;
                            }
                        });
                })
                .catch(error => console.error('Error loading SUTs:', error));

            // Save settings
            document.getElementById('saveBtn').addEventListener('click', () => {
                const profile = document.getElementById('profile').value;
                const sut = document.getElementById('sut').value;

                fetch('/api/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        profile: profile,
                        sut: sut
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById('status');
                    statusDiv.style.display = 'block';

                    if (data.success) {
                        statusDiv.className = 'status success';
                        statusDiv.textContent = 'Settings saved successfully!';
                    } else {
                        statusDiv.className = 'status error';
                        statusDiv.textContent = 'Error: ' + data.message;
                    }
                })
                .catch(error => {
                    const statusDiv = document.getElementById('status');
                    statusDiv.style.display = 'block';
                    statusDiv.className = 'status error';
                    statusDiv.textContent = 'Error saving settings: ' + error.message;
                });
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Global settings endpoints
class GlobalSettings(BaseModel):
    """Model for global settings."""

    profile: Optional[str] = None
    sut: Optional[str] = None


# In-memory storage for global settings
# In a production app, this would be persisted to a database
global_settings = GlobalSettings()


@app.post("/api/settings", response_model=Dict[str, Any], tags=["settings"])
async def set_global_settings(settings: GlobalSettings):
    """Set global profile and SUT settings.

    These settings will be used as defaults when specific values are not provided
    in other API calls.

    Args:
        settings: Global settings to save

    Returns:
        Confirmation of saved settings
    """
    global global_settings

    try:
        # Validate profile if provided
        if settings.profile:
            profile_manager = get_profile_manager()
            profile = profile_manager.get_profile(settings.profile)
            if not profile:
                return {
                    "success": False,
                    "message": f"Profile '{settings.profile}' does not exist",
                }

            # Validate SUT if provided
            if settings.sut:
                storage = get_storage_instance(profile_name=settings.profile)
                sessions = storage.load_sessions()
                suts = {session.sut_name for session in sessions if session.sut_name}

                if settings.sut not in suts:
                    return {
                        "success": False,
                        "message": f"SUT '{settings.sut}' does not exist",
                    }

        # Save settings
        global_settings = settings

        return {"success": True, "profile": settings.profile, "sut": settings.sut}

    except Exception as e:
        logging.exception("Error setting global settings")
        return {"success": False, "message": str(e)}


@app.get("/api/settings/current", response_model=GlobalSettings, tags=["settings"])
async def get_global_settings():
    """Get current global profile and SUT settings."""
    return global_settings


# Add a home page
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home():
    """Serve the home page with links to selector and API docs."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>pytest-insight API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                margin-top: 0;
            }
            h2 {
                color: #555;
                margin-top: 30px;
            }
            p {
                line-height: 1.5;
                color: #444;
            }
            .card {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 15px;
                margin-bottom: 20px;
                background-color: #f9f9f9;
            }
            .card h3 {
                margin-top: 0;
                color: #333;
            }
            .btn {
                display: inline-block;
                padding: 10px 15px;
                background-color: #4CAF50;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin-right: 10px;
                margin-top: 10px;
            }
            .btn:hover {
                background-color: #45a049;
            }
            .btn-secondary {
                background-color: #6c757d;
            }
            .btn-secondary:hover {
                background-color: #5a6268;
            }
            .nav-links {
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #eee;
                text-align: center;
            }
            .nav-links a {
                display: inline-block;
                margin: 0 10px;
                color: #0d6efd;
                text-decoration: none;
            }
            .nav-links a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>pytest-insight API</h1>
            <p>Welcome to the pytest-insight API server. This tool provides analytics and insights for your pytest test results.</p>

            <h2>Core Components</h2>
            <p>pytest-insight is built around four primary operations:</p>

            <div class="card">
                <h3>1. Query</h3>
                <p>Find and filter test sessions based on various criteria like SUT, time range, and test outcomes.</p>
            </div>

            <div class="card">
                <h3>2. Compare</h3>
                <p>Compare test results between different versions, time periods, or environments to identify changes and regressions.</p>
            </div>

            <div class="card">
                <h3>3. Analyze</h3>
                <p>Extract insights and metrics from test sessions to understand health, stability, and performance.</p>
            </div>

            <div class="card">
                <h3>4. Insights</h3>
                <p>Get consolidated views with health scores, recommendations, and actionable information.</p>
            </div>

            <h2>Storage Profiles</h2>
            <p>The API supports multiple storage profiles, allowing you to work with different test data sources.</p>

            <div style="margin-top: 20px;">
                <a href="/selector" class="btn">Configure Profile & SUT</a>
                <a href="/docs" class="btn btn-secondary">API Documentation</a>
            </div>

            <div class="nav-links">
                <a href="/selector">Profile Selector</a>
                <a href="/docs">API Docs</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Test data generation page
@app.get("/generator", response_class=HTMLResponse, include_in_schema=False)
async def test_data_generator():
    """Provide a UI for generating test data."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>pytest-insight Test Data Generator</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                margin-top: 0;
            }
            .form-group {
                margin-bottom: 15px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            select, input {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                box-sizing: border-box;
            }
            input[type="checkbox"] {
                width: auto;
            }
            .checkbox-label {
                display: inline-block;
                font-weight: normal;
                margin-left: 5px;
            }
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background-color: #45a049;
            }
            .status {
                margin-top: 20px;
                padding: 10px;
                border-radius: 4px;
            }
            .success {
                background-color: #dff0d8;
                color: #3c763d;
            }
            .error {
                background-color: #f2dede;
                color: #a94442;
            }
            .nav-links {
                margin-top: 20px;
                padding-top: 15px;
                border-top: 1px solid #eee;
            }
            .nav-links a {
                display: inline-block;
                margin-right: 15px;
                color: #0d6efd;
                text-decoration: none;
            }
            .nav-links a:hover {
                text-decoration: underline;
            }
            .category-group {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }
            .category-item {
                display: flex;
                align-items: center;
                margin-right: 15px;
            }
            .slider-container {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .slider-value {
                min-width: 40px;
                text-align: right;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Test Data Generator</h1>
            <p>Generate practice test data for pytest-insight with customizable parameters.</p>

            <div class="form-group">
                <label for="days">Number of Days:</label>
                <div class="slider-container">
                    <input type="range" id="days" name="days" min="1" max="90" value="7" oninput="updateValue('days')">
                    <span id="days-value" class="slider-value">7</span>
                </div>
            </div>

            <div class="form-group">
                <label for="targets">Target Sessions per Base:</label>
                <div class="slider-container">
                    <input type="range" id="targets" name="targets" min="1" max="10" value="3" oninput="updateValue('targets')">
                    <span id="targets-value" class="slider-value">3</span>
                </div>
            </div>

            <div class="form-group">
                <label for="start-date">Start Date:</label>
                <input type="date" id="start-date" name="start-date">
            </div>

            <div class="form-group">
                <label for="output">Output Path:</label>
                <input type="text" id="output" name="output" placeholder="Default: ~/.pytest_insight/practice.json">
            </div>

            <div class="form-group">
                <label for="pass-rate">Pass Rate:</label>
                <div class="slider-container">
                    <input type="range" id="pass-rate" name="pass-rate" min="0.1" max="0.9" step="0.05" value="0.45" oninput="updateValue('pass-rate')">
                    <span id="pass-rate-value" class="slider-value">0.45</span>
                </div>
            </div>

            <div class="form-group">
                <label for="reliability-rate">Reliability Test Rate:</label>
                <div class="slider-container">
                    <input type="range" id="reliability-rate" name="reliability-rate" min="0.05" max="0.99" step="0.01" value="0.83" oninput="updateValue('reliability-rate')">
                    <span id="reliability-rate-value" class="slider-value">0.83</span>
                </div>
            </div>

            <div class="form-group">
                <label for="warning-rate">Warning Rate:</label>
                <div class="slider-container">
                    <input type="range" id="warning-rate" name="warning-rate" min="0.01" max="0.2" step="0.01" value="0.085" oninput="updateValue('warning-rate')">
                    <span id="warning-rate-value" class="slider-value">0.085</span>
                </div>
            </div>

            <div class="form-group">
                <label for="sut-filter">SUT Filter Prefix:</label>
                <select id="sut-filter" name="sut-filter">
                    <option value="">All SUTs</option>
                    <option value="api-">api-*</option>
                    <option value="ui-">ui-*</option>
                    <option value="db-">db-*</option>
                    <option value="auth-">auth-*</option>
                    <option value="integration-">integration-*</option>
                    <option value="performance-">performance-*</option>
                </select>
            </div>

            <div class="form-group">
                <label>Test Categories:</label>
                <div class="category-group">
                    <div class="category-item">
                        <input type="checkbox" id="cat-api" name="categories" value="api" checked>
                        <label class="checkbox-label" for="cat-api">API</label>
                    </div>
                    <div class="category-item">
                        <input type="checkbox" id="cat-ui" name="categories" value="ui" checked>
                        <label class="checkbox-label" for="cat-ui">UI</label>
                    </div>
                    <div class="category-item">
                        <input type="checkbox" id="cat-db" name="categories" value="db" checked>
                        <label class="checkbox-label" for="cat-db">Database</label>
                    </div>
                    <div class="category-item">
                        <input type="checkbox" id="cat-auth" name="categories" value="auth" checked>
                        <label class="checkbox-label" for="cat-auth">Auth</label>
                    </div>
                    <div class="category-item">
                        <input type="checkbox" id="cat-integration" name="categories" value="integration" checked>
                        <label class="checkbox-label" for="cat-integration">Integration</label>
                    </div>
                    <div class="category-item">
                        <input type="checkbox" id="cat-performance" name="categories" value="performance" checked>
                        <label class="checkbox-label" for="cat-performance">Performance</label>
                    </div>
                </div>
            </div>

            <div class="form-group">
                <input type="checkbox" id="quiet" name="quiet">
                <label class="checkbox-label" for="quiet">Quiet Mode (suppress detailed output)</label>
            </div>

            <div class="form-group">
                <label for="profile">Storage Profile:</label>
                <select id="profile">
                    <option value="">Loading profiles...</option>
                </select>
            </div>

            <button id="generateBtn">Generate Test Data</button>

            <div id="status" class="status" style="display: none;"></div>

            <div class="nav-links">
                <a href="/">Home</a>
                <a href="/selector">Profile Selector</a>
                <a href="/api-docs">API Documentation</a>
            </div>
        </div>

        <script>
            // Function to update slider value displays
            function updateValue(id) {
                const slider = document.getElementById(id);
                const valueDisplay = document.getElementById(id + '-value');
                valueDisplay.textContent = slider.value;
            }

            // Set default date to 2023-01-01
            document.getElementById('start-date').value = '2023-01-01';

            // Fetch available profiles
            fetch('/api/insights/profiles')
                .then(response => response.json())
                .then(profiles => {
                    const profileSelect = document.getElementById('profile');
                    profileSelect.innerHTML = '<option value="">Select a profile</option>';

                    profiles.forEach(profile => {
                        const option = document.createElement('option');
                        option.value = profile;
                        option.textContent = profile;
                        profileSelect.appendChild(option);
                    });

                    // Set current value if available
                    fetch('/api/settings/current')
                        .then(response => response.json())
                        .then(settings => {
                            if (settings.profile) {
                                profileSelect.value = settings.profile;
                            }
                        });
                })
                .catch(error => console.error('Error loading profiles:', error));

            // Generate test data
            document.getElementById('generateBtn').addEventListener('click', () => {
                const days = document.getElementById('days').value;
                const targets = document.getElementById('targets').value;
                const startDate = document.getElementById('start-date').value;
                const output = document.getElementById('output').value;
                const passRate = document.getElementById('pass-rate').value;
                const reliabilityRate = document.getElementById('reliability-rate').value;
                const warningRate = document.getElementById('warning-rate').value;
                const sutFilter = document.getElementById('sut-filter').value;
                const quiet = document.getElementById('quiet').checked;
                const profile = document.getElementById('profile').value;

                // Get selected categories
                const categoryCheckboxes = document.querySelectorAll('input[name="categories"]:checked');
                const categories = Array.from(categoryCheckboxes).map(cb => cb.value).join(',');

                // Build request payload
                const payload = {
                    days: parseInt(days),
                    targets: parseInt(targets),
                    pass_rate: parseFloat(passRate),
                    reliability_rate: parseFloat(reliabilityRate),
                    warning_rate: parseFloat(warningRate),
                    quiet: quiet,
                    profile: profile || null
                };

                if (startDate) payload.start_date = startDate;
                if (output) payload.output = output;
                if (sutFilter) payload.sut_filter = sutFilter;
                if (categories) payload.categories = categories;

                // Show generating message
                const statusDiv = document.getElementById('status');
                statusDiv.className = 'status';
                statusDiv.textContent = 'Generating test data...';
                statusDiv.style.display = 'block';

                // Send request to generate data
                fetch('/api/generator/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                })
                .then(response => response.json())
                .then(data => {
                    statusDiv.style.display = 'block';

                    if (data.success) {
                        statusDiv.className = 'status success';
                        statusDiv.textContent = `Test data generated successfully! Created ${data.sessions} sessions with ${data.tests} test results.`;
                    } else {
                        statusDiv.className = 'status error';
                        statusDiv.textContent = `Error: ${data.message}`;
                    }
                })
                .catch(error => {
                    statusDiv.className = 'status error';
                    statusDiv.textContent = `Error: ${error.message}`;
                    statusDiv.style.display = 'block';
                });
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# Add generator API endpoint
class GeneratorOptions(BaseModel):
    """Model for test data generator options."""

    days: int = Field(7, description="Number of days to generate data for")
    targets: int = Field(3, description="Maximum number of target sessions per base session")
    start_date: Optional[str] = Field(None, description="Start date for data generation (YYYY-MM-DD)")
    output: Optional[str] = Field(None, description="Output path for practice database")
    pass_rate: float = Field(0.45, description="Base pass rate for normal tests")
    reliability_rate: float = Field(0.83, description="Rate of reliable tests")
    warning_rate: float = Field(0.085, description="Base rate for test warnings")
    sut_filter: Optional[str] = Field(None, description="Filter SUTs by prefix")
    categories: Optional[str] = Field(None, description="Comma-separated list of test categories to include")
    quiet: bool = Field(False, description="Suppress detailed output")
    profile: Optional[str] = Field(None, description="Storage profile to use for the generated data")


@app.post("/api/generator/generate", response_model=Dict[str, Any], tags=["generator"])
async def generate_test_data(options: GeneratorOptions):
    """Generate test data with the specified options.

    This endpoint runs the test data generator with the provided configuration
    and returns information about the generated data.

    Args:
        options: Configuration options for test data generation

    Returns:
        Information about the generated test data
    """
    try:
        import subprocess
        import sys

        # Build command arguments
        cmd = [sys.executable, "-m", "pytest_insight.scripts.db_generator"]

        # Add all options
        cmd.extend(["--days", str(options.days)])
        cmd.extend(["--targets", str(options.targets)])

        if options.start_date:
            cmd.extend(["--start-date", options.start_date])

        if options.output:
            cmd.extend(["--output", options.output])
        elif options.profile:
            # If profile is specified but no output, use the profile's path
            from pytest_insight.core.storage import get_profile_manager

            profile_manager = get_profile_manager()
            profile = profile_manager.get_profile(options.profile)
            if profile and profile.file_path:
                cmd.extend(["--output", profile.file_path])

        cmd.extend(["--pass-rate", str(options.pass_rate)])
        cmd.extend(["--reliability-rate", str(options.reliability_rate)])
        cmd.extend(["--warning-rate", str(options.warning_rate)])

        if options.sut_filter:
            cmd.extend(["--sut-filter", options.sut_filter])

        if options.categories:
            cmd.extend(["--categories", options.categories])

        if options.quiet:
            cmd.append("--quiet")

        # Run the generator
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            # Parse output to get session and test counts
            output = result.stdout
            sessions_count = 0
            tests_count = 0

            for line in output.splitlines():
                if "Generated" in line and "sessions" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "Generated":
                            sessions_count = int(parts[i + 1])
                        elif part == "with":
                            tests_count = int(parts[i + 1])
                            break

            return {
                "success": True,
                "sessions": sessions_count,
                "tests": tests_count,
                "message": "Test data generated successfully",
                "details": output,
            }
        else:
            return {
                "success": False,
                "message": f"Error generating test data: {result.stderr}",
                "details": result.stderr,
            }

    except Exception as e:
        logging.exception("Error generating test data")
        return {"success": False, "message": str(e)}


# Debug endpoint to directly inspect database files for SUTs
@app.get("/api/debug/suts", response_model=Dict[str, Any], tags=["debug"])
async def debug_available_suts():
    """Debug endpoint to directly inspect database files for SUTs.

    This is a diagnostic endpoint that bypasses the normal API and directly
    inspects the database files to find all available SUTs.

    Returns:
        Detailed information about SUTs found in each database file
    """
    result = {"profiles": {}, "direct_files": {}, "all_suts": set()}

    try:
        # Import necessary modules
        import json
        from pathlib import Path

        from pytest_insight.core.storage import get_profile_manager
        from pytest_insight.utils.constants import DEFAULT_STORAGE_PATH

        # Get profile information
        profile_manager = get_profile_manager()
        profiles_dict = profile_manager.list_profiles()
        result["profile_names"] = list(profiles_dict.keys())

        # Check default storage path
        default_path = Path(DEFAULT_STORAGE_PATH)
        result["default_path"] = str(default_path)
        result["default_path_exists"] = default_path.exists()

        if default_path.exists():
            try:
                with open(default_path, "r") as f:
                    data = json.load(f)
                    suts = set()
                    for session in data:
                        if isinstance(session, dict) and "sut_name" in session and session["sut_name"]:
                            suts.add(session["sut_name"])
                    result["direct_files"]["default"] = {
                        "path": str(default_path),
                        "suts": list(suts),
                        "session_count": len(data),
                    }
                    result["all_suts"].update(suts)
            except Exception as e:
                result["direct_files"]["default"] = {
                    "path": str(default_path),
                    "error": str(e),
                }

        # Check profile storage paths
        for profile_name, profile in profiles_dict.items():
            result["profiles"][profile_name] = {
                "storage_type": profile.storage_type,
                "file_path": profile.file_path,
            }

            if profile.file_path and Path(profile.file_path).exists():
                try:
                    with open(profile.file_path, "r") as f:
                        data = json.load(f)
                        suts = set()
                        for session in data:
                            if isinstance(session, dict) and "sut_name" in session and session["sut_name"]:
                                suts.add(session["sut_name"])
                        result["profiles"][profile_name]["suts"] = list(suts)
                        result["profiles"][profile_name]["session_count"] = len(data)
                        result["all_suts"].update(suts)
                except Exception as e:
                    result["profiles"][profile_name]["error"] = str(e)

        # Look for any other JSON files that might contain sessions
        home_dir = Path.home()
        pytest_insight_dirs = [
            home_dir / ".pytest_insight",
            home_dir / ".config" / "pytest_insight",
            Path("/tmp/pytest_insight"),
        ]

        for directory in pytest_insight_dirs:
            if directory.exists():
                json_files = list(directory.glob("*.json"))
                for json_file in json_files:
                    if str(json_file) not in [str(default_path)] + [
                        p.file_path for p in profiles_dict.values() if p.file_path
                    ]:
                        try:
                            with open(json_file, "r") as f:
                                data = json.load(f)
                                if isinstance(data, list):
                                    for session in data:
                                        if isinstance(session, dict) and "sut_name" in session and session["sut_name"]:
                                            result["all_suts"].add(session["sut_name"])
                            result["direct_files"][str(json_file)] = {
                                "path": str(json_file),
                                "suts": list(result["all_suts"]),
                                "session_count": len(data),
                            }
                        except Exception:
                            # Skip files that can't be parsed as JSON or don't contain sessions
                            pass

        # Convert set to list for JSON serialization
        result["all_suts"] = sorted(list(result["all_suts"]))
        return result
    except Exception as e:
        return {"error": str(e)}
