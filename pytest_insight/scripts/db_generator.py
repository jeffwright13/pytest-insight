import json
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import typer

from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession
from pytest_insight.storage import get_profile_manager, get_storage_instance


class TextGenerator:
    """Generate random text content for testing."""

    WORD_LENGTH_RANGE = (3, 10)
    WORDS_PER_SENTENCE = (5, 15)
    SENTENCES_PER_PARAGRAPH = (3, 7)

    @staticmethod
    def word(length=None):
        """Generate a random word."""
        if length is None:
            length = random.randint(*TextGenerator.WORD_LENGTH_RANGE)
        return "".join(random.choices(string.ascii_lowercase, k=length))

    @classmethod
    def sentence(cls):
        """Generate a random sentence."""
        num_words = random.randint(*cls.WORDS_PER_SENTENCE)
        words = [cls.word() for _ in range(num_words)]
        words[0] = words[0].capitalize()
        return " ".join(words) + "."

    @classmethod
    def paragraph(cls):
        """Generate a random paragraph."""
        num_sentences = random.randint(*cls.SENTENCES_PER_PARAGRAPH)
        return " ".join(cls.sentence() for _ in range(num_sentences))


class PracticeDataGenerator:
    """
    Generates practice test data with variations for learning and exploration.

    Parameters:
        storage_profile (Optional[str]): Storage profile to use.
        target_path (Optional[Path]): Path to save the generated data.
        days (int): Number of days to generate data for.
        targets_per_base (int): Number of targets per base SUT.
        start_date (Optional[datetime]): Start date for the data generation.
        pass_rate (float): Percentage of passing tests.
        flaky_rate (float): Percentage of flaky tests.
        warning_rate (float): Percentage of warning tests.
        sut_filter (Optional[str]): Filter SUTs by prefix.
        test_categories (Optional[list[str]]): List of test categories.

    """

    def __init__(
        self,
        storage_profile: Optional[str] = None,
        target_path: Optional[Path] = None,
        days: int = 7,
        targets_per_base: int = 3,
        start_date: Optional[datetime] = None,
        pass_rate: float = 0.45,
        flaky_rate: float = 0.17,
        warning_rate: float = 0.085,
        sut_filter: Optional[str] = None,
        test_categories: Optional[list[str]] = None,
    ):
        self.storage_profile = storage_profile
        self.target_path = target_path or Path.home() / ".pytest_insight" / "practice.json"
        self.days = days
        self.targets_per_base = targets_per_base
        self.start_date = start_date
        self.pass_rate = max(0.1, min(0.9, pass_rate))
        self.flaky_rate = max(0.05, min(0.3, flaky_rate))
        self.warning_rate = max(0.01, min(0.2, warning_rate))
        self.text_gen = TextGenerator()

        # Define variations for generating data
        self.module_types = ["api", "ui", "db", "auth", "integration", "performance"]
        self.test_types = ["get", "post", "update", "delete", "list", "create"]

        self.sut_variations = [f"{module}-service" for module in self.module_types] + [
            "ref-sut-openjdk11",
            "ref-sut-openjdk17",
            "ref-sut-openjdk21",
            "ref-sut-python39",
            "ref-sut-python310",
            "ref-sut-python311",
            "ref-sut-python312",
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
            ],
            "ui": [
                "test_ui/test_pages.py::test_home_page",
                "test_ui/test_pages.py::test_login_page",
                "test_ui/test_components.py::test_button_click",
            ],
            "db": [
                "test_db/test_queries.py::test_select",
                "test_db/test_queries.py::test_insert",
                "test_db/test_transactions.py::test_commit",
            ],
            "auth": [
                "test_auth/test_login.py::test_valid_credentials",
                "test_auth/test_login.py::test_invalid_password",
                "test_auth/test_tokens.py::test_token_expiry",
            ],
            "integration": [
                "test_integration/test_workflow.py::test_end_to_end",
                "test_integration/test_services.py::test_service_communication",
                "test_integration/test_database.py::test_data_consistency",
            ],
            "performance": [
                "test_performance/test_load.py::test_concurrent_users[100]",
                "test_performance/test_load.py::test_concurrent_users[500]",
                "test_performance/test_response.py::test_response_time",
            ],
        }

        # Filter test categories if specified
        if test_categories:
            invalid_categories = set(test_categories) - set(self.test_patterns.keys())
            if invalid_categories:
                raise ValueError(f"Invalid test categories: {invalid_categories}")
            self.test_patterns = {k: v for k, v in self.test_patterns.items() if k in test_categories}

    def _get_test_time(self, offset_seconds: int = 0) -> datetime:
        """Get a consistent timezone-aware timestamp for tests.

        Args:
            offset_seconds: Number of seconds to add to base time.

        Returns:
            A UTC datetime starting from a fixed base time plus the offset.
        """
        base_time = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))
        return base_time + timedelta(seconds=offset_seconds)

    def _generate_session_id(self, sut_name: str, is_base: bool = False) -> str:
        """Generate a session ID following the proper pattern."""
        timestamp = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%d-%H%M%S")
        prefix = "base" if is_base else "target"
        return f"{prefix}-{sut_name}-{timestamp}-{random.randint(10000000, 99999999):x}"

    def _generate_test_result(
        self,
        nodeid: str,
        start_time: datetime,
        outcome: TestOutcome,
        duration: float,
        has_warning: bool = False,
    ) -> TestResult:
        """Generate a test result with realistic output."""
        # Ensure start_time is timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=ZoneInfo("UTC"))

        caplog = self.text_gen.sentence()
        capstderr = self.text_gen.sentence() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else ""
        capstdout = self.text_gen.sentence()
        longreprtext = self.text_gen.paragraph() if outcome in [TestOutcome.FAILED, TestOutcome.ERROR] else ""

        return TestResult(
            nodeid=nodeid,
            outcome=outcome,
            start_time=start_time,
            duration=duration,
            caplog=caplog,
            capstderr=capstderr,
            capstdout=capstdout,
            longreprtext=longreprtext,
            has_warning=has_warning,
        )

    def _create_session(
        self,
        sut_name: str,
        session_time: datetime,
        is_base: bool = False,
    ) -> TestSession:
        """Create a test session with realistic test results."""
        # Select a module type that matches the SUT name
        module_type = next(
            (m for m in self.module_types if m in sut_name.lower()),
            random.choice(self.module_types),
        )

        # Get test patterns for this module
        test_patterns = self.test_patterns.get(module_type, [])
        if not test_patterns:
            test_patterns = random.choice(list(self.test_patterns.values()))

        # Generate test results
        test_results = []
        rerun_groups = []
        current_time = session_time

        for test_pattern in test_patterns:
            # Determine if this test should be flaky
            is_flaky = random.random() < self.flaky_rate

            if is_flaky:
                # Create a rerun group
                rerun_group = RerunTestGroup(nodeid=test_pattern)
                num_runs = random.randint(2, 4)

                for i in range(num_runs):
                    is_final = i == num_runs - 1
                    outcome = (
                        random.choices(
                            [TestOutcome.PASSED, TestOutcome.FAILED],
                            weights=[0.8, 0.2],
                        )[0]
                        if is_final
                        else TestOutcome.RERUN
                    )

                    result = self._generate_test_result(
                        test_pattern,
                        current_time,
                        outcome,
                        random.uniform(0.1, 5.0),
                        has_warning=random.random() < self.warning_rate,
                    )
                    rerun_group.add_test(result)
                    test_results.append(result)
                    current_time += timedelta(seconds=result.duration + 1)

                rerun_groups.append(rerun_group)
            else:
                # Regular test result
                outcome = random.choices(
                    list(TestOutcome),
                    weights=[
                        self.pass_rate,  # PASSED
                        0.1,  # FAILED
                        0.05,  # ERROR
                        0.05,  # SKIPPED
                        0.15,  # XFAILED
                        0.05,  # XPASSED
                        0.0,  # RERUN (handled separately)
                    ],
                )[0]

                result = self._generate_test_result(
                    test_pattern,
                    current_time,
                    outcome,
                    random.uniform(0.1, 5.0),
                    has_warning=random.random() < self.warning_rate,
                )
                test_results.append(result)
                current_time += timedelta(seconds=result.duration + 0.5)

        # Create session with proper timing
        session_start_time = min(r.start_time for r in test_results)
        session_stop_time = max(r.stop_time for r in test_results)

        return TestSession(
            sut_name=sut_name,
            session_id=self._generate_session_id(sut_name, is_base),
            session_start_time=session_start_time,
            session_stop_time=session_stop_time,
            test_results=test_results,
            rerun_test_groups=rerun_groups,
        )

    def _ensure_valid_profile(self, profile_name):
        """Ensure that the profile exists and has a valid file path."""
        profile_manager = get_profile_manager()

        try:
            # Try to get the existing profile
            profile = profile_manager.get_profile(profile_name)
            print(f"Using existing profile: {profile_name}")

            # Check if the profile has a valid file path
            if profile.file_path is None:
                # Create a default path for this profile
                default_path = str(Path.home() / ".pytest_insight" / f"{profile_name}.json")
                print(f"Profile has no file path. Creating a new profile with path: {default_path}")

                # We can't modify the existing profile directly, so we need to create a new one
                # First, remember if this was the active profile
                was_active = profile_manager.active_profile_name == profile_name

                try:
                    # Try to delete the profile (might fail if it's the active profile)
                    profile_manager.delete_profile(profile_name)
                except ValueError as e:
                    if "active profile" in str(e):
                        # It's the active profile, so we need to switch to another one first
                        print("Temporarily switching to default profile")
                        profile_manager.switch_profile("default")
                        profile_manager.delete_profile(profile_name)
                    else:
                        raise

                # Create a new profile with the same name but a valid file path
                profile = profile_manager.create_profile(name=profile_name, storage_type="json", file_path=default_path)

                # If it was the active profile, switch back to it
                if was_active:
                    profile_manager.switch_profile(profile_name)

            return profile

        except ValueError:
            # Profile doesn't exist, create it
            print(f"Creating new profile: {profile_name}")
            default_path = str(Path.home() / ".pytest_insight" / f"{profile_name}.json")
            return profile_manager.create_profile(name=profile_name, storage_type="json", file_path=default_path)

    def _save_to_file(self, all_sessions):
        # Save to file directly (backward compatibility)
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.target_path, "w") as f:
            json.dump(
                {"sessions": [session.to_dict() for session in all_sessions]},
                f,
                indent=2,
            )

    def generate_practice_data(self) -> None:
        """Generate practice data with various test scenarios."""
        all_sessions = []
        base_time = self.start_date or self._get_test_time()

        for sut_name in self.sut_variations:
            for day in range(self.days):
                session_date = base_time + timedelta(days=day)

                # Create base session
                base_session = self._create_session(
                    sut_name=sut_name,
                    session_time=session_date,
                    is_base=True,
                )
                all_sessions.append(base_session)

                # Generate target sessions
                num_targets = random.randint(1, self.targets_per_base)
                for _ in range(num_targets):
                    target_date = session_date + timedelta(
                        hours=random.randint(1, 23),
                        minutes=random.randint(0, 59),
                    )
                    target_session = self._create_session(
                        sut_name=sut_name,
                        session_time=target_date,
                        is_base=False,
                    )
                    all_sessions.append(target_session)

        # Sort sessions by start time
        all_sessions.sort(key=lambda x: x.session_start_time)

        # Save to file or storage profile
        if self.storage_profile:
            try:
                # Ensure the profile exists and has a valid file path
                profile = self._ensure_valid_profile(self.storage_profile)

                # Get a storage instance for this profile
                storage = get_storage_instance(profile_name=self.storage_profile)

                # Save the sessions (storage expects TestSession objects)
                storage.save_sessions(all_sessions)

                print(f"Data saved to storage profile: {self.storage_profile}")
                print(f"Profile path: {profile.file_path}")

                # Update target_path to match the profile's path
                self.target_path = Path(profile.file_path)
            except Exception as e:
                print(f"Error saving to profile {self.storage_profile}: {e}")
                print("Falling back to direct file save")
                self._save_to_file(all_sessions)
        else:
            # Save to file directly (backward compatibility)
            self._save_to_file(all_sessions)


