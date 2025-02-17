from pytest_insight.storage import InMemoryStorage, JSONStorage
import json
import random
import string
from datetime import datetime, timedelta
from importlib.metadata import version

import pytest
from pytest_insight.models import (
    RerunTestGroup,
    TestResult,
    TestSession,
)

# Enable the pytester plugin explicitly
pytest_plugins = ["pytester"]


@pytest.fixture
def tester(request):
    """Version-agnostic fixture that returns appropriate test directory fixture."""
    pytest_version = version("pytest")
    fixture_name = "pytester" if pytest_version >= "7.0" else "testdir"
    return request.getfixturevalue(fixture_name)


class TextGenerator:
    """Generate random text content for testing."""

    WORD_LENGTH_RANGE = (3, 10)
    WORDS_PER_SENTENCE = (5, 15)
    SENTENCES_PER_PARAGRAPH = (3, 7)

    @staticmethod
    def word(length=None):
        """Generate a random word."""
        if length is None:
            length = random.randint(*TextGenerator.WORD_LENGTH_RANGE)
        return "".join(random.choices(string.ascii_lowercase, k=length))

    @classmethod
    def sentence(cls):
        """Generate a random sentence."""
        num_words = random.randint(*cls.WORDS_PER_SENTENCE)
        words = [cls.word() for _ in range(num_words)]
        words[0] = words[0].capitalize()
        return " ".join(words) + "."

    @classmethod
    def paragraph(cls):
        """Generate a random paragraph."""
        num_sentences = random.randint(*cls.SENTENCES_PER_PARAGRAPH)
        return " ".join(cls.sentence() for _ in range(num_sentences))


@pytest.fixture
def text_gen():
    """Fixture providing access to TextGenerator."""
    return TextGenerator()


class NodeId:
    """Generate and manage pytest NodeIds for testing."""

    def __init__(self):
        self.path_parts = self._generate_path_parts()
        self.filename = self._generate_filename()
        self.test_name = self._generate_test_name()
        self.params = self._generate_params()

    @staticmethod
    def _random_word(length=6):
        """Generate a random word using lowercase letters."""
        return "".join(random.choices(string.ascii_lowercase, k=length))

    def _generate_path_parts(self):
        """Generate random path components."""
        num_folders = random.randint(1, 3)
        return [self._random_word() for _ in range(num_folders)]

    def _generate_filename(self):
        """Generate random Python filename."""
        return f"{self._random_word()}.py"

    def _generate_test_name(self):
        """Generate random test function name."""
        return f"test_{self._random_word()}"

    def _generate_params(self):
        """Generate random parameter string."""
        if random.choice([True, False]):
            num_params = random.randint(1, 3)
            params = [self._random_word() for _ in range(num_params)]
            return f"[{'-'.join(params)}]"
        return ""

    @property
    def path(self):
        """Get the full path including filename."""
        return "/".join(self.path_parts + [self.filename])

    @property
    def full_name(self):
        """Get the complete NodeId."""
        return f"{self.path}::{self.test_name}{self.params}"

    def __str__(self):
        return self.full_name


@pytest.fixture
def nodeid():
    """Fixture that returns a NodeId instance."""
    return NodeId()


@pytest.fixture
def random_test_session(nodeid, text_gen):
    """Fixture to generate a random TestSession object."""
    sut_name = f"SUT-{random.randint(1, 10)}"
    session_id = f"session-{random.randint(100, 999)}"

    # Create base session time window
    base_time = datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
    session_start_time = base_time
    session_stop_time = base_time + timedelta(seconds=random.randint(30, 300))

    # Generate unique test results
    session_test_results = []
    for _ in range(random.randint(2, 6)):
        result = TestResult(
            nodeid=str(nodeid),
            outcome=random.choice(["PASSED", "FAILED", "SKIPPED", "XFAILED", "XPASSED", "RERUN", "ERROR"]),
            start_time=session_start_time + timedelta(seconds=random.randint(1, 30)),
            duration=random.uniform(0.1, 5.0),
            caplog=text_gen.sentence(),
            capstderr=text_gen.sentence(),
            capstdout=text_gen.sentence(),
            longreprtext=text_gen.paragraph(),
            has_warning=random.choice([True, False]),
        )
        session_test_results.append(result)

    # Generate unique rerun groups
    session_rerun_test_groups = []
    for _ in range(random.randint(1, 3)):
        group = RerunTestGroup(nodeid=str(nodeid), final_outcome=random.choice(["PASSED", "FAILED"]))
        for _ in range(random.randint(1, 4)):
            result = TestResult(
                nodeid=str(nodeid),
                outcome=random.choice(["PASSED", "FAILED"]),
                start_time=session_start_time + timedelta(seconds=random.randint(1, 30)),
                duration=random.uniform(0.1, 5.0),
                caplog=text_gen.sentence(),
                capstderr=text_gen.sentence(),
                capstdout=text_gen.sentence(),
                longreprtext=text_gen.paragraph(),
                has_warning=random.choice([True, False]),
            )
            group.add_rerun(result)
            group.add_test(result)
        session_rerun_test_groups.append(group)

    session = TestSession(
        sut_name=sut_name,
        session_id=session_id,
        session_start_time=session_start_time,
        session_stop_time=session_stop_time,
    )

    # Add test results using proper method
    for result in session_test_results:
        session.add_test_result(result)

    # Add rerun groups using proper method
    for group in session_rerun_test_groups:
        session.add_rerun_group(group)

    # Add session tags
    session.session_tags = {
        "environment": random.choice(["dev", "qa", "prod"]),
        "platform": random.choice(["linux", "windows", "macos"]),
        "python_version": random.choice(["3.8", "3.9", "3.10"]),
    }

    return session


