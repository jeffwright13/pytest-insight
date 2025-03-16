"""Interactive playground for experimenting with pytest-insight API features.

This module demonstrates the three core operations in an interactive way:
1. Query - Finding and filtering test sessions
2. Compare - Comparing between versions/times
3. Analyze - Extracting insights and metrics

Run each section individually to explore the API features.
"""

import json
from pathlib import Path

from pytest_insight import InsightAPI, get_storage_instance
from pytest_insight.db_generator import PracticeDataGenerator


def setup_environment():
    """Set up the environment and generate test data."""
    try:
        print("=== Setting Up Environment ===")

        # Set up storage path
        storage_path = Path.home() / ".pytest_insight" / "practice.json"
        print(f"Storage path: {storage_path}")

        # Initialize storage and API
        storage = get_storage_instance(file_path=str(storage_path))
        api = InsightAPI(storage=storage)

        # Generate fresh practice data
        print("\nGenerating practice data...")

        # First clear any existing data
        storage.clear_sessions()

        # Generate new data with specific test categories
        generator = PracticeDataGenerator(
            target_path=storage_path,
            days=30,  # 30 days of history
            targets_per_base=3,  # 3 target sessions per base
            pass_rate=0.75,  # 75% pass rate
            flaky_rate=0.15,  # 15% flaky tests
            warning_rate=0.10,  # 10% warning rate
            test_categories=["api", "integration"],  # Focus on API and integration tests
            sut_filter="api-",  # Only generate API service data
        )
        generator.generate_practice_data()

        # Fix the data format - convert from {sessions: [...]} to [...]
        with open(storage_path) as f:
            data = json.load(f)
            sessions = data["sessions"]

        with open(storage_path, "w") as f:
            json.dump(sessions, f, indent=2)

        print(f" Data saved to: {storage_path}")
        return storage, api

    except Exception as e:
        print(f" Setup failed: {str(e)}")
        return None, None


def demo_query(api):
    """Demonstrate the Query operation with two-level filtering."""
    try:
        print("\n=== Query Operation ===")

        # 1. Session-level filtering
        print("\n1. Session-level filtering:")
        sessions = (
            api.query()
            .for_sut("api-service")  # Filter by SUT
            .in_last_days(30)  # Time range filter - increased to match our data generation
            .execute()
        )
        print(f" Found {len(sessions)} sessions for api-service in last 30 days")

        if sessions:
            session = sessions[0]
            print("\nExample session context:")
            print(f"Session ID: {session.session_id}")
            print(f"Start Time: {session.session_start_time}")
            print(f"Total Tests: {len(session.test_results)}")

        # 2. Test-level filtering with context preservation
        print("\n2. Test-level filtering (preserving session context):")
        sessions_with_slow_tests = (
            api.query()
            .for_sut("api-service")
            .filter_by_test()  # Enter test filtering context
            .with_duration(5.0, None)  # Find slow tests (>5s)
            .with_outcome("failed")  # That also failed
            .apply()  # Back to session context
            .execute()
        )
        print(f" Found {len(sessions_with_slow_tests)} sessions with slow, failed tests")

        # Demonstrate session context preservation
        if sessions_with_slow_tests:
            session = sessions_with_slow_tests[0]
            print("\nSession Context Example:")
            print(f"Session ID: {session.session_id}")
            print(f"Total tests in session: {len(session.test_results)}")

            # Show related tests that ran together
            print("\nTests that ran together in this session:")
            for test in session.test_results[:3]:  # Show first 3 tests
                print(f"- {test.nodeid}")
                print(f"  Outcome: {test.outcome.value}")
                print(f"  Duration: {test.duration:.2f}s")
                if test.has_warning:
                    print("  Has warnings!")

            # Show rerun patterns if any
            if session.rerun_test_groups:
                print("\nRerun patterns found:")
                for group in session.rerun_test_groups[:2]:  # Show first 2 rerun groups
                    print(f"Test: {group.nodeid}")
                    print(f"Attempts: {len(group.test_results)}")
                    for attempt in group.test_results:
                        print(f"- {attempt.outcome.value}")

    except Exception as e:
        print(f" Query demo failed: {str(e)}")


def demo_compare(api):
    """Demonstrate the Compare operation between versions."""
    try:
        print("\n=== Compare Operation ===")

        diff = (
            api.compare()
            .between_suts("api-service", "integration-service")
            .with_test_pattern("test_api")  # Focus on API tests
            .execute()
        )

        print("\nDifferences found:")
        print(f" New Failures: {len(diff.new_failures)}")
        print(f" Fixed Tests: {len(diff.fixed_tests)}")
        print(f" Still Failing: {len(diff.still_failing)}")

        if diff.new_failures:
            print("\nExample new failure:")
            failure = diff.new_failures[0]
            print(f"Test: {failure.nodeid}")
            print(f"Duration: {failure.duration:.2f}s")

    except Exception as e:
        print(f" Compare demo failed: {str(e)}")


def demo_analyze(api):
    """Demonstrate the Analyze operation for insights."""
    try:
        print("\n=== Analyze Operation ===")

        analysis = api.analyze()

        # Get session-level metrics
        failure_rate = analysis.sessions.failure_rate(days=30)  # Match our data generation period
        print(f"\n Failure Rate (30 days): {failure_rate:.2%}")

        # Get test-level insights
        stability = analysis.tests.stability()
        print("\nTest Stability:")
        print(f" Flaky Tests: {len(stability['flaky_tests'])}")
        print(f" Stable Tests: {len(stability['stable_tests'])}")

        # Get overall health metrics
        health = analysis.metrics.health_score()
        print(f"\n Overall Health Score: {health['overall_score']}/100")
        if health["recommendations"]:
            print("\nTop Recommendation:", health["recommendations"][0])

    except Exception as e:
        print(f" Analysis demo failed: {str(e)}")


def main():
    """Run the interactive demo."""
    print("=== pytest-insight Interactive Demo ===")
    print("Run each section to explore the API features.")
    print("\nTip: Set breakpoints or use pdb to inspect objects in detail!")

    # Step 1: Setup
    storage, api = setup_environment()
    if not api:
        return

    # Step 2: Query Demo
    input("\nPress Enter to run Query demo...")
    demo_query(api)

    # Step 3: Compare Demo
    input("\nPress Enter to run Compare demo...")
    demo_compare(api)

    # Step 4: Analyze Demo
    input("\nPress Enter to run Analyze demo...")
    demo_analyze(api)

    print("\nDone! Try modifying the queries or exploring the API further.")


if __name__ == "__main__":
    main()
