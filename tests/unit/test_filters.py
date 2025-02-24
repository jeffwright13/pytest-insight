import pytest
import typer
from typing import Optional
from pytest_insight.filters import common_filter_options, TestFilter
from pytest_insight.core.analyzer import SessionFilter

# Test command setup
app = typer.Typer()

@app.command()
@common_filter_options
def test_command(
    base_arg: str,
    sut: Optional[str] = None,
    days: Optional[int] = None,
    outcome: Optional[str] = None,
    warnings: Optional[bool] = None,
    reruns: Optional[bool] = None,
    contains: Optional[str] = None,
):
    """Test command for filter options."""
    return {
        "base_arg": base_arg,
        "sut": sut,
        "days": days,
        "outcome": outcome,
        "warnings": warnings,
        "reruns": reruns,
        "contains": contains,
    }

def test_common_filter_options_basic(cli_runner):
    """Test basic filter option passing."""
    result = cli_runner.invoke(
        app,
        ["test-arg", "--sut", "api", "--days", "7"]
    )
    assert result.exit_code == 0
    assert result.called_with_args == {
        "base_arg": "test-arg",
        "sut": "api",
        "days": 7,
        "outcome": None,
        "warnings": None,
        "reruns": None,
        "contains": None,
    }

def test_common_filter_options_all_options(cli_runner):
    """Test all options available in common_filter_options."""
    from typer.testing import CliRunner
    runner = CliRunner()

    result = cli_runner.invoke(
        app,
        [
            "test-arg",
            "--sut", "api",
            "--days", "7",
            "--hours", "12",
            "--minutes", "30",
            "--outcome", "FAILED",
            "--warnings",
            "--reruns",
            "--contains", "test_api"
        ]
    )
    assert result.exit_code == 0
    assert result.called_with_args == {
        "base_arg": "test-arg",
        "sut": "api",
        "days": 7,
        "outcome": "FAILED",
        "warnings": True,
        "reruns": True,
        "contains": "test_api",
    }

def test_common_filter_options_no_options(cli_runner):
    """Test command without any filters."""
    from typer.testing import CliRunner
    runner = CliRunner()

    result = cli_runner.invoke(app, ["test-arg"])
    assert result.exit_code == 0
    assert result.called_with_args == {
        "base_arg": "test-arg",
        "sut": None,
        "days": None,
        "minutes": None,
        "seconds": None,
        "outcome": None,
        "warnings": None,
        "reruns": None,
        "contains": None,
    }

@pytest.mark.parametrize(
    "days",
    [
        0,
        -1,
        "a",
        "1.5",
    ]
)

def test_common_filter_options_invalid_values(cli_runner, days):
    """Test invalid filter values."""
    from typer.testing import CliRunner
    runner = CliRunner()

    result = cli_runner.invoke(
        app,
        ["test-arg", "--days", days]
    )
    assert result.exit_code == 2  # Typer error code for invalid value

def test_common_filter_options_help(cli_runner):
    """Test help message for filter options."""
    from typer.testing import CliRunner
    runner = CliRunner()

    result = cli_runner.invoke(app, ["test-arg", "--help"])
    assert result.exit_code == 0
    assert "--sut" in result.stdout
    assert "--days" in result.stdout
    assert "--hours" in result.stdout
    assert "--minutes" in result.stdout
    assert "--outcome" in result.stdout
    assert "--warnings" in result.stdout
    assert "--reruns" in result.stdout
    assert "--contains" in result.stdout

def _rnd_utf_8_chars() -> str:
    """Return a random string of UTF-8 characters."""
    import random
    import string
    return "".join(
        random.choices(string.printable, k=random.randint(1, 100))
    )

# inject w/ random utf-8s
@pytest.mark.parametrize(
    "sut",
    [
        _rnd_utf_8_chars(),
        _rnd_utf_8_chars(),
        _rnd_utf_8_chars(),
    ]
)
def test_common_filter_options_sut(cli_runner, sut):
    """Test System Under Test filter option."""
    from typer.testing import CliRunner
    runner = CliRunner()

    result = cli_runner.invoke(
        app,
        ["test-arg", "--sut", sut]
    )
    assert result.exit_code == 0
    assert sut in result.stdout
    assert all(
        word not in result.stdout
        for word in [
            "days",
            "hours",
            "minutes",
            "outcome",
            "warnings",
            "reruns",
            "contains",
        ]
    )



# class Result:
#     """Holds the captured result of an invoked CLI script."""

#     def __init__(
#         self,
#         runner: "CliRunner",
#         stdout_bytes: bytes,
#         stderr_bytes: t.Optional[bytes],
#         return_value: t.Any,
#         exit_code: int,
#         exception: t.Optional[BaseException],
#         exc_info: t.Optional[
#             t.Tuple[t.Type[BaseException], BaseException, TracebackType]
#         ] = None,
#     ):
#         #: The runner that created the result
#         self.runner = runner
#         #: The standard output as bytes.
#         self.stdout_bytes = stdout_bytes
#         #: The standard error as bytes, or None if not available
#         self.stderr_bytes = stderr_bytes
#         #: The value returned from the invoked command.
#         #:
#         #: .. versionadded:: 8.0
#         self.return_value = return_value
#         #: The exit code as integer.
#         self.exit_code = exit_code
#         #: The exception that happened if one did.
#         self.exception = exception
#         #: The traceback
#         self.exc_info = exc_info

#     @property
#     def output(self) -> str:
#         """The (standard) output as unicode string."""

#     @property
#     def stdout(self) -> str:
#         """The standard output as unicode string."""

#     @property
#     def stderr(self) -> str:
#         """The standard error as unicode string."""
