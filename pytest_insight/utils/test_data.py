"""Test data generation utilities for pytest-insight (modern version).

This module provides centralized test data factories and helpers for unit/integration
tests and development scripts, ensuring all generated data is valid for the current model.
"""

import random
import string
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pytest_insight.core.models import (
    RerunTestGroup,
    TestOutcome,
    TestResult,
    TestSession,
)


class TextGenerator:
    """Generate random text content for testing."""

    WORD_LENGTH_RANGE = (3, 10)
    WORDS_PER_SENTENCE = (5, 15)
    SENTENCES_PER_PARAGRAPH = (3, 7)

    @staticmethod
    def word() -> str:
        length = random.randint(*TextGenerator.WORD_LENGTH_RANGE)
        return "".join(random.choices(string.ascii_lowercase, k=length))

    @staticmethod
    def sentence() -> str:
        return " ".join(TextGenerator.word() for _ in range(random.randint(*TextGenerator.WORDS_PER_SENTENCE))) + "."

    @staticmethod
    def paragraph() -> str:
        return " ".join(TextGenerator.sentence() for _ in range(random.randint(*TextGenerator.SENTENCES_PER_PARAGRAPH)))


class NodeId:
    """Generate and manage pytest NodeIds."""

    @staticmethod
    def random(module: str = None) -> str:
        module = module or TextGenerator.word()
        cls = TextGenerator.word().capitalize()
        func = TextGenerator.word()
        return f"{module}.py::{cls}::{func}"


def get_test_time(offset: int = 0, tz_aware: bool = True) -> datetime:
    """Return a timezone-aware or naive datetime for testing, offset by N seconds."""
    base = datetime(2025, 1, 1, 12, 0, 0)
    if tz_aware:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(seconds=offset)


def random_test_result(
    outcome: Optional[TestOutcome] = None,
    duration: Optional[float] = None,
    nodeid: Optional[str] = None,
    start_time: Optional[datetime] = None,
    stop_time: Optional[datetime] = None,
    caplog: Optional[str] = None,
    capstderr: Optional[str] = None,
    capstdout: Optional[str] = None,
    longreprtext: Optional[str] = None,
    has_warning: Optional[bool] = None,
) -> TestResult:
    """Generate a random TestResult with valid required fields (matches current model)."""
    outcome = outcome or random.choice(list(TestOutcome))
    duration = duration or random.uniform(0.01, 10.0)
    nodeid = nodeid or NodeId.random()
    start_time = start_time or get_test_time()
    stop_time = stop_time or (start_time + timedelta(seconds=duration))
    caplog = caplog if caplog is not None else TextGenerator.sentence()
    capstderr = capstderr if capstderr is not None else ""
    capstdout = capstdout if capstdout is not None else ""
    longreprtext = longreprtext if longreprtext is not None else ""
    has_warning = has_warning if has_warning is not None else False
    return TestResult(
        nodeid=nodeid,
        outcome=outcome,
        start_time=start_time,
        stop_time=stop_time,
        duration=duration,
        caplog=caplog,
        capstderr=capstderr,
        capstdout=capstdout,
        longreprtext=longreprtext,
        has_warning=has_warning,
    )


def random_test_results(count: int = 3) -> List[TestResult]:
    """Generate a list of random TestResult objects."""
    return [random_test_result() for _ in range(count)]


def random_rerun_test_group() -> RerunTestGroup:
    """Generate a random RerunTestGroup (modern signature)."""
    tests = random_test_results(random.randint(2, 4))
    nodeid = tests[0].nodeid if tests else NodeId.random()
    return RerunTestGroup(
        nodeid=nodeid,
        tests=tests,
    )


def random_test_session(
    session_id: Optional[str] = None,
    sut_name: Optional[str] = None,
    num_results: int = 3,
    tz_aware: bool = True,
) -> TestSession:
    """Generate a random TestSession with valid required fields."""
    session_id = session_id or f"sess-{random.randint(1000,9999)}"
    sut_name = sut_name or TextGenerator.word()
    start_time = get_test_time(0, tz_aware)
    duration = random.uniform(1.0, 60.0)
    stop_time = start_time + timedelta(seconds=duration)
    results = random_test_results(num_results)
    return TestSession(
        session_id=session_id,
        sut_name=sut_name,
        session_start_time=start_time,
        session_stop_time=stop_time,
        session_duration=duration,
        test_results=results,
        rerun_test_groups=[random_rerun_test_group()],
        session_tags={},
        testing_system={},
    )


def random_test_sessions(count: int = 2) -> List[TestSession]:
    """Generate a list of random TestSession objects."""
    return [random_test_session() for _ in range(count)]