# Constants for test result generation
TEST_OUTCOMES = {
    "PASSED": {"weight": 70, "can_have_warning": True, "needs_error_output": False},
    "FAILED": {"weight": 15, "can_have_warning": False, "needs_error_output": True},
    "SKIPPED": {"weight": 5, "can_have_warning": False, "needs_error_output": False},
    "XFAILED": {"weight": 3, "can_have_warning": False, "needs_error_output": True},
    "XPASSED": {"weight": 2, "can_have_warning": False, "needs_error_output": False},
    "RERUN": {"weight": 15, "can_have_warning": False, "needs_error_output": True},
    "ERROR": {"weight": 2, "can_have_warning": False, "needs_error_output": True},
}


@pytest.fixture
def random_test_result(nodeid, text_gen):
    """Generate a random TestResult instance."""
    return TestResult(
        nodeid=str(nodeid),
        outcome=random.choice(["PASSED", "FAILED", "SKIPPED", "XFAILED", "XPASSED", "RERUN", "ERROR"]),
        start_time=datetime.utcnow(),
        duration=random.uniform(0.1, 5.0),
        caplog="" if random.choice([True, False]) else text_gen.sentence(),  # Allow empty strings
        capstderr="",  # Default empty
        capstdout="",  # Default empty
        longreprtext="",  # Default empty
        has_warning=random.choice([True, False]),
    )



# STORAGE FIXTURES - for testing storage.py
# ------------------------------------------------------------------------------
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
def mock_rerun_group1(mock_test_result):
    """Fixture for a rerun test group with a single test result."""
    group = RerunTestGroup(nodeid="test_rerun_group_1", final_outcome="PASSED")
    group.add_rerun(mock_test_result)
    group.add_test(mock_test_result)
    return group

@pytest.fixture
def mock_session_no_reruns():
    """Generate a test session."""
    return TestSession(
        sut_name="test_sut",
        session_id="123",
        session_start_time=datetime.utcnow(),
        session_stop_time=datetime.utcnow(),
        test_results=[],
        rerun_test_groups=[],
    )

@pytest.fixture
def mock_session_w_reruns(mocker):
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
        "duration": 2.5
    }
    mock_rerun_group1.to_dict.return_value = {
        "nodeid": mock_rerun_group1.nodeid,
        "final_outcome": mock_rerun_group1.final_outcome,
        "reruns": [r.to_dict() for r in mock_rerun_group1.reruns],
        "full_test_list": [r.to_dict() for r in mock_rerun_group1.reruns]
    }

    # Create second rerun group with pass after failure
    mock_rerun_group2 = mocker.MagicMock(spec=RerunTestGroup)
    mock_rerun_group2.nodeid = "test_file.py::test_case_2"
    mock_rerun_group2.final_outcome = "PASSED"
    mock_rerun_group2.reruns = [
        mocker.MagicMock(spec=TestResult),
        mocker.MagicMock(spec=TestResult)
    ]
    mock_rerun_group2.reruns[0].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_2",
        "outcome": "FAILED",
        "start_time": (datetime.utcnow() - timedelta(minutes=3)).isoformat(),
        "duration": 1.5
    }
    mock_rerun_group2.reruns[1].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_2",
        "outcome": "PASSED",
        "start_time": (datetime.utcnow() - timedelta(minutes=2)).isoformat(),
        "duration": 1.2
    }
    mock_rerun_group2.to_dict.return_value = {
        "nodeid": mock_rerun_group2.nodeid,
        "final_outcome": mock_rerun_group2.final_outcome,
        "reruns": [r.to_dict() for r in mock_rerun_group2.reruns],
        "full_test_list": [r.to_dict() for r in mock_rerun_group2.reruns]
    }

    # Create test session with rerun groups
    session = TestSession(
        sut_name="test-sut",
        session_id="test-session-123",
        session_start_time=datetime.utcnow() - timedelta(minutes=10),
        session_stop_time=datetime.utcnow(),
        rerun_test_groups=[mock_rerun_group1, mock_rerun_group2]
    )

    return session
