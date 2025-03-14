import random
import string
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path

import pytest
from pytest_insight.models import (
    RerunTestGroup,
    TestHistory,
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
# ------------------------------vvv Fixtures vvv ---------------------------- #
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


# class NodeId:
#     """Generate and manage pytest NodeIds for testing."""
#
#     def __init__(self):
#         self.path_parts = self._generate_path_parts()
#         self.filename = self._generate_filename()
#         self.test_name = self._generate_test_name()
#         self.params = self._generate_params()
#
#     @staticmethod
#     def _random_word(length=6):
#         """Generate a random word using lowercase letters."""
#         return "".join(random.choices(string.ascii_lowercase, k=length))
#
#     def _generate_path_parts(self):
#         """Generate random path components."""
#         num_folders = random.randint(1, 3)
#         return [self._random_word() for _ in range(num_folders)]
#
#     def _generate_filename(self):
#         """Generate random Python filename."""
#         return f"{self._random_word()}.py"
#
#     def _generate_test_name(self):
#         """Generate random test function name."""
#         return f"test_{self._random_word()}"
#
#     def _generate_params(self):
#         """Generate random parameter string."""
#         if random.choice([True, False]):
#             num_params = random.randint(1, 3)
#             params = [self._random_word() for _ in range(num_params)]
#             return f"[{'-'.join(params)}]"
#         return ""
#
#     @property
#     def path(self):
#         """Get the full path including filename."""
#         return "/".join(self.path_parts + [self.filename])
#
#     @property
#     def full_name(self):
#         """Get the complete NodeId."""
#         return f"{self.path}::{self.test_name}{self.params}"
#
#     def __str__(self):
#         return self.full_name


# @pytest.fixture
# def nodeid():
#     """Fixture that returns a NodeId instance."""
#     return NodeId()


@pytest.fixture
def random_test_session(text_gen):
    """A factory fixture to create a random TestSession instance."""

    def _create():
        # Generate new random values each time the factory is called
        num_tests = random.randint(2, 6)  # More realistic test count
        include_rerun = random.choice([True, False, False, False])  # 25% chance of having reruns

        # Create base session time window for consistent timing
        base_time = datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 60))
        session_start_time = base_time
        session_stop_time = base_time + timedelta(seconds=random.randint(30, 300))

        # Generate test nodeids that support our pattern matching rules
        module_types = ["api", "ui", "db", "auth"]
        test_types = ["get", "post", "update", "delete", "list", "create"]

        # Create related tests in the same module to preserve relationships
        module_name = random.choice(module_types)
        test_file = f"test_{module_name}.py"

        # Create base test results with realistic output
        test_results = []
        current_time = session_start_time

        # Generate multiple tests in the same module to show relationships
        for _ in range(num_tests):
            test_name = f"test_{random.choice(test_types)}_{module_name}"
            nodeid = f"{test_file}::{test_name}"

            outcome = random.choice(list(TestOutcome))
            caplog = text_gen.sentence()
            capstderr = text_gen.sentence() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else ""
            capstdout = text_gen.sentence()
            longreprtext = text_gen.paragraph() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else ""
            has_warning = random.choice([True, False])

            result = TestResult(
                nodeid=nodeid,
                outcome=outcome,
                start_time=current_time + timedelta(seconds=random.randint(1, 10)),
                duration=random.uniform(0.1, 5.0),
                caplog=caplog,
                capstderr=capstderr,
                capstdout=capstdout,
                longreprtext=longreprtext,
                has_warning=has_warning,
            )
            test_results.append(result)
            current_time = result.stop_time

        # Maybe add rerun groups with proper timing and relationships
        rerun_groups = []
        if include_rerun:
            # Use same module for rerun groups to maintain relationships
            num_rerun_groups = random.randint(1, 2)
            for _ in range(num_rerun_groups):
                test_name = f"test_{random.choice(test_types)}_{module_name}"
                rerun_nodeid = f"{test_file}::{test_name}"

                group = RerunTestGroup(nodeid=rerun_nodeid)

                # Create rerun sequence
                num_reruns = random.randint(2, 4)  # Store the number of reruns
                for i in range(num_reruns):
                    is_final = i == num_reruns - 1

                    # For final attempt, more likely to pass than fail
                    final_outcome = (
                        random.choices(
                            [TestOutcome.PASSED, TestOutcome.FAILED],
                            weights=[0.8, 0.2],  # 80% chance to pass on final attempt
                        )[0]
                        if is_final
                        else TestOutcome.RERUN
                    )

                    result = TestResult(
                        nodeid=rerun_nodeid,
                        outcome=final_outcome,
                        start_time=current_time + timedelta(seconds=random.randint(1, 10)),
                        duration=random.uniform(0.1, 5.0),
                        caplog=f"Attempt {i+1}" if not is_final else "Final attempt",
                        capstderr=(
                            "" if not is_final or final_outcome == TestOutcome.PASSED else "Test failed after reruns"
                        ),
                        capstdout=f"Running test (attempt {i+1})",
                        longreprtext=(
                            ""
                            if not is_final or final_outcome == TestOutcome.PASSED
                            else "Failed after multiple attempts"
                        ),
                        has_warning=random.choice([True, False]) if is_final else False,
                    )
                    group.add_test(result)
                    test_results.append(result)
                    current_time = result.stop_time + timedelta(seconds=1)
                rerun_groups.append(group)

        # Create session with base components and realistic tags
        session = TestSession(
            sut_name=f"{module_name}_service",  # More realistic service name
            session_id=f"session_{random.randint(1, 1000)}",
            session_start_time=session_start_time,
            session_stop_time=session_stop_time,
            test_results=test_results,
            rerun_test_groups=[],
            session_tags=[
                f"module_{module_name}",
                f"type_{random.choice(['unit', 'integration', 'e2e'])}",
                f"env_{random.choice(['dev', 'staging', 'prod'])}",
            ],
        )

        # Add rerun groups using the proper method
        for group in rerun_groups:
            session.add_rerun_group(group)

        return session

    return _create


