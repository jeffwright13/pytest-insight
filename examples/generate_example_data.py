from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random
from pathlib import Path
from typing import List
import json

from pytest_insight.models import TestResult, TestSession
from pytest_insight.storage import JSONStorage

class ExampleDataGenerator:
    """Generate example test data for demonstrations."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path  # Store path separately
        self.storage = JSONStorage(storage_path)
        self.suts = ["api-service", "web-frontend", "batch-processor"]

        # Define realistic test patterns
        self.test_patterns = {
            "api-service": [
                # Authentication patterns
                ("test_api/test_auth.py::test_login", {
                    "flaky": True,
                    "slow": False,
                    "resource_heavy": False,
                    "patterns": ["intermittent_timeout", "redis_connection"]
                }),
                ("test_api/test_auth.py::test_token_refresh", {
                    "flaky": True,
                    "slow": False,
                    "resource_heavy": False,
                    "patterns": ["token_expired", "redis_connection"]
                }),

                # CRUD operations
                ("test_api/test_endpoints.py::test_create_user", {
                    "flaky": False,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["db_deadlock", "unique_constraint"]
                }),
                ("test_api/test_endpoints.py::test_bulk_update", {
                    "flaky": False,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["timeout", "memory_usage"]
                }),

                # Search functionality
                ("test_api/test_search.py::test_complex_query", {
                    "flaky": False,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["elastic_timeout", "query_optimization"]
                }),

                # Cache operations
                ("test_api/test_cache.py::test_cache_invalidation", {
                    "flaky": True,
                    "slow": False,
                    "resource_heavy": False,
                    "patterns": ["race_condition", "redis_connection"]
                })
            ],
            "web-frontend": [
                # UI Components
                ("test_ui/test_login.py::test_login_form", {
                    "flaky": True,
                    "slow": False,
                    "resource_heavy": False,
                    "patterns": ["element_not_found", "animation_timing"]
                }),
                ("test_ui/test_dashboard.py::test_load_widgets", {
                    "flaky": True,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["js_error", "network_timeout"]
                }),

                # Reports
                ("test_ui/test_reports.py::test_generate_pdf", {
                    "flaky": False,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["memory_leak", "file_handle"]
                }),

                # Interactive features
                ("test_ui/test_search.py::test_autocomplete", {
                    "flaky": True,
                    "slow": False,
                    "resource_heavy": False,
                    "patterns": ["race_condition", "debounce_timing"]
                })
            ],
            "batch-processor": [
                # ETL Jobs
                ("test_batch/test_etl.py::test_data_transform", {
                    "flaky": False,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["memory_usage", "disk_space"]
                }),

                # Queue Processing
                ("test_batch/test_queue.py::test_job_processing", {
                    "flaky": True,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["queue_timeout", "worker_crash"]
                }),

                # Maintenance
                ("test_batch/test_cleanup.py::test_old_data_cleanup", {
                    "flaky": False,
                    "slow": True,
                    "resource_heavy": True,
                    "patterns": ["disk_space", "db_lock"]
                })
            ]
        }

    def create_test_result(self, sut: str, base_time: datetime) -> TestResult:
        """Create a test result with realistic patterns."""
        # Select a test pattern for this SUT
        test_pattern, properties = random.choice(self.test_patterns[sut])

        # Determine outcome based on patterns
        if properties["flaky"]:
            outcome = random.choices(
                ["PASSED", "FAILED", "RERUN"],
                weights=[60, 20, 20]
            )[0]
        else:
            outcome = random.choices(
                ["PASSED", "FAILED", "SKIPPED"],
                weights=[85, 10, 5]
            )[0]

        # Calculate duration with realistic patterns
        base_duration = random.uniform(0.1, 2.0)
        if properties["slow"]:
            # Add occasional performance degradation
            if random.random() < 0.2:  # 20% chance of being slow
                base_duration *= random.uniform(2.0, 5.0)

        return TestResult(
            nodeid=test_pattern,
            outcome=outcome,
            start_time=base_time + timedelta(seconds=random.randint(0, 300)),
            duration=base_duration,
            has_warning=random.random() < 0.1,  # 10% chance of warning
            longreprtext=self._generate_error_text(outcome, properties) if outcome in ["FAILED", "ERROR"] else "",
        )

    def _generate_error_text(self, outcome: str, test_pattern: dict) -> str:
        """Generate context-aware error messages."""
        if outcome not in ["FAILED", "ERROR"]:
            return ""

        error_patterns = {
            "intermittent_timeout": [
                "TimeoutError: Operation timed out after 30s",
                "ConnectionError: Read timed out after 30s"
            ],
            "redis_connection": [
                "ConnectionError: Error connecting to Redis: Connection refused",
                "RedisError: Connection pool exhausted"
            ],
            "db_deadlock": [
                "OperationalError: Deadlock found when trying to get lock",
                "IntegrityError: Transaction deadlock detected"
            ],
            "elastic_timeout": [
                "elasticsearch.ConnectionTimeout: Connection timed out",
                "elasticsearch.TransportError: [504] Gateway Time-out"
            ],
            "race_condition": [
                "AssertionError: Expected state change not detected",
                "ValueError: Resource modified by another process"
            ],
            "memory_usage": [
                "MemoryError: Unable to allocate array",
                "ResourceWarning: Excessive memory usage detected"
            ],
            "disk_space": [
                "OSError: No space left on device",
                "IOError: [Errno 28] No space left on device"
            ]
        }

        # Select error pattern based on test properties
        applicable_patterns = []
        for pattern in test_pattern["patterns"]:
            if pattern in error_patterns:
                applicable_patterns.extend(error_patterns[pattern])

        return random.choice(applicable_patterns) if applicable_patterns else "Test failed"

    def create_session(self, sut: str, start_time: datetime) -> TestSession:
        """Create a test session with realistic patterns."""
        num_tests = random.randint(20, 50)
        results = [
            self.create_test_result(sut, start_time)
            for _ in range(num_tests)
        ]

        # Calculate session duration based on test results
        max_test_end = max(
            r.start_time + timedelta(seconds=r.duration)
            for r in results
        )
        session_duration = (max_test_end - start_time).total_seconds()

        return TestSession(
            session_id=f"session_{start_time.strftime('%Y%m%d%H%M%S')}",
            sut_name=sut,
            session_start_time=start_time,
            session_duration=session_duration,  # Add session duration
            test_results=results
        )

    def generate_example_data(self, num_days: int = 30) -> None:
        """Generate example data spanning multiple days."""
        sessions: List[TestSession] = []
        now = datetime.now(ZoneInfo("UTC"))

        # Generate sessions across the time span
        for day in range(num_days):
            day_date = now - timedelta(days=day)

            # Generate 2-4 sessions per day per SUT
            for sut in self.suts:
                num_sessions = random.randint(2, 4)
                for _ in range(num_sessions):
                    session_time = day_date.replace(
                        hour=random.randint(0, 23),
                        minute=random.randint(0, 59)
                    )
                    sessions.append(self.create_session(sut, session_time))

        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize storage file if it doesn't exist
        if not self.storage_path.exists():
            with open(self.storage_path, 'w') as f:
                json.dump([], f)  # Initialize with empty array

        # Load existing sessions
        existing_sessions = self.storage.load_sessions()

        # Combine existing and new sessions
        all_sessions = existing_sessions + sessions

        # Save all sessions at once using json dump
        with open(self.storage_path, 'w') as f:
            json.dump([s.to_dict() for s in all_sessions], f, indent=2)

        print(f"Generated {len(sessions)} example test sessions across {num_days} days")
