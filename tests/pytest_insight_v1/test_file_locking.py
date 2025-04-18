"""Tests for the file locking mechanism in storage.py."""

import json
import os
import tempfile
import threading
from datetime import datetime
from unittest.mock import patch

from filelock import FileLock
from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.core.storage import JSONStorage


def test_file_locking_prevents_concurrent_writes():
    """Test that file locking prevents concurrent writes to the same file."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # No need to store the storage instance
        JSONStorage(file_path=temp_path)

        # Create a lock file to simulate another process holding the lock
        lock_file = f"{temp_path}.lock"

        # Track if we reached the timeout
        timeout_reached = False

        # Define a function that will try to write while the lock is held
        def write_with_timeout():
            nonlocal timeout_reached
            try:
                # Use a short timeout to avoid hanging the test
                with FileLock(lock_file, timeout=0.5):
                    # This should not be reached during the test
                    pass
            except TimeoutError:
                timeout_reached = True

        # Acquire the lock manually to simulate another process
        lock = FileLock(lock_file)
        lock.acquire()

        try:
            # Start a thread that will try to write while the lock is held
            thread = threading.Thread(target=write_with_timeout)
            thread.start()
            thread.join(1.0)  # Wait for the thread to finish or timeout

            # Verify that the timeout was reached
            assert timeout_reached, "Expected a timeout when lock is held by another process"
        finally:
            # Release the lock
            lock.release()

            # Clean up the lock file
            if os.path.exists(lock_file):
                os.unlink(lock_file)

    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_write_json_safely_uses_file_lock():
    """Test that _write_json_safely uses a file lock."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # Initialize storage with the temporary file
        storage = JSONStorage(file_path=temp_path)

        # Mock the FileLock to verify it's called
        with patch("filelock.FileLock", autospec=True) as mock_file_lock:
            # Configure the mock to work like a context manager
            mock_lock_instance = mock_file_lock.return_value
            mock_lock_instance.__enter__.return_value = None
            mock_lock_instance.__exit__.return_value = None

            # Call the method that should use file locking
            storage._write_json_safely([{"test": "data"}])

            # Verify that FileLock was called with the expected lock file path
            mock_file_lock.assert_called_once_with(f"{temp_path}.lock", timeout=30)

            # Verify that the lock's __enter__ and __exit__ methods were called
            mock_lock_instance.__enter__.assert_called_once()
            mock_lock_instance.__exit__.assert_called_once()

    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_file_lock_prevents_data_corruption():
    """Test that file locking prevents data corruption during concurrent writes."""
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as temp_file:
        temp_path = temp_file.name
        # Initialize with empty data
        json.dump({"sessions": []}, temp_file)

    try:
        # Create a counter to track successful writes
        successful_writes = 0
        lock = threading.Lock()

        # Function for writer thread
        def writer_thread():
            nonlocal successful_writes

            # Create a test session
            now = datetime.now()
            session = TestSession(
                sut_name="test_sut",
                session_id=f"session_{threading.get_ident()}",
                session_start_time=now,
                session_duration=1.0,
            )

            # Add a test result
            test_result = TestResult(
                nodeid="test_module.py::test_function",
                outcome=TestOutcome.PASSED,
                start_time=now,
                duration=0.5,
            )
            session.add_test_result(test_result)

            # Save the session using the file lock mechanism
            try:
                storage = JSONStorage(file_path=temp_path)
                storage.save_session(session)

                # Increment the counter safely
                with lock:
                    successful_writes += 1
            except Exception as e:
                print(f"Error in thread {threading.get_ident()}: {e}")

        # Create and start multiple writer threads
        num_threads = 10
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=writer_thread)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify that all writes were successful
        assert successful_writes == num_threads, f"Expected {num_threads} successful writes, got {successful_writes}"

        # Verify the file contains valid JSON
        with open(temp_path, "r") as f:
            data = json.load(f)
            assert "sessions" in data
            assert isinstance(data["sessions"], list)

    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        # Clean up the lock file
        lock_file = f"{temp_path}.lock"
        if os.path.exists(lock_file):
            os.unlink(lock_file)
