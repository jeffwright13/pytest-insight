"""
Generate realistic test data with meaningful trends and patterns for pytest-insight.

This script extends the basic practice data generator to create more realistic
test data with trends, patterns, and anomalies that showcase pytest-insight's
visualization and analysis capabilities.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.core.models import TestOutcome, TestResult, TestSession
from pytest_insight.utils.db_generator import PracticeDataGenerator


class TrendDataGenerator(PracticeDataGenerator):
    """
    Generates test data with realistic trends and patterns for visualization.

    This generator creates test data that demonstrates:
    1. Gradual degradation in test stability over time
    2. Cyclic patterns in test failures (e.g., day of week effects)
    3. Correlated test failures (tests that fail together)
    4. Anomaly patterns for detection
    5. Common error patterns for failure analysis
    """

    # Common error patterns to simulate realistic failures
    ERROR_PATTERNS = {
        "connection": [
            "ConnectionError: Failed to connect to {service} on port {port}",
            "TimeoutError: Connection to {service} timed out after {timeout} seconds",
            "ConnectionRefusedError: Connection refused by {service}",
        ],
        "authentication": [
            "AuthenticationError: Invalid credentials for user {user}",
            "PermissionError: User {user} doesn't have permission to access {resource}",
            "TokenExpiredError: Authentication token expired at {timestamp}",
        ],
        "database": [
            "DatabaseError: Query failed: {query}",
            "IntegrityError: Duplicate key value violates unique constraint",
            "OperationalError: database connection failed: {reason}",
        ],
        "assertion": [
            "AssertionError: Expected {expected} but got {actual}",
            "AssertionError: {value} is not {expected_type}",
            "AssertionError: Response status code {status_code} != {expected_code}",
        ],
    }

    def __init__(
        self,
        storage_profile: Optional[str] = None,
        target_path: Optional[Path] = None,
        days: int = 30,
        targets_per_base: int = 3,
        start_date: Optional[datetime] = None,
        trend_strength: float = 0.7,  # How strong the trends should be (0.0-1.0)
        anomaly_rate: float = 0.05,  # Rate of anomalous test sessions
        correlation_groups: int = 5,  # Number of correlated test failure groups
        sut_filter: Optional[str] = None,
        test_categories: Optional[list[str]] = None,
    ):
        # Initialize with default values optimized for trend visualization
        super().__init__(
            storage_profile=storage_profile,
            target_path=target_path,
            days=days,
            targets_per_base=targets_per_base,
            start_date=start_date,
            # Start with good pass rates that will degrade over time
            pass_rate=0.85,
            flaky_rate=0.10,
            warning_rate=0.05,
            sut_filter=sut_filter,
            test_categories=test_categories,
        )

        self.trend_strength = max(0.1, min(1.0, trend_strength))
        self.anomaly_rate = max(0.01, min(0.2, anomaly_rate))
        self.correlation_groups = min(correlation_groups, 3)  # Limit to 3 for performance

        # Create correlated test groups that will fail together
        self.correlated_groups = self._create_correlated_groups()

        # Create error pattern distributions for each SUT
        self.sut_error_patterns = self._create_error_pattern_distributions()

        # Create cyclic patterns (e.g., day of week effects)
        self.day_of_week_factors = self._create_day_of_week_factors()

        # Error patterns for test failures
        self.error_patterns = [
            "AssertionError: Expected {expected}, got {actual}",
            "ValueError: Invalid value for parameter",
            "TypeError: Cannot convert type",
            "IndexError: List index out of range",
        ]

        # Stack trace patterns
        self.stack_trace_patterns = [
            "File 'test_file.py', line {line}, in test_function\n    assert result == expected",
            "File 'module.py', line {line}, in function\n    return process(value)",
        ]

        # Warning patterns
        self.warning_patterns = [
            "DeprecationWarning: This function is deprecated",
            "UserWarning: This feature will change in the future",
            "ResourceWarning: Resource not properly closed",
        ]

        # Default duration degradation factor
        self.duration_degradation_factor = 1.2  # 20% slower over time

        # Dictionary to store test durations for consistency
        self.test_durations = {}

    def _create_correlated_groups(self) -> Dict[str, List[List[str]]]:
        """Create groups of tests that will fail together to show correlation patterns."""
        correlated_groups = {}

        # For each SUT, create correlation groups
        for sut in self.sut_variations[:3]:  # Limit to 3 SUTs for performance
            correlated_groups[sut] = []

            # Create correlation groups for this SUT
            for i in range(self.correlation_groups):
                # Each group will contain 3-5 tests that tend to fail together
                group_size = random.randint(3, 5)
                group = []

                # Generate test nodeids for this correlation group
                for j in range(group_size):
                    module = random.choice(self.test_patterns.get(sut.split("-")[0], ["test_module"]))
                    test_type = random.choice(self.test_types)
                    test_name = f"test_{test_type}_{self.text_gen.word()}"
                    nodeid = f"{module}::{test_name}"
                    group.append(nodeid)

                correlated_groups[sut].append(group)

        return correlated_groups

    def _create_error_pattern_distributions(self) -> Dict[str, Dict[str, float]]:
        """Create error pattern distributions for each SUT."""
        sut_error_patterns = {}

        for sut in self.sut_variations:
            # Different SUTs will have different error pattern distributions
            if "api" in sut:
                distribution = {
                    "connection": 0.4,
                    "authentication": 0.3,
                    "assertion": 0.2,
                    "database": 0.1,
                }
            elif "db" in sut:
                distribution = {
                    "database": 0.6,
                    "connection": 0.2,
                    "assertion": 0.1,
                    "authentication": 0.1,
                }
            elif "auth" in sut:
                distribution = {
                    "authentication": 0.7,
                    "connection": 0.1,
                    "assertion": 0.1,
                    "database": 0.1,
                }
            else:
                # Default distribution
                distribution = {
                    "assertion": 0.4,
                    "connection": 0.3,
                    "database": 0.2,
                    "authentication": 0.1,
                }

            sut_error_patterns[sut] = distribution

        return sut_error_patterns

    def _create_day_of_week_factors(self) -> Dict[int, float]:
        """Create factors for day-of-week effects on test failures."""
        # Create factors that make certain days of the week more prone to failures
        # Monday (0) and Friday (4) will have higher failure rates
        return {
            0: 1.2,  # Monday: 20% more failures
            1: 0.9,  # Tuesday: 10% fewer failures
            2: 0.8,  # Wednesday: 20% fewer failures
            3: 0.9,  # Thursday: 10% fewer failures
            4: 1.3,  # Friday: 30% more failures
            5: 1.0,  # Saturday: normal failure rate
            6: 1.0,  # Sunday: normal failure rate
        }

    def _get_degradation_factor(self, session_time: datetime) -> float:
        """
        Calculate degradation factor based on time.

        This creates a gradual degradation trend over time, with some random noise.
        """
        # Calculate how far we are into the total time period (0.0 to 1.0)
        if not self.start_date:
            self.start_date = datetime.now(ZoneInfo("UTC")) - timedelta(days=self.days)

        total_duration = timedelta(days=self.days)
        elapsed = session_time - self.start_date
        progress = max(0.0, min(1.0, elapsed / total_duration))

        # Apply a curve to the degradation (starts slow, accelerates)
        curve_factor = progress**1.5

        # Apply trend strength
        trend_factor = 1.0 + (curve_factor * self.trend_strength)

        # Add some random noise (±10%)
        noise = random.uniform(0.9, 1.1)

        # Apply day-of-week factor
        day_of_week = session_time.weekday()
        day_factor = self.day_of_week_factors.get(day_of_week, 1.0)

        return trend_factor * noise * day_factor

    def _is_correlated_failure(self, sut: str, nodeid: str, session_time: datetime) -> bool:
        """Determine if this test should fail as part of a correlated group."""
        # Check if this test is part of any correlated group
        for group in self.correlated_groups.get(sut, []):
            if nodeid in group:
                # If it's in a group, determine if this is a "group failure" session
                # Use a hash of the session time and group to ensure consistency
                session_hash = hash(f"{session_time.isoformat()}_{str(group)}")
                random.seed(session_hash)

                # The probability increases over time to show degradation
                degradation = self._get_degradation_factor(session_time)
                base_probability = 0.2  # Base probability of group failure
                probability = min(0.9, base_probability * degradation)

                is_group_failure = random.random() < probability
                random.seed()  # Reset the seed

                return is_group_failure

        return False

    def _generate_error_message(self, sut: str, nodeid: str) -> str:
        """Generate a realistic error message based on SUT and test type."""
        # Select error pattern type based on SUT distribution
        error_dist = self.sut_error_patterns.get(
            sut,
            {
                "assertion": 0.4,
                "connection": 0.3,
                "database": 0.2,
                "authentication": 0.1,
            },
        )

        error_type = random.choices(list(error_dist.keys()), weights=list(error_dist.values()), k=1)[0]

        # Select a specific error pattern
        error_pattern = random.choice(self.ERROR_PATTERNS[error_type])

        # Fill in the template with realistic values
        error_message = error_pattern.format(
            service=f"{sut}-{random.randint(1, 5)}",
            port=random.choice([80, 443, 8080, 8443, 3306, 5432]),
            user=f"user_{random.randint(100, 999)}",
            resource=f"/{self.text_gen.word()}/{self.text_gen.word()}",
            timestamp=datetime.now().isoformat(),
            query=f"SELECT * FROM {self.text_gen.word()} WHERE id = {random.randint(1, 1000)}",
            reason=random.choice(
                [
                    "connection timeout",
                    "server closed connection",
                    "too many connections",
                ]
            ),
            expected=random.choice(["200", "True", "Success", "42", "'active'"]),
            actual=random.choice(["404", "False", "Error", "None", "'inactive'"]),
            value=random.choice(["response", "user", "config", "result"]),
            expected_type=random.choice(["dict", "list", "str", "int", "bool"]),
            status_code=random.choice(["404", "500", "403", "400"]),
            expected_code=random.choice(["200", "201", "204"]),
            timeout=random.randint(5, 60),
        )

        return error_message

    def _generate_test_result(
        self,
        nodeid: str,
        outcome: TestOutcome,
        duration: float,
        start_time: datetime,
        is_flaky: bool = False,
    ) -> TestResult:
        """Generate a test result with realistic attributes.

        Args:
            nodeid: Test node ID
            outcome: Test outcome
            duration: Test duration in seconds
            start_time: Test start time
            is_flaky: Whether the test is flaky

        Returns:
            TestResult object
        """
        # Generate a realistic test result
        result = TestResult(
            nodeid=nodeid,
            outcome=outcome,
            duration=duration,
            start_time=start_time,
        )

        # Add realistic attributes based on outcome
        if outcome == TestOutcome.FAILED:
            # Select an error pattern
            error_pattern = random.choice(self.error_patterns)

            # Format the error message with random values
            error_message = error_pattern.format(
                expected=random.choice(["True", "False", "42", "'expected'", "None"]),
                actual=random.choice(["True", "False", "24", "'actual'", "None"]),
                line=random.randint(10, 500),
            )

            # Select a stack trace pattern
            stack_trace_pattern = random.choice(self.stack_trace_patterns)

            # Format the stack trace with random values
            stack_trace = stack_trace_pattern.format(
                line=random.randint(10, 500),
            )

            # Add error message and stack trace
            result.longrepr = f"{error_message}\n\n{stack_trace}"

            # Add crash attributes
            if random.random() < 0.3:  # 30% of failures are crashes
                result.crash = {
                    "type": random.choice(["segfault", "timeout", "oom"]),
                    "message": f"Test crashed with {random.choice(['segmentation fault', 'timeout', 'out of memory'])}",
                }

        # Add warnings
        if random.random() < self.warning_rate:
            # Select 1-3 warning patterns
            num_warnings = random.randint(1, min(3, len(self.warning_patterns)))
            warning_patterns = random.sample(self.warning_patterns, num_warnings)

            # Format warnings
            warnings = []
            for warning_pattern in warning_patterns:
                warnings.append(
                    {
                        "message": warning_pattern,
                        "category": warning_pattern.split(":")[0],
                        "filename": f"{random.choice(['test_', 'core/', 'api/'])}{random.choice(['module', 'utils', 'client'])}.py",
                        "lineno": random.randint(10, 500),
                    }
                )

            result.warnings = warnings

        # Add flaky attributes if the test is flaky
        if is_flaky:
            result.flaky = True

            # Add rerun information
            if random.random() < 0.7:  # 70% of flaky tests have reruns
                result.reruns = random.randint(1, 3)
                result.rerun_outcomes = [
                    random.choice([TestOutcome.PASSED, TestOutcome.FAILED]) for _ in range(result.reruns)
                ]

        return result

    def _generate_nodeid(self, sut_name: str) -> str:
        """Generate a realistic test nodeid.

        Args:
            sut_name: Name of the system under test

        Returns:
            A realistic test nodeid
        """
        # Create module path
        sut_type = sut_name.split("-")[0] if "-" in sut_name else sut_name
        module_options = [
            f"tests/test_{sut_type}.py",
            f"tests/unit/test_{sut_type}.py",
            f"tests/integration/test_{sut_type}_integration.py",
            f"tests/functional/test_{sut_type}_functional.py",
        ]
        module = random.choice(module_options)

        # Create test name
        test_categories = [
            "create",
            "read",
            "update",
            "delete",
            "validate",
            "process",
            "calculate",
            "convert",
        ]
        test_objects = [
            "user",
            "account",
            "data",
            "config",
            "file",
            "connection",
            "request",
            "response",
        ]
        test_scenarios = [
            "valid",
            "invalid",
            "empty",
            "large",
            "edge_case",
            "normal",
            "error",
        ]

        # Create a test name with a realistic pattern
        test_name = f"test_{random.choice(test_categories)}_{random.choice(test_objects)}"

        # Sometimes add a scenario
        if random.random() < 0.5:
            test_name += f"_{random.choice(test_scenarios)}"

        # Sometimes add a class name
        if random.random() < 0.3:
            class_name = f"Test{sut_type.capitalize()}"
            return f"{module}::{class_name}::{test_name}"

        return f"{module}::{test_name}"

    def _create_session(self, sut_name: str, session_time: datetime, is_base: bool = False) -> TestSession:
        """Create a test session with realistic test results and trends.

        Args:
            sut_name: Name of the system under test
            session_time: Timestamp for the session
            is_base: Whether this is a base session

        Returns:
            TestSession object
        """
        # Create a session ID
        session_id = f"{sut_name}-{session_time.strftime('%Y%m%d%H%M%S')}-{random.randint(1000, 9999)}"

        # Calculate session duration (5-30 minutes)
        session_duration = random.uniform(300, 1800)
        session_stop_time = session_time + timedelta(seconds=session_duration)

        # Create the session
        session = TestSession(
            sut_name=sut_name,
            session_id=session_id,
            session_start_time=session_time,
            session_stop_time=session_stop_time,
            session_duration=session_duration,
            session_tags={
                "env": random.choice(["dev", "staging", "prod"]),
                "region": random.choice(["us-east", "us-west", "eu-central"]),
                "build": f"{random.randint(1000, 9999)}",
                "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                "is_anomaly": ("true" if random.random() < self.anomaly_rate else "false"),
            },
        )

        # Get degradation factor based on time
        degradation_factor = self._get_degradation_factor(session_time)

        # Adjust pass rate based on degradation
        adjusted_pass_rate = max(0.5, self.pass_rate * degradation_factor)

        # Adjust flaky rate based on degradation (inverse relationship)
        adjusted_flaky_rate = min(0.2, self.flaky_rate / degradation_factor)

        # Determine if this is an anomalous session
        is_anomalous = random.random() < self.anomaly_rate
        if is_anomalous:
            # Anomalous sessions have much worse pass rates
            adjusted_pass_rate *= 0.6

        # Generate test results for this session
        num_tests = random.randint(20, 50)

        # For each test
        for i in range(num_tests):
            # Generate a realistic nodeid
            nodeid = self._generate_nodeid(sut_name)

            # Determine outcome based on pass rate
            if random.random() < adjusted_pass_rate:
                outcome = TestOutcome.PASSED
            else:
                # For failed tests, determine if it's part of a correlated group
                if sut_name in self.correlated_groups and nodeid in self.correlated_groups[sut_name]:
                    # This test is part of a correlated group
                    # If any test in the group has failed, this one is more likely to fail
                    outcome = TestOutcome.FAILED
                else:
                    outcome = random.choice([TestOutcome.FAILED, TestOutcome.ERROR, TestOutcome.SKIPPED])

            # Determine duration
            if outcome == TestOutcome.PASSED:
                # Passed tests have more consistent durations
                base_duration = self.test_durations.get(nodeid, random.uniform(0.1, 1.0))
                duration = base_duration * random.uniform(0.9, 1.1)
            else:
                duration = random.uniform(0.05, 2.0)

            # Apply duration degradation factor
            duration *= self.duration_degradation_factor

            # Create the test result
            test_result = self._generate_test_result(
                nodeid=nodeid,
                outcome=outcome,
                duration=duration,
                start_time=session_time,
                is_flaky=random.random() < adjusted_flaky_rate,
            )

            # Add to session
            session.add_test_result(test_result)

        return session

    def generate_trend_data(self):
        """Generate test data with realistic trends and patterns.

        This method creates multiple test sessions over a period of time,
        with realistic patterns of test failures, performance degradation,
        and other trends.

        Returns:
            List of generated TestSession objects
        """
        console = Console()

        # Display generation parameters
        table = Table(title="Trend Generation Parameters")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Days", str(self.days))
        table.add_row("Targets per base", str(self.targets_per_base))
        table.add_row("Initial pass rate", f"{self.pass_rate*100:.1f}%")
        table.add_row("Trend strength", f"{self.trend_strength*100:.1f}%")
        table.add_row("Anomaly rate", f"{self.anomaly_rate*100:.1f}%")
        table.add_row("Correlation groups", str(self.correlation_groups))
        console.print(table)

        # Generate the sessions
        all_sessions = self._generate_sessions()

        # Save to profile if specified
        if self.storage_profile:
            self._save_to_profile(all_sessions)

        # Show success message only after all operations are complete
        console.print(
            Panel(
                f"Generated trend data for {self.days} days\n" f"Total sessions: {len(all_sessions)}",
                title="Success",
                border_style="green",
            )
        )

        return all_sessions

    def _generate_sessions(self) -> List[TestSession]:
        """Generate test sessions with realistic trends and patterns.

        Returns:
            List of generated TestSession objects
        """
        console = Console()
        all_sessions = []

        # Calculate time range
        if not self.start_date:
            self.start_date = datetime.now(ZoneInfo("UTC")) - timedelta(days=self.days)

        # Limit SUTs for better performance
        limited_suts = self.sut_variations[:5]

        # Show progress
        with console.status(
            f"[bold green]Generating trend data for {self.days} days...[/bold green]",
            spinner="dots",
        ):
            # For each day
            for day in range(self.days):
                day_time = self.start_date + timedelta(days=day)

                # For each SUT
                for sut_name in limited_suts:
                    # Create a base session
                    base_session = self._create_session(
                        sut_name=sut_name,
                        session_time=day_time,
                        is_base=True,
                    )
                    all_sessions.append(base_session)

                    # Create target sessions - limit for performance
                    num_targets = min(2, random.randint(1, self.targets_per_base))
                    for _ in range(num_targets):
                        target_time = day_time + timedelta(hours=random.randint(12, 23), minutes=random.randint(0, 59))
                        target_session = self._create_session(
                            sut_name=sut_name,
                            session_time=target_time,
                        )
                        all_sessions.append(target_session)

        return all_sessions

    def _save_to_profile(self, sessions: List[TestSession]) -> None:
        """Save generated sessions to the specified storage profile.

        Args:
            sessions: List of TestSession objects to save

        Returns:
            None
        """
        try:
            from pytest_insight.core.storage import get_storage_instance

            # Get storage instance for the profile
            storage = get_storage_instance(profile_name=self.storage_profile)

            # Save each session to storage
            for session in sessions:
                storage.save_session(session)

            console = Console()
            console.print(f"[green]Saved {len(sessions)} sessions to profile: {self.storage_profile}[/green]")
        except Exception as e:
            console = Console()
            console.print(f"[bold red]Error saving to profile: {str(e)}[/bold red]")

    @staticmethod
    def create_showcase_profile(days: int = 30, lightweight: bool = False) -> None:
        """Create a comprehensive showcase profile demonstrating all dashboard features.

        This method generates a rich dataset that showcases all the capabilities
        of the pytest-insight dashboard, including:
        - Long-term trends (30 days by default)
        - Multiple SUTs with different characteristics
        - Various test failure patterns
        - Flaky tests and anomalies
        - Correlated test failures
        - Performance degradation patterns
        - Warning patterns

        Args:
            days: Number of days of data to generate
            lightweight: If True, generate a smaller, more efficient dataset

        Returns:
            None
        """
        console = Console()

        # Create the profile if it doesn't exist
        try:
            from pytest_insight.core.storage import create_profile, get_profile_manager

            profile_manager = get_profile_manager()

            # Check if profile exists
            if "showcase" in profile_manager.profiles:
                console.print("Using existing profile: showcase")
            else:
                create_profile("showcase", "json")
                console.print("Created new profile: showcase")
        except Exception as e:
            console.print(f"[bold red]Error creating profile: {str(e)}[/bold red]")
            return

        # Adjust parameters for lightweight mode
        if lightweight:
            # Reduce days if in lightweight mode
            actual_days = min(days, 15)
            targets_per_base = 2
            suts_to_use = 3
            console.print("[bold yellow]Using lightweight mode with reduced data volume[/bold yellow]")
        else:
            actual_days = days
            targets_per_base = 3
            suts_to_use = 5

        # Generate showcase data in multiple batches to create diverse patterns

        # 1. Generate stable baseline data (first third of time period)
        console.print("\n[bold]Generating baseline data...[/bold]")
        baseline_generator = TrendDataGenerator(
            storage_profile="showcase",
            days=actual_days // 3,
            targets_per_base=targets_per_base,
            start_date=datetime.now(ZoneInfo("UTC")) - timedelta(days=actual_days),
            trend_strength=0.2,  # Minimal trend
            anomaly_rate=0.02,  # Few anomalies
            correlation_groups=2,
        )
        # Limit the number of SUTs for better performance
        baseline_generator.sut_variations = baseline_generator.sut_variations[:suts_to_use]

        # Ensure we have a high pass rate but with some consistent failures
        baseline_generator.pass_rate = 0.95  # Start with high pass rate
        baseline_generator.flaky_rate = 0.03  # Low flakiness

        # Add specific error patterns for the error message analysis
        baseline_generator.error_patterns = [
            "AssertionError: Expected value",
            "TypeError: Cannot convert",
            "ValueError: Invalid parameter",
        ]

        # Add stack trace patterns for stack trace analysis
        baseline_generator.stack_trace_patterns = [
            "File 'test_module.py', line 42, in test_function\n    assert value == expected",
            "File 'core/utils.py', line 123, in function\n    return process(value)",
        ]

        # Ensure we have some tests with warnings
        baseline_generator.warning_rate = 0.15  # 15% of tests have warnings
        baseline_generator.warning_patterns = [
            "DeprecationWarning: This function is deprecated",
            "ResourceWarning: Unclosed file",
        ]

        baseline_generator.generate_trend_data()

        # 2. Generate degradation period (middle third)
        console.print("\n[bold]Generating degradation period...[/bold]")
        degradation_generator = TrendDataGenerator(
            storage_profile="showcase",
            days=actual_days // 3,
            targets_per_base=targets_per_base,
            start_date=datetime.now(ZoneInfo("UTC")) - timedelta(days=actual_days - (actual_days // 3)),
            trend_strength=0.7,  # Strong degradation trend
            anomaly_rate=0.1,  # More anomalies
            correlation_groups=3,
        )
        # Limit the number of SUTs for better performance
        degradation_generator.sut_variations = degradation_generator.sut_variations[:suts_to_use]

        degradation_generator.pass_rate = 0.85  # Lower pass rate
        degradation_generator.flaky_rate = 0.08  # Higher flakiness

        # Add performance degradation patterns
        degradation_generator.duration_degradation_factor = 1.5  # Tests get 50% slower

        # Add more error patterns for the error message analysis
        degradation_generator.error_patterns = [
            "TimeoutError: Operation timed out",
            "ConnectionError: Failed to connect",
            "RuntimeError: Unexpected condition",
        ]

        # Add more stack trace patterns
        degradation_generator.stack_trace_patterns = [
            "File 'database/connection.py', line 78, in connect\n    conn = driver.connect(url, timeout=30)",
            "File 'network/client.py', line 142, in send_request\n    response = await self.session.post(endpoint, data=payload)",
        ]

        # Increase warning rate
        degradation_generator.warning_rate = 0.25  # 25% of tests have warnings

        degradation_generator.generate_trend_data()

        # 3. Generate recovery period (final third)
        console.print("\n[bold]Generating recovery period...[/bold]")
        recovery_generator = TrendDataGenerator(
            storage_profile="showcase",
            days=actual_days // 3,
            targets_per_base=targets_per_base,
            start_date=datetime.now(ZoneInfo("UTC")) - timedelta(days=actual_days - 2 * (actual_days // 3)),
            trend_strength=0.5,  # Moderate trend (improvement)
            anomaly_rate=0.05,  # Fewer anomalies
            correlation_groups=2,
        )
        # Limit the number of SUTs for better performance
        recovery_generator.sut_variations = recovery_generator.sut_variations[:suts_to_use]

        recovery_generator.pass_rate = 0.75  # Starting from lower point
        recovery_generator.flaky_rate = 0.12  # Still dealing with flakiness

        # Add performance improvement patterns
        recovery_generator.duration_degradation_factor = 0.8  # Tests get 20% faster

        # Add error patterns that are being fixed
        recovery_generator.error_patterns = [
            "AssertionError: Expected value",  # Consistent with baseline
            "ValueError: Invalid parameter",  # Consistent with baseline
            "BugFixedError: This error is being fixed",
        ]

        # Add stack trace patterns showing fixes
        recovery_generator.stack_trace_patterns = [
            "File 'test_module.py', line 42, in test_function\n    assert value == expected",
            "File 'fixed_module.py', line 87, in improved_function\n    return process_safely(data)",
        ]

        # Decrease warning rate
        recovery_generator.warning_rate = 0.10  # 10% of tests have warnings

        # Invert the trend to show improvement
        recovery_generator._get_degradation_factor = lambda session_time: max(
            0.5,
            1.0
            - recovery_generator.trend_strength
            * ((session_time - recovery_generator.start_date) / timedelta(days=recovery_generator.days)),
        )
        recovery_generator.generate_trend_data()

        # Show success message
        console.print(
            Panel(
                f"Generated showcase data for {actual_days} days\n"
                f"The showcase dataset demonstrates:\n"
                f"- Initial stability period\n"
                f"- Degradation period with increasing failures\n"
                f"- Recovery period showing improvement\n"
                f"- Various test failure patterns and anomalies\n"
                f"- Correlated test failures and performance trends",
                title="Showcase Profile Created",
                border_style="green",
            )
        )

        # Provide instructions for viewing
        console.print("\n[bold]To view the showcase data:[/bold]")
        console.print("insight dashboard launch --profile showcase")

        return
