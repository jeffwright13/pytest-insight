from typing import Optional

from pytest_insight.core.models import TestSession
from pytest_insight.insight_api import InsightAPI


def console_insights(sessions: list[TestSession] = None, profile: str = None):
    pass


def populate_terminal_section(
    sessions: list[TestSession], extra: Optional[dict] = None
) -> str:
    """Format the pytest-insight terminal section for display.

    Args:
        sessions (list[TestSession]): The test session objects to summarize.
        extra (Optional[dict]): Any extra analytics or context to include.

    Returns:
        str: Formatted string for terminal output.
    """
    import sys

    from pytest_insight.insight_api import InsightAPI

    # ANSI color codes
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    GREY = "\033[90m"

    # Compose header for context
    sut_name = (
        sessions[0].sut_name
        if sessions and hasattr(sessions[0], "sut_name")
        else "unknown-sut"
    )
    system_name = (
        sessions[0].testing_system["name"]
        if sessions
        and hasattr(sessions[0], "testing_system")
        and "name" in sessions[0].testing_system
        else "unknown-system"
    )
    header = f"[Session Insight: SUT={sut_name} System={system_name}]\n"

    # Prepare API
    api = InsightAPI(sessions=sessions)

    # Gather all available insights as structured data
    summary = api.summary_dict()
    session_metrics = api.session_dict()
    test_metrics = api.test_dict()
    temporal_metrics = api.temporal_dict()
    comparative_metrics = api.comparative_dict()
    trend_metrics = api.trend_dict()
    predictive_metrics = api.predictive_dict()
    meta_metrics = api.meta_dict()

    # Compose output
    output = header
    output += f"{HEADER}{BOLD}Pytest-Insight: Session Metrics{ENDC}\n"
    output += f"  {OKCYAN}Summary:{ENDC}      {OKGREEN}{summary}{ENDC}\n"
    if session_metrics:
        output += f"  {OKCYAN}Session:{ENDC}      {session_metrics}\n"
    if test_metrics:
        output += f"  {OKCYAN}Reliability:{ENDC}   {test_metrics.get('test_reliability_metrics', test_metrics)}\n"
    if temporal_metrics:
        output += f"  {OKCYAN}Temporal Trend:{ENDC} {temporal_metrics}\n"
    if comparative_metrics:
        output += f"  {OKCYAN}Regression:{ENDC}    {comparative_metrics}\n"
    if trend_metrics:
        output += f"  {OKCYAN}Trend:{ENDC}         {trend_metrics}\n"
    if predictive_metrics:
        output += f"  {OKCYAN}Predictive:{ENDC}    {predictive_metrics}\n"
    if meta_metrics:
        output += f"  {OKCYAN}Meta:{ENDC}          {meta_metrics}\n"
    if extra:
        output += f"  {GREY}Extra:{ENDC}         {extra}\n"
    return output
