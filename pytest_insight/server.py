import logging
import os
from collections import defaultdict
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from pytest_insight.filters import TestFilter
from pytest_insight.storage import JSONStorage

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("pytest_insight.server")

# Add file handler
log_file = os.path.expanduser("~/.pytest_insight/grafana_warning.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# Update FastAPI initialization with metadata
app = FastAPI(
    title="pytest-insight API",
    description="API for pytest test result analytics and metrics",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI endpoint
    redoc_url="/redoc",  # ReDoc endpoint
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="pytest-insight API",
        version="1.0.0",
        description="API for analyzing pytest test results and metrics",
        routes=app.routes,
    )

    # Add metric schema definitions
    openapi_schema["components"] = {
        "schemas": {
            "Metric": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Metric identifier following style guide",
                    },
                    "datapoints": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": [{"type": "number"}, {"type": "integer"}],
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        "description": "Array of [value, timestamp] pairs",
                    },
                },
                "required": ["target", "datapoints"],
            },
            "MetricQuery": {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "sut": {"type": "string"},
                            "days": {"type": "integer"},
                            "has_warnings": {"type": "boolean"},
                            "has_reruns": {"type": "boolean"},
                            "nodeid_contains": {"type": "string"},
                        },
                    },
                },
                "required": ["target"],
            },
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

storage = JSONStorage()

# Enable CORS for Grafana
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint for Grafana connection test."""
    logger.warning("Received root endpoint request")
    return {"status": "ok"}


# Add health check endpoint
@app.get("/health", response_class=JSONResponse)
async def health_check():
    """API health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/search")
async def search():
    """Return complete metric set following style guide."""
    logger.debug("Received metrics search request")
    return [
        # Test Outcomes (from TEST_OUTCOMES)
        "test.outcome.passed",
        "test.outcome.failed",
        "test.outcome.skipped",
        "test.outcome.xfailed",
        "test.outcome.xpassed",
        "test.outcome.rerun",
        "test.outcome.error",
        # Test Duration
        "test.duration.elapsed",
        "test.duration.trend",
        "test.duration.average",
        "test.duration.maximum",
        "test.duration.minimum",
        # Test Warning
        "test.warning.occurred",
        "test.warning.count",
        "test.warning.message",
        # Test Pattern
        "test.pattern.slowed",
        "test.pattern.fluctuated",
        "test.pattern.failed_often",
        "test.pattern.recovered",
        "test.pattern.flaked",
        # Session Metrics
        "session.metric.started",
        "session.metric.completed",
        "session.metric.duration",
        "session.metric.count",
        "session.metric.tagged",
        # SUT Metrics
        "sut.metric.count",
        "sut.metric.latest",
        "sut.metric.active",
        # Rerun Metrics
        "rerun.metric.attempted",
        "rerun.metric.succeeded",
        "rerun.metric.count",
        "rerun.metric.recovered",
        # History Metrics
        "history.metric.collected",
        "history.metric.duration",
        "history.metric.trend",
        "history.metric.compared",
        # Group Metrics
        "group.metric.formed",
        "group.metric.size",
        "group.metric.duration",
        "group.metric.pattern",
    ]


