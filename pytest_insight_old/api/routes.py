from datetime import datetime, timedelta
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


def calculate_test_stability(tests) -> Dict:
    """Calculate stability metrics for a set of tests."""
    test_map = {}

    # Group by nodeid
    for test in tests:
        nodeid = test["nodeid"]
        if nodeid not in test_map:
            test_map[nodeid] = []
        test_map[nodeid].append(test)

    # Calculate stability metrics
    stability_data = []
    for nodeid, occurrences in test_map.items():
        if len(occurrences) < 2:
            continue  # Need at least 2 occurrences to calculate stability

        outcomes = {}
        for test in occurrences:
            outcome = test["outcome"]
            if outcome not in outcomes:
                outcomes[outcome] = 0
            outcomes[outcome] += 1

        # Calculate stability score (0-100)
        total = len(occurrences)
        dominant_outcome_count = max(outcomes.values())
        stability_score = (dominant_outcome_count / total) * 100

        # Calculate duration stability
        durations = [test["duration"] for test in occurrences]
        avg_duration = sum(durations) / len(durations)
        duration_variance = sum((d - avg_duration) ** 2 for d in durations) / len(durations)
        duration_stability = 100 - min(100, (duration_variance * 10))  # Higher variance = lower stability

        stability_data.append(
            {
                "nodeid": nodeid,
                "runs": total,
                "outcomes": outcomes,
                "stability_score": stability_score,
                "avg_duration": avg_duration,
                "duration_stability": duration_stability,
                "overall_stability": (stability_score + duration_stability) / 2,
            }
        )

    # Sort by stability (least stable first)
    stability_data.sort(key=lambda x: x["overall_stability"])

    return stability_data


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


