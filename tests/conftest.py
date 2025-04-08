import random
from importlib.metadata import version
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.storage import JSONStorage
from pytest_insight.test_data import (
    NodeId,
    TextGenerator,
)
from pytest_insight.test_data import get_test_time as get_test_time_fn
from pytest_insight.test_data import (
    mock_test_result_error,
    mock_test_result_fail,
    mock_test_result_pass,
    mock_test_result_skip,
    mock_test_result_warning,
    mock_test_result_xfail,
    mock_test_result_xpass,
    mock_test_session,
    random_rerun_test_group,
    random_test_result,
    random_test_session,
)

# Enable the pytester plugin explicitly
pytest_plugins = ["pytester"]


@pytest.fixture
def tester(request):
    """Version-agnostic fixture that returns appropriate test directory fixture."""
    pytest_version = version("pytest")
    fixture_name = "pytester" if pytest_version >= "7.0" else "testdir"
    return request.getfixturevalue(fixture_name)


@pytest.fixture
def text_gen():
    """Fixture providing access to TextGenerator."""
    return TextGenerator()


@pytest.fixture
def nodeid():
    """Fixture providing access to NodeId generator."""
    return NodeId()


@pytest.fixture
def get_test_time():
    """Fixture that provides timezone-aware test timestamps.

    Returns a function that generates UTC timestamps starting from 2023-01-01
    plus the given offset in seconds. This ensures consistent timezone handling
    and prevents comparison issues between naive and aware datetimes.
    """
    return get_test_time_fn


@pytest.fixture
def random_test_session_factory(get_test_time):
    """Factory fixture that creates random test sessions with timezone-aware timestamps.

    All datetime operations use UTC to prevent comparison issues between naive and
    aware datetimes, following the get_test_time pattern for consistency.

    Returns:
        function: Factory function that creates a TestSession with:
            - Timezone-aware timestamps via get_test_time()
            - Proper session context preservation
            - Test results with consistent timing relationships
    """

    def _factory():
        # Create base session
        session = random_test_session()

        # Ensure timezone-aware timestamps
        base_time = get_test_time()
        session.session_start_time = base_time

        # Space test results 5 seconds apart
        for i, result in enumerate(session.test_results):
            result.start_time = get_test_time(i * 5)

        # Set session stop time after all tests
        session.session_stop_time = get_test_time(len(session.test_results) * 5 + 1)

        return session

    return _factory


@pytest.fixture
def random_test_sessions_factory(random_test_session_factory, get_test_time):
    """Factory fixture that creates multiple random test sessions.

    Uses random_test_session_factory to ensure all sessions:
    - Have timezone-aware timestamps
    - Maintain proper session context and relationships
    - Preserve test result timing within each session

    Returns:
        function: Factory function that creates a list of TestSessions
    """

    def _factory(num_sessions=None):
        if num_sessions is None:
            num_sessions = random.randint(2, 5)

        sessions = []
        for i in range(num_sessions):
            session = random_test_session_factory()
            # Offset each session by 10 minutes to maintain clear chronological order
            session.session_start_time = get_test_time(
                i * 600
            )  # 600 seconds = 10 minutes
            session.session_stop_time = get_test_time(
                (i + 1) * 600 - 1
            )  # End just before next session
            for j, result in enumerate(session.test_results):
                result.start_time = get_test_time(
                    i * 600 + j * 5
                )  # Space tests 5 seconds apart
            sessions.append(session)

        return sessions

    return _factory


@pytest.fixture
def random_test_result_factory():
    """A factory fixture to create a random TestResult instance."""
    return random_test_result


@pytest.fixture
def random_rerun_test_group_factory():
    """A factory fixture to create a random RerunTestGroup instance."""
    return random_rerun_test_group


@pytest.fixture
def test_data_dir():
    """Return path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create temporary storage directory."""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    return storage_dir


@pytest.fixture
def temp_json_file(tmp_path):
    """Create a temporary JSON file for testing."""
    return tmp_path / "test.json"


@pytest.fixture
def json_storage(temp_json_file):
    """Fixture for a JSONStorage instance using a temporary file."""
    return JSONStorage(temp_json_file)


@pytest.fixture
def cli_runner():
    """Fixture to create a CLI runner for Typer."""
    return CliRunner()


@pytest.fixture
def mock_terminal_reporter(mocker: MockerFixture):
    """Create a mock terminal reporter with standard attributes."""
    reporter = mocker.MagicMock()
    reporter._tw = mocker.MagicMock()
    reporter.write = mocker.MagicMock()
    reporter.write_line = mocker.MagicMock()
    reporter.ensure_newline = mocker.MagicMock()
    return reporter


@pytest.fixture
def mock_config(mocker: MockerFixture):
    """Create a mock pytest config."""
    config = mocker.MagicMock()
    config.option = mocker.MagicMock()
    return config


# Test Result Fixtures
@pytest.fixture
def test_result_pass(get_test_time):
    """Fixture that returns a mock test result with PASSED outcome.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    result = mock_test_result_pass()
    result.start_time = get_test_time()
    return result


@pytest.fixture
def test_result_fail(get_test_time):
    """Fixture that returns a mock test result with FAILED outcome.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    result = mock_test_result_fail()
    result.start_time = get_test_time()
    result.stop_time = get_test_time(1)  # 1 second later
    result.capstdout = "Standard output from failed test"
    result.capstderr = "Standard error from failed test"
    result.caplog = "Log output from failed test"
    return result


