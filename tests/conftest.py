import random
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path

import pytest
from pytest_insight.models import (
    RerunTestGroup,
    TestOutcome,
    TestResult,
    TestSession,
)
from pytest_insight.storage import JSONStorage
from pytest_mock import MockerFixture
from typer.testing import CliRunner

# Enable the pytester plugin explicitly
pytest_plugins = ["pytester"]


@pytest.fixture
def tester(request):
    """Version-agnostic fixture that returns appropriate test directory fixture."""
    pytest_version = version("pytest")
    fixture_name = "pytester" if pytest_version >= "7.0" else "testdir"
    return request.getfixturevalue(fixture_name)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "cli: CLI tests")
    config.addinivalue_line("markers", "api: API tests")
    config.addinivalue_line("markers", "storage: Storage tests")
    config.addinivalue_line("markers", "analyzer: Analyzer tests")
    config.addinivalue_line("markers", "filters: Filter tests")
    config.addinivalue_line("markers", "display: Display tests")
    config.addinivalue_line("markers", "commands: Command tests")
    config.addinivalue_line("markers", "metrics: Metrics tests")
    config.addinivalue_line("markers", "grafana: Grafana tests")
    config.addinivalue_line("markers", "server: FastAPI Server tests")
    config.addinivalue_line("markers", "smoke: Smoke tests")


# Add common fixtures
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
    temp_file = tmp_path / "test_sessions.json"
    return temp_file


@pytest.fixture
def json_storage(temp_json_file, mocker):
    """Fixture for a JSONStorage instance using a temporary file."""
    mocker.patch.object(JSONStorage, "FILE_PATH", temp_json_file)
    return JSONStorage()


