#!/usr/bin/env python3
"""
Script to modify the default.json file to make backfilled entries have a random number of tests
that fluctuate ±15% from the maximum (around 81).
"""

import json
import random
import re
from pathlib import Path

# Path to the default.json file
DEFAULT_JSON_PATH = Path.home() / ".pytest_insight" / "default.json"

# Maximum number of tests (around 81)
MAX_TESTS = 81

# Fluctuation percentage (±15%)
FLUCTUATION_PERCENTAGE = 15

def is_backfilled_session(session):
    """Check if a session is a backfilled session."""
    # Check if the session ID contains 'backfill' or the SUT name ends with '-backfill'
    return (
        'backfill' in session.get('session_id', '').lower() or
        session.get('sut_name', '').lower().endswith('-backfill')
    )

def modify_default_json():
    """Modify the default.json file to have random test counts for backfilled entries."""
    # Read the default.json file
    with open(DEFAULT_JSON_PATH, 'r') as f:
        data = json.load(f)
    
    # Get all session IDs to ensure uniqueness
    session_ids = {session['session_id'] for session in data['sessions']}
    
    # Count the number of backfilled sessions modified
    modified_count = 0
    
    # Iterate through the sessions
    for session in data['sessions']:
        if is_backfilled_session(session):
            # Calculate the random number of tests to have
            min_tests = int(MAX_TESTS * (100 - FLUCTUATION_PERCENTAGE) / 100)
            max_tests = int(MAX_TESTS * (100 + FLUCTUATION_PERCENTAGE) / 100)
            num_tests = random.randint(min_tests, max_tests)
            
            # Get the existing test results
            existing_tests = session.get('test_results', [])
            
            # If we already have enough tests, randomly select from them
            if len(existing_tests) >= num_tests:
                session['test_results'] = random.sample(existing_tests, num_tests)
            else:
                # We need to add more tests
                # First, let's keep all existing tests
                new_tests = existing_tests.copy()
                
                # Then, let's duplicate some of the existing tests with modified nodeids
                while len(new_tests) < num_tests:
                    # Select a random test to duplicate
                    template_test = random.choice(existing_tests)
                    
                    # Create a copy of the test
                    new_test = template_test.copy()
                    
                    # Modify the nodeid to make it unique
                    original_nodeid = new_test['nodeid']
                    
                    # Extract parts of the nodeid
                    match = re.match(r'(.+)::(.+)', original_nodeid)
                    if match:
                        file_part, test_part = match.groups()
                        
                        # Create a new unique test name
                        new_test_part = f"{test_part}_var{len(new_tests)}"
                        new_nodeid = f"{file_part}::{new_test_part}"
                        
                        # Update the nodeid
                        new_test['nodeid'] = new_nodeid
                        
                        # Randomly adjust the duration
                        if 'duration' in new_test:
                            duration_factor = random.uniform(0.8, 1.2)  # ±20% duration variation
                            new_test['duration'] = new_test['duration'] * duration_factor
                        
                        # Randomly change the outcome (10% chance of failure)
                        if random.random() < 0.1:
                            new_test['outcome'] = 'failed'
                            new_test['longreprtext'] = f"AssertionError: Random failure for test {new_test_part}"
                        
                        # Add the new test
                        new_tests.append(new_test)
                
                # Update the session with the new tests
                session['test_results'] = new_tests
            
            modified_count += 1
    
    # Write the modified data back to the file
    with open(DEFAULT_JSON_PATH, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Modified {modified_count} backfilled sessions in {DEFAULT_JSON_PATH}")
    print(f"Each session now has between {min_tests} and {max_tests} tests (±{FLUCTUATION_PERCENTAGE}% of {MAX_TESTS})")

if __name__ == "__main__":
    # Make a backup of the original file
    backup_path = DEFAULT_JSON_PATH.with_suffix('.json.bak')
    with open(DEFAULT_JSON_PATH, 'r') as src, open(backup_path, 'w') as dst:
        dst.write(src.read())
    print(f"Created backup at {backup_path}")
    
    # Modify the file
    modify_default_json()
