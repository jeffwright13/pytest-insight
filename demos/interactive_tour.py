"""Interactive tour of pytest-insight features.

This module provides an interactive tour demonstrating pytest-insight's core operations:
1. Query - Two-level test session filtering
2. Compare - Version and trend analysis
3. Analyze - Test insights and metrics
"""

from pathlib import Path
from typing import Optional

from bullet import Bullet, YesNo, colors
from pytest_insight import InsightAPI, get_storage_instance
from pytest_insight.core.models import TestSession
from pytest_insight.core.query import InvalidQueryParameterError

from tour.steps.analyze_steps import AnalyzeTourSteps
from tour.steps.compare_steps import CompareTourSteps
from tour.steps.query_steps import QueryTourSteps
from tour.utils.tour_helpers import TourHelper, Style


class InsightTour:
    # Core operations with two-level filtering design
    OPERATIONS = [
        "Query",
        "Compare",
        "Analyze",
        "Exit"
    ]

    # Operation descriptions emphasizing session context preservation
    DESCRIPTIONS = {
        "Query": "Level 1: Filter sessions by SUT/time/warnings\nLevel 2: Filter by test properties - preserving session context",
        "Compare": "Compare test sessions across versions and analyze trends - with full session context",
        "Analyze": "Extract insights from complete test sessions - stability, performance, and relationships"
    }

    def __init__(self):
        self.helper = TourHelper()
        self.api = InsightAPI()
        self.query_steps = QueryTourSteps(self.api, self.helper)
        self.compare_steps = CompareTourSteps(self.api, self.helper)
        self.analyze_steps = AnalyzeTourSteps(self.api, self.helper)

    def welcome(self) -> None:
        """Display welcome message and setup options."""
        self.helper.print_header("Welcome to pytest-insight Interactive Tour")
        self.helper.format_output("\nKey Features:", Style.INFO)

        # Show feature descriptions with better formatting
        for op, desc in self.DESCRIPTIONS.items():
            self.helper.format_output(f"\n{op}:", Style.INFO)
            for line in desc.split('\n'):
                self.helper.format_output(f"  {line}", Style.INFO)

        # Ask about practice data with styled YesNo
        setup = YesNo(
            "\nWould you like to generate fresh practice data?",
            word_color=colors.bright(colors.foreground["white"])
        )
        if setup.launch():
            self._setup_practice_data()

    def _setup_practice_data(self) -> None:
        """Generate practice data for the tour."""
        try:
            storage = get_storage_instance()
            storage.generate_practice_data()
            self.helper.print_success("Practice data generated successfully!")
        except Exception as e:
            self.helper.print_error(f"Failed to generate practice data: {str(e)}")

    def start(self) -> None:
        """Start the interactive tour."""
        self.welcome()

        while True:
            # Let user choose operation with styled Bullet
            operation = Bullet(
                "\nWhat would you like to explore?",
                choices=self.OPERATIONS,
                bullet="→",
                bullet_color=colors.bright(colors.foreground["cyan"]),
                word_color=colors.bright(colors.foreground["white"]),
                word_on_switch=colors.bright(colors.foreground["yellow"]),
                background_on_switch=colors.background["black"]
            ).launch()

            if operation == "Exit":
                self.helper.format_output("\nThanks for taking the tour!", Style.INFO)
                break

            try:
                if operation == "Query":
                    # Level 1: Session filtering
                    sessions = self.query_steps.step_1_session_filtering()
                    if sessions:
                        # Level 2: Test filtering with context
                        self.query_steps.step_2_test_filtering()
                        # Show context benefits
                        self.query_steps.step_3_context_benefits(sessions)

                elif operation == "Compare":
                    diff = self.compare_steps.step_1_version_compare()
                    if diff:
                        self.compare_steps.step_2_time_analysis()
                        self.compare_steps.step_3_change_detection(diff)

                elif operation == "Analyze":
                    stability = self.analyze_steps.step_1_stability()
                    if stability:
                        self.analyze_steps.step_2_performance()
                        self.analyze_steps.step_3_health_metrics()

            except InvalidQueryParameterError as e:
                self.helper.print_error(f"Invalid query: {str(e)}")
            except Exception as e:
                self.helper.print_error(f"An error occurred: {str(e)}")

            # Show operation description before asking to continue
            if operation in self.DESCRIPTIONS:
                self.helper.format_output(f"\nNext Steps for {operation}:", Style.INFO)
                for line in self.DESCRIPTIONS[operation].split('\n'):
                    self.helper.format_output(f"  {line}", Style.INFO)

            # Ask if user wants to continue with styled YesNo
            continue_tour = YesNo(
                "\nWould you like to explore another feature?",
                word_color=colors.bright(colors.foreground["white"])
            )
            if not continue_tour.launch():
                self.helper.format_output("\nThanks for taking the tour!", Style.INFO)
                break


if __name__ == "__main__":
    tour = InsightTour()
    tour.start()
