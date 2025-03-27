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
    timestamp: datetime


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
    for session in sessions[:limit]:
        results.append({
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
):
    """Get health report for test sessions."""
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

    return health_report


@app.get("/api/analysis/stability", response_model=StabilityReportResponse, tags=["Analysis"])
async def get_stability_report(
    sut: Optional[str] = FastAPIQuery(None, description="System Under Test name"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
):
    """Get stability report for test sessions."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    analysis = api.analyze().sessions(sessions)

    # Get flaky tests
    flaky_tests = analysis.find_flaky_tests()

    # Get consistent failures
    consistent_failures = analysis.find_consistent_failures()

    # Get outcome patterns
    outcome_patterns = analysis.outcome_patterns()

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
):
    """Get performance report for test sessions."""
    api = InsightAPI()
    query = api.query()

    if sut:
        query = query.for_sut(sut)

    query = query.in_last_days(days)
    sessions = query.execute()

    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found matching the criteria")

    analysis = api.analyze().sessions(sessions)

    # Get slow tests
    slow_tests = analysis.find_slow_tests()

    # Get duration trends
    duration_trends = analysis.duration_trends()

    # Get performance metrics
    performance_metrics = analysis.performance_metrics()

    return {
        "slow_tests": slow_tests,
        "duration_trends": duration_trends,
        "performance_metrics": performance_metrics,
        "timestamp": datetime.now(),
    }


# Comparison Endpoints
@app.get("/api/compare", response_model=ComparisonResponse, tags=["Comparison"])
async def compare_suts(
    sut1: str = FastAPIQuery(..., description="First SUT to compare"),
    sut2: str = FastAPIQuery(..., description="Second SUT to compare"),
    days: int = FastAPIQuery(7, description="Number of days to include"),
):
    """Compare two SUTs and return the differences."""
    api = InsightAPI()
    comparison = api.compare().between_suts(sut1, sut2).in_last_days(days)
    result = comparison.execute()

    if not result:
        raise HTTPException(status_code=404, detail="No comparison data available for the specified SUTs")

    # Extract comparison data
    added_tests = result.get("added_tests", [])
    removed_tests = result.get("removed_tests", [])
    changed_outcomes = result.get("changed_outcomes", [])
    performance_changes = result.get("performance_changes", [])

    return {
        "sut1": sut1,
        "sut2": sut2,
        "added_tests": added_tests,
        "removed_tests": removed_tests,
        "changed_outcomes": changed_outcomes,
        "performance_changes": performance_changes,
        "timestamp": datetime.now(),
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
