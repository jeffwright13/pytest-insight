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

    unique_tests = {test.nodeid: test for test in session.test_results}  # Unique tests by NodeID
    total_num_tests = len(unique_tests)

    total_warnings = sum(bool(test.has_warning)
                     for test in session.test_results)
    unique_warning_tests = len(
        {test.nodeid for test in session.test_results if test.has_warning}
    )

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

    # **Step 3: Print insights**
    typer.echo("Session Info:")
    typer.echo(f"  Session {session.session_id}")
    typer.echo(f"  SUT: {session.sut_name}")
    typer.echo(f"  Start time: {session.session_start_time}")
    typer.echo(f"  Stop time: {session.session_stop_time}")
    typer.echo(f"  Duration: {session.session_stop_time - session.session_start_time}")  # Fix duration

    typer.echo("Session Stats:")
    typer.echo(f"  Total Tests: {total_num_tests}")
    for outcome, count in sorted(outcomes.items()):
        typer.echo(f"  {outcome}: {count}")
    typer.echo(f"  Unique Warnings: {unique_warning_tests}")

    # Rerun groups
    total_num_reruns = sum(len(group) for group in rerun_tests.values())
    reruns_that_failed = sum(
        group.final_outcome == "FAILED" for group in session.rerun_test_groups
    )
    reruns_that_passed = sum(
        group.final_outcome == "PASSED" for group in session.rerun_test_groups
    )
    typer.echo(f"  Total Number of Rerun Tests: {total_num_reruns}")
    typer.echo(f"  ↳ Rerun Groups: {len(session.rerun_test_groups)}")
    typer.echo(f"  ↳ Rerun Groups That Passed: {reruns_that_passed}")
    typer.echo(f"  ↳ Rerun Groups That Failed: {reruns_that_failed}")


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
