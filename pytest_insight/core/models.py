"""TestSession and TestResult models."""

from typing import List, Optional
from datetime import datetime

class TestResult:
    def __init__(self, nodeid: str, outcome: str, start_time: datetime, stop_time: datetime, duration: float):
        self.nodeid = nodeid
        self.outcome = outcome
        self.start_time = start_time
        self.stop_time = stop_time
        self.duration = duration

class TestSession:
    def __init__(self, session_id: str, session_start_time: datetime, outcome: Optional[str], test_results: List[TestResult]):
        self.session_id = session_id
        self.session_start_time = session_start_time
        self.outcome = outcome
        self.test_results = test_results