app = typer.Typer(
    name="insight-gen",
    help="Generate practice test data for pytest-insight",
    no_args_is_help=True,
)


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
        help="Start date for data generation (format: YYYY-MM-DD). Default: 2023-01-01",
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
        help="Filter SUTs by prefix (api-, ui-, db-, auth-, integration-, performance-)",
    ),
    categories: str = typer.Option(
        None,
        "--categories",
        "-c",
        help="Comma-separated list of test categories to include (api,ui,db,auth,integration,performance)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress detailed output, only show essential information",
    ),
    storage_profile: str = typer.Option(
        None,
        "--storage-profile",
        help="Storage profile to use for data generation",
    ),
):
    """Generate practice test data with configurable parameters.

    Examples:
        # Generate 30 days of data with up to 5 target sessions per base
        insight-gen --days 30 --targets 5

        # Generate data with custom outcome rates
        insight-gen --pass-rate 0.6 --flaky-rate 0.1 --warning-rate 0.05

        # Generate data for specific SUT type and test categories
        insight-gen --sut-filter api- --categories api,integration

        # Generate minimal data quickly
        insight-gen --days 3 --targets 2 --quiet

    The generated data will maintain realistic test outcome distributions while
    respecting the configured parameters. Test categories include:
    - api: API endpoint tests
    - ui: User interface tests
    - db: Database operation tests
    - auth: Authentication tests
    - integration: Service integration tests
    - performance: Load and response time tests
    """
    try:
        # Parse start date if provided
        parsed_start_date = None
        if start_date:
            try:
                # Use datetime(2023, 1, 1) as base like conftest.py
                base = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))
                parsed_date = datetime.strptime(start_date, "%Y-%m-%d")
                parsed_start_date = base + timedelta(days=(parsed_date - datetime(2023, 1, 1)).days)
            except ValueError as e:
                if "format" in str(e):
                    raise typer.BadParameter("Start date must be in YYYY-MM-DD format")
                raise typer.BadParameter(str(e))

        # Parse test categories if provided
        test_categories = None
        if categories:
            test_categories = [cat.strip() for cat in categories.split(",")]
            valid_categories = {"api", "ui", "db", "auth", "integration", "performance"}
            invalid = set(test_categories) - valid_categories
            if invalid:
                raise typer.BadParameter(
                    f"Invalid categories: {', '.join(invalid)}. "
                    f"Valid categories are: {', '.join(sorted(valid_categories))}"
                )

        # Create generator instance
        generator = PracticeDataGenerator(
            storage_profile=storage_profile,
            target_path=Path(output) if output else None,
            days=days,
            targets_per_base=targets,
            start_date=parsed_start_date,
            pass_rate=pass_rate,
            flaky_rate=flaky_rate,
            warning_rate=warning_rate,
            sut_filter=sut_filter,
            test_categories=test_categories,
        )

        # Generate practice data
        generator.generate_practice_data()

        if not quiet:
            print(f"Generated practice data for {days} days")
            print(f"Data saved to: {generator.target_path}")

    except Exception as e:
        raise typer.BadParameter(str(e))


if __name__ == "__main__":
    app()
