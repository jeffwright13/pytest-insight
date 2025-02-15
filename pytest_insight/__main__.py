import typer

from pytest_insight.storage import JSONTestResultStorage

app = typer.Typer()
storage = JSONTestResultStorage()


@app.command()
def summary():
    """Display a summary of past test sessions."""
    sessions = storage.load_sessions()
    if not sessions:
        print("[pytest-insight] No stored sessions.")
        return

    print("\n[pytest-insight] Stored Sessions Summary:")
    for idx, session in enumerate(sessions, start=1):
        print(f"Session {idx}: {session.session_id}, Started: {session.session_start_time}")
        print(f"Duration: {session.session_duration}, Tests: {len(session.test_results)}")


@app.command()
def session(session_id: str):
    """Show details for a specific test session."""
    session = storage.get_session_by_id(session_id)
    if not session:
        print(f"[pytest-insight] No session found with ID: {session_id}")
        return

    print(f"\n[pytest-insight] Session {session.session_id}:")
    print(f"Start Time: {session.session_start_time}")
    print(f"Duration: {session.session_duration}")
    print(f"Total Tests: {len(session.test_results)}")


@app.command()
def last():
    """Show the most recent test session."""
    session = storage.get_last_session()
    if not session:
        print("[pytest-insight] No previous test sessions found.")
        return

    print(f"\n[pytest-insight] Last Session {session.session_id}:")
    print(f"Start Time: {session.session_start_time}")
    print(f"Duration: {session.session_duration}")
    print(f"Total Tests: {len(session.test_results)}")


@app.command()
def test(nodeid: str):
    """Show results for a specific test case across sessions."""
    sessions = storage.get_test_results(nodeid)
    if not sessions:
        print(f"[pytest-insight] No results found for test: {nodeid}")
        return

    print(f"\n[pytest-insight] Test Results for {nodeid}:")
    for session in sessions:
        result = next(test for test in session.test_results if test["nodeid"] == nodeid)
        print(f"- Session {session.session_id}: {result['outcome']}")


if __name__ == "__main__":
    app()
