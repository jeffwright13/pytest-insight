import logging
from datetime import datetime

import pytest


@pytest.fixture
def fake_data():
    """Return canned test data."""
    return {"id": "TEST-001", "timestamp": datetime.now(), "value": "test data", "status": "active"}


@pytest.fixture
def logger():
    """Provide a logger for the tests."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    return logger
