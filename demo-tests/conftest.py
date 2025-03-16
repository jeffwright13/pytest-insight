"""Demo test fixtures."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


@pytest.fixture
def test_data():
    """Return test data fixture."""
    return {
        "id": "TEST-001",
        "timestamp": datetime.now(ZoneInfo("UTC")),
        "value": "test data",
        "status": "active"
    }


@pytest.fixture
def logger():
    """Provide a logger for the tests."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    return logger
