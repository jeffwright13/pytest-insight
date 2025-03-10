from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from pytest_insight.models import TestOutcome, TestResult, TestSession
from pytest_insight.query.comparison import Comparison, ComparisonResult
from pytest_insight.storage import get_storage_instance

router = APIRouter(prefix="/api/v1")


# Helper function to convert datetime to ISO 8601 string
def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO-8601 string with UTC Z suffix."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# Use model's native serialization with datetime formatting
def format_session_dict(session: TestSession) -> Dict:
    """Format a session dictionary with ISO 8601 dates."""
    session_dict = session.to_dict()

    # Format datetime fields
    if session_dict.get("session_start_time"):
        session_dict["start_time"] = format_datetime(session.session_start_time)
        del session_dict["session_start_time"]

    if session_dict.get("session_stop_time"):
        session_dict["stop_time"] = format_datetime(session.session_stop_time)
        del session_dict["session_stop_time"]

    return session_dict


# When counting outcomes, use the full enum
def get_outcome_counts(session: TestSession) -> Dict[str, int]:
    """Get counts for all test outcomes in a session."""
    counts = {outcome.value: 0 for outcome in TestOutcome}

    for test in session.test_results:
        outcome_value = test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
        counts[outcome_value] = counts.get(outcome_value, 0) + 1

    return counts


def format_test_result_dict(test: TestResult) -> Dict:
    """Format a test result dictionary with ISO 8601 dates."""
    test_dict = test.to_dict()

    # Format datetime fields
    if test_dict.get("start_time"):
        test_dict["start_time"] = format_datetime(test.start_time)

    if test_dict.get("stop_time"):
        test_dict["stop_time"] = format_datetime(test.stop_time)

    return test_dict


def format_comparison_result(result: ComparisonResult) -> Dict:
    """Format comparison result for API response."""
    # Convert sets to lists for JSON serialization
    return {
        "outcome_changes": result.outcome_changes,
        "new_failures": list(result.new_failures),
        "new_passes": list(result.new_passes),
        "flaky_tests": list(result.flaky_tests),
        "slower_tests": result.slower_tests,
        "faster_tests": result.faster_tests,
        "duration_change": result.duration_change,
        "statistics": {
            "change_count": len(result.outcome_changes),
            "failure_count": len(result.new_failures),
            "fix_count": len(result.new_passes),
            "flaky_count": len(result.flaky_tests),
            "slower_count": len(result.slower_tests),
            "faster_count": len(result.faster_tests),
        },
    }


