from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, List, Optional

import typer

from pytest_insight.models import TestResult, TestSession


class TestFilter:
    """Filter test sessions and results based on various criteria."""

    def __init__(
        self,
        sut: Optional[str] = None,
        days: Optional[int] = None,
        outcome: Optional[str] = None,
        has_warnings: Optional[bool] = None,
        has_reruns: Optional[bool] = None,
        nodeid_contains: Optional[str] = None,
    ):
        self.sut = sut
        self.days = days
        self.outcome = outcome.upper() if outcome else None
        self.has_warnings = has_warnings
        self.has_reruns = has_reruns
        self.nodeid_contains = nodeid_contains

    def filter_sessions(self, sessions: List[TestSession]) -> List[TestSession]:
        """Apply filters to a list of test sessions."""
        filtered = sessions

        if self.sut:
            filtered = [s for s in filtered if s.sut_name == self.sut]

        if self.days:
            cutoff = datetime.now() - timedelta(days=self.days)
            filtered = [s for s in filtered if s.session_start_time > cutoff]

        return filtered

    def filter_results(self, results: List[TestResult]) -> List[TestResult]:
        """Apply filters to a list of test results."""
        filtered = results

        if self.outcome:
            filtered = [r for r in filtered if r.outcome.upper() == self.outcome]

        if self.has_warnings is not None:
            filtered = [r for r in filtered if r.has_warning == self.has_warnings]

        if self.nodeid_contains:
            filtered = [r for r in filtered if self.nodeid_contains in r.nodeid]

        return filtered


# Common filter options for CLI commands
def common_filter_options(f: Callable) -> Callable:
    """Decorator to add common filter options to CLI commands."""

    @wraps(f)
    def wrapper(
        *args,
        sut: Optional[str] = typer.Option(
            None, "--sut", help="Filter by System Under Test name"
        ),
        days: Optional[int] = typer.Option(
            None, "--days", help="Filter to last N days", min=0
        ),
        outcome: Optional[str] = typer.Option(
            None, "--outcome", help="Filter by test outcome (PASSED, FAILED, etc.)"
        ),
        warnings: Optional[bool] = typer.Option(
            None, "--warnings", help="Filter tests with warnings"
        ),
        reruns: Optional[bool] = typer.Option(
            None, "--reruns", help="Filter tests that were rerun"
        ),
        contains: Optional[str] = typer.Option(
            None, "--contains", help="Filter tests whose nodeid contains this string"
        ),
        **kwargs,
    ):
        # Only pass filter options if they're not None and not OptionInfo objects
        filter_args = {}
        if not isinstance(sut, typer.models.OptionInfo):
            filter_args["sut"] = sut
        if not isinstance(days, typer.models.OptionInfo):
            filter_args["days"] = days
        if not isinstance(outcome, typer.models.OptionInfo):
            filter_args["outcome"] = outcome
        if not isinstance(warnings, typer.models.OptionInfo):
            filter_args["warnings"] = warnings
        if not isinstance(reruns, typer.models.OptionInfo):
            filter_args["reruns"] = reruns
        if not isinstance(contains, typer.models.OptionInfo):
            filter_args["contains"] = contains

        return f(*args, **{**kwargs, **filter_args})

    return wrapper
