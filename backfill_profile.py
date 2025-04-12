#!/usr/bin/env python
"""
Backfill script for pytest-insight profiles.

This script analyzes an existing profile, identifies dates with missing data,
and generates synthetic test sessions to fill in those gaps.
"""

import os
import sys
import uuid
import random
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Set, Optional

from pytest_insight.core.storage import get_storage_instance, get_profile_manager
from pytest_insight.core.models import TestSession, TestResult, TestOutcome, RerunTestGroup


def analyze_profile(profile_name: str) -> Dict[str, Any]:
    """
    Analyze a profile to understand its structure and identify missing dates.
    
    Args:
        profile_name: Name of the profile to analyze
        
    Returns:
        Dictionary with analysis results
    """
    print(f"Analyzing profile '{profile_name}'...")
    
    # Get storage instance for the profile
    storage = get_storage_instance(profile_name)
    
    # Load existing sessions
    sessions = storage.load_sessions()
    print(f"Found {len(sessions)} existing sessions")
    
    if not sessions:
        print("No sessions found in profile. Cannot determine pattern for backfilling.")
        sys.exit(1)
    
    # Extract key information
    sut_names = set()
    dates = set()
    test_counts = []
    pass_rates = []
    durations = []
    
    for session in sessions:
        # Get SUT name
        if hasattr(session, "sut_name") and session.sut_name:
            sut_names.add(session.sut_name)
        
        # Get session date
        if hasattr(session, "session_start_time") and session.session_start_time:
            session_date = session.session_start_time.date()
            dates.add(session_date)
            
            # Get test counts and pass rates
            if hasattr(session, "test_results") and session.test_results:
                test_counts.append(len(session.test_results))
                
                # Calculate pass rate
                passed = sum(1 for r in session.test_results if r.outcome == TestOutcome.PASSED)
                if session.test_results:
                    pass_rates.append(passed / len(session.test_results))
                
                # Get session duration
                if hasattr(session, "session_start_time") and hasattr(session, "session_stop_time"):
                    if session.session_start_time and session.session_stop_time:
                        duration = (session.session_stop_time - session.session_start_time).total_seconds()
                        durations.append(duration)
    
    # Calculate statistics
    avg_test_count = sum(test_counts) / len(test_counts) if test_counts else 0
    avg_pass_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Identify date range and missing dates
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        all_dates = set(min_date + timedelta(days=i) for i in range((max_date - min_date).days + 1))
        missing_dates = all_dates - dates
    else:
        min_date = max_date = datetime.now().date()
        missing_dates = set()
    
    return {
        "profile_name": profile_name,
        "session_count": len(sessions),
        "sut_names": list(sut_names),
        "min_date": min_date,
        "max_date": max_date,
        "existing_dates": sorted(list(dates)),
        "missing_dates": sorted(list(missing_dates)),
        "avg_test_count": avg_test_count,
        "avg_pass_rate": avg_pass_rate,
        "avg_duration": avg_duration,
        "sample_session": sessions[0] if sessions else None
    }


