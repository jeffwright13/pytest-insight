import pytest

from pytest_insight.storage import InMemoryStorage

@pytest.fixture
def storage():
    """Provide clean in-memory storage for each test."""
    return InMemoryStorage()


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
def base_time():
    """Provide consistent timestamp for tests."""
    return datetime.now()


@pytest.fixture
def random_test_session(base_time):
    """Provide a test session with random results."""
    results = [
        TestResult(
            nodeid=f"test_{i}.py::test_func",
            outcome=random.choice(["passed", "failed", "skipped"]),
            start_time=base_time - timedelta(minutes=i),
            duration=random.uniform(0.5, 3.0),
            caplog="",
            capstderr="",
            capstdout="",
            longreprtext=""
        )
        for i in range(3)
    ]

    return TestSession(
        sut_name="random-sut",
        session_id=f"random-session-{random.randint(1000, 9999)}",
        session_start_time=base_time,
        session_duration=sum(r.duration for r in results),
        test_results=results,
        rerun_test_groups=[],
        session_tags={}
    )


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


@pytest.fixture
def test_results(base_time):
    """Provide a list of test results with known patterns."""
    return [
        TestResult(
            nodeid=f"test_api.py::test_{i}",
            outcome="passed",
            start_time=base_time - timedelta(minutes=i),  # Changed from start_time
            duration=1.0 + (i * 0.5),
            caplog="",
            capstderr="",
            capstdout="",
            longreprtext=""
        )
        for i in range(3)
    ]


@pytest.fixture
def test_session(test_results, base_time):
    """Provide a test session with known results."""
    return TestSession(
        sut_name="test-api",
        session_id="test-session-1",
        session_start_time=base_time,
        session_duration=10.0,
        test_results=test_results
    )
