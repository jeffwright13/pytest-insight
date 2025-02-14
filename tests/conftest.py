import random
import string
from datetime import datetime, timedelta
from importlib.metadata import version

import pytest
from pytest_insight.models import (
    OutputFields,
    OutputFieldType,
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
def random_rerun_test_group(nodeid):
    """Fixture to generate a random RerunTestGroup object."""
    final_outcome = random.choice(["PASSED", "FAILED"])
    group = RerunTestGroup(nodeid=str(nodeid), final_outcome=final_outcome)
    num_reruns = random.randint(1, 5)

    for _ in range(num_reruns):
        result = TestResult(
            nodeid=str(nodeid),
            outcome=random.choice(["PASSED", "FAILED"]),
            start_time=datetime.utcnow() - timedelta(minutes=random.randint(1, 60)),
            duration=random.uniform(0.1, 5.0),
            caplog="Log output",
            capstderr="Error output" if random.choice([True, False]) else "",
            capstdout="Standard output",
            longreprtext="Traceback details" if random.choice([True, False]) else "",
            has_warning=random.choice([True, False]),
        )
        group.reruns.append(result)
        group.full_test_list.append(result)

    return group


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
    """Fixture to generate a random TestResult object with realistic properties."""
    # Extract outcomes and weights
    outcomes = list(TEST_OUTCOMES.keys())
    weights = [data["weight"] for data in TEST_OUTCOMES.values()]

    # Generate timestamps within last 2 minutes
    start_time = datetime.utcnow() - timedelta(seconds=random.randint(1, 120))
    duration = random.uniform(0.1, 5.0)

    # Select outcome using weights
    outcome = random.choices(outcomes, weights=weights, k=1)[0]
    outcome_config = TEST_OUTCOMES[outcome]

    # Generate appropriate output based on outcome
    result = TestResult(
        nodeid=str(nodeid),
        outcome=outcome,
        start_time=start_time,
        duration=duration,
        caplog=text_gen.sentence(),
        capstderr=text_gen.sentence() if outcome_config["needs_error_output"] else "",
        capstdout=text_gen.sentence(),
        longreprtext=(
            text_gen.paragraph() if outcome_config["needs_error_output"] else ""
        ),
        has_warning=(
            random.choice([True, False])
            if outcome_config["can_have_warning"]
            else False
        ),
    )

    return result


@pytest.fixture
def random_output_fields(text_gen):
    """Fixture to generate random OutputFields."""
    fields = OutputFields()
    for _ in range(random.randint(1, 5)):
        key = random.choice(list(OutputFieldType))
        fields.set(key, text_gen.paragraph())
    return fields


@pytest.fixture
def random_test_session(nodeid, text_gen, random_output_fields):
    """Fixture to generate a random TestSession object."""
    sut_name = f"SUT-{random.randint(1, 10)}"
    session_id = f"session-{random.randint(100, 999)}"

    # Create base session time window
    base_time = datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
    session_start_time = base_time
    session_stop_time = base_time + timedelta(seconds=random.randint(30, 300))
    session_duration = session_stop_time - session_start_time

    # Generate unique test results
    session_test_results = []
    for _ in range(random.randint(2, 6)):
        result = TestResult(
            nodeid=str(nodeid),
            outcome=random.choices(
                ["PASSED", "FAILED", "SKIPPED", "XFAILED", "XPASSED", "RERUN", "ERROR"],
                weights=[70, 15, 5, 3, 2, 3, 2],
                k=1,
            )[0],
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
        group = RerunTestGroup(
            nodeid=str(nodeid), final_outcome=random.choice(["PASSED", "FAILED"])
        )
        for _ in range(random.randint(1, 4)):
            result = TestResult(
                nodeid=str(nodeid),
                outcome=random.choice(["PASSED", "FAILED"]),
                start_time=session_start_time
                + timedelta(seconds=random.randint(1, 30)),
                duration=random.uniform(0.1, 5.0),
                caplog=text_gen.sentence(),
                capstderr=text_gen.sentence(),
                capstdout=text_gen.sentence(),
                longreprtext=text_gen.paragraph(),
                has_warning=random.choice([True, False]),
            )
            group.reruns.append(result)
            group.full_test_list.append(result)
        session_rerun_test_groups.append(group)

    session = TestSession(
        sut_name=sut_name,
        session_id=session_id,
        session_start_time=session_start_time,
        session_stop_time=session_stop_time,
        session_duration=session_duration,
    )
    session.test_results = session_test_results
    session.rerun_test_groups = session_rerun_test_groups
    session.output_fields = random_output_fields
    session.session_tags = {"key": text_gen.word()}

    return session
