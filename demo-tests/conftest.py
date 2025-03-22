"""Demo test fixtures."""

import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

data = """Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo."""

# Pre-split once to avoid redoing on every fixture call
_sentences = [s.strip() for s in data.split(".") if s.strip()]


@pytest.fixture
def fake_data() -> str:
    base = random.choice(_sentences)
    punctuation = random.choice([".", ";", "?"])
    return base + punctuation


@pytest.fixture
def test_data():
    """Return test data fixture."""
    return {
        "id": "TEST-001",
        "timestamp": datetime.now(ZoneInfo("UTC")),
        "value": "test data",
        "status": "active",
    }


@pytest.fixture
def logger():
    """Provide a logger for the tests."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    return logger
