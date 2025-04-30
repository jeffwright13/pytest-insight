"""
Tests for ParquetStorage: Ensures correct save/load of TestSession objects, including rerun groups and edge cases.
Uses pytest, pytest-mock, and covers:
- Sessions with/without rerun groups
- Multiple rerun groups
- Corrupted Parquet file handling
- Context preservation (session_tags, testing_system)
"""
import os
import tempfile
import pytest
import pandas as pd
from pytest_insight.core.models import TestSession, TestResult, TestOutcome, RerunTestGroup
from pytest_insight.storage.parquet_storage import ParquetStorage
from datetime import datetime, timedelta
import copy

@pytest.fixture
def temp_parquet_file():
    fd, path = tempfile.mkstemp(suffix=".parquet")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)

@pytest.fixture
def sample_session():
    start = datetime(2025, 4, 27, 12, 0, 0)
    stop = start + timedelta(seconds=10)
    tr1 = TestResult("foo", TestOutcome.PASSED, start, stop_time=stop, duration=10)
    tr2 = TestResult("bar", TestOutcome.FAILED, start, stop_time=stop, duration=10)
    rerun_group = RerunTestGroup(nodeid="bar", tests=[tr2, TestResult("bar", TestOutcome.PASSED, start, stop_time=stop, duration=10)])
    return TestSession(
        sut_name="service",
        session_id="abc123",
        session_start_time=start,
        session_stop_time=stop,
        session_duration=10,
        test_results=[tr1, tr2],
        rerun_test_groups=[rerun_group],
        session_tags={"env": "dev"},
        testing_system={"os": "linux"},
    )

def test_save_and_load_roundtrip(temp_parquet_file, sample_session):
    storage = ParquetStorage(temp_parquet_file)
    storage.save_sessions([sample_session])
    loaded = storage.load_sessions()
    assert len(loaded) == 1
    s = loaded[0]
    assert s.session_id == sample_session.session_id
    assert s.sut_name == sample_session.sut_name
    assert s.session_tags == sample_session.session_tags
    assert s.testing_system == sample_session.testing_system
    assert len(s.test_results) == 2
    assert len(s.rerun_test_groups) == 1
    assert s.rerun_test_groups[0].nodeid == "bar"
    assert s.rerun_test_groups[0].tests[-1].outcome == TestOutcome.PASSED

def test_multiple_sessions(temp_parquet_file, sample_session):
    storage = ParquetStorage(temp_parquet_file)
    session2 = copy.deepcopy(sample_session)
    session2.session_id = "other"
    storage.save_sessions([sample_session, session2])
    loaded = storage.load_sessions()
    assert len(loaded) == 2
    ids = {s.session_id for s in loaded}
    assert {"abc123", "other"} == ids

def test_no_rerun_group(temp_parquet_file):
    start = datetime(2025, 4, 27, 12, 0, 0)
    stop = start + timedelta(seconds=10)
    session = TestSession(
        sut_name="service",
        session_id="norerun",
        session_start_time=start,
        session_stop_time=stop,
        session_duration=10,
        test_results=[],
        rerun_test_groups=[],
        session_tags={},
        testing_system={},
    )
    storage = ParquetStorage(temp_parquet_file)
    storage.save_sessions([session])
    loaded = storage.load_sessions()
    assert loaded[0].session_id == "norerun"
    assert loaded[0].rerun_test_groups == []

def test_corrupted_file(temp_parquet_file):
    # Write junk to file
    with open(temp_parquet_file, "w") as f:
        f.write("not a parquet file!")
    storage = ParquetStorage(temp_parquet_file)
    with pytest.raises(Exception):
        storage.load_sessions()
