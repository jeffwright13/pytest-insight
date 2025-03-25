"""Query tour steps demonstrating the two-level filtering design.

This module implements the Query tour steps, showcasing:
1. Session-Level Filtering: Filter entire test sessions
2. Test-Level Filtering: Filter by test properties while preserving context
3. Context Benefits: Demonstrate why context preservation matters
"""

from typing import List

from bullet import Bullet, Check, YesNo, colors
from pytest_insight import InsightAPI, TestSession

from ..utils.tour_helpers import Style, TourHelper


class QueryTourSteps:
    def __init__(self, api: InsightAPI, helper: TourHelper):
        self.api = api
        self.helper = helper

    def step_1_session_filtering(self) -> List[TestSession]:
        """Demo session-level filtering with SUT and time range."""
        self.helper.print_header("Step 1: Session-Level Filtering")
        self.helper.format_output("First, let's find all test sessions for a specific service...", Style.INFO)

        # Let user choose SUT with styled bullet
        sut_prompt = Bullet(
            "Choose a service to query:",
            choices=["api-", "integration-", "ui-"],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"],
        )
        sut = sut_prompt.launch()

        # Let user choose time range
        days_prompt = Bullet(
            "Choose time range to search:",
            choices=["Last 7 days", "Last 30 days", "Last 90 days"],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"],
        )
        days = int(days_prompt.launch().split()[1])

        # Show example code from MEMORY[96f9d536]
        self.helper.print_code(
            """
api.query()
   .for_sut("service").in_last_days(7).execute()
"""
        )

        # Execute query
        try:
            sessions = self.api.query().for_sut(sut).in_last_days(days).execute()
            self.helper.print_success(f"Found {len(sessions)} sessions for {sut} in last {days} days")
            return sessions
        except Exception as e:
            self.helper.print_error(f"Query failed: {str(e)}")
            return []

    def step_2_test_filtering(self) -> List[TestSession]:
        """Demo test-level filtering while preserving context."""
        self.helper.print_header("Step 2: Test-Level Filtering")
        self.helper.format_output("Now let's filter by test properties while keeping session context...", Style.INFO)

        # Let user choose duration threshold
        duration_prompt = Bullet(
            "Find tests that took longer than:",
            choices=["5 seconds", "10 seconds", "30 seconds"],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"],
        )
        duration = float(duration_prompt.launch().split()[0])

        # Let user choose outcomes with multiple selection
        outcome_prompt = Check(
            "Select test outcomes to filter by:",
            ["failed", "passed", "skipped"],
            check="✓",
            check_color=colors.bright(colors.foreground["green"]),
            check_on_switch=colors.bright(colors.foreground["yellow"]),
            word_color=colors.bright(colors.foreground["white"]),
            background_on_switch=colors.background["black"],
        )
        outcomes = outcome_prompt.launch()

        # Show example code from MEMORY[96f9d536]
        self.helper.print_code(
            """
api.query()
   .filter_by_test()  # Filters sessions by test criteria
   .with_duration_between(10.0, float("inf"))
   .apply()  # Back to session context
   .execute()
"""
        )

        # Execute query with test filtering
        try:
            sessions = []
            for outcome in outcomes:
                result = (
                    self.api.query()
                    .filter_by_test()  # Start test-level filtering
                    .with_duration_between(duration, None)
                    .with_outcome(outcome)
                    .apply()  # Back to session context
                    .execute()
                )
                sessions.extend(result)

            self.helper.print_success(f"Found {len(sessions)} sessions with tests over {duration}s")
            return sessions
        except Exception as e:
            self.helper.print_error(f"Query failed: {str(e)}")
            return []

    def step_3_context_benefits(self, sessions: List[TestSession]) -> None:
        """Show benefits of context preservation."""
        self.helper.print_header("Step 3: Context Benefits")
        self.helper.format_output("Let's see why preserving session context is valuable...", Style.INFO)

        if not sessions:
            self.helper.print_warning("No sessions available to demonstrate context benefits.")
            return

        session = sessions[0]
        show_warnings = YesNo(
            "Would you like to see test warnings?",
            word_color=colors.bright(colors.foreground["white"]),
            background_on_switch=colors.background["black"],
        ).launch()

        # Show related tests
        self.helper.format_output("\nTests that ran together in this session:", Style.INFO)
        for test in session.test_results[:3]:
            print(f"- {test.nodeid}")
            print(f"  Outcome: {test.outcome.value}")
            print(f"  Duration: {test.duration:.2f}s")
            if show_warnings and test.has_warning:
                self.helper.print_warning("  Has warnings!")

        # Show rerun patterns if any
        if session.rerun_test_groups:
            show_reruns = YesNo(
                "Would you like to see rerun patterns?",
                word_color=colors.bright(colors.foreground["white"]),
                background_on_switch=colors.background["black"],
            ).launch()

            if show_reruns:
                self.helper.format_output("\nRerun patterns found:", Style.INFO)
                for group in session.rerun_test_groups[:2]:
                    print(f"Test: {group.nodeid}")
                    self.helper.format_output(f"Attempts: {len(group.test_results)}", Style.INFO)
                    for attempt in group.test_results:
                        print(f"- {attempt.outcome.value}")

        # Update tour state
        self.helper.update_state("query", {"last_session": session})
