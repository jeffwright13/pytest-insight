"""Test data generation utilities for pytest-insight.

This module provides a centralized location for all test data generation code,
supporting both unit testing and development experimentation with the Query,
Compare, Analyze (QCA) system.

Key Features:
1. TextGenerator - Generate random text content
2. NodeId - Generate and manage pytest NodeIds
3. Factory functions for creating test data:
   - random_test_result
   - random_test_session
   - random_test_sessions
   - random_rerun_test_group
4. Timezone-aware datetime handling via get_test_time
"""

import random
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession


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


def get_test_time(offset_seconds: int = 0) -> datetime:
    """Get a test timestamp with optional offset.

    Args:
        offset_seconds: Number of seconds to add to base time

    Returns:
        A UTC datetime starting from 2023-01-01 plus the given offset in seconds.
        This provides consistent timestamps for test cases while avoiding any
        timezone issues.
    """
    base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


def random_test_result():
    """Create a random TestResult instance.

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
    # Generate nodeids that support our pattern matching rules
    module_types = ["api", "ui", "db", "auth"]
    module_name = random.choice(module_types)
    test_types = ["get", "post", "update", "delete", "list", "create"]
    test_name = random.choice(test_types)

    # Format: test_{module}.py::test_{action}_{module}
    nodeid = f"test_{module_name}.py::test_{test_name}_{module_name}"

    # Generate timing info - use smaller duration range
    start_time = get_test_time(random.randint(0, 3600))  # Random time within first hour
    duration = random.uniform(0.1, 10.0)  # Keep duration under 10 seconds

    # Determine outcome first
    outcome = random.choice(list(TestOutcome))

    text_gen = TextGenerator()
    caplog = text_gen.sentence()
    capstderr = (
        text_gen.sentence()
        if outcome in [TestOutcome.FAILED, TestOutcome.ERROR]
        else ""
    )
    capstdout = text_gen.sentence()
    longreprtext = (
        text_gen.paragraph()
        if outcome in [TestOutcome.FAILED, TestOutcome.ERROR]
        else ""
    )

    return TestResult(
        nodeid=nodeid,
        outcome=outcome,
        start_time=start_time,
        duration=duration,
        caplog=caplog,
        capstderr=capstderr,
        capstdout=capstdout,
        longreprtext=longreprtext,
        has_warning=random.choice([True, False]),
    )


def random_test_session():
    """Create a random TestSession instance.

    The session includes:
    1. Multiple test results from same module (preserves relationships)
    2. Optional rerun groups (25% chance)
    3. Consistent timing across all components
    4. Realistic tags based on module and environment
    """
    # Generate new random values each time the factory is called
    num_tests = random.randint(2, 6)  # More realistic test count
    include_rerun = random.choice(
        [True, False, False, False]
    )  # 25% chance of having reruns

    # Create base session time window for consistent timing
    base_time = get_test_time(random.randint(0, 3600))  # Random time within first hour
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
    text_gen = TextGenerator()

    # Generate multiple tests in the same module to show relationships
    for _ in range(num_tests):
        test_name = f"test_{random.choice(test_types)}_{module_name}"
        nodeid = f"{test_file}::{test_name}"

        outcome = random.choice(list(TestOutcome))
        caplog = text_gen.sentence()
        capstderr = (
            text_gen.sentence()
            if outcome in [TestOutcome.FAILED, TestOutcome.ERROR]
            else ""
        )
        capstdout = text_gen.sentence()
        longreprtext = (
            text_gen.paragraph()
            if outcome in [TestOutcome.FAILED, TestOutcome.ERROR]
            else ""
        )
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
                        ""
                        if not is_final or final_outcome == TestOutcome.PASSED
                        else "Test failed after reruns"
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
        sut_name=f"SUT-{module_name}",  # Match test expectations for SUT name format
        session_id=f"session-{random.randint(1, 1000)}",  # Match test expectations for session ID format
        session_start_time=session_start_time,
        session_stop_time=session_stop_time,
        test_results=test_results,
        rerun_test_groups=rerun_groups,  # Initialize with rerun groups
        session_tags={  # Use dict for session tags
            "module": module_name,
            "type": random.choice(["unit", "integration", "e2e"]),
            "env": random.choice(["dev", "staging", "prod"]),
        },
    )

    return session


def random_test_sessions(num_sessions=None):
    """Create multiple random TestSession instances.

    Args:
        num_sessions: Optional number of sessions to create. If None,
                     generates 1-10 sessions randomly.

    Returns:
        List of unique TestSession instances, each with its own test results
        and optional rerun groups.
    """
    if num_sessions is None:
        num_sessions = random.randint(1, 10)
    return [random_test_session() for _ in range(num_sessions)]


def random_rerun_test_group():
    """Create a random RerunTestGroup instance.

    Maintains session context by:
    1. Using consistent nodeid for all tests in group
    2. Preserving test relationships and timing
    3. Following proper outcome progression (RERUN → PASSED/FAILED)

    Supports pattern matching with nodeids:
    - "test_api.py::test_get_api"      # Module pattern
    - "test_api.py::test_post_api"     # Test name pattern
    - "test_api.py::TestApi::test_get" # Full path with class
    """
    # Generate test nodeids that support pattern matching rules
    module_types = ["api", "ui", "db", "auth"]
    module_name = random.choice(module_types)
    test_types = ["get", "post", "update", "delete", "list", "create"]

    # Create test nodeid with optional class
    test_name = f"test_{random.choice(test_types)}_{module_name}"
    test_file = f"test_{module_name}.py"

    # 30% chance to include a class in the nodeid
    if random.random() < 0.3:
        class_name = f"Test{random.choice(['Api', 'Ui', 'Db', 'Auth'])}"
        nodeid = f"{test_file}::{class_name}::{test_name}"
    else:
        nodeid = f"{test_file}::{test_name}"

    # Create rerun group
    group = RerunTestGroup(nodeid=nodeid)
    num_reruns = random.randint(1, 3)  # Random number of reruns
    current_time = get_test_time()  # Start time for first test
    text_gen = TextGenerator()

    # Generate rerun sequence with proper timing and outcomes
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

        # Generate test output based on outcome
        caplog = text_gen.sentence()
        capstderr = text_gen.sentence() if final_outcome == TestOutcome.FAILED else ""
        capstdout = text_gen.sentence()
        longreprtext = (
            text_gen.paragraph() if final_outcome == TestOutcome.FAILED else ""
        )
        has_warning = random.choice([True, False]) if is_final else False

        result = TestResult(
            nodeid=nodeid,
            outcome=final_outcome,
            start_time=current_time,
            duration=random.uniform(0.1, 5.0),
            caplog=caplog,
            capstderr=capstderr,
            capstdout=capstdout,
            longreprtext=longreprtext,
            has_warning=has_warning,
        )

        group.add_test(result)
        current_time = result.stop_time + timedelta(
            seconds=1
        )  # 1 second gap between reruns

    return group


def mock_test_result_pass():
    """Create a mock test result with PASSED outcome."""
    return TestResult(
        nodeid="test_feature.py::test_success",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),  # Use get_test_time for consistent timezone handling
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )


def mock_test_result_fail():
    """Create a mock test result with FAILED outcome."""
    return TestResult(
        nodeid="test_feature.py::test_failure",
        outcome=TestOutcome.FAILED,
        start_time=get_test_time(),  # Use get_test_time for consistent timezone handling
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )


def mock_test_result_skip():
    """Create a mock test result with SKIPPED outcome."""
    return TestResult(
        nodeid="test_feature.py::test_skipped",
        outcome=TestOutcome.SKIPPED,
        start_time=get_test_time(),  # Use get_test_time for consistent timezone handling
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )


def mock_test_result_xfail():
    """Create a mock test result with XFAILED outcome."""
    return TestResult(
        nodeid="test_feature.py::test_known_failure",
        outcome=TestOutcome.XFAILED,  # Fix: XFAIL -> XFAILED
        start_time=get_test_time(),  # Use get_test_time for consistent timezone handling
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )


def mock_test_result_xpass():
    """Create a mock test result with XPASSED outcome."""
    return TestResult(
        nodeid="test_feature.py::test_unexpected_pass",
        outcome=TestOutcome.XPASSED,
        start_time=get_test_time(),  # Use get_test_time for consistent timezone handling
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )


def mock_test_result_error():
    """Create a mock test result with ERROR outcome."""
    return TestResult(
        nodeid="test_feature.py::test_error",
        outcome=TestOutcome.ERROR,
        start_time=get_test_time(),  # Use get_test_time for consistent timezone handling
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
    )


def mock_test_result_warning():
    """Create a mock test result with warning."""
    return TestResult(
        nodeid="test_feature.py::test_warning",
        outcome=TestOutcome.PASSED,
        start_time=get_test_time(),  # Use get_test_time for consistent timezone handling
        duration=0.1,
        caplog="",
        capstderr="",
        capstdout="",
        longreprtext="",
        has_warning=True,
    )


def mock_test_session():
    """Create a mock test session with all possible test outcomes.

    Uses get_test_time() to ensure consistent timezone-aware timestamps.
    All test results in the session have proper timing relationships:
    1. Session start = First test start
    2. Each test starts after the previous one
    3. Session stop = Last test stop + buffer
    """
    # Get base time for first test
    base_time = get_test_time()
    current_time = base_time

    # Create test results with sequential timing
    test_results = []
    for mock_fn in [
        mock_test_result_pass,
        mock_test_result_fail,
        mock_test_result_skip,
        mock_test_result_xfail,
        mock_test_result_xpass,
        mock_test_result_error,
        mock_test_result_warning,
    ]:
        result = mock_fn()
        result.start_time = current_time
        test_results.append(result)
        current_time += timedelta(
            seconds=result.duration + 0.1
        )  # Add small gap between tests

    return TestSession(
        sut_name="test_sut",
        session_id="test-123",
        session_start_time=base_time,  # Same as first test
        session_stop_time=current_time
        + timedelta(seconds=0.5),  # Add buffer after last test
        test_results=test_results,
        rerun_test_groups=[],
    )