@router.get("/sessions")
async def get_sessions(
    sut: Optional[str] = Query(None, description="Filter by SUT name"),
    tag: Optional[str] = Query(None, description="Filter by tag (format: key=value)"),
    limit: int = Query(100, description="Maximum number of sessions to return"),
    offset: int = Query(0, description="Skip the first N sessions"),
) -> JSONResponse:
    """Get list of test sessions with optional filtering."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Apply SUT filter if provided
    if sut:
        sessions = [s for s in sessions if s.sut_name == sut]

    # Apply tag filter if provided
    if tag:
        try:
            key, value = tag.split("=", 1)
            sessions = [s for s in sessions if s.session_tags.get(key) == value]
        except ValueError:
            return JSONResponse(
                status_code=400, content={"error": {"message": "Tag filter must be in format 'key=value'"}}
            )

    # Sort sessions by start time (newest first)
    sessions.sort(key=lambda x: x.session_start_time, reverse=True)

    # Apply pagination
    total_count = len(sessions)
    sessions = sessions[offset : offset + limit]

    # Enhance session data with outcome counts
    session_data = []
    for session in sessions:
        formatted = format_session_dict(session)
        formatted["outcome_counts"] = get_outcome_counts(session)
        formatted["test_count"] = len(session.test_results)
        session_data.append(formatted)

    return JSONResponse(
        content={"data": session_data, "meta": {"total": total_count, "limit": limit, "offset": offset}}
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    """Get details of a specific test session."""
    storage = get_storage_instance()
    session = storage.get_session_by_id(session_id)

    if not session:
        return JSONResponse(status_code=404, content={"error": {"message": f"Session with ID {session_id} not found"}})

    # Format session and test results
    session_data = format_session_dict(session)
    session_data["outcome_counts"] = get_outcome_counts(session)
    session_data["test_results"] = [format_test_result_dict(test) for test in session.test_results]

    return JSONResponse(content={"data": session_data})


@router.post("/compare")
async def compare_sessions(request: Request) -> JSONResponse:
    """Compare two test sessions and return differences."""
    # Parse request JSON
    data = await request.json()
    base_session_id = data.get("base_session_id")
    target_session_id = data.get("target_session_id")
    test_pattern = data.get("test_pattern")
    duration_threshold = float(data.get("duration_threshold", 1.0))

    if not base_session_id or not target_session_id:
        return JSONResponse(
            status_code=400, content={"error": {"message": "base_session_id and target_session_id are required"}}
        )

    storage = get_storage_instance()
    base_session = storage.get_session_by_id(base_session_id)
    target_session = storage.get_session_by_id(target_session_id)

    if not base_session:
        return JSONResponse(
            status_code=404, content={"error": {"message": f"Base session with ID {base_session_id} not found"}}
        )

    if not target_session:
        return JSONResponse(
            status_code=404, content={"error": {"message": f"Target session with ID {target_session_id} not found"}}
        )

    # Configure comparison
    comparison = Comparison()

    if test_pattern:
        comparison.with_test_pattern(test_pattern)

    comparison.with_duration_threshold(duration_threshold)

    # Execute comparison
    try:
        result = comparison.execute([base_session, target_session])

        # Build response with formatted data
        response_data = {
            "base_session": format_session_dict(base_session),
            "target_session": format_session_dict(target_session),
            **format_comparison_result(result),
        }

        return JSONResponse(content={"data": response_data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"message": f"Comparison failed: {str(e)}"}})


@router.post("/compare/bulk")
async def compare_sessions_bulk(request: Request) -> JSONResponse:
    """Compare multiple sessions against each other."""
    # Parse request JSON
    data = await request.json()
    base_session_ids = data.get("base_session_ids", [])
    target_session_ids = data.get("target_session_ids", [])
    test_pattern = data.get("test_pattern")
    duration_threshold = float(data.get("duration_threshold", 1.0))

    if not base_session_ids or not target_session_ids:
        return JSONResponse(
            status_code=400, content={"error": {"message": "base_session_ids and target_session_ids are required"}}
        )

    storage = get_storage_instance()

    # Get sessions by IDs
    base_sessions = []
    missing_base = []
    for session_id in base_session_ids:
        session = storage.get_session_by_id(session_id)
        if session:
            base_sessions.append(session)
        else:
            missing_base.append(session_id)

    target_sessions = []
    missing_target = []
    for session_id in target_session_ids:
        session = storage.get_session_by_id(session_id)
        if session:
            target_sessions.append(session)
        else:
            missing_target.append(session_id)

    if missing_base or missing_target:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": "Some sessions not found",
                    "missing_base": missing_base,
                    "missing_target": missing_target,
                }
            },
        )

    if not base_sessions or not target_sessions:
        return JSONResponse(status_code=400, content={"error": {"message": "No valid sessions found for comparison"}})

    # Perform all comparisons
    comparisons = []
    for base_session in base_sessions:
        for target_session in target_sessions:
            comparison = Comparison()

            if test_pattern:
                comparison.with_test_pattern(test_pattern)

            comparison.with_duration_threshold(duration_threshold)

            try:
                result = comparison.execute([base_session, target_session])

                # Only include comparisons with changes
                if (
                    result.new_failures
                    or result.new_passes
                    or result.outcome_changes
                    or result.slower_tests
                    or result.faster_tests
                ):
                    comparisons.append(
                        {
                            "base_session": format_session_dict(base_session),
                            "target_session": format_session_dict(target_session),
                            **format_comparison_result(result),
                        }
                    )
            except Exception as e:
                print(f"Error comparing {base_session.session_id} with {target_session.session_id}: {str(e)}")

    return JSONResponse(content={"data": comparisons})


@router.get("/compare/recent")
async def compare_recent_sessions(
    sut: str = Query(..., description="Filter by SUT name"),
    test_pattern: Optional[str] = Query(None, description="Filter by test pattern"),
    duration_threshold: float = Query(1.0, description="Minimum duration change (seconds)"),
) -> JSONResponse:
    """Compare most recent session with previous session for the same SUT."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter by SUT and sort by start time (newest first)
    sut_sessions = [s for s in sessions if s.sut_name == sut]
    sut_sessions.sort(key=lambda x: x.session_start_time, reverse=True)

    if len(sut_sessions) < 2:
        return JSONResponse(
            status_code=404, content={"error": {"message": f"Need at least 2 sessions for SUT '{sut}' to compare"}}
        )

    # Get most recent and previous session
    most_recent = sut_sessions[0]
    previous = sut_sessions[1]

    # Configure comparison
    comparison = Comparison()

    if test_pattern:
        comparison.with_test_pattern(test_pattern)

    comparison.with_duration_threshold(duration_threshold)

    # Execute comparison
    try:
        result = comparison.execute([previous, most_recent])

        # Build response
        response_data = {
            "base_session": format_session_dict(previous),
            "target_session": format_session_dict(most_recent),
            **format_comparison_result(result),
        }

        return JSONResponse(content={"data": response_data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"message": f"Comparison failed: {str(e)}"}})