# @pytest.fixture
# def random_test_result(text_gen):
#     """Generate a random TestResult instance."""
#     outcome = random.choice(list(TestOutcome))
#     start_time = datetime.utcnow()
#     duration = random.uniform(0.1, 5.0)
#
#     return TestResult(
#         nodeid="test_nodeid",
#         outcome=outcome,
#         start_time=start_time,
#         duration=duration,
#         caplog=text_gen.sentence(),
#         capstderr=text_gen.sentence() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else "",
#         capstdout=text_gen.sentence(),
#         longreprtext=text_gen.paragraph() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else "",
#         has_warning=random.choice([True, False]),
#     )


@pytest.fixture
def test_history():
    """Create empty TestHistory instance."""
    return TestHistory()


@pytest.fixture
def sample_session(sut_name="test-sut", session_id="session-1"):
    """Create a sample test session."""
    now = datetime.now()
    return TestSession(
        sut_name=sut_name,
        session_id=session_id,
        session_start_time=now,
        session_stop_time=now + timedelta(seconds=10),
        test_results=[],
    )


# ------------------------------^^^ Fixtures ^^^------------------------------ #


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
    group = RerunTestGroup(nodeid="test_rerun_group_1")
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
    mock_rerun_group1.reruns = [mocker.MagicMock(spec=TestResult)]
    mock_rerun_group1.reruns[0].to_dict.return_value = {
        "nodeid": "test_file.py::test_case_1",
        "outcome": "FAILED",
        "start_time": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
        "duration": 2.5,
    }
    mock_rerun_group1.to_dict.return_value = {
        "nodeid": mock_rerun_group1.nodeid,
        "reruns": [r.to_dict() for r in mock_rerun_group1.reruns],
        "full_test_list": [r.to_dict() for r in mock_rerun_group1.reruns],
    }

    # Create second rerun group with pass after failure
    mock_rerun_group2 = mocker.MagicMock(spec=RerunTestGroup)
    mock_rerun_group2.nodeid = "test_file.py::test_case_2"
    mock_rerun_group2.reruns = [
        mocker.MagicMock(spec=TestResult),
        mocker.MagicMock(spec=TestResult),
    ]
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
    reporter.stats = {
        "passed": [],
        "failed": [],
        "skipped": [],
        "xfailed": [],
        "xpassed": [],
        "error": [],
        "rerun": [],
    }
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
    """A factory fixture to create a random TestResult instance.

    Returns test results with nodeids that support pattern matching:
    1. Non-regex patterns:
       - Split on :: into parts
       - Module part: Strip .py before matching
       - Test name part: Direct pattern match
    2. Pattern matches if ANY part matches

    Example nodeids:
    - "test_api.py::test_get_api"      # Matches 'api' in both parts
    - "test_api.py::test_post_api"     # Matches 'api' in both parts
    - "test_ui.py::test_get_ui"        # Matches 'get' in test name
    """

    def _create():
        # Generate nodeids that support our pattern matching rules
        module_types = ["api", "ui", "db", "auth"]
        module_name = random.choice(module_types)
        test_types = ["get", "post", "update", "delete", "list", "create"]
        test_name = random.choice(test_types)

        # Format: test_{module}.py::test_{action}_{module}
        nodeid = f"test_{module_name}.py::test_{test_name}_{module_name}"

        # Generate timing info - use smaller duration range
        start_time = datetime.now(timezone.utc)
        duration = random.uniform(0.1, 10.0)  # Keep duration under 10 seconds
        stop_time = start_time + timedelta(seconds=duration)

        # Determine outcome first
        outcome = random.choice(list(TestOutcome))

        return TestResult(
            nodeid=nodeid,
            outcome=outcome,
            start_time=start_time,
            stop_time=stop_time,  # Set both stop_time and duration for consistency
            duration=duration,
            caplog="",  # Initialize with empty strings
            capstderr="",  # Will be populated by session fixture
            capstdout="",  # Will be populated by session fixture
            longreprtext="",  # Will be populated by session fixture
            has_warning=random.choice([True, False]),
        )

    return _create


