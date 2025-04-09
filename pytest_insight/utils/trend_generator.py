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

from pytest_insight.core.models import (
    TestOutcome,
    TestResult,
    TestSession,
)
from pytest_insight.core.storage import get_storage_instance
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
        start_time: datetime,
        outcome: TestOutcome,
        duration: float,
        has_warning: bool = False,
        sut: str = "",
    ) -> TestResult:
        """Generate a test result with realistic output and error patterns."""
        # Use the parent class implementation as a starting point
        result = super()._generate_test_result(
            nodeid=nodeid,
            start_time=start_time,
            outcome=outcome,
            duration=duration,
            has_warning=has_warning,
        )

        # For failed tests, generate more realistic error messages
        if outcome in [TestOutcome.FAILED, TestOutcome.ERROR]:
            error_message = self._generate_error_message(sut, nodeid)
            result.error_message = error_message

            # Simplified stack trace
            result.stack_trace = (
                "Traceback (most recent call last):\n"
                f'  File "{nodeid.split("::")[0]}.py", line {random.randint(10, 500)}, in {nodeid.split("::")[-1]}\n'
                f"    {self.text_gen.word()}({self.text_gen.word()}, {self.text_gen.word()})\n"
                f"{outcome.name}Error: {error_message}"
            )

        return result

    def _create_session(
        self,
        sut_name: str,
        session_time: datetime,
        is_base: bool = False,
    ) -> TestSession:
        """Create a test session with realistic test results and trends."""
        # Generate session ID
        session_id = self._generate_session_id(sut_name, is_base)

        # Calculate degradation factor for this session time
        degradation = self._get_degradation_factor(session_time)

        # Adjust pass/fail rates based on degradation
        adjusted_pass_rate = max(0.2, self.pass_rate / degradation)
        adjusted_flaky_rate = min(0.5, self.flaky_rate * degradation)
        adjusted_warning_rate = min(0.3, self.warning_rate * degradation)

        # Check if this is an anomaly session
        is_anomaly = random.random() < self.anomaly_rate
        if is_anomaly:
            # Anomaly sessions have much worse pass rates
            adjusted_pass_rate = max(0.1, adjusted_pass_rate * 0.5)
            adjusted_flaky_rate = min(0.7, adjusted_flaky_rate * 2.0)

        # Create the session
        session = TestSession(
            sut_name=sut_name,
            session_id=session_id,
            session_start_time=session_time,
            session_stop_time=session_time + timedelta(minutes=random.randint(5, 30)),
            session_duration=random.uniform(300, 1800),  # 5-30 minutes
            test_results=[],
            session_tags={
                "env": random.choice(["dev", "staging", "prod"]),
                "region": random.choice(["us-east", "us-west", "eu-central"]),
                "build": f"{random.randint(1000, 9999)}",
                "version": f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                "is_anomaly": "true" if is_anomaly else "false",
            },
        )

        # Get test patterns for this SUT
        sut_type = sut_name.split("-")[0]
        test_patterns = self.test_patterns.get(sut_type, ["test_default"])

        # Generate test results - reduced number for performance
        num_tests = random.randint(10, 25)

        # Track which tests are part of correlated groups
        correlated_tests = set()
        for group in self.correlated_groups.get(sut_name, []):
            for test in group:
                correlated_tests.add(test)

        # Generate the tests
        for i in range(num_tests):
            # Determine test details
            module = random.choice(test_patterns)
            test_type = random.choice(self.test_types)
            test_name = f"test_{test_type}_{self.text_gen.word()}"
            nodeid = f"{module}::{test_name}"

            # Determine test outcome
            has_warning = random.random() < adjusted_warning_rate

            # Check if this is a correlated failure
            if nodeid in correlated_tests and self._is_correlated_failure(sut_name, nodeid, session_time):
                outcome = TestOutcome.FAILED
            else:
                # Normal outcome determination
                if random.random() < adjusted_pass_rate:
                    outcome = TestOutcome.PASSED
                elif random.random() < adjusted_flaky_rate:
                    outcome = random.choice([TestOutcome.PASSED, TestOutcome.FAILED])
                else:
                    outcome = random.choice(
                        [
                            TestOutcome.FAILED,
                            TestOutcome.ERROR,
                            TestOutcome.SKIPPED,
                        ]
                    )

            # Generate test duration (failed tests tend to be faster)
            if outcome == TestOutcome.PASSED:
                duration = random.uniform(0.1, 5.0)
            else:
                duration = random.uniform(0.05, 2.0)

            # Create the test result
            test_result = self._generate_test_result(
                nodeid=nodeid,
                start_time=session_time + timedelta(seconds=random.randint(0, 300)),
                outcome=outcome,
                duration=duration,
                has_warning=has_warning,
                sut=sut_name,
            )

            # Add to session
            session.test_results.append(test_result)

        return session

    def generate_trend_data(self):
        """Generate test data with realistic trends and patterns."""
        console = Console()

        # Determine storage target
        if self.storage_profile:
            try:
                self._ensure_valid_profile(self.storage_profile)
            except Exception as e:
                console.print(f"[bold red]Error with profile: {str(e)}[/bold red]")
                raise
        else:
            self.target_path.parent.mkdir(parents=True, exist_ok=True)

        # Show generation parameters
        if not hasattr(self, "quiet") or not self.quiet:
            table = Table(title="Trend Generation Parameters")
            table.add_column("Parameter", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Days", str(self.days))
            table.add_row("Targets per base", str(self.targets_per_base))
            table.add_row("Initial pass rate", f"{self.pass_rate:.1%}")
            table.add_row("Trend strength", f"{self.trend_strength:.1%}")
            table.add_row("Anomaly rate", f"{self.anomaly_rate:.1%}")
            table.add_row("Correlation groups", str(self.correlation_groups))

            console.print(table)

        # Generate sessions with trends
        with console.status(
            f"[bold green]Generating trend data for {self.days} days...[/bold green]",
            spinner="dots",
        ):
            all_sessions = []

            # Calculate time range
            if not self.start_date:
                self.start_date = datetime.now(ZoneInfo("UTC")) - timedelta(days=self.days)

            # Limit SUTs for better performance
            limited_suts = self.sut_variations[:5]

            # For each day
            for day in range(self.days):
                day_time = self.start_date + timedelta(days=day)

                # For each SUT
                for sut_name in limited_suts:
                    # Create a base session
                    base_session = self._create_session(
                        sut_name=sut_name,
                        session_time=day_time + timedelta(hours=random.randint(0, 12)),
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

            # Save the sessions
            if self.storage_profile:
                # Save to profile
                storage = get_storage_instance(profile_name=self.storage_profile)
                storage.save_sessions(all_sessions)
            else:
                # Save to file
                self._save_to_file(all_sessions)

        # Show success message
        console.print(
            Panel(
                f"[bold green]Generated trend data for {self.days} days[/bold green]\n"
                f"Saved to: {self.target_path if self.target_path else f'profile {self.storage_profile}'}\n"
                f"Total sessions: {len(all_sessions)}",
                title="Success",
                border_style="green",
            )
        )

        return all_sessions
