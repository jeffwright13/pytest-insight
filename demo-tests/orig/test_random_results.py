import random
from dataclasses import dataclass

import pytest

OUTCOMES = [
    "failed",
    "passed",
    "skipped",
    "xfailed",
    "xpassed",
    "warning",
    "error",
    "rerun",
]
WEIGHTS = [0.15, 0.60, 0.05, 0.03, 0.02, 0.07, 0.03, 0.05]


@pytest.fixture
def random_result_loglevel():
    @dataclass
    class Result:
        outcome: str
        log_msg: str
        log_level: str

    choice = random.choices(OUTCOMES, WEIGHTS)[0]
    if choice == "passed":
        return Result(
            outcome=choice, log_msg="Passed: Blah blah blah ...", log_level="info"
        )
    elif choice == "failed":
        return Result(
            outcome=choice, log_msg="Failed: Blah blah blah ...", log_level="error"
        )
    elif choice == "skipped":
        return Result(
            outcome=choice, log_msg="Skipped: Blah blah blah ...", log_level="info"
        )
    elif choice == "xfailed":
        return Result(
            outcome=choice, log_msg="XFailed: Blah blah blah ...", log_level="info"
        )
    elif choice == "xpassed":
        return Result(
            outcome=choice, log_msg="XPassed: Blah blah blah ...", log_level="info"
        )
    elif choice == "warning":
        return Result(
            outcome=choice, log_msg="Warning: Blah blah blah ...", log_level="warning"
        )
    elif choice == "error":
        return Result(
            outcome=choice, log_msg="Error: Blah blah blah ...", log_level="error"
        )
    elif choice == "rerun":
        return Result(
            outcome=choice, log_msg="Rerun: Blah blah blah ...", log_level="info"
        )