@pytest.fixture
def mock_test_result_pass():
    """Fixture for a mock test result."""
    return TestResult(
        nodeid="test_file.py::test_case_1_pass",
        outcome="PASSED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def mock_test_result_fail():
    """Fixture for a mock test result."""
    return TestResult(
        nodeid="test_file.py::test_case_2_fail",
        outcome="FAILED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def mock_test_result_skip():
    """Fixture for a mock test result."""
    return TestResult(
        nodeid="test_file.py::test_case_3_skip",
        outcome="SKIPPED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def mock_test_result_xfail():
    """Fixture for a mock test result."""
    return TestResult(
        nodeid="test_file.py::test_case_4_xfail",
        outcome="XFAILED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def mock_test_result_xpass():
    """Fixture for a mock test result."""
    return TestResult(
        nodeid="test_file.py::test_case_5_xpass",
        outcome="XPASSED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def mock_test_result_warning():
    """Fixture for a mock test result."""
    return TestResult(
        nodeid="test_file.py::test_case_6_warning",
        outcome="PASSED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=True,
    )


@pytest.fixture
def mock_test_result_error():
    """Fixture for a mock test result."""
    return TestResult(
        nodeid="test_file.py::test_case_7_error",
        outcome="ERROR",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def mock_rerun_group1(mock_test_result):
    """Fixture for a rerun test group with a single test result."""
    group = RerunTestGroup(nodeid="test_rerun_group_1", final_outcome="PASSED")
    group.add_rerun(mock_test_result)
    group.add_test(mock_test_result)
    return group


@pytest.fixture
def mock_session_no_reruns(
    mock_test_result_pass,
    mock_test_result_fail,
    mock_test_result_skip,
    mock_test_result_xfail,
    mock_test_result_xpass,
    mock_test_result_warning,
    mock_test_result_error,
):
    """Fixture for a test session with no reruns."""
    return TestSession(
        sut_name="test_sut",
        session_id="123",
        session_start_time=datetime.utcnow(),
        session_stop_time=datetime.utcnow() + timedelta(minutes=1),
        test_results=[
            mock_test_result_pass,
            mock_test_result_fail,
            mock_test_result_skip,
            mock_test_result_xfail,
            mock_test_result_xpass,
            mock_test_result_warning,
            mock_test_result_error,
        ],
        rerun_test_groups=[],
        session_tags=["tag1", "tag2"],
    )


@pytest.fixture
def mock_session_w_reruns(
    mocker,
    mock_test_result_pass,
    mock_test_result_fail,
    mock_test_result_skip,
    mock_test_result_xfail,
    mock_test_result_xpass,
    mock_test_result_warning,
    mock_test_result_error,
):
    """Generate a test session with mocked rerun test groups."""

    # Create first rerun group with failure
    mock_rerun_group1 = mocker.MagicMock(spec=RerunTestGroup)
    mock_rerun_group1.nodeid = "test_file.py::test_case_1"
    mock_rerun_group1.final_outcome = "FAILED"
    mock_rerun_group1.reruns = [mocker.MagicMock(spec=TestResult)]
    mock_rerun_group1.reruns[0].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_1",
        "outcome": "FAILED",
        "start_time": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
        "duration": 2.5,
    }
    mock_rerun_group1.to_dict.return_value = {
        "nodeid": mock_rerun_group1.nodeid,
        "final_outcome": mock_rerun_group1.final_outcome,
        "reruns": [r.to_dict() for r in mock_rerun_group1.reruns],
        "full_test_list": [r.to_dict() for r in mock_rerun_group1.reruns],
    }

    # Create second rerun group with pass after failure
    mock_rerun_group2 = mocker.MagicMock(spec=RerunTestGroup)
    mock_rerun_group2.nodeid = "test_file.py::test_case_2"
    mock_rerun_group2.final_outcome = "PASSED"
    mock_rerun_group2.reruns = [mocker.MagicMock(spec=TestResult), mocker.MagicMock(spec=TestResult)]
    mock_rerun_group2.reruns[0].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_2",
        "outcome": "FAILED",
        "start_time": (datetime.utcnow() - timedelta(minutes=3)).isoformat(),
        "duration": 1.5,
    }
    mock_rerun_group2.reruns[1].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_2",
        "outcome": "PASSED",
        "start_time": (datetime.utcnow() - timedelta(minutes=2)).isoformat(),
        "duration": 1.2,
    }
    mock_rerun_group2.to_dict.return_value = {
        "nodeid": mock_rerun_group2.nodeid,
        "final_outcome": mock_rerun_group2.final_outcome,
        "reruns": [r.to_dict() for r in mock_rerun_group2.reruns],
        "full_test_list": [r.to_dict() for r in mock_rerun_group2.reruns],
    }

    # Create test session with 2 rerun groups
    session = TestSession(
        sut_name="test-sut",
        session_id="test-session-123",
        session_start_time=datetime.utcnow() - timedelta(minutes=10),
        session_stop_time=datetime.utcnow(),
        test_results=[
            mock_test_result_pass,
            mock_test_result_fail,
            mock_test_result_skip,
            mock_test_result_xfail,
            mock_test_result_xpass,
            mock_test_result_warning,
            mock_test_result_error,
        ],
        rerun_test_groups=[mock_rerun_group1, mock_rerun_group2],
        session_tags=["tag1", "tag2"],
    )

    return session


@pytest.fixture
def cli_runner():
    """Fixture to create a CLI runner for Typer."""
    return CliRunner()


@pytest.fixture
def mock_terminal_reporter(mocker: MockerFixture):
    """Create a mock terminal reporter with standard attributes."""
    reporter = mocker.Mock()
    reporter.stats = {"passed": [], "failed": [], "skipped": [], "xfailed": [], "xpassed": [], "error": [], "rerun": []}
    return reporter


@pytest.fixture
def mock_config(mocker: MockerFixture):
    """Create a mock pytest config."""
    config = mocker.Mock()
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)
    return config


@pytest.fixture
def sample_test_result():
    """Create a sample test result."""
    return TestResult(
        nodeid="test_example.py::test_something",
        outcome="PASSED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage for tests."""
    storage_file = tmp_path / "test_sessions.json"
    return JSONStorage(storage_file)


@pytest.fixture
def random_test_result():
    """Create a random test result."""
    nodeid = f"test_file_{random.randint(1, 1000)}.py::test_case_{random.randint(1, 1000)}"
    outcome = random.choice(TestOutcome.to_list())
    start_time = datetime.now(timezone.utc)
    duration = random.uniform(0.1, 10.0)
    caplog = random.choice([None, "", "Some log message"])
    error_outcomes = [TestOutcome.FAILED.value.lower(), TestOutcome.ERROR.value.lower()]
    capstderr = "Some error message" if outcome in error_outcomes else None
    capstdout = random.choice([None, "", "Some system output"])
    longreprtext = random.choice([None, "", "Some long representation text"])
    has_warning = random.choice([True, False])

    return TestResult(
        nodeid=nodeid,
        outcome=TestOutcome.from_str(outcome),
        start_time=start_time,
        duration=duration,
        caplog=caplog,
        capstderr=capstderr,
        capstdout=capstdout,
        longreprtext=longreprtext,
        has_warning=has_warning,
    )


@pytest.fixture
def random_test_session(random_test_result):
    """Create a random test session."""
    return TestSession(
        sut_name=f"test_sut_{random.randint(1, 1000)}",
        session_id=f"{random.randint(1, 1000)}",
        session_start_time=datetime.now(timezone.utc),
        session_stop_time=datetime.now(timezone.utc),
        test_results=[random_test_result],
        rerun_test_groups=[],
        session_tags=[f"tag_{random.randint(1, 100)}"],
    )


@pytest.fixture
def random_test_sessions(random_test_session):
    """Create a list of random test sessions."""
    return [random_test_session for _ in range(random.randint(1, 10))]


@pytest.fixture
def static_test_session_list(
    mock_test_result_pass,
    mock_test_result_fail,
    mock_test_result_skip,
    mock_test_result_xfail,
    mock_test_result_xpass,
    mock_test_result_warning,
    mock_test_result_error,
):
    """Create a static test session."""
    return [
        TestSession(
            sut_name="test_sut",
            session_id="123",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow() + timedelta(minutes=1),
            test_results=[mock_test_result_pass],
            rerun_test_groups=[],
            session_tags=["tag_always", "tag_pass"],
        ),
        TestSession(
            sut_name="test_sut",
            session_id="124",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow() + timedelta(minutes=1),
            test_results=[mock_test_result_fail],
            rerun_test_groups=[],
            session_tags=["tag_always", "tag_fail"],
        ),
        TestSession(
            sut_name="test_sut",
            session_id="125",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow() + timedelta(minutes=1),
            test_results=[mock_test_result_skip],
            rerun_test_groups=[],
            session_tags=["tag_always", "tag_skip"],
        ),
        TestSession(
            sut_name="test_sut",
            session_id="126",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow() + timedelta(minutes=1),
            test_results=[mock_test_result_xfail],
            rerun_test_groups=[],
            session_tags=["tag_always", "tag_xfail"],
        ),
        TestSession(
            sut_name="test_sut",
            session_id="127",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow() + timedelta(minutes=1),
            test_results=[mock_test_result_xpass],
            rerun_test_groups=[],
            session_tags=["tag_always", "tag_xpass"],
        ),
        TestSession(
            sut_name="test_sut",
            session_id="128",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow() + timedelta(minutes=1),
            test_results=[mock_test_result_warning],
            rerun_test_groups=[],
            session_tags=["tag_always", "tag_warning"],
        ),
        TestSession(
            sut_name="test_sut",
            session_id="129",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow() + timedelta(minutes=1),
            test_results=[mock_test_result_error],
            rerun_test_groups=[],
            session_tags=["tag_always", "tag_error"],
        ),
    ]
