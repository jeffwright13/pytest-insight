import random
import string
from datetime import datetime, timedelta

import pytest
from pytest_insight.models import (
    RerunTestGroup,
    TestHistory,
    TestOutcome,
    TestResult,
    TestSession,
)


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
            outcome=random.choice(list(TestOutcome)),  # Use enum values
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
            nodeid=str(nodeid), final_outcome=random.choice([TestOutcome.PASSED, TestOutcome.FAILED])
        )
        for _ in range(random.randint(1, 4)):
            result = TestResult(
                nodeid=str(nodeid),
                outcome=random.choice([TestOutcome.PASSED, TestOutcome.FAILED]),
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


@pytest.fixture
def random_test_result(nodeid, text_gen):
    """Generate a random TestResult instance."""
    node_id = str(nodeid)
    # Use the Enum directly instead of converting to string
    outcome = random.choice(list(TestOutcome))
    start_time = datetime.utcnow()

    # Remove trailing commas to prevent tuple creation
    caplog = "" if random.choice([True, False]) else text_gen.sentence()
    capstderr = ""
    capstdout = ""
    longreprtext = ""
    has_warning = random.choice([True, False])

    if random.choice(["duration", "stop_time"]) == "duration":
        return TestResult(
            nodeid=node_id,
            outcome=outcome,  # Pass Enum directly
            start_time=start_time,
            duration=random.uniform(1, 30),
            caplog=caplog,
            capstderr=capstderr,
            capstdout=capstdout,
            longreprtext=longreprtext,
            has_warning=has_warning,
        )
    else:
        return TestResult(
            nodeid=node_id,
            outcome=outcome,  # Pass Enum directly
            start_time=start_time,
            stop_time=start_time + timedelta(seconds=random.randint(1, 30)),
            caplog=caplog,
            capstderr=capstderr,
            capstdout=capstdout,
            longreprtext=longreprtext,
            has_warning=has_warning,
        )


# ------------------------------^^^ Fixtures ^^^------------------------------ #


# ------------------------------vvv Tests vvv -------------------------------- #
class Test_TestOutcome:
    """Test the TestOutcome enum."""

    def test_test_outcome_enum(self):
        """Test TestOutcome enum functionality."""
        # Test creation from string
        assert TestOutcome.from_str("PASSED") == TestOutcome.PASSED
        assert TestOutcome.from_str("passed") == TestOutcome.PASSED

        # Test string representation matches serialization format
        assert TestOutcome.FAILED.to_str() == "failed"

    def test_test_outcome_case_handling(self):
        """Test TestOutcome enum handles case conversion correctly."""
        # Verify from_str() always creates uppercase internal values
        assert TestOutcome.from_str("passed").value == "PASSED"
        assert TestOutcome.from_str("PASSED").value == "PASSED"
        assert TestOutcome.from_str("PaSsEd").value == "PASSED"

        # Verify to_str() always returns lowercase
        assert TestOutcome.PASSED.to_str() == "passed"
        assert TestOutcome.FAILED.to_str() == "failed"
        assert TestOutcome.RERUN.to_str() == "rerun"

        # Verify raw enum values remain uppercase
        assert TestOutcome.PASSED.value == "PASSED"
        assert str(TestOutcome.PASSED) == "TestOutcome.PASSED"

    def test_test_outcome_invalid_values(self):
        """Test TestOutcome enum handles invalid values appropriately."""
        with pytest.raises(ValueError) as exc:
            TestOutcome.from_str("INVALID")
        assert "Invalid test outcome: INVALID" in str(exc.value)

        with pytest.raises(ValueError) as exc:
            TestOutcome.from_str("")
        assert "Invalid test outcome: " in str(exc.value)


class Test_TestResult:
    """Test the TestResult model."""

    def test_random_test_results(self, random_test_result):
        """Test the random_test_result fixture's properties."""

        assert random_test_result.nodeid != ""
        assert isinstance(random_test_result.nodeid, str)
        assert random_test_result.outcome in TestOutcome

        assert isinstance(random_test_result.start_time, datetime)
        if hasattr(random_test_result, "stop_time"):
            assert isinstance(random_test_result.stop_time, datetime)
        if hasattr(random_test_result, "duration"):
            assert isinstance(random_test_result.duration, float)
        assert isinstance(random_test_result.has_warning, bool)

        # Fields that can be empty but must be strings
        assert isinstance(random_test_result.caplog, str)
        assert isinstance(random_test_result.capstderr, str)
        assert isinstance(random_test_result.capstdout, str)
        assert isinstance(random_test_result.longreprtext, str)

    def test_test_result_with_enum(self, nodeid):
        """Test TestResult with TestOutcome enum."""
        result = TestResult(
            nodeid=str(nodeid),
            outcome=TestOutcome.PASSED,
            start_time=datetime.utcnow(),
            duration=1.0,  # Add required duration
        )
        assert result.outcome == TestOutcome.PASSED
        assert isinstance(result.outcome, TestOutcome)

        # Test string conversion
        result = TestResult(
            nodeid=str(nodeid),
            outcome=TestOutcome.FAILED,
            start_time=datetime.utcnow(),
            duration=1.0,  # Add required duration
        )
        assert isinstance(result.outcome, TestOutcome)
        assert result.outcome == TestOutcome.FAILED

    def test_test_result_to_dict(self, random_test_result):
        """Test the to_dict method of the TestResult model."""
        result_dict = random_test_result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["nodeid"] == random_test_result.nodeid
        assert result_dict["outcome"] == random_test_result.outcome.to_str()  # Use to_str() consistently
        assert result_dict["start_time"] == random_test_result.start_time.isoformat()
        assert result_dict["duration"] == random_test_result.duration
        assert result_dict["caplog"] == random_test_result.caplog
        assert result_dict["capstderr"] == random_test_result.capstderr
        assert result_dict["capstdout"] == random_test_result.capstdout
        assert result_dict["longreprtext"] == random_test_result.longreprtext
        assert result_dict["has_warning"] == random_test_result.has_warning

    def test_test_result_from_dict(self, random_test_result):
        """Test the from_dict method of the TestResult model."""
        result_dict = random_test_result.to_dict()
        result = TestResult.from_dict(result_dict)

        assert isinstance(result, TestResult)
        assert result.nodeid == random_test_result.nodeid
        assert result.outcome == random_test_result.outcome
        assert result.start_time == random_test_result.start_time

        # Use pytest.approx for floating-point comparison
        assert result.duration == pytest.approx(random_test_result.duration)

        assert result.caplog == random_test_result.caplog
        assert result.capstderr == random_test_result.capstderr
        assert result.capstdout == random_test_result.capstdout
        assert result.longreprtext == random_test_result.longreprtext
        assert result.has_warning == random_test_result.has_warning

    # def test_test_result_timing_calculations(self):
    #     """Test that timing values are calculated correctly on initialization."""
    #     now = datetime.now()

    #     # Test initialization with duration
    #     result1 = TestResult(
    #         nodeid="test_example.py::test_case",
    #         outcome=TestOutcome.PASSED,
    #         start_time=now,
    #         duration=5.0,
    #     )
    #     assert result1.stop_time == now + timedelta(seconds=5.0)
    #     assert result1.duration == 5.0

    #     # Test initialization with stop_time
    #     stop_time = now + timedelta(seconds=10.0)
    #     result2 = TestResult(
    #         nodeid="test_example.py::test_case",
    #         outcome=TestOutcome.PASSED,
    #         start_time=now,
    #         stop_time=stop_time,
    #     )
    #     assert result2.stop_time == stop_time
    #     assert result2.duration == 10.0

    def test_test_result_timing_calculations(self):
        """Test TestResult handles timing calculations correctly."""
        now = datetime.utcnow()

        # Test with duration provided
        result1 = TestResult(nodeid="test_a.py::test_1", outcome=TestOutcome.PASSED, start_time=now, duration=1.5)
        assert result1.stop_time == now + timedelta(seconds=1.5)

        # Test with stop_time provided
        result2 = TestResult(
            nodeid="test_a.py::test_1",
            outcome=TestOutcome.PASSED,
            start_time=now,
            stop_time=now + timedelta(seconds=2.0),
        )
        assert result2.duration == 2.0

        # Test invalid initialization
        with pytest.raises(ValueError) as exc:
            TestResult(nodeid="test_a.py::test_1", outcome=TestOutcome.PASSED, start_time=now)
        assert "Either stop_time or duration must be provided" in str(exc.value)


class test_TestSession:
    """Test the TestSession model."""

    def test_random_test_session(self, random_test_session):
        """Test the random_test_session fixxture's properties and methods."""
        assert isinstance(random_test_session.sut_name, str) and random_test_session.sut_name.startswith("SUT-")
        assert isinstance(random_test_session.session_id, str) and random_test_session.session_id.startswith("session-")

        assert isinstance(random_test_session.session_start_time, datetime)
        assert isinstance(random_test_session.session_stop_time, datetime)
        assert isinstance(random_test_session.session_duration, timedelta)
        assert random_test_session.session_stop_time > random_test_session.session_start_time

        # Ensure test results and rerun groups are populated
        assert len(random_test_session.test_results) >= 2
        assert len(random_test_session.rerun_test_groups) >= 1

        # Test outcome categorization
        outcomes = {test.outcome for test in random_test_session.test_results}
        warnings = any(test.has_warning for test in random_test_session.test_results)

        # Verify we have at least one test result with a meaningful outcome
        assert any(
            [
                TestOutcome.PASSED in outcomes,
                TestOutcome.FAILED in outcomes,
                TestOutcome.SKIPPED in outcomes,
                TestOutcome.FAILED in outcomes,
                TestOutcome.XPASSED in outcomes,
                TestOutcome.RERUN in outcomes,
                TestOutcome.ERROR in outcomes,
                warnings,
            ]
        )

    def test_test_session(self):
        """Test basic TestSession functionality."""
        start_time = datetime.utcnow()
        stop_time = start_time + timedelta(seconds=10)

        session = TestSession(
            sut_name="SUT-1",
            session_id="session-123",
            session_start_time=start_time,
            session_stop_time=stop_time,
        )

        # Add test results
        for _ in range(5):
            session.add_test_result(
                TestResult(
                    nodeid="test_pass",
                    outcome=TestOutcome.PASSED,
                    start_time=start_time,
                    duration=0.1,
                )
            )

        assert len(session.test_results) == 5
        assert session.session_duration.total_seconds() == 10.0

    def test_test_session_tags(self):
        """Test session tags functionality."""
        session = TestSession(
            sut_name="SUT-1",
            session_id="session-123",
            session_start_time=datetime.utcnow(),
            session_stop_time=datetime.utcnow(),
        )

        session.add_tag("environment", "dev")
        session.add_tag("platform", "linux")
        session.add_tag("python_version", "3.8")

        assert session.session_tags == {
            "environment": "dev",
            "platform": "linux",
            "python_version": "3.8",
        }

    def test_test_session_to_dict(self, random_test_session):
        """Test the to_dict method of the TestSession model."""
        session_dict = random_test_session.to_dict()
        assert isinstance(session_dict, dict)
        assert session_dict["sut_name"] == random_test_session.sut_name
        assert session_dict["session_id"] == random_test_session.session_id
        assert session_dict["session_start_time"] == random_test_session.session_start_time.isoformat()
        assert session_dict["session_stop_time"] == random_test_session.session_stop_time.isoformat()
        assert session_dict["session_duration"] == random_test_session.session_duration.total_seconds()
        assert len(session_dict["test_results"]) == len(random_test_session.test_results)
        assert len(session_dict["rerun_test_groups"]) == len(random_test_session.rerun_test_groups)
        assert session_dict["session_tags"] == random_test_session.session_tags

    def test_test_session_from_dict(self, random_test_session):
        """Test the from_dict method of the TestSession model."""
        session_dict = random_test_session.to_dict()
        session = TestSession.from_dict(session_dict)
        assert isinstance(session, TestSession)
        assert session.sut_name == random_test_session.sut_name
        assert session.session_id == random_test_session.session_id
        assert session.session_start_time == random_test_session.session_start_time
        assert session.session_stop_time == random_test_session.session_stop_time
        assert session.session_duration == random_test_session.session_duration
        assert len(session.test_results) == len(random_test_session.test_results)
        assert len(session.rerun_test_groups) == len(random_test_session.rerun_test_groups)
        assert session.session_tags == random_test_session.session_tags

    def test_test_session_serialization(self):
        """Test TestSession serialization to dictionary."""
        now = datetime.utcnow()
        session = TestSession(
            sut_name="test-app",
            session_id="session-123",
            session_start_time=now,
            session_stop_time=now + timedelta(minutes=1),
            test_results=[
                TestResult(nodeid="test_a.py::test_1", outcome=TestOutcome.PASSED, start_time=now, duration=1.0)
            ],
            session_tags={"env": "test"},
        )

        data = session.to_dict()
        assert data["sut_name"] == "test-app"
        assert data["session_id"] == "session-123"
        assert isinstance(data["session_start_time"], str)
        assert isinstance(data["session_stop_time"], str)
        assert isinstance(data["test_results"], list)
        assert data["session_tags"] == {"env": "test"}


class Test_RerunTestGroup:
    """Test the RerunTestGroup model."""

    def test_rerun_test_group(self):
        """Test RerunTestGroup functionality."""
        now = datetime.utcnow()
        group = RerunTestGroup(nodeid="test_example.py::test_case")

        # Create test results in chronological order
        result1 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=0.5,
        )
        result2 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.PASSED,
            start_time=now + timedelta(seconds=1),
            duration=0.7,
        )

        # Add tests in order
        group.add_test(result1)
        group.add_test(result2)

        assert group.nodeid == "test_example.py::test_case"
        assert group.final_outcome == TestOutcome.PASSED
        assert len(group.tests) == 2
        assert group.tests == [result1, result2]

    def test_rerun_test_group_to_dict(self):
        """Test the to_dict method of the RerunTestGroup model."""
        now = datetime.utcnow()
        group = RerunTestGroup(nodeid="test_example.py::test_case")

        result1 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=0.5,
        )
        result2 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.PASSED,
            start_time=now + timedelta(seconds=1),
            duration=0.7,
        )

        group.add_test(result1)
        group.add_test(result2)

        group_dict = group.to_dict()
        assert isinstance(group_dict, dict)
        assert group_dict["nodeid"] == group.nodeid
        assert len(group_dict["tests"]) == 2
        assert group_dict["tests"][0]["outcome"] == "rerun"
        assert group_dict["tests"][1]["outcome"] == "passed"

    def test_rerun_test_group_from_dict(self):
        """Test the from_dict method of the RerunTestGroup model."""
        now = datetime.utcnow()
        group = RerunTestGroup(nodeid="test_example.py::test_case")

        result1 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.RERUN,
            start_time=now,
            duration=0.5,
        )
        result2 = TestResult(
            nodeid="test_example.py::test_case",
            outcome=TestOutcome.PASSED,
            start_time=now + timedelta(seconds=1),
            duration=0.7,
        )

        group.add_test(result1)
        group.add_test(result2)

        # Test serialization/deserialization
        group_dict = group.to_dict()
        new_group = RerunTestGroup.from_dict(group_dict)

        assert isinstance(new_group, RerunTestGroup)
        assert new_group.nodeid == group.nodeid
        assert new_group.final_outcome == TestOutcome.PASSED
        assert len(new_group.tests) == 2
        assert new_group.tests[0].outcome == TestOutcome.RERUN
        assert new_group.tests[1].outcome == TestOutcome.PASSED


