"""Compare tour steps demonstrating version and time-based comparisons.

This module implements the Compare tour steps, showcasing:
1. Version Comparison: Compare between different service versions
2. Time Analysis: Compare results across time periods
3. Change Detection: Identify and analyze changes
"""

from typing import Dict, Optional
from pathlib import Path
from bullet import Bullet, Check, YesNo, colors
from pytest_insight import InsightAPI, TestSession

from ..utils.tour_helpers import TourHelper, Style


class CompareTourSteps:
    def __init__(self, api: InsightAPI, helper: TourHelper):
        self.api = api
        self.helper = helper

    def step_1_version_compare(self) -> Optional[Dict]:
        """Demo version comparison between services."""
        self.helper.print_header("Step 1: Version Comparison")
        self.helper.format_output("Let's compare test results between different services...", Style.INFO)

        # Let user choose base service with styled bullet
        base_prompt = Bullet(
            "Choose base service:",
            choices=["api-", "integration-", "ui-"],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"]
        )
        base_sut = base_prompt.launch()

        # Let user choose target service
        target_prompt = Bullet(
            "Choose target service:",
            choices=["api-", "integration-", "ui-"],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"]
        )
        target_sut = target_prompt.launch()

        # Show example code
        self.helper.print_code("""
api.compare()
   .between_suts("api-", "integration-")
   .execute()
""")

        # Execute comparison
        try:
            diff = (
                self.api.compare()
                .between_suts(base_sut, target_sut)
                .execute()
            )
            self.helper.print_success("Comparison completed successfully")
            return diff
        except Exception as e:
            self.helper.print_error(f"Comparison failed: {str(e)}")
            return None

    def step_2_time_analysis(self) -> Optional[Dict]:
        """Demo time-based analysis."""
        self.helper.print_header("Step 2: Time Analysis")
        self.helper.format_output("Now let's analyze how results change over time...", Style.INFO)

        # Let user choose time range with styled bullet
        time_prompt = Bullet(
            "Choose time range to analyze:",
            choices=["Last 7 days", "Last 30 days", "Last 90 days"],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"]
        )
        days = int(time_prompt.launch().split()[1])

        # Show example code
        self.helper.print_code("""
api.compare()
   .between_times(days=30)
   .execute()
""")

        # Execute time analysis
        try:
            diff = (
                self.api.compare()
                .between_times(days=days)
                .execute()
            )
            self.helper.print_success("Time analysis completed successfully")
            return diff
        except Exception as e:
            self.helper.print_error(f"Time analysis failed: {str(e)}")
            return None

    def step_3_change_detection(self, diff: Optional[Dict]) -> None:
        """Demo change detection analysis."""
        self.helper.print_header("Step 3: Change Detection")
        self.helper.format_output("Let's analyze what changed...", Style.INFO)

        if not diff:
            self.helper.print_warning("No comparison data available.")
            return

        # Let user select what changes to view
        changes = []
        if diff.get("new_failures"):
            changes.append("❌ New Failures")
        if diff.get("fixed_tests"):
            changes.append("✅ Fixed Tests")
        if diff.get("persistent_failures"):
            changes.append("⚠️ Persistent Failures")

        if changes:
            # Use Check to allow multiple selections with styling
            change_prompt = Check(
                "What changes would you like to see?",
                changes,
                check="✓",
                check_color=colors.bright(colors.foreground["green"]),
                check_on_switch=colors.bright(colors.foreground["yellow"]),
                word_color=colors.bright(colors.foreground["white"]),
                background_on_switch=colors.background["black"]
            )
            selected_changes = change_prompt.launch()

            for selected in selected_changes:
                if "New Failures" in selected:
                    self.helper.print_error("\nNew Failures:")
                    for failure in diff["new_failures"][:3]:
                        print(f"- {failure.nodeid}")

                if "Fixed Tests" in selected:
                    self.helper.print_success("\nFixed Tests:")
                    for fixed in diff["fixed_tests"][:3]:
                        print(f"- {fixed.nodeid}")

                if "Persistent Failures" in selected:
                    self.helper.print_warning("\nPersistent Failures:")
                    for failure in diff["persistent_failures"][:3]:
                        print(f"- {failure.nodeid}")

                # Ask if user wants to see details for this change type
                show_details = YesNo(
                    f"Would you like to see details for {selected.strip('✓❌✅⚠️ ')}?",
                    word_color=colors.bright(colors.foreground["white"]),
                    background_on_switch=colors.background["black"]
                ).launch()

                if show_details:
                    self.helper.format_output("\nTest Details:", Style.INFO)
                    change_type = selected.strip('✓❌✅⚠️ ').lower().replace(" ", "_")
                    for test in diff.get(change_type, [])[:3]:
                        print(f"\nTest: {test.nodeid}")
                        print(f"Duration: {test.duration:.2f}s")
                        print(f"Outcome: {test.outcome.value}")
                        if test.has_warning:
                            self.helper.print_warning("Has warnings!")

        # Update tour state
        self.helper.update_state("compare", diff)
