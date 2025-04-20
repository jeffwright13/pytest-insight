from typing import Optional

from pytest_insight.core.models import TestSession
from pytest_insight.insight_api import InsightAPI


def console_insights(sessions: list[TestSession] = None, profile: str = None):
    pass


def populate_terminal_section(sessions: list[TestSession], extra: Optional[dict] = None) -> str:
    """Format the pytest-insight terminal section for display.

    Args:
        sessions (list[TestSession]): The test session objects to summarize.
        extra (Optional[dict]): Any extra analytics or context to include.

    Returns:
        str: Formatted string for terminal output.
    """
    from pytest_insight.insight_api import InsightAPI
    import sys

    # ANSI color codes
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GREY = '\033[90m'

    # Compose header for context
    sut_name = sessions[0].sut_name if sessions and hasattr(sessions[0], "sut_name") else "unknown-sut"
    system_name = (
        sessions[0].testing_system["name"]
        if sessions and hasattr(sessions[0], "testing_system") and "name" in sessions[0].testing_system
        else "unknown-system"
    )
    header = f"[Session Insight: SUT={sut_name} System={system_name}]\n"

    # Prepare API
    api = InsightAPI(sessions=sessions)

    # Gather all available insights
    summary = api.summary().insight()
    session_insight = api.session().insight() if hasattr(api.session(), 'insight') else ''
    test_reliability = api.test().insight('reliability')
    temporal_trend = api.temporal().insight('trend')
    comparative_regression = api.comparative().insight('regression')
    trend = api.trend().insight('trend')
    predictive = api.predictive().insight('predictive_failure')
    meta = api.meta().insight('maintenance_burden')

    # Compose output
    output = header
    output += f"{HEADER}{BOLD}Pytest-Insight: Session Metrics{ENDC}\n"
    output += f"  {OKCYAN}Summary:{ENDC}      {OKGREEN}{summary}{ENDC}\n"
    if session_insight:
        output += f"  {OKCYAN}Session:{ENDC}      {session_insight}\n"
    output += f"  {OKCYAN}Reliability:{ENDC}   {test_reliability}\n"
    output += f"  {OKCYAN}Temporal Trend:{ENDC} {temporal_trend}\n"
    output += f"  {OKCYAN}Regression:{ENDC}    {comparative_regression}\n"
    output += f"  {OKCYAN}Trend:{ENDC}         {trend}\n"
    output += f"  {OKCYAN}Predictive:{ENDC}    {predictive}\n"
    output += f"  {OKCYAN}Meta:{ENDC}          {meta}\n"
    if extra:
        output += f"  {GREY}Extra:{ENDC}         {extra}\n"
    return output