@pytest.fixture
def random_rerun_test_group(random_test_result):
    """A factory fixture to create a random RerunTestGroup instance.

    Maintains session context by:
    1. Using consistent nodeid for all tests in group
    2. Preserving test relationships and timing
    3. Following proper outcome progression (RERUN → PASSED/FAILED)

    Supports pattern matching with nodeids:
    - "test_api.py::test_get_api"      # Matches 'api' in both parts
    - "test_api.py::test_post_api"     # Matches 'api' in both parts
    - "test_ui.py::test_get_ui"        # Matches 'get' in test name
    """

    def _create():
        # Use consistent nodeid for all tests in the group to maintain relationships
        module_types = ["api", "ui", "db", "auth"]
        module_name = random.choice(module_types)
        test_types = ["get", "post", "update", "delete", "list", "create"]
        test_name = random.choice(test_types)

        # Format: test_{module}.py::test_{action}_{module}
        # This format supports our pattern matching rules:
        # - Non-regex: Splits on :: into parts
        # - Module part: Strips .py before matching
        # - Test name part: Direct pattern match
        nodeid = f"test_{module_name}.py::test_{test_name}_{module_name}"

        num_reruns = random.randint(1, 3)  # Random number of reruns

        # Create rerun results - all with RERUN outcome
        rerun_results = []
        for _ in range(num_reruns):
            result = random_test_result()
            result.nodeid = nodeid  # Override with consistent nodeid
            result.outcome = TestOutcome.RERUN
            rerun_results.append(result)

        # Create final result with PASSED/FAILED
        final_result = random_test_result()
        final_result.nodeid = nodeid  # Override with consistent nodeid
        final_result.outcome = TestOutcome.from_str(random.choice(["PASSED", "FAILED"]))

        # Combine all results in chronological order
        all_results = rerun_results + [final_result]

        return RerunTestGroup(
            nodeid=nodeid,
            tests=all_results,  # Contains all results in order, with final result last
        )

    return _create


@pytest.fixture
def random_test_sessions(random_test_session):
    """Create a list of random test sessions.

    Each session is unique and contains multiple unique test results.
    """
    num_sessions = random.randint(1, 10)
    return [random_test_session() for _ in range(num_sessions)]


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
        return "".join(random.choice(string.ascii_lowercase) for _ in range(length))

    def _generate_path_parts(self):
        """Generate random path components."""
        num_parts = random.randint(0, 3)
        return [self._random_word() for _ in range(num_parts)]

    def _generate_filename(self):
        """Generate random Python filename."""
        return f"test_{self._random_word()}.py"

    def _generate_test_name(self):
        """Generate random test function name."""
        return f"test_{self._random_word()}"

    def _generate_params(self):
        """Generate random parameter string."""
        if random.choice([True, False]):
            return f"[{random.randint(0, 100)}]"
        return ""

    def path(self):
        """Get the full path including filename."""
        if self.path_parts:
            return str(Path(*self.path_parts, self.filename))
        return self.filename

    def full_name(self):
        """Get the complete NodeId."""
        parts = [self.path()]
        if self.test_name:
            parts.append(self.test_name)
        if self.params:
            parts[-1] += self.params
        return "::".join(parts)

    def __str__(self):
        return self.full_name()


@pytest.fixture
def nodeid():
    """Fixture that returns a NodeId instance."""
    return NodeId()


@pytest.fixture
def random_test_result_legacy(nodeid, text_gen):
    """Legacy version of random_test_result that uses NodeId."""

    def _create():
        outcome = random.choice(TestOutcome.to_list())
        start_time = datetime.now(timezone.utc)
        duration = random.uniform(0.1, 5.0)

        return TestResult(
            nodeid=str(nodeid),
            outcome=TestOutcome.from_str(outcome),
            start_time=start_time,
            duration=duration,
            caplog=text_gen.sentence(),
            capstderr=(text_gen.sentence() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else ""),
            capstdout=text_gen.sentence(),
            longreprtext=(text_gen.paragraph() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else ""),
            has_warning=random.choice([True, False]),
        )

    return _create
