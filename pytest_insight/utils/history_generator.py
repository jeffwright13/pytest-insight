"""
HistoryDataGenerator: Generate realistic, configurable historical test data for pytest-insight v2.
- Output: JSON profile (list of TestSessions and associated data)
- Usage: CLI or importable class for integration/testing/demo
"""

import os
import random
from datetime import datetime, timedelta
from typing import List, Optional

import typer

from pytest_insight.core.models import (
    RerunTestGroup,
    TestOutcome,
    TestResult,
    TestSession,
)
from pytest_insight.core.storage import ProfileManager, get_storage_instance


class HistoryDataGenerator:
    """Generates historical test sessions with trends, correlations, and variability."""

    def __init__(
        self,
        days: int = 30,
        sessions_per_day: int = 4,
        suts: Optional[List[str]] = None,
        test_ids: Optional[List[str]] = None,
        trend_strength: float = 0.7,
        anomaly_rate: float = 0.05,
        correlation_groups: int = 3,
        pass_rate_range: tuple = (0.5, 0.95),
        warning_rate: float = 0.1,
        seed: Optional[int] = None,
    ):
        self.days = days
        self.sessions_per_day = sessions_per_day
        self.suts = suts or ["api-service", "ui-service", "db-service"]
        self.test_ids = test_ids or [
            "test_login",
            "test_logout",
            "test_create_user",
            "test_delete_user",
            "test_update_profile",
            "test_list_items",
            "test_db_connect",
            "test_db_query",
            "test_api_health",
            "test_ui_render",
        ]
        self.trend_strength = trend_strength
        self.anomaly_rate = anomaly_rate
        self.correlation_groups = correlation_groups
        self.pass_rate_range = pass_rate_range
        self.warning_rate = warning_rate
        self.seed = seed
        if seed is not None:
            random.seed(seed)

    def _get_pass_rate(self, day: int, sut: str) -> float:
        # Simulate trends: SUT0 improves, SUT1 declines, SUT2 cyclic
        base, top = self.pass_rate_range
        if sut == self.suts[0]:
            # Improving
            return min(top, base + (top - base) * self.trend_strength * day / (self.days - 1))
        elif sut == self.suts[1]:
            # Declining
            return max(base, top - (top - base) * self.trend_strength * day / (self.days - 1))
        else:
            # Cyclic
            return base + (top - base) * (0.5 + 0.5 * random.uniform(-1, 1) * self.trend_strength)

    def _get_correlated_failures(self, day: int) -> List[str]:
        # Pick a group of tests to fail together (simulate correlation)
        group_size = max(2, len(self.test_ids) // self.correlation_groups)
        start = random.randint(0, len(self.test_ids) - group_size)
        return self.test_ids[start : start + group_size]

    def generate(self) -> List[TestSession]:
        now = datetime.now()
        sessions = []
        for day in range(self.days):
            day_time = now - timedelta(days=(self.days - day))
            for s in range(self.sessions_per_day):
                sut = random.choice(self.suts)
                session_id = f"{sut}-{day}-{s}-{random.randint(1000,9999)}"
                pass_rate = self._get_pass_rate(day, sut)
                correlated = self._get_correlated_failures(day) if random.random() < self.anomaly_rate else []
                test_results = []
                for tid in self.test_ids:
                    if tid in correlated:
                        outcome = "FAILED"
                    else:
                        outcome = "PASSED" if random.random() < pass_rate else "FAILED"
                    duration = 0 if outcome == "PASSED" else random.uniform(0, 10)
                    test_results.append(
                        TestResult(
                            nodeid=tid,
                            outcome=TestOutcome.from_str(outcome),
                            start_time=day_time,
                            stop_time=day_time + timedelta(seconds=duration),
                            duration=duration,
                        )
                    )
                # Add realistic session tags and system info
                session_tags = {
                    "env": random.choice(["dev", "staging", "prod"]),
                    "branch": random.choice(["main", "develop", "feature-x"]),
                    "user": random.choice(["alice", "bob", "carol"]),
                }
                testing_system = {
                    "os": random.choice(["linux", "windows", "macos"]),
                    "python": random.choice(["3.9", "3.10", "3.11", "3.12"]),
                    "ci": random.choice(["github", "gitlab", "jenkins"]),
                }
                # Simulate rerun test groups for a subset of test_ids
                rerun_test_groups = []
                rerun_candidates = random.sample(self.test_ids, k=max(1, len(self.test_ids) // 4))
                for nodeid in rerun_candidates:
                    rerun_results = [
                        TestResult(
                            nodeid=nodeid,
                            outcome=TestOutcome.from_str(random.choice(["FAILED", "PASSED"])),
                            start_time=day_time,
                            stop_time=day_time + timedelta(seconds=random.uniform(0.1, 2)),
                            duration=random.uniform(0.1, 2),
                            caplog="Rerun log",
                            capstderr="",
                            capstdout="",
                            longreprtext="",
                            has_warning=False,
                        )
                        for _ in range(random.randint(2, 3))
                    ]
                    rerun_test_groups.append(
                        RerunTestGroup(
                            nodeid=nodeid,
                            tests=rerun_results,
                        )
                    )
                session_stop_time = max(tr.stop_time for tr in test_results)
                session_duration = (session_stop_time - day_time).total_seconds()
                sessions.append(
                    TestSession(
                        sut_name=sut,
                        session_id=session_id,
                        session_start_time=day_time,
                        session_stop_time=session_stop_time,
                        session_duration=session_duration,
                        test_results=test_results,
                        rerun_test_groups=rerun_test_groups,
                        session_tags=session_tags,
                        testing_system=testing_system,
                    )
                )
        return sessions

    def save_profile(self, sessions: List[TestSession], profile_name: str, append: bool = False):
        """
        Save sessions using the ProfileManager and get_storage_instance exclusively (no direct file handling).
        """
        profile_mgr = ProfileManager()
        # Ensure profile exists (create if not present)
        if profile_name not in profile_mgr.profiles:
            profile_mgr.add_profile(profile_name, storage_type="json")
        storage = get_storage_instance(profile_name=profile_name)
        if append:
            existing = storage.load_sessions()
            all_sessions = existing + sessions
        else:
            all_sessions = sessions
        # Save all sessions (overwrite or append)
        if hasattr(storage, '_write_json_safely'):
            storage._write_json_safely([s.to_dict() for s in all_sessions])
        else:
            if not append:
                storage.clear_sessions()
            for session in all_sessions:
                storage.save_session(session)
        typer.echo(f"Saved {len(sessions)} sessions to profile '{profile_name}' at {getattr(storage, 'file_path', 'unknown location')}")

    def to_dict(self, sess: TestSession):
        return {
            "session_id": sess.session_id,
            "sut_name": sess.sut_name,
            "session_start_time": sess.session_start_time.isoformat(),
            "session_stop_time": sess.session_stop_time.isoformat(),
            "session_duration": sess.session_duration,
            "session_tags": sess.session_tags,
            "testing_system": sess.testing_system,
            "test_results": [
                {
                    "nodeid": tr.nodeid,
                    "outcome": (tr.outcome.to_str() if hasattr(tr.outcome, "to_str") else str(tr.outcome)),
                    "start_time": tr.start_time.isoformat(),
                    "stop_time": tr.stop_time.isoformat(),
                    "duration": tr.duration,
                    "caplog": getattr(tr, "caplog", ""),
                    "capstderr": getattr(tr, "capstderr", ""),
                    "capstdout": getattr(tr, "capstdout", ""),
                    "longreprtext": getattr(tr, "longreprtext", ""),
                    "has_warning": getattr(tr, "has_warning", False),
                }
                for tr in sess.test_results
            ],
            "rerun_test_groups": [
                {
                    "nodeid": rg.nodeid,
                    "tests": [
                        {
                            "nodeid": t.nodeid,
                            "outcome": (t.outcome.to_str() if hasattr(t.outcome, "to_str") else str(t.outcome)),
                            "start_time": t.start_time.isoformat(),
                            "stop_time": t.stop_time.isoformat(),
                            "duration": t.duration,
                            "caplog": getattr(t, "caplog", ""),
                            "capstderr": getattr(t, "capstderr", ""),
                            "capstdout": getattr(t, "capstdout", ""),
                            "longreprtext": getattr(t, "longreprtext", ""),
                            "has_warning": getattr(t, "has_warning", False),
                        }
                        for t in rg.tests
                    ],
                }
                for rg in sess.rerun_test_groups
            ],
        }


app = typer.Typer()


@app.command()
def generate(
    days: int = typer.Option(30, help="Number of days of history to generate."),
    sessions_per_day: int = typer.Option(4, help="Sessions per day."),
    suts: str = typer.Option("api-service,ui-service,db-service", help="Comma-separated SUT names."),
    test_ids: str = typer.Option(
        "test_login,test_logout,test_create_user,test_delete_user,test_update_profile,test_list_items,test_db_connect,test_db_query,test_api_health,test_ui_render",
        help="Comma-separated test ids.",
    ),
    trend_strength: float = typer.Option(0.7, help="Trend strength (0-1)."),
    anomaly_rate: float = typer.Option(0.05, help="Rate of correlated/anomalous failures."),
    correlation_groups: int = typer.Option(3, help="Number of correlated test groups."),
    pass_rate_min: float = typer.Option(0.5, help="Minimum pass rate."),
    pass_rate_max: float = typer.Option(0.95, help="Maximum pass rate."),
    warning_rate: float = typer.Option(0.1, help="Warning rate."),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducibility."),
    profile_name: str = typer.Option("default", help="Storage profile to use (default: 'default')."),
    append: bool = typer.Option(False, help="Append to existing profile instead of overwriting."),
):
    """Generate historical test data and save using a pytest-insight storage profile (via ProfileManager)."""
    generator = HistoryDataGenerator(
        days=days,
        sessions_per_day=sessions_per_day,
        suts=[s.strip() for s in suts.split(",")],
        test_ids=[t.strip() for t in test_ids.split(",")],
        trend_strength=trend_strength,
        anomaly_rate=anomaly_rate,
        correlation_groups=correlation_groups,
        pass_rate_range=(pass_rate_min, pass_rate_max),
        warning_rate=warning_rate,
        seed=seed,
    )
    sessions = generator.generate()
    generator.save_profile(sessions, profile_name, append)
    typer.echo(f"Generated {len(sessions)} sessions and saved to profile '{profile_name}'")


@app.command()
def purge_profiles(
    force: bool = typer.Option(False, help="Actually delete profiles and files (required for destructive action)."),
    dry_run: bool = typer.Option(False, help="Show what would be deleted, but don't actually delete anything."),
):
    """Purge all pytest-insight storage profiles and their data files (with dry run support)."""
    profile_mgr = ProfileManager()
    profiles = list(profile_mgr.profiles.values())
    if not profiles:
        typer.echo("No profiles found.")
        raise typer.Exit(0)

    typer.echo("The following profiles and files would be deleted:")
    for prof in profiles:
        typer.echo(f"- {prof.name}: {prof.file_path}")

    if dry_run:
        typer.echo("[DRY RUN] No files or profiles deleted.")
        raise typer.Exit(0)

    if not force:
        typer.echo("This is a destructive operation. Use --force to actually delete all profiles and files.")
        raise typer.Exit(1)

    for prof in profiles:
        if prof.file_path and os.path.exists(prof.file_path):
            os.remove(prof.file_path)
            typer.echo(f"Deleted file: {prof.file_path}")
        else:
            typer.echo(f"File not found: {prof.file_path}")
        typer.echo(f"Removed profile: {prof.name}")
    profile_mgr.profiles.clear()
    profile_mgr.active_profile_name = None
    profile_mgr._save_profiles()
    typer.echo("All profiles and their files have been purged.")


if __name__ == "__main__":
    app()
