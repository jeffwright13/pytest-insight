from datetime import datetime, timedelta

import pytest
import typer

from pytest_insight.storage import get_storage_instance

app = typer.Typer(help="Test history and analytics tool for pytest")
session_app = typer.Typer(help="Manage test sessions")
history_app = typer.Typer(help="View and analyze test history")
sut_app = typer.Typer(help="Manage Systems Under Test")
analytics_app = typer.Typer(help="Generate test analytics and reports")

# Add sub-applications
app.add_typer(session_app, name="session")
app.add_typer(history_app, name="history")
app.add_typer(sut_app, name="sut")
app.add_typer(analytics_app, name="analytics")

storage = get_storage_instance()


# Session commands
@session_app.command("run")
def run_session(
    path: str = typer.Argument("tests", help="Path to test directory or file")
):
    """Run a new test session."""
    pytest.main([path, "--insight"])



@session_app.command("show")
def show_session(
    session_id: str = typer.Argument(
        None, help="Session ID to show. Latest if not specified"
    )
):
    """Show details of a specific test session with insights beyond raw test stats."""
    storage = get_storage_instance()
    session = (
        storage.get_session_by_id(session_id) if session_id else storage.get_last_session()
    )

    if not session:
        typer.echo("[pytest-insight] No test sessions found.")
        raise typer.Exit(code=1)

    # **Step 1: Gather data**
    unique_tests = {test.nodeid: test for test in session.test_results}  # Unique tests by NodeID
    total_tests = len(unique_tests)

    total_warnings = sum(1 for test in session.test_results if test.has_warning)
    unique_warning_tests = len(set(test.nodeid for test in session.test_results if test.has_warning))

    # Outcome tally (including XPASSED, XFAILED, ERROR, etc.)
    outcomes = {}
    rerun_tests = {}

    for test in session.test_results:
        outcome = test.outcome.capitalize()  # Camel Case
        if outcome not in outcomes:
            outcomes[outcome] = 0
        outcomes[outcome] += 1

        # Track reruns separately
        if outcome == "Rerun":
            if test.nodeid not in rerun_tests:
                rerun_tests[test.nodeid] = []
            rerun_tests[test.nodeid].append(test)

    # **Step 2: Analyze reruns**
    total_reruns = sum(len(tests) for tests in rerun_tests.values())  # Total instances of rerun
    reruns_failed = sum(1 for tests in rerun_tests.values() if tests[-1].outcome == "FAILED")
    reruns_passed = sum(1 for tests in rerun_tests.values() if tests[-1].outcome == "PASSED")

    # **Step 3: Print insights**
    typer.echo(f"Session {session.session_id}")
    typer.echo(f"SUT: {session.sut_name}")
    typer.echo(f"Start time: {session.session_start_time}")
    typer.echo(f"Duration: {session.session_stop_time - session.session_start_time}")  # Fix duration
    typer.echo(f"Total Tests: {total_tests}")

    # Warnings summary
    typer.echo(f"Total Warnings: {total_warnings}")
    typer.echo(f"Unique Tests with Warnings: {unique_warning_tests}")

    # Outcome summary (sorted alphabetically for clarity)
    for outcome, count in sorted(outcomes.items()):
        typer.echo(f"{outcome}: {count}")

    # Rerun insights
    typer.echo(f"Total Reruns: {total_reruns}")
    typer.echo(f"  ↳ Reruns that Failed: {reruns_failed}")
    typer.echo(f"  ↳ Reruns that Passed: {reruns_passed}")


# @session_app.command("show")
# def show_session():
#     """Display the latest test session results."""
#     storage = get_storage_instance()
#     session = storage.get_last_session()

#     if not session:
#         typer.echo("[pytest-insight] No test sessions found.")
#         raise typer.Exit(code=1)

#     # Ensure each test case is counted only once by its nodeid
#     unique_tests = {test.nodeid: test for test in session.test_results}

#     total_tests = len(unique_tests)
#     passed = sum(1 for test in unique_tests.values() if test.outcome == "PASSED")
#     failed = sum(1 for test in unique_tests.values() if test.outcome == "FAILED")
#     skipped = sum(1 for test in unique_tests.values() if test.outcome == "SKIPPED")
#     rerun = sum(1 for test in unique_tests.values() if test.outcome == "RERUN")
#     warnings = sum(1 for test in unique_tests.values() if test.has_warning)

#     typer.echo(f"Session {session.session_id}")
#     typer.echo(f"SUT: {session.sut_name}")
#     typer.echo(f"Start time: {session.session_start_time}")
#     typer.echo(f"Duration: {session.session_duration}")
#     typer.echo(f"Total tests: {total_tests}")
#     typer.echo(f"WARNING: {warnings}")
#     typer.echo(f"PASSED: {passed}")
#     typer.echo(f"FAILED: {failed}")
#     typer.echo(f"SKIPPED: {skipped}")
#     typer.echo(f"RERUN: {rerun}")


# @session_app.command("show")
# def show_session(
#     session_id: str = typer.Argument(
#         None, help="Session ID to show. Latest if not specified"
#     )
# ):
#     """Show details of a specific test session."""
#     session = (
#         storage.get_session(session_id) if session_id else storage.get_last_session()
#     )
#     if not session:
#         typer.secho("Session not found", fg=typer.colors.RED)
#         return

#     typer.echo(f"Session {session.session_id}")
#     typer.echo(f"SUT: {session.sut_name}")
#     typer.echo(f"Start time: {session.session_start_time}")
#     typer.echo(f"Duration: {session.session_duration}")
#     typer.echo(f"Total tests: {len(session.test_results)}")

#     # Group test results by outcome
#     outcomes = {}
#     for test in session.test_results:
#         if test.outcome not in outcomes:
#             outcomes[test.outcome] = 0
#         outcomes[test.outcome] += 1

#     # Show outcome summary
#     for outcome, count in outcomes.items():
#         typer.echo(f"{outcome}: {count}")


# History commands
@history_app.command("list")
def list_history(days: int = typer.Option(7, help="Number of days of history to show")):
    """List test session history."""
    sessions = storage.load_sessions()
    cutoff = datetime.now() - timedelta(days=days)
    recent = [s for s in sessions if s.session_start_time > cutoff]
    for session in recent:
        typer.echo(f"{session.session_start_time}: {session.session_id}")


# SUT commands
@sut_app.command("list")
def list_suts():
    """List all known Systems Under Test."""
    sessions = storage.load_sessions()
    suts = {s.sut_name for s in sessions}
    for sut in sorted(suts):
        typer.echo(sut)


# Analytics commands
@analytics_app.command("summary")
def show_summary(sut: str = typer.Argument(None, help="Show summary for specific SUT")):
    """Show test execution summary."""
    session = storage.get_last_session()
    if not session:
        typer.secho("No test data available", fg=typer.colors.YELLOW)
        return

    # Group test results by outcome
    outcomes = {}
    for test in session.test_results:
        if test.outcome not in outcomes:
            outcomes[test.outcome] = 0
        outcomes[test.outcome] += 1

    # Show summary
    typer.echo(f"\nTest Summary for {session.sut_name}")
    typer.echo(f"Session: {session.session_id}")
    typer.echo(f"Run at: {session.session_start_time}")
    typer.echo(f"Duration: {session.session_duration}\n")

    for outcome, count in outcomes.items():
        typer.echo(f"{outcome}: {count}")


if __name__ == "__main__":
    app()