@router.get("/analytics/trends")
async def get_test_trends(
    sut: str = Query(..., description="Filter by SUT name"),
    days: int = Query(30, description="Number of days of history to analyze"),
    test_pattern: Optional[str] = Query(None, description="Filter tests by pattern"),
) -> JSONResponse:
    """Get trend analysis for tests over time."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter by SUT and time range
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_sessions = [s for s in sessions if s.sut_name == sut and s.session_start_time >= cutoff_date]

    # Sort sessions by time (oldest first for trending)
    filtered_sessions.sort(key=lambda x: x.session_start_time)

    # Apply test pattern if provided
    if test_pattern:
        for session in filtered_sessions:
            session.test_results = [
                t for t in session.test_results if test_pattern in t.nodeid or test_pattern == t.nodeid
            ]

    # Group sessions by time period (day, week depending on range)
    time_groups = {}
    for session in filtered_sessions:
        # Use date as key for grouping
        date_key = session.session_start_time.date().isoformat()
        if date_key not in time_groups:
            time_groups[date_key] = []
        time_groups[date_key].append(session)

    # Calculate metrics for each time period
    trend_data = []
    test_metrics = {}  # Track metrics by test nodeid

    for date_key, date_sessions in time_groups.items():
        # Aggregate test results for this date
        date_outcomes = {outcome.value: 0 for outcome in TestOutcome}
        date_tests = {}

        for session in date_sessions:
            for test in session.test_results:
                test_id = test.nodeid
                outcome = test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
                date_outcomes[outcome] = date_outcomes.get(outcome, 0) + 1

                # Track individual test metrics
                if test_id not in date_tests:
                    date_tests[test_id] = {"count": 0, "pass_count": 0, "fail_count": 0, "skip_count": 0, "duration": 0}

                date_tests[test_id]["count"] += 1
                if outcome == TestOutcome.PASSED.value:
                    date_tests[test_id]["pass_count"] += 1
                elif outcome == TestOutcome.FAILED.value:
                    date_tests[test_id]["fail_count"] += 1
                elif outcome == TestOutcome.SKIPPED.value:
                    date_tests[test_id]["skip_count"] += 1

                date_tests[test_id]["duration"] += test.duration

        # Update global test metrics
        for test_id, metrics in date_tests.items():
            if test_id not in test_metrics:
                test_metrics[test_id] = {"history": []}

            test_metrics[test_id]["history"].append(
                {
                    "date": date_key,
                    "pass_rate": metrics["pass_count"] / max(metrics["count"], 1) * 100,
                    "avg_duration": metrics["duration"] / max(metrics["count"], 1),
                    "run_count": metrics["count"],
                }
            )

        total_tests = sum(date_outcomes.values())
        trend_data.append(
            {
                "date": date_key,
                "session_count": len(date_sessions),
                "test_count": total_tests,
                "outcomes": date_outcomes,
                "pass_rate": date_outcomes.get(TestOutcome.PASSED.value, 0) / max(total_tests, 1) * 100,
                "avg_duration": sum(s.session_duration for s in date_sessions) / len(date_sessions)
                if date_sessions
                else 0,
            }
        )

    # Find tests with most significant changes
    changed_tests = []
    for test_id, data in test_metrics.items():
        if len(data["history"]) > 1:
            # Calculate rate of change
            first = data["history"][0]
            last = data["history"][-1]
            pass_rate_change = last["pass_rate"] - first["pass_rate"]
            duration_change = last["avg_duration"] - first["avg_duration"]

            if abs(pass_rate_change) > 5 or abs(duration_change) > 0.5:
                changed_tests.append(
                    {
                        "nodeid": test_id,
                        "pass_rate_change": pass_rate_change,
                        "duration_change": duration_change,
                        "history": data["history"],
                    }
                )

    # Sort by largest change
    changed_tests.sort(key=lambda x: abs(x["pass_rate_change"]), reverse=True)

    return JSONResponse(
        content={
            "data": {
                "trends": trend_data,
                "significant_changes": changed_tests[:20],  # Top 20 most changed tests
            },
            "meta": {"sut": sut, "days": days, "test_pattern": test_pattern, "session_count": len(filtered_sessions)},
        }
    )


@router.get("/analytics/test/{test_id}")
async def get_test_details(
    test_id: str,
    sut: Optional[str] = Query(None, description="Filter by SUT name"),
    limit: int = Query(50, description="Maximum number of test occurrences to return"),
) -> JSONResponse:
    """Get detailed history for a specific test."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter by SUT if provided
    if sut:
        sessions = [s for s in sessions if s.sut_name == sut]

    # Sort sessions by time (newest first)
    sessions.sort(key=lambda x: x.session_start_time, reverse=True)

    # Extract all occurrences of the test
    test_occurrences = []
    for session in sessions:
        for test in session.test_results:
            if test.nodeid == test_id:
                test_occurrences.append(
                    {
                        "session_id": session.session_id,
                        "sut": session.sut_name,
                        "start_time": format_datetime(test.start_time),
                        "duration": test.duration,
                        "outcome": test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome),
                        "has_warning": test.has_warning,
                    }
                )

    # Calculate statistics
    total = len(test_occurrences)
    if total > 0:
        outcomes = {}
        for occurrence in test_occurrences:
            outcome = occurrence["outcome"]
            if outcome not in outcomes:
                outcomes[outcome] = 0
            outcomes[outcome] += 1

        # Calculate pass rate and other metrics
        pass_count = outcomes.get(TestOutcome.PASSED.value, 0)
        pass_rate = pass_count / total * 100 if total > 0 else 0

        # Calculate duration statistics
        durations = [o["duration"] for o in test_occurrences]
        avg_duration = sum(durations) / len(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        max_duration = max(durations) if durations else 0

        # Detect if test is flaky
        is_flaky = len(outcomes) > 1 and pass_count > 0 and pass_count < total

        # Build test history with limited entries
        test_history = test_occurrences[:limit]

        statistics = {
            "total_runs": total,
            "outcomes": outcomes,
            "pass_rate": pass_rate,
            "avg_duration": avg_duration,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "is_flaky": is_flaky,
        }
    else:
        statistics = {
            "total_runs": 0,
            "outcomes": {},
            "pass_rate": 0,
            "avg_duration": 0,
            "min_duration": 0,
            "max_duration": 0,
            "is_flaky": False,
        }
        test_history = []

    return JSONResponse(
        content={
            "data": {"nodeid": test_id, "statistics": statistics, "history": test_history},
            "meta": {"sut": sut, "total_occurrences": total, "shown_occurrences": min(total, limit)},
        }
    )


@router.get("/analytics/stacked")
async def get_stacked_analytics(
    sut: str = Query(..., description="Filter by SUT name"),
    stack_by: str = Query("folder", description="Group results by: folder, module, class, day, outcome"),
    days: int = Query(30, description="Number of days of history to analyze"),
) -> JSONResponse:
    """Get stacked analytics to visualize test patterns."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter by SUT and time range
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_sessions = [s for s in sessions if s.sut_name == sut and s.session_start_time >= cutoff_date]

    # Sort sessions by time (newest first)
    filtered_sessions.sort(key=lambda x: x.session_start_time, reverse=True)

    # Extract all test results
    all_tests = []
    for session in filtered_sessions:
        for test in session.test_results:
            all_tests.append(
                {
                    "nodeid": test.nodeid,
                    "outcome": test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome),
                    "duration": test.duration,
                    "session_id": session.session_id,
                    "session_date": session.session_start_time.date().isoformat(),
                }
            )

    # Group tests based on stack_by parameter
    grouped_tests = {}

    if stack_by == "folder":
        # Group by top-level folder/directory
        for test in all_tests:
            nodeid = test["nodeid"]
            parts = nodeid.split("/")
            if len(parts) > 1:
                folder = parts[0]
            else:
                folder = "root"

            if folder not in grouped_tests:
                grouped_tests[folder] = []
            grouped_tests[folder].append(test)

    elif stack_by == "module":
        # Group by module (filename)
        for test in all_tests:
            nodeid = test["nodeid"]
            module = nodeid.split("::")[0]

            if module not in grouped_tests:
                grouped_tests[module] = []
            grouped_tests[module].append(test)

    elif stack_by == "class":
        # Group by test class if available
        for test in all_tests:
            nodeid = test["nodeid"]
            parts = nodeid.split("::")

            if len(parts) > 1 and parts[1].startswith("Test"):
                class_name = parts[1]
            else:
                class_name = "functions"  # Non-class tests

            if class_name not in grouped_tests:
                grouped_tests[class_name] = []
            grouped_tests[class_name].append(test)

    elif stack_by == "day":
        # Group by day
        for test in all_tests:
            day = test["session_date"]

            if day not in grouped_tests:
                grouped_tests[day] = []
            grouped_tests[day].append(test)

    elif stack_by == "outcome":
        # Group by outcome
        for test in all_tests:
            outcome = test["outcome"]

            if outcome not in grouped_tests:
                grouped_tests[outcome] = []
            grouped_tests[outcome].append(test)

    # Calculate metrics for each group
    stacked_data = []
    for group_name, tests in grouped_tests.items():
        # Count tests by outcome
        outcomes = {}
        for test in tests:
            outcome = test["outcome"]
            if outcome not in outcomes:
                outcomes[outcome] = 0
            outcomes[outcome] += 1

        # Calculate pass rate and other metrics
        total = len(tests)
        pass_count = outcomes.get(TestOutcome.PASSED.value, 0)
        pass_rate = pass_count / total * 100 if total > 0 else 0

        # Calculate average duration
        avg_duration = sum(test["duration"] for test in tests) / total if total > 0 else 0

        stacked_data.append(
            {
                "name": group_name,
                "test_count": total,
                "outcomes": outcomes,
                "pass_rate": pass_rate,
                "avg_duration": avg_duration,
            }
        )

    # Sort by test count (largest first)
    stacked_data.sort(key=lambda x: x["test_count"], reverse=True)

    return JSONResponse(
        content={
            "data": stacked_data,
            "meta": {
                "sut": sut,
                "stack_by": stack_by,
                "days": days,
                "total_tests": len(all_tests),
                "total_groups": len(stacked_data),
            },
        }
    )


@router.post("/analytics/filter-complex")
async def filter_tests_complex(request: Request) -> JSONResponse:
    """Apply complex filtering and aggregation to test results."""
    # Parse request JSON
    data = await request.json()

    # Extract filter criteria
    sut = data.get("sut")
    test_patterns = data.get("test_patterns", [])
    outcomes = data.get("outcomes", [])  # e.g. ["passed", "failed"]
    tags = data.get("tags", {})  # e.g. {"environment": "test"}
    min_duration = data.get("min_duration")
    max_duration = data.get("max_duration")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    group_by = data.get("group_by")  # How to group results (optional)

    # Convert date strings to datetime
    if start_date:
        start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    if end_date:
        end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Apply SUT filter
    if sut:
        sessions = [s for s in sessions if s.sut_name == sut]

    # Apply date filters
    if start_date:
        sessions = [s for s in sessions if s.session_start_time >= start_date]
    if end_date:
        sessions = [s for s in sessions if s.session_start_time <= end_date]

    # Apply tag filters
    for key, value in tags.items():
        sessions = [s for s in sessions if s.session_tags.get(key) == value]

    # Extract matching tests from all sessions
    matching_tests = []
    for session in sessions:
        for test in session.test_results:
            # Apply test pattern filters
            pattern_match = not test_patterns  # If no patterns, all tests match
            for pattern in test_patterns:
                if pattern in test.nodeid:
                    pattern_match = True
                    break

            if not pattern_match:
                continue

            # Apply outcome filters
            outcome = test.outcome.value if hasattr(test.outcome, "value") else str(test.outcome)
            if outcomes and outcome not in outcomes:
                continue

            # Apply duration filters
            if min_duration is not None and test.duration < min_duration:
                continue
            if max_duration is not None and test.duration > max_duration:
                continue

            # Test matches all filters, add to results
            matching_tests.append(
                {
                    "nodeid": test.nodeid,
                    "outcome": outcome,
                    "duration": test.duration,
                    "session_id": session.session_id,
                    "sut": session.sut_name,
                    "start_time": format_datetime(test.start_time),
                    "has_warning": test.has_warning,
                }
            )

    # Group results if requested
    if group_by:
        grouped_results = {}

        if group_by == "outcome":
            # Group by test outcome
            for test in matching_tests:
                outcome = test["outcome"]
                if outcome not in grouped_results:
                    grouped_results[outcome] = []
                grouped_results[outcome].append(test)

        elif group_by == "module":
            # Group by module file
            for test in matching_tests:
                module = test["nodeid"].split("::")[0]
                if module not in grouped_results:
                    grouped_results[module] = []
                grouped_results[module].append(test)

        elif group_by == "session":
            # Group by test session
            for test in matching_tests:
                session_id = test["session_id"]
                if session_id not in grouped_results:
                    grouped_results[session_id] = []
                grouped_results[session_id].append(test)

        # Convert groups to list format
        result_data = [
            {"group": group_key, "tests": tests, "count": len(tests)} for group_key, tests in grouped_results.items()
        ]

        # Sort groups by count (largest first)
        result_data.sort(key=lambda x: x["count"], reverse=True)
    else:
        # No grouping, return flat list
        result_data = matching_tests

    return JSONResponse(
        content={
            "data": result_data,
            "meta": {
                "total_matches": len(matching_tests),
                "filters": {
                    "sut": sut,
                    "test_patterns": test_patterns,
                    "outcomes": outcomes,
                    "tags": tags,
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                    "start_date": data.get("start_date"),
                    "end_date": data.get("end_date"),
                },
            },
        }
    )
