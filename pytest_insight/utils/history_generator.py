"""
HistoryDataGenerator: Generate realistic, configurable historical test data for pytest-insight v2.
- Output: JSON profile (list of TestSessions and associated data)
- Usage: CLI or importable class for integration/testing/demo
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import typer
from pytest_insight.core.models import TestSession, TestResult

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
            return min(top, base + (top-base)*self.trend_strength*day/(self.days-1))
        elif sut == self.suts[1]:
            # Declining
            return max(base, top - (top-base)*self.trend_strength*day/(self.days-1))
        else:
            # Cyclic
            return base + (top-base)*(0.5+0.5*random.uniform(-1,1)*self.trend_strength)

    def _get_correlated_failures(self, day: int) -> List[str]:
        # Pick a group of tests to fail together (simulate correlation)
        group_size = max(2, len(self.test_ids)//self.correlation_groups)
        start = random.randint(0, len(self.test_ids)-group_size)
        return self.test_ids[start:start+group_size]

    def generate(self) -> List[TestSession]:
        now = datetime.now()
        sessions = []
        for day in range(self.days):
            day_time = now - timedelta(days=(self.days-day))
            for s in range(self.sessions_per_day):
                sut = random.choice(self.suts)
                session_id = f"{sut}-{day}-{s}-{random.randint(1000,9999)}"
                pass_rate = self._get_pass_rate(day, sut)
                correlated = self._get_correlated_failures(day) if random.random() < self.anomaly_rate else []
                test_results = []
                for tid in self.test_ids:
                    if tid in correlated:
                        outcome = "failed"
                    else:
                        outcome = "passed" if random.random() < pass_rate else "failed"
                    duration = random.uniform(1, 10) + (0 if outcome=="passed" else random.uniform(0, 10))
                    test_results.append(TestResult(
                        nodeid=tid,
                        outcome=outcome,
                        start_time=day_time,
                        stop_time=day_time + timedelta(seconds=duration),
                        duration=duration,
                    ))
                session_outcome = "passed" if all(t.outcome=="passed" for t in test_results) else "failed"
                sessions.append(TestSession(
                    session_id=session_id,
                    session_start_time=day_time,
                    outcome=session_outcome,
                    test_results=test_results,
                ))
        return sessions

    def save_profile(self, sessions: List[TestSession], path: Path):
        # Serialize sessions to JSON (as dicts)
        def session_to_dict(sess: TestSession):
            return {
                "session_id": sess.session_id,
                "session_start_time": sess.session_start_time.isoformat(),
                "outcome": sess.outcome,
                "test_results": [
                    {
                        "nodeid": tr.nodeid,
                        "outcome": tr.outcome,
                        "start_time": tr.start_time.isoformat(),
                        "stop_time": tr.stop_time.isoformat(),
                        "duration": tr.duration,
                    } for tr in sess.test_results
                ]
            }
        with open(path, "w") as f:
            json.dump([session_to_dict(s) for s in sessions], f, indent=2)

app = typer.Typer()

@app.command()
def generate(
    days: int = typer.Option(30, help="Number of days of history to generate."),
    sessions_per_day: int = typer.Option(4, help="Sessions per day."),
    suts: str = typer.Option("api-service,ui-service,db-service", help="Comma-separated SUT names."),
    test_ids: str = typer.Option("test_login,test_logout,test_create_user,test_delete_user,test_update_profile,test_list_items,test_db_connect,test_db_query,test_api_health,test_ui_render", help="Comma-separated test ids."),
    trend_strength: float = typer.Option(0.7, help="Trend strength (0-1)."),
    anomaly_rate: float = typer.Option(0.05, help="Rate of correlated/anomalous failures."),
    correlation_groups: int = typer.Option(3, help="Number of correlated test groups."),
    pass_rate_min: float = typer.Option(0.5, help="Minimum pass rate."),
    pass_rate_max: float = typer.Option(0.95, help="Maximum pass rate."),
    warning_rate: float = typer.Option(0.1, help="Warning rate."),
    seed: Optional[int] = typer.Option(None, help="Random seed for reproducibility."),
    output: Path = typer.Option("practice_profile.json", help="Output JSON file."),
):
    """Generate historical test data and save as a profile (JSON)."""
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
    generator.save_profile(sessions, output)
    typer.echo(f"Generated {len(sessions)} sessions and saved to {output}")

if __name__ == "__main__":
    app()