class Test_TestHistory:
    """Test the TestHistory model."""

    def test_test_history(self):
        """Test TestHistory functionality."""
        history = TestHistory()
        now = datetime.utcnow()
        stop_time1 = now + timedelta(seconds=5)
        stop_time2 = now + timedelta(seconds=20)

        session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
        session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

        history.add_test_session(session1)
        history.add_test_session(session2)

        assert len(history.sessions) == 2
        assert history.latest_session() == session2

    def test_test_history_sessions_property(self):
        """Test the sessions property."""
        history = TestHistory()
        assert history.sessions == []

        session = TestSession("SUT-1", "session-001", datetime.utcnow(), datetime.utcnow(), [], [])
        history.add_test_session(session)

        assert history.sessions == [session]

    def test_test_history_add_test_session(self):
        """Test the add_test_session method."""
        history = TestHistory()
        now = datetime.utcnow()
        stop_time1 = now + timedelta(seconds=5)
        stop_time2 = now + timedelta(seconds=20)

        session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
        session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

        history.add_test_session(session1)
        history.add_test_session(session2)

        assert len(history.sessions) == 2
        assert history.latest_session() == session2

    def test_test_history_latest_session(self):
        """Test the latest_session method."""
        history = TestHistory()
        now = datetime.utcnow()
        stop_time1 = now + timedelta(seconds=5)
        stop_time2 = now + timedelta(seconds=20)

        session1 = TestSession("SUT-1", "session-001", now, stop_time1, [], [])
        session2 = TestSession("SUT-1", "session-002", now + timedelta(seconds=10), stop_time2, [], [])

        history.add_test_session(session1)
        history.add_test_session(session2)

        assert history.latest_session() == session2
