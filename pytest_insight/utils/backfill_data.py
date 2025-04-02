


#!/usr/bin/env python3
"""
Back-fill pytest-insight data with a month's worth of test sessions.
This script reads the existing practice.json file, generates additional test sessions
with dates going back a month, and writes the combined data back to the file.

The script will:
1. Read your existing practice.json file
2. Generate new test sessions with dates going back 30 days from your earliest existing session
3. Vary the SUT names between "sample-app", "api-service", "web-frontend", etc.
4. Create realistic variations in test outcomes (75% pass rate, 15% failure rate, etc.)
5. Add the new sessions to your practice.json file
6. This will give you a rich dataset spanning a month, which you can use to analyze trends over time.
The script preserves your existing data while adding new historical data before it.
"""

import copy
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# Path to the practice.json file
PRACTICE_JSON_PATH = Path.home() / ".pytest_insight" / "practice.json"

# Alternative SUT names to use
SUT_NAMES = [
    "sample-app",
    "api-service",
    "web-frontend",
    "data-processor",
    "auth-service",
    "mobile-app"
]

# Test outcome probabilities (to create realistic variation)
OUTCOME_PROBABILITIES = {
    "passed": 0.75,  # 75% pass rate
    "failed": 0.15,  # 15% failure rate
    "skipped": 0.05, # 5% skip rate
    "xfailed": 0.02, # 2% expected failure
    "xpassed": 0.02, # 2% unexpected pass
    "error": 0.01    # 1% error rate
}

def load_json_data():
    """Load the existing practice.json data."""
    try:
        with open(PRACTICE_JSON_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Could not load {PRACTICE_JSON_PATH}. Starting with empty data.")
        return []

def save_json_data(data):
    """Save the updated data back to practice.json."""
    # Create parent directory if it doesn't exist
    PRACTICE_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(PRACTICE_JSON_PATH, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(data)} test sessions to {PRACTICE_JSON_PATH}")

def generate_session_id(sut_name, date, index):
    """Generate a unique session ID."""
    date_str = date.strftime("%Y%m%d")
    return f"{sut_name.lower()}-{date_str}-{index}"

def modify_test_result(test_result):
    """Modify a test result with a new outcome and timing."""
    # Randomly select a new outcome based on probabilities
    outcome = random.choices(
        list(OUTCOME_PROBABILITIES.keys()),
        weights=list(OUTCOME_PROBABILITIES.values())
    )[0]

    # Update the outcome
    test_result["outcome"] = outcome

    # Adjust duration slightly (±20%)
    original_duration = test_result["duration"]
    variation = random.uniform(0.8, 1.2)
    new_duration = original_duration * variation
    test_result["duration"] = new_duration

    # If the test failed or had an error, add some error text
    if outcome in ["failed", "error"]:
        test_result["longreprtext"] = f"Sample error for {test_result['nodeid']}"
    else:
        test_result["longreprtext"] = ""

    return test_result

def create_session_for_date(template_session, target_date, index):
    """Create a new session for a specific date based on a template session."""
    # Create a deep copy of the template
    new_session = copy.deepcopy(template_session)

    # Update the SUT name (occasionally)
    if random.random() < 0.3:  # 30% chance to change SUT name
        new_session["sut_name"] = random.choice(SUT_NAMES)

    # Update session ID
    new_session["session_id"] = generate_session_id(new_session["sut_name"], target_date, index)

    # Set the start time to the target date with a random hour
    hour = random.randint(8, 18)  # Business hours
    minute = random.randint(0, 59)
    start_time = target_date.replace(hour=hour, minute=minute)
    new_session["session_start_time"] = start_time.isoformat()

    # Calculate a realistic session duration (5-30 minutes)
    session_duration = random.uniform(300, 1800)  # seconds
    stop_time = start_time + timedelta(seconds=session_duration)
    new_session["session_stop_time"] = stop_time.isoformat()
    new_session["session_duration"] = session_duration

    # Update each test result
    for test_result in new_session["test_results"]:
        # Modify the test result with new outcome and timing
        modify_test_result(test_result)

        # Update test start and stop times relative to session start
        test_start_offset = random.uniform(0, session_duration * 0.8)  # Start within first 80% of session
        test_start = start_time + timedelta(seconds=test_start_offset)
        test_result["start_time"] = test_start.isoformat()

        test_stop = test_start + timedelta(seconds=test_result["duration"])
        test_result["stop_time"] = test_stop.isoformat()

    return new_session

def backfill_data(existing_data, days=30, sessions_per_day=3):
    """Generate back-filled data for the specified number of days."""
    # If no existing data, we can't generate more
    if not existing_data:
        print("No existing data to use as a template.")
        return []

    # Use the first session as a template
    template_session = existing_data[0]

    # Find the earliest date in the existing data
    earliest_date = min(
        datetime.fromisoformat(session["session_start_time"])
        for session in existing_data
    ).date()

    # Generate new data starting from one day before the earliest date
    start_date = earliest_date - timedelta(days=days)
    end_date = earliest_date - timedelta(days=1)

    new_data = []
    current_date = start_date

    while current_date <= end_date:
        # Generate 1-5 sessions for this day
        daily_sessions = random.randint(1, sessions_per_day)

        for i in range(daily_sessions):
            new_session = create_session_for_date(template_session, datetime.combine(current_date, datetime.min.time()), i)
            new_data.append(new_session)

        current_date += timedelta(days=1)

    print(f"Generated {len(new_data)} new test sessions spanning {days} days")
    return new_data

def main():
    """Main function to back-fill the practice.json file."""
    print(f"Reading data from {PRACTICE_JSON_PATH}")
    existing_data = load_json_data()
    print(f"Found {len(existing_data)} existing test sessions")

    # Generate new data
    new_data = backfill_data(existing_data)

    # Combine data (new data first, then existing data)
    combined_data = new_data + existing_data

    # Save the combined data
    save_json_data(combined_data)

if __name__ == "__main__":
    main()