@app.post("/query")
async def query(request: Request):
    """Query metrics with filter support."""
    try:
        req = await request.json()
        metric = req.get("target")
        filters = req.get("filters", {})  # New: support filter parameters

        # Convert API filters to TestFilter
        test_filter = TestFilter(
            sut=filters.get("sut"),
            days=filters.get("days"),
            outcome=filters.get("outcome"),
            has_warnings=filters.get("warnings"),
            has_reruns=filters.get("reruns"),
            nodeid_contains=filters.get("contains"),
        )

        sessions = storage.load_sessions()
        filtered_sessions = test_filter.filter_sessions(sessions)

        # Apply filters before calculating metrics
        if metric == "test.outcome.passed":
            return [
                {
                    "target": "Test Passes",
                    "datapoints": [
                        [
                            sum(
                                1
                                for t in session.test_results
                                if test_filter.matches(t) and t.outcome == "PASSED"
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in filtered_sessions
                    ],
                }
            ]

        # ... other metrics
        if metric == "test.outcome.failed":
            return [
                {
                    "target": "Test Failures",
                    "datapoints": [
                        [
                            sum(
                                1
                                for t in session.test_results
                                if test_filter.matches(t) and t.outcome == "FAILED"
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in filtered_sessions
                    ],
                }
            ]
        if metric == "test.outcome.skipped":
            return [
                {
                    "target": "Test Skips",
                    "datapoints": [
                        [
                            sum(
                                1
                                for t in session.test_results
                                if test_filter.matches(t) and t.outcome == "SKIPPED"
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in filtered_sessions
                    ],
                }
            ]
        if metric == "test.outcome.xfailed":
            return [
                {
                    "target": "Test XFailures",
                    "datapoints": [
                        [
                            sum(
                                1
                                for t in session.test_results
                                if test_filter.matches(t) and t.outcome == "XFAILED"
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in filtered_sessions
                    ],
                }
            ]
        if metric == "test.outcome.xpassed":
            return [
                {
                    "target": "Test XPasses",
                    "datapoints": [
                        [
                            sum(
                                1
                                for t in session.test_results
                                if test_filter.matches(t) and t.outcome == "XPASSED"
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in filtered_sessions
                    ],
                }
            ]
        if metric == "test.outcome.rerun":
            return [
                {
                    "target": "Test Reruns",
                    "datapoints": [
                        [
                            sum(
                                1
                                for t in session.test_results
                                if test_filter.matches(t) and t.outcome == "RERUN"
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in filtered_sessions
                    ],
                }
            ]
        if metric == "test.outcome.error":
            return [
                {
                    "target": "Test Errors",
                    "datapoints": [
                        [
                            sum(
                                1
                                for t in session.test_results
                                if test_filter.matches(t) and t.outcome == "ERROR"
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in filtered_sessions
                    ],
                }
            ]

        logger.warning(f"Processing metric request: {metric}")

        if not metric:
            logger.warning("No target metric specified")
            return []

        result = []  # Store the response

        # Basic metrics processing
        if metric == "test.duration.trend":
            result = [
                {
                    "target": "Test Duration Trend",
                    "datapoints": [
                        [result.duration, int(result.start_time.timestamp() * 1000)]
                        for session in sessions
                        for result in session.test_results
                        if result.duration is not None
                    ],
                }
            ]

        elif metric == "test.failure.rate":
            # Calculate failure rate over time
            failures_by_time = defaultdict(lambda: {"total": 0, "failed": 0})
            for session in sessions:
                for result in session.test_results:
                    timestamp = int(result.start_time.timestamp() * 1000)
                    failures_by_time[timestamp]["total"] += 1
                    if result.outcome == "failed":
                        failures_by_time[timestamp]["failed"] += 1

            result = [
                {
                    "target": "Failure Rate",
                    "datapoints": [
                        [
                            (
                                stats["failed"] / stats["total"] * 100
                                if stats["total"] > 0
                                else 0
                            ),
                            timestamp,
                        ]
                        for timestamp, stats in sorted(failures_by_time.items())
                    ],
                }
            ]

        elif metric == "test.patterns.slow":
            # Identify consistently slow tests
            test_stats = defaultdict(list)
            for session in sessions:
                for result in session.test_results:
                    test_stats[result.nodeid].append(result.duration)

            slow_tests = [
                {"nodeid": nodeid, "avg_duration": sum(durations) / len(durations)}
                for nodeid, durations in test_stats.items()
                if sum(durations) / len(durations) > 1.0  # More than 1 second average
            ]

            # Fixed: datetime.now() is a method call, not a property
            current_timestamp = int(datetime.now().timestamp() * 1000)

            result = [
                {
                    "target": f"Slow Test: {test['nodeid']}",
                    "datapoints": [[test["avg_duration"], current_timestamp]],
                }
                for test in sorted(
                    slow_tests, key=lambda x: x["avg_duration"], reverse=True
                )[:5]
            ]

        elif metric == "test.warnings.count":
            result = [
                {
                    "target": "Warning Count",
                    "datapoints": [
                        [
                            sum(
                                bool(result.has_warning)
                                for result in session.test_results
                            ),
                            int(session.session_start_time.timestamp() * 1000),
                        ]
                        for session in sessions
                    ],
                }
            ]

        logger.warning(f"Returning data for metric {metric}: {result}")
        return result

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return []