def generate_synthetic_session(
    date_to_fill: date,
    analysis: Dict[str, Any],
    variation_factor: float = 0.2
) -> TestSession:
    """
    Generate a synthetic test session for a specific date based on analysis of existing data.
    
    Args:
        date_to_fill: Date to generate session for
        analysis: Analysis results from analyze_profile
        variation_factor: How much to vary metrics from the average (0.0-1.0)
        
    Returns:
        A synthetic TestSession object
    """
    # Get a sample SUT name or use a default
    sut_name = random.choice(analysis["sut_names"]) if analysis["sut_names"] else "unknown-sut"
    
    # Add a suffix to indicate this is synthetic data
    sut_name = f"{sut_name}-backfill"
    
    # Generate session start and end times
    # Assume tests typically run in the morning between 8am and 11am
    hour = random.randint(8, 11)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    
    session_start_time = datetime.combine(
        date_to_fill, 
        datetime.min.time()
    ).replace(hour=hour, minute=minute, second=second)
    
    # Vary the average duration by the variation factor
    duration_variation = random.uniform(
        1.0 - variation_factor,
        1.0 + variation_factor
    )
    duration_seconds = analysis["avg_duration"] * duration_variation
    
    session_stop_time = session_start_time + timedelta(seconds=duration_seconds)
    
    # Determine number of tests with some variation
    test_count_variation = random.uniform(
        1.0 - variation_factor,
        1.0 + variation_factor
    )
    test_count = int(analysis["avg_test_count"] * test_count_variation)
    test_count = max(1, test_count)  # Ensure at least one test
    
    # Determine pass rate with some variation
    pass_rate_variation = random.uniform(
        1.0 - variation_factor/2,  # Less variation for pass rate
        1.0 + variation_factor/2
    )
    pass_rate = analysis["avg_pass_rate"] * pass_rate_variation
    pass_rate = max(0.0, min(1.0, pass_rate))  # Ensure between 0 and 1
    
    # Generate test results
    test_results = []
    for i in range(test_count):
        # Determine if this test passed based on the pass rate
        outcome = TestOutcome.PASSED if random.random() < pass_rate else TestOutcome.FAILED
        
        # Generate a test duration between 0.1 and 5 seconds
        test_duration = random.uniform(0.1, 5.0)
        
        # Create a test result
        test_result = TestResult(
            nodeid=f"test_module.py::test_function_{i}",
            outcome=outcome,
            start_time=session_start_time + timedelta(seconds=i*test_duration),
            duration=test_duration,
            caplog="",
            capstderr="",
            capstdout="",
            longreprtext="" if outcome == TestOutcome.PASSED else "AssertionError: Test failed",
            has_warning=random.random() < 0.1,  # 10% chance of warning
        )
        
        test_results.append(test_result)
    
    # Generate a unique session ID
    session_id = (
        f"{sut_name}-{session_start_time.strftime('%Y%m%d-%H%M%S')}-"
        f"{str(uuid.uuid4())[:8]}"
    ).lower()
    
    # Create the session
    session = TestSession(
        session_id=session_id,
        sut_name=sut_name,
        session_start_time=session_start_time,
        session_stop_time=session_stop_time,
        test_results=test_results,
        rerun_test_groups=[],
        session_tags={
            "platform": "darwin",
            "python_version": "3.9.16",
            "environment": "test",
            "synthetic": "true",
        },
        testing_system={
            "name": "backfill-script",
            "type": "synthetic",
            "platform": "darwin",
            "python_version": "3.9.16",
            "pytest_version": "8.3.4",
            "plugins": ["pytest-insight"],
        },
    )
    
    return session


def backfill_profile(
    profile_name: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    dry_run: bool = False
) -> None:
    """
    Backfill a profile with synthetic data for missing dates.
    
    Args:
        profile_name: Name of the profile to backfill
        start_date: Optional start date for backfilling (defaults to earliest date in profile)
        end_date: Optional end date for backfilling (defaults to latest date in profile)
        dry_run: If True, don't actually save the data
    """
    # Analyze the profile
    analysis = analyze_profile(profile_name)
    
    # Determine date range
    if not start_date:
        start_date = analysis["min_date"]
    if not end_date:
        end_date = analysis["max_date"]
    
    # Get missing dates within the specified range
    all_dates = set(start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1))
    existing_dates = set(d for d in analysis["existing_dates"] if start_date <= d <= end_date)
    missing_dates = sorted(list(all_dates - existing_dates))
    
    print(f"Found {len(missing_dates)} missing dates between {start_date} and {end_date}")
    
    if not missing_dates:
        print("No missing dates to backfill.")
        return
    
    # Get storage instance
    storage = get_storage_instance(profile_name)
    
    # Generate and save sessions for missing dates
    new_sessions = []
    for missing_date in missing_dates:
        print(f"Generating session for {missing_date}...")
        session = generate_synthetic_session(missing_date, analysis)
        new_sessions.append(session)
        
        print(f"  Session ID: {session.session_id}")
        print(f"  SUT Name: {session.sut_name}")
        print(f"  Tests: {len(session.test_results)}")
        print(f"  Pass Rate: {sum(1 for r in session.test_results if r.outcome == TestOutcome.PASSED) / len(session.test_results):.2f}")
    
    if dry_run:
        print(f"Dry run - would have added {len(new_sessions)} sessions")
    else:
        # Save the sessions
        for session in new_sessions:
            try:
                storage.save_session(session)
                print(f"Saved session {session.session_id}")
            except Exception as e:
                print(f"Error saving session: {e}")
        
        print(f"Added {len(new_sessions)} sessions to profile '{profile_name}'")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill pytest-insight profiles with synthetic data")
    parser.add_argument("profile", help="Name of the profile to backfill")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually save data")
    
    args = parser.parse_args()
    
    # Parse dates if provided
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date() if args.start_date else None
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else None
    
    # Run backfill
    backfill_profile(args.profile, start_date, end_date, args.dry_run)
