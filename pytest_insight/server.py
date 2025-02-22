from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pytest_insight.storage import JSONStorage
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
import logging
import os

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("pytest_insight.server")

# Add file handler
log_file = os.path.expanduser("~/.pytest_insight/grafana_warning.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

app = FastAPI()
storage = JSONStorage()

# Enable CORS for Grafana
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint for Grafana connection test."""
    logger.warning("Received root endpoint request")
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.warning("Received health check request")
    response = {"status": "ok"}
    logger.warning(f"Returning health check response: {response}")
    return response

@app.get("/search")
async def search():
    """Return available metrics."""
    logger.warning("Received metrics search request")
    metrics = [
        "test.duration.trend",
        "test.duration.average",
        "test.duration.max",
        "test.failure.rate",
        "test.patterns.slow",
        "test.warnings.count",

        # Outcome metrics
        "test.outcomes.total",
        "test.outcomes.passed",
        "test.outcomes.failed",
        "test.outcomes.skipped",
        "test.failure.rate",

        # Warning metrics
        "test.warnings.count",
        "test.warnings.bytest",

        # Timing patterns
        "test.patterns.slow",
        "test.patterns.inconsistent",

        # Session metrics
        "session.duration",
        "session.count"
    ]
    logger.warning(f"Returning available metrics: {metrics}")
    return metrics

@app.get("/query")
@app.post("/query")
async def query(request: Request, target: Optional[str] = None):
    """Handle both GET and POST queries from Grafana."""
    logger.warning(f"Received request method: {request.method}")

    try:
        if request.method == "POST":
            req = await request.json()
            metric = req.get("target")
        else:
            metric = target

        logger.warning(f"Processing metric request: {metric}")

        if not metric:
            logger.warning("No target metric specified")
            return []

        sessions = storage.load_sessions()
        result = []  # Store the response

        # Basic metrics processing
        if metric == "test.duration.trend":
            result = [{
                "target": "Test Duration Trend",
                "datapoints": [
                    [result.duration, int(result.start_time.timestamp() * 1000)]
                    for session in sessions
                    for result in session.test_results
                    if result.duration is not None
                ]
            }]

        elif metric == "test.failure.rate":
            # Calculate failure rate over time
            failures_by_time = defaultdict(lambda: {"total": 0, "failed": 0})
            for session in sessions:
                for result in session.test_results:
                    timestamp = int(result.start_time.timestamp() * 1000)
                    failures_by_time[timestamp]["total"] += 1
                    if result.outcome == "failed":
                        failures_by_time[timestamp]["failed"] += 1

            result = [{
                "target": "Failure Rate",
                "datapoints": [
                    [stats["failed"] / stats["total"] * 100 if stats["total"] > 0 else 0,
                     timestamp]
                    for timestamp, stats in sorted(failures_by_time.items())
                ]
            }]

        elif metric == "test.patterns.slow":
            # Identify consistently slow tests
            test_stats = defaultdict(list)
            for session in sessions:
                for result in session.test_results:
                    test_stats[result.nodeid].append(result.duration)

            slow_tests = [
                {
                    "nodeid": nodeid,
                    "avg_duration": sum(durations) / len(durations)
                }
                for nodeid, durations in test_stats.items()
                if sum(durations) / len(durations) > 1.0  # More than 1 second average
            ]

            # Fixed: datetime.now() is a method call, not a property
            current_timestamp = int(datetime.now().timestamp() * 1000)

            result = [{
                "target": f"Slow Test: {test['nodeid']}",
                "datapoints": [[test["avg_duration"], current_timestamp]]
            } for test in sorted(slow_tests, key=lambda x: x["avg_duration"], reverse=True)[:5]]

        elif metric == "test.warnings.count":
            result = [{
                "target": "Warning Count",
                "datapoints": [
                    [sum(bool(result.has_warning)
                     for result in session.test_results),
                     int(session.session_start_time.timestamp() * 1000)]
                    for session in sessions
                ]
            }]

        logger.warning(f"Returning data for metric {metric}: {result}")
        return result

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return []