@router.get("/flaky-tests")
async def get_flaky_tests(
    sut: Optional[str] = Query(None, description="Filter by SUT name"),
    limit: int = Query(20, description="Maximum number of flaky tests to return"),
    min_occurrences: int = Query(2, description="Minimum flakiness occurrences"),
) -> JSONResponse:
    """Identify flaky tests across sessions (tests that change outcome)."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter by SUT if provided
    if sut:
        sessions = [s for s in sessions if s.sut_name == sut]

    if len(sessions) < 2:
        return JSONResponse(
            status_code=404, content={"error": {"message": "Need at least 2 sessions to identify flaky tests"}}
        )

    # Sort sessions by start time
    sessions.sort(key=lambda x: x.session_start_time)

    # Track test outcomes across sessions
    test_outcomes = {}  # nodeid -> list of outcomes

    for session in sessions:
        for test in session.test_results:
            if test.nodeid not in test_outcomes:
                test_outcomes[test.nodeid] = []

            outcome = test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
            test_outcomes[test.nodeid].append(
                {
                    "session_id": session.session_id,
                    "outcome": outcome,
                    "time": format_datetime(session.session_start_time),
                }
            )

    # Identify flaky tests (tests with different outcomes)
    flaky_tests = []
    for nodeid, outcomes in test_outcomes.items():
        if len(outcomes) < 2:
            continue

        # Count unique outcomes
        unique_outcomes = {o["outcome"] for o in outcomes}
        if len(unique_outcomes) > 1:
            # Calculate flakiness
            changes = 0
            for i in range(1, len(outcomes)):
                if outcomes[i]["outcome"] != outcomes[i - 1]["outcome"]:
                    changes += 1

            if changes >= min_occurrences - 1:
                flaky_tests.append(
                    {
                        "nodeid": nodeid,
                        "outcomes": outcomes,
                        "changes": changes,
                        "last_seen": outcomes[-1]["time"],
                        "unique_outcomes": list(unique_outcomes),
                    }
                )

    # Sort by number of changes (most flaky first)
    flaky_tests.sort(key=lambda x: x["changes"], reverse=True)

    # Apply limit
    flaky_tests = flaky_tests[:limit]

    return JSONResponse(content={"data": flaky_tests, "meta": {"total": len(flaky_tests), "sut": sut or "all"}})


@router.get("/stats")
async def get_stats(sut: Optional[str] = Query(None, description="Filter by SUT name")) -> JSONResponse:
    """Get statistics about test sessions."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter by SUT if provided
    if sut:
        sessions = [s for s in sessions if s.sut_name == sut]

    if not sessions:
        return JSONResponse(
            status_code=404,
            content={"error": {"message": f"No sessions found for SUT '{sut}'" if sut else "No sessions found"}},
        )

    # Calculate statistics
    suts = {}
    tags = {}
    outcome_totals = {outcome.value: 0 for outcome in TestOutcome}
    total_tests = 0

    # Get unique SUTs and count by SUT
    for session in sessions:
        sut_name = session.sut_name
        if sut_name not in suts:
            suts[sut_name] = 0
        suts[sut_name] += 1

        # Count tag occurrences
        for key, value in session.session_tags.items():
            tag = f"{key}={value}"
            if tag not in tags:
                tags[tag] = 0
            tags[tag] += 1

        # Count test outcomes
        for test in session.test_results:
            total_tests += 1
            outcome = test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
            outcome_totals[outcome] = outcome_totals.get(outcome, 0) + 1

    # Calculate trends (compare first half with second half)
    mid_point = len(sessions) // 2
    if mid_point > 0:
        first_half = sessions[:mid_point]
        second_half = sessions[mid_point:]

        first_pass_rate = sum(
            sum(1 for t in s.test_results if t.outcome == TestOutcome.PASSED) for s in first_half
        ) / max(1, sum(len(s.test_results) for s in first_half))

        second_pass_rate = sum(
            sum(1 for t in s.test_results if t.outcome == TestOutcome.PASSED) for s in second_half
        ) / max(1, sum(len(s.test_results) for s in second_half))

        trend = {
            "pass_rate_change": second_pass_rate - first_pass_rate,
            "direction": "improving"
            if second_pass_rate > first_pass_rate
            else "declining"
            if second_pass_rate < first_pass_rate
            else "stable",
        }
    else:
        trend = {"pass_rate_change": 0, "direction": "stable"}

    # Build statistics response
    stats = {
        "session_count": len(sessions),
        "sut_count": len(suts),
        "suts": suts,
        "common_tags": dict(sorted(tags.items(), key=lambda x: x[1], reverse=True)[:10]),
        "test_stats": {
            "total": total_tests,
            **outcome_totals,
            "pass_rate": outcome_totals.get(TestOutcome.PASSED.value, 0) / max(1, total_tests) * 100,
        },
        "trend": trend,
        "first_session_date": format_datetime(min(s.session_start_time for s in sessions)),
        "last_session_date": format_datetime(max(s.session_start_time for s in sessions)),
    }

    return JSONResponse(content={"data": stats})