@pytest.fixture
def test_result_skip(get_test_time):
    """Fixture that returns a mock test result with SKIPPED outcome.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    result = mock_test_result_skip()
    result.start_time = get_test_time()
    return result


@pytest.fixture
def test_result_xfailed(get_test_time):
    """Fixture that returns a mock test result with XFAILED outcome.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    result = mock_test_result_xfail()
    result.start_time = get_test_time()
    return result


@pytest.fixture
def test_result_xpassed(get_test_time):
    """Fixture that returns a mock test result with XPASSED outcome.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    result = mock_test_result_xpass()
    result.start_time = get_test_time()
    return result


@pytest.fixture
def test_result_error(get_test_time):
    """Fixture that returns a mock test result with ERROR outcome.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    result = mock_test_result_error()
    result.start_time = get_test_time()
    return result


@pytest.fixture
def test_result_warning(get_test_time):
    """Fixture that returns a mock test result with warning.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    result = mock_test_result_warning()
    result.start_time = get_test_time()
    return result


# Test Session Fixtures
@pytest.fixture
def test_session_basic(get_test_time):
    """Fixture that returns a mock test session with all possible outcomes.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    basic_session = mock_test_session()
    basic_session.session_start_time = get_test_time()
    basic_session.session_stop_time = get_test_time(60)  # 1 minute later
    for i, result in enumerate(basic_session.test_results):
        result.start_time = get_test_time(i * 5)  # Space tests 5 seconds apart
    return basic_session


@pytest.fixture
def test_session_no_reruns(test_session_basic):
    """Fixture that returns a mock test session with no reruns.
    Inherits timezone-aware timestamps from test_session_basic.
    """
    session = test_session_basic
    session.rerun_test_groups = []
    return session


@pytest.fixture
def test_session_with_reruns(test_session_basic, mocker: MockerFixture, get_test_time):
    """Generate a test session with mocked rerun test groups.
    Uses get_test_time() to ensure timezone-aware timestamps.
    """
    session = test_session_basic

    # Create first rerun group with failure
    mock_rerun_group1 = mocker.MagicMock()
    mock_rerun_group1.nodeid = "test_file.py::test_case_1"
    mock_rerun_group1.reruns = [mocker.MagicMock()]
    mock_rerun_group1.reruns[0].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_1",
        "outcome": "FAILED",
        "start_time": get_test_time(-300).isoformat(),  # 5 minutes ago
        "duration": 2.5,
    }
    mock_rerun_group1.to_dict.return_value = {
        "nodeid": mock_rerun_group1.nodeid,
        "reruns": [r.to_dict() for r in mock_rerun_group1.reruns],
        "full_test_list": [r.to_dict() for r in mock_rerun_group1.reruns],
    }

    # Create second rerun group with pass after failure
    mock_rerun_group2 = mocker.MagicMock()
    mock_rerun_group2.nodeid = "test_file.py::test_case_2"
    mock_rerun_group2.reruns = [mocker.MagicMock(), mocker.MagicMock()]
    mock_rerun_group2.reruns[0].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_2",
        "outcome": "FAILED",
        "start_time": get_test_time(-180).isoformat(),  # 3 minutes ago
        "duration": 1.5,
    }
    mock_rerun_group2.reruns[1].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_2",
        "outcome": "PASSED",
        "start_time": get_test_time(-120).isoformat(),  # 2 minutes ago
        "duration": 1.2,
    }
    mock_rerun_group2.to_dict.return_value = {
        "nodeid": mock_rerun_group2.nodeid,
        "reruns": [r.to_dict() for r in mock_rerun_group2.reruns],
        "full_test_list": [r.to_dict() for r in mock_rerun_group2.reruns],
    }

    session.rerun_test_groups = [mock_rerun_group1, mock_rerun_group2]
    return session


# Query Test Fixtures
@pytest.fixture
def api_session(get_test_time):
    """Fixture providing a test session for API tests with both passing and failing tests."""
    session = TestSession(
        sut_name="api",
        session_id="session1",
        session_tags={"type": "api"},
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(10),
        test_results=[
            TestResult(
                nodeid="test_get.py",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_post.py",
                outcome=TestOutcome.FAILED,
                start_time=get_test_time(1),
                duration=2.0,
            ),
        ],
        rerun_test_groups=[["test_post.py"]],  # Failed test was rerun
    )
    return session


@pytest.fixture
def db_session(get_test_time):
    """Fixture providing a test session for database tests with all passing tests."""
    session = TestSession(
        sut_name="db",
        session_id="session2",
        session_tags={"type": "db"},
        session_start_time=get_test_time(),
        session_stop_time=get_test_time(10),
        test_results=[
            TestResult(
                nodeid="test_query.py",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(),
                duration=1.0,
            ),
            TestResult(
                nodeid="test_update.py",
                outcome=TestOutcome.PASSED,
                start_time=get_test_time(1),
                duration=0.5,
            ),
        ],
        rerun_test_groups=[],  # No reruns needed
    )
    return session


@pytest.fixture
def test_sessions(api_session, db_session):
    """Fixture providing a list of test sessions for query testing."""
    return [api_session, db_session]
