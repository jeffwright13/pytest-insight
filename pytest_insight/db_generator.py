import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer

from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession

app = typer.Typer(
    name="insight-gen",
    help="Generate practice test data for pytest-insight",
    no_args_is_help=True,
)

"""Generate practice test data for pytest-insight with configurable parameters.

This module provides a CLI tool for generating realistic test data that matches
established test outcome distributions:

- PASSED: ~45% (configurable via --pass-rate)
- RERUN: ~17% (configurable via --flaky-rate)
- XFAILED: ~15%
- ERROR: ~9%
- FAILED: ~6.5%
- XPASSED: ~5%
- SKIPPED: ~2.5%

Usage:
    insight-gen --days 30 --targets 5
    insight-gen --pass-rate 0.6 --flaky-rate 0.1
    insight-gen --sut-filter qa- --categories api,integration
"""


class PracticeDataGenerator:
    """Generates practice test data with variations for learning and exploration."""

    def __init__(
        self,
        target_path: Optional[Path] = None,
        days: int = 7,
        targets_per_base: int = 3,
        start_date: Optional[datetime] = None,
        pass_rate: float = 0.45,  # Default from established distribution
        flaky_rate: float = 0.17,
        warning_rate: float = 0.085,
        sut_filter: Optional[str] = None,  # Filter SUTs by prefix (qa-, prod-, etc.)
        test_categories: Optional[list[str]] = None,  # Filter test categories
    ):
        """Initialize generator with optional parameters.

        Args:
            target_path: Optional path for practice database.
                        If not provided, uses ~/.pytest_insight/practice.json
            days: Number of days to generate data for (min: 1, max: 90)
            targets_per_base: Maximum number of target sessions per base session (min: 1, max: 10)
            start_date: Start date for data generation (format: YYYY-MM-DD). Default: 7 days ago
            pass_rate: Base pass rate for normal tests (default: 0.45)
            flaky_rate: Rate of flaky tests (default: 0.17)
            warning_rate: Base rate for test warnings (default: 0.085)
            sut_filter: Optional prefix to filter SUTs (e.g., 'qa-', 'prod-')
            test_categories: Optional list of test categories to include
                           ['api', 'integration', 'performance', 'flaky', 'data']
        """
        self.target_path = target_path or Path.home() / ".pytest_insight" / "practice.json"
        self.days = days
        self.targets_per_base = targets_per_base
        self.start_date = start_date
        self.pass_rate = max(0.1, min(0.9, pass_rate))  # Clamp between 0.1 and 0.9
        self.flaky_rate = max(0.05, min(0.3, flaky_rate))
        self.warning_rate = max(0.01, min(0.2, warning_rate))

        # Define variations for generating data
        self.sut_variations = [
            "ref-sut-openjdk11",
            "ref-sut-openjdk17",
            "ref-sut-openjdk21",
            "ref-sut-python39",
            "ref-sut-python310",
            "ref-sut-python311",
            "ref-sut-python312",
            "perf-sut-600",
            "perf-sut-100",
            "perf-sut-200",
            "perf-sut-400",
            "prod-service-a",
            "prod-service-b",
            "prod-service-c",
            "beta-service-a",
            "beta-service-b",
            "beta-service-c",
            "qa-service-a",
            "qa-service-b",
            "qa-service-c",
        ]

        # Filter SUTs if specified
        if sut_filter:
            self.sut_variations = [sut for sut in self.sut_variations if sut.startswith(sut_filter)]
            if not self.sut_variations:
                raise ValueError(f"No SUTs found matching prefix '{sut_filter}'")

        # Test patterns with different categories
        self.test_patterns = {
            "api": [
                "test_api/test_users.py::test_create_user",
                "test_api/test_users.py::test_update_user",
                "test_api/test_users.py::test_delete_user",
                "test_api/test_auth.py::test_login",
                "test_api/test_auth.py::test_refresh_token",
                "test_api/test_auth.py::test_invalid_token[xfail]",  # Expected failure
                "test_api/test_rate_limit.py::test_high_concurrency[xfail]",  # Both flaky and xfail
            ],
            "integration": [
                "test_integration/test_workflow.py::test_end_to_end_flow",
                "test_integration/test_workflow.py::test_error_handling",
                "test_integration/test_database.py::test_data_consistency",
                "test_integration/test_database.py::test_concurrent_access[xfail]",  # Expected failure
                "test_integration/test_cleanup.py::test_resource_cleanup[xfail]",  # Both flaky and xfail
            ],
            "performance": [
                "test_performance/test_load.py::test_concurrent_users[100]",
                "test_performance/test_load.py::test_concurrent_users[500]",
                "test_performance/test_load.py::test_concurrent_users[1000]",
                "test_performance/test_load.py::test_max_throughput[xfail]",  # Expected failure
                "test_performance/test_scaling.py::test_auto_scaling[xfail]",  # Both flaky and xfail
            ],
            "flaky": [  # Known flaky tests that may need reruns
                "test_network/test_connectivity.py::test_remote_service",
                "test_async/test_events.py::test_event_processing",
                "test_database/test_deadlock.py::test_concurrent_writes",
                "test_api/test_rate_limit.py::test_high_concurrency[xfail]",  # Also in api category
                "test_integration/test_cleanup.py::test_resource_cleanup[xfail]",  # Also in integration
                "test_performance/test_scaling.py::test_auto_scaling[xfail]",  # Also in performance
            ],
            "data": [
                "test_data/test_validation.py::test_input_validation",
                "test_data/test_transformation.py::test_data_transform",
                "test_data/test_persistence.py::test_save_load",
                "test_data/test_edge_cases.py::test_invalid_data[xfail]",  # Expected failure
                "test_data/test_race_condition.py::test_concurrent_update[xfail]",  # Both flaky and xfail
            ],
        }

        # Filter test categories if specified
        if test_categories:
            invalid_categories = set(test_categories) - set(self.test_patterns.keys())
            if invalid_categories:
                raise ValueError(f"Invalid test categories: {invalid_categories}")
            self.test_patterns = {k: v for k, v in self.test_patterns.items() if k in test_categories}

        # Define common test failure patterns with more realistic messages
        self.error_patterns = {
            "assertion": "AssertionError: Expected {expected}, but got {actual}",
            "timeout": "TimeoutError: Operation timed out after {timeout} seconds",
            "connection": "ConnectionError: Failed to connect to {service}: Connection refused",
            "validation": "ValidationError: Invalid data format for field '{field}'",
            "database": "DatabaseError: Could not execute query: {error}",
            "concurrency": "ConcurrencyError: Deadlock detected in transaction {txn}",
            "memory": "MemoryError: Out of memory while processing {operation}",
            "race": "RaceConditionError: Data changed during {operation}",
            "resource": "ResourceError: Failed to {action} resource: {reason}",
        }

        # Define session tags for different test environments
        self.session_tags = {
            "qa": {"environment": "qa", "test_type": "regression"},
            "prod": {"environment": "production", "test_type": "smoke"},
            "beta": {"environment": "beta", "test_type": "integration"},
            "ref": {"environment": "ref", "test_type": "ref"},
            "perf": {"environment": "performance", "test_type": "performance"},
        }

    def _generate_session_id(self, sut_name: str, is_base: bool = False) -> str:
        """Generate a session ID following the proper pattern."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = "base" if is_base else "target"
        return f"{prefix}-{sut_name}-{timestamp}-{random.randint(10000000, 99999999):x}"

    def _generate_error_message(self, error_type: str) -> str:
        """Generate realistic error messages."""
        if error_type == "assertion":
            expected = random.choice(["200", "True", "User created", "[]"])
            actual = random.choice(["404", "False", "Permission denied", "None"])
            return self.error_patterns["assertion"].format(expected=expected, actual=actual)
        elif error_type == "timeout":
            return self.error_patterns["timeout"].format(timeout=random.randint(30, 120))
        elif error_type == "connection":
            service = random.choice(["database", "cache", "auth-service", "api"])
            return self.error_patterns["connection"].format(service=service)
        elif error_type == "validation":
            field = random.choice(["email", "user_id", "timestamp", "status"])
            return self.error_patterns["validation"].format(field=field)
        elif error_type == "concurrency":
            txn = random.choice(["read", "write", "update", "delete"])
            return self.error_patterns["concurrency"].format(txn=txn)
        elif error_type == "memory":
            operation = random.choice(["loading", "processing", "saving", "transforming"])
            return self.error_patterns["memory"].format(operation=operation)
        elif error_type == "race":
            operation = random.choice(["loading", "processing", "saving", "transforming"])
            return self.error_patterns["race"].format(operation=operation)
        elif error_type == "resource":
            action = random.choice(["allocate", "deallocate", "update"])
            reason = random.choice(["insufficient resources", "invalid request", "timeout"])
            return self.error_patterns["resource"].format(action=action, reason=reason)
        else:
            error = random.choice(["deadlock detected", "connection lost", "invalid state"])
            return self.error_patterns["database"].format(error=error)

    def _create_test_result(
        self,
        nodeid: str,
        start_time: datetime,
        make_flaky: bool = False,
        test_type: str = None,
    ) -> TestResult:
        """Create a test result with realistic timing and outcomes."""
        # Adjust duration based on test type
        if test_type == "performance":
            duration = random.uniform(60.0, 600.0)  # Performance tests take longer
        elif test_type == "integration":
            duration = random.uniform(5.0, 15.0)  # Integration tests are medium
        else:
            duration = random.uniform(0.1, 5.0)  # Unit tests are quick

        stop_time = start_time + timedelta(seconds=duration)

        # Check if test is marked for expected failure
        is_xfail = "[xfail]" in nodeid.lower()

        # Generate realistic test outcomes with proper categorization
        if make_flaky and is_xfail:
            # Tests that are both flaky and marked for expected failure
            # These can have various outcomes: XFAILED (expected), XPASSED (unexpected),
            # RERUN (flaky), or ERROR (flaky with error)
            outcome = random.choice(
                [
                    TestOutcome.XFAILED,
                    TestOutcome.XFAILED,
                    TestOutcome.XFAILED,  # 30%
                    TestOutcome.XPASSED,  # 10%
                    TestOutcome.RERUN,
                    TestOutcome.RERUN,  # 20%
                    TestOutcome.ERROR,  # 10%
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,  # 30%
                ]
            )
            error_type = "timeout" if outcome in [TestOutcome.ERROR, TestOutcome.RERUN] else None
        elif make_flaky:
            # Pure flaky tests (not marked for expected failure)
            outcome = random.choice(
                [
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,  # 40%
                    TestOutcome.FAILED,  # 10%
                    TestOutcome.ERROR,  # 10%
                    TestOutcome.RERUN,
                    TestOutcome.RERUN,
                    TestOutcome.RERUN,  # 30%
                    TestOutcome.PASSED,  # 10%
                ]
            )
            error_type = (
                random.choice(["timeout", "connection", "race", "concurrency"])
                if outcome in [TestOutcome.ERROR, TestOutcome.RERUN]
                else None
            )
        elif is_xfail:
            # Pure xfail tests (not flaky)
            outcome = random.choice(
                [
                    TestOutcome.XFAILED,
                    TestOutcome.XFAILED,
                    TestOutcome.XFAILED,
                    TestOutcome.XFAILED,
                    TestOutcome.XFAILED,
                    TestOutcome.XFAILED,  # 60%
                    TestOutcome.XPASSED,
                    TestOutcome.XPASSED,  # 20%
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,  # 20%
                ]
            )
            error_type = random.choice(["assertion", "validation"]) if outcome == TestOutcome.XFAILED else None
        elif test_type == "performance":
            # Performance tests have higher failure rates and more skips under load
            outcome = random.choice(
                [
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,  # 30%
                    TestOutcome.FAILED,
                    TestOutcome.FAILED,  # 20%
                    TestOutcome.SKIPPED,
                    TestOutcome.SKIPPED,  # 20%
                    TestOutcome.ERROR,
                    TestOutcome.ERROR,  # 20%
                    TestOutcome.PASSED,  # 10%
                ]
            )
            error_type = (
                random.choice(["timeout", "memory", "resource"])
                if outcome in [TestOutcome.ERROR, TestOutcome.FAILED]
                else None
            )
        else:
            # Normal test distribution with high pass rate
            outcome = random.choice(
                [
                    # 80% pass rate for normal tests
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    TestOutcome.PASSED,
                    # 20% other outcomes
                    TestOutcome.FAILED,  # 10%
                    TestOutcome.ERROR,  # 5%
                    TestOutcome.SKIPPED,  # 5%
                ]
            )
            error_type = (
                random.choice(["assertion", "validation", "database"])
                if outcome in [TestOutcome.ERROR, TestOutcome.FAILED]
                else None
            )

        error_message = self._generate_error_message(error_type) if error_type else ""

        # Add warnings with specific patterns
        warning_chance = {
            "performance": 0.15,  # Higher chance for performance tests
            "flaky": 0.12,  # Elevated for flaky tests
            "integration": 0.08,  # Medium for integration
            None: self.warning_rate,  # Base rate for others
        }.get(test_type, self.warning_rate)

        has_warning = random.random() < warning_chance

        caplog = []
        if has_warning:
            warning_patterns = {
                "performance": [
                    f"WARNING: Performance threshold exceeded in {nodeid}",
                    f"WARNING: Resource utilization high during {nodeid}",
                    f"WARNING: Response time degradation in {nodeid}",
                ],
                "flaky": [
                    f"WARNING: Test {nodeid} shows non-deterministic behavior",
                    f"WARNING: Potential race condition detected in {nodeid}",
                    f"WARNING: Network instability affecting {nodeid}",
                ],
                "integration": [
                    f"WARNING: Service dependency timeout in {nodeid}",
                    f"WARNING: Database connection unstable during {nodeid}",
                    f"WARNING: Cache inconsistency detected in {nodeid}",
                ],
            }
            if test_type in warning_patterns:
                caplog.append(random.choice(warning_patterns[test_type]))
            else:
                caplog.append(f"WARNING: Deprecation warning in {nodeid}")

        caplog.append(f"Test execution log for {nodeid}")
        if error_type:
            caplog.append(f"ERROR: {error_message}")
            if outcome in [TestOutcome.ERROR, TestOutcome.FAILED]:
                caplog.append(
                    f'Stack trace:\n  File "{nodeid}", line {random.randint(10, 100)}\n  in test_function\n    {error_message}'
                )

        return TestResult(
            nodeid=nodeid,
            outcome=outcome,
            start_time=start_time,
            stop_time=stop_time,
            duration=duration,
            caplog="\n".join(caplog),
            longreprtext=error_message if error_type else "",
            has_warning=has_warning,
        )

    def _create_session(
        self,
        sut_name: str,
        base_time: datetime,
        is_base: bool = False,
        include_flaky: bool = False,
    ) -> TestSession:
        """Create a test session with realistic data."""
        session_id = self._generate_session_id(sut_name, is_base)
        session_duration = random.uniform(60, 300)  # 1-5 minutes
        session_stop_time = base_time + timedelta(seconds=session_duration)

        # Determine environment and tags based on SUT name prefix
        env_type = next(
            (k for k in ["qa", "prod", "beta", "ref", "perf"] if sut_name.startswith(f"{k}-")),
            "qa",
        )
        session_tags = self.session_tags[env_type].copy()

        # Add specific tags based on session type
        session_tags["session_type"] = "baseline" if is_base else "verification"

        # Generate test results
        test_results = []
        rerun_groups = []
        current_time = base_time

        # Select tests based on SUT and environment
        selected_categories = []
        if sut_name.startswith("perf-"):
            selected_categories.extend(["performance", "api"])
        elif sut_name.startswith("ref-"):
            selected_categories.extend(["api", "integration", "data"])
        elif sut_name.startswith("beta-"):
            selected_categories.extend(["integration", "api", "data"])
        else:
            selected_categories = list(self.test_patterns.keys())

        # Generate test results for each category
        for category in selected_categories:
            tests = self.test_patterns[category]
            selected_tests = random.sample(tests, min(len(tests), random.randint(2, len(tests))))

            for test in selected_tests:
                if category == "flaky" or (include_flaky and random.random() < self.flaky_rate):
                    # Create a rerun group for flaky tests
                    runs = []
                    for _ in range(random.randint(2, 4)):
                        result = self._create_test_result(test, current_time, make_flaky=True, test_type=category)
                        runs.append(result)
                        current_time += timedelta(seconds=result.duration + 0.5)

                    test_results.extend(runs)
                    rerun_groups.append(RerunTestGroup(nodeid=test, tests=runs))
                else:
                    result = self._create_test_result(test, current_time, test_type=category)
                    test_results.append(result)
                    current_time += timedelta(seconds=result.duration + 0.5)

        return TestSession(
            sut_name=sut_name,
            session_id=session_id,
            session_start_time=base_time,
            session_stop_time=session_stop_time,
            session_duration=session_duration,
            test_results=test_results,
            rerun_test_groups=rerun_groups,
            session_tags=session_tags,
        )

    def generate_practice_data(self) -> None:
        """Generate practice data with various test scenarios."""
        all_sessions = []
        base_time = self.start_date or datetime.now() - timedelta(days=7)  # Start from a week ago

        for sut_name in self.sut_variations:
            # Generate multiple session pairs (base/target) over time
            for day_offset in range(self.days):
                session_time = base_time + timedelta(days=day_offset)

                # Create base session
                base_session = self._create_session(
                    sut_name=sut_name,
                    base_time=session_time,
                    is_base=True,  # Ensures base-* session ID
                    include_flaky=True,
                )
                all_sessions.append(base_session)

                # Create 1-3 target sessions for each base
                for _ in range(random.randint(1, self.targets_per_base)):
                    target_time = session_time + timedelta(hours=random.randint(1, 8))
                    target_session = self._create_session(
                        sut_name=sut_name,
                        base_time=target_time,
                        is_base=False,  # Ensures target-* session ID
                        include_flaky=True,
                    )
                    all_sessions.append(target_session)

        # Save all sessions at once instead of one by one
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.target_path, "w") as f:
            json.dump([s.to_dict() for s in all_sessions], f, indent=2)

        print(f"Generated practice database with {len(all_sessions)} sessions")
        print(f"File saved to: {self.target_path}")

        # Print detailed outcome distribution
        sut_counts = {}
        outcome_counts = {outcome.value: 0 for outcome in TestOutcome}
        warning_count = 0
        rerun_count = 0

        for session in all_sessions:
            sut_counts[session.sut_name] = sut_counts.get(session.sut_name, 0) + 1
            for result in session.test_results:
                outcome_counts[result.outcome.value] += 1
                if result.has_warning:
                    warning_count += 1
            rerun_count += len(session.rerun_test_groups)

        print("\nSUT Distribution:")
        for sut, count in sorted(sut_counts.items()):
            print(f"  {sut}: {count} sessions")

        print("\nOutcome Distribution:")
        total_tests = sum(outcome_counts.values())
        for outcome, count in sorted(outcome_counts.items()):
            percentage = (count / total_tests * 100) if total_tests > 0 else 0
            print(f"  {outcome}: {count} tests ({percentage:.1f}%)")

        print("\nAdditional Statistics:")
        print(f"  Tests with Warnings: {warning_count}")
        print(f"  Rerun Groups: {rerun_count}")


@app.command()
def main(
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Number of days to generate data for (min: 1, max: 90)",
        min=1,
        max=90,
    ),
    targets: int = typer.Option(
        3,
        "--targets",
        "-t",
        help="Maximum number of target sessions per base session (min: 1, max: 10)",
        min=1,
        max=10,
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for practice database (default: ~/.pytest_insight/practice.json)",
    ),
    start_date: str = typer.Option(
        None,
        "--start-date",
        "-s",
        help="Start date for data generation (format: YYYY-MM-DD). Default: 7 days ago",
    ),
    pass_rate: float = typer.Option(
        0.45,
        "--pass-rate",
        "-p",
        help="Base pass rate for normal tests (0.1-0.9)",
        min=0.1,
        max=0.9,
    ),
    flaky_rate: float = typer.Option(
        0.17,
        "--flaky-rate",
        "-f",
        help="Rate of flaky tests (0.05-0.3)",
        min=0.05,
        max=0.3,
    ),
    warning_rate: float = typer.Option(
        0.085,
        "--warning-rate",
        "-w",
        help="Base rate for test warnings (0.01-0.2)",
        min=0.01,
        max=0.2,
    ),
    sut_filter: str = typer.Option(
        None,
        "--sut-filter",
        help="Filter SUTs by prefix (qa-, prod-, beta-, ref-, perf-)",
    ),
    categories: str = typer.Option(
        None,
        "--categories",
        "-c",
        help="Comma-separated list of test categories to include (api,integration,performance,flaky,data,python312,java21)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress detailed output, only show essential information",
    ),
) -> None:
    """Generate practice test data with configurable parameters.

    Examples:
        # Generate 30 days of data with up to 5 target sessions per base
        insight-gen --days 30 --targets 5

        # Generate data with custom outcome rates
        insight-gen --pass-rate 0.6 --flaky-rate 0.1 --warning-rate 0.05

        # Generate data for specific SUT type and test categories
        insight-gen --sut-filter qa- --categories api,integration

        # Generate minimal data quickly
        insight-gen --days 3 --targets 2 --quiet

    The generated data will maintain realistic test outcome distributions while
    respecting the configured parameters. Test categories include:
    - api: API endpoint tests
    - integration: Database, cache, and external service tests
    - performance: Load, memory, and resource tests
    - flaky: Tests with non-deterministic behavior
    - data: Data validation and integrity tests
    - python312: Python 3.12 specific feature tests
    - java21: Java 21 specific feature tests
    """
    try:
        if days < 1 or days > 90:
            raise ValueError("Days must be between 1 and 90")
        if targets < 1 or targets > 10:
            raise ValueError("Targets must be between 1 and 10")

        target_path = Path(output) if output else None
        start = None
        if start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                if start > datetime.now():
                    raise ValueError("Start date cannot be in the future")
            except ValueError as e:
                if "format" in str(e):
                    raise ValueError("Start date must be in YYYY-MM-DD format")
                raise

        # Parse categories if provided
        test_categories = None
        if categories:
            test_categories = [c.strip() for c in categories.split(",")]

        generator = PracticeDataGenerator(
            target_path=target_path,
            days=days,
            targets_per_base=targets,
            start_date=start,
            pass_rate=pass_rate,
            flaky_rate=flaky_rate,
            warning_rate=warning_rate,
            sut_filter=sut_filter,
            test_categories=test_categories,
        )
        generator.generate_practice_data()
    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