@router.get("/suts")
async def get_suts() -> JSONResponse:
    """Get list of available SUTs."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Get unique SUTs and their counts
    suts = {}
    for session in sessions:
        sut_name = session.sut_name
        if sut_name not in suts:
            suts[sut_name] = {"count": 0, "last_run": None, "first_run": None, "tags": set()}

        suts[sut_name]["count"] += 1

        # Track first and last run times
        current_time = session.session_start_time
        if suts[sut_name]["last_run"] is None or current_time > suts[sut_name]["last_run"]:
            suts[sut_name]["last_run"] = current_time

        if suts[sut_name]["first_run"] is None or current_time < suts[sut_name]["first_run"]:
            suts[sut_name]["first_run"] = current_time

        # Track unique tags
        for key, value in session.session_tags.items():
            suts[sut_name]["tags"].add(f"{key}={value}")

    # Format for response
    sut_list = []
    for name, info in suts.items():
        sut_list.append(
            {
                "name": name,
                "session_count": info["count"],
                "last_run": format_datetime(info["last_run"]),
                "first_run": format_datetime(info["first_run"]),
                "tags": list(info["tags"]),
            }
        )

    # Sort by session count
    sut_list.sort(key=lambda x: x["session_count"], reverse=True)

    return JSONResponse(content={"data": sut_list, "meta": {"total": len(sut_list)}})
