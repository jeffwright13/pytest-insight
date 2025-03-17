"""Analyze tour steps demonstrating insights and metrics.

This module implements the Analyze tour steps, showcasing:
1. Stability Analysis: Identify flaky and stable tests
2. Performance Trends: Track test execution times
3. Health Metrics: Calculate overall test health scores
"""

from typing import Dict, Optional
from pathlib import Path
from bullet import Bullet, Numbers, YesNo, colors
from pytest_insight import InsightAPI, TestSession

from ..utils.tour_helpers import TourHelper, Style


class AnalyzeTourSteps:
    def __init__(self, api: InsightAPI, helper: TourHelper):
        self.api = api
        self.helper = helper

    def step_1_stability(self) -> Optional[Dict]:
        """Demo stability analysis."""
        self.helper.print_header("Step 1: Stability Analysis")
        self.helper.format_output("Let's identify flaky and stable tests...", Style.INFO)

        # Let user choose analysis period with styled bullet
        period_prompt = Bullet(
            "Choose analysis period:",
            choices=["Last 7 days", "Last 30 days", "Last 90 days"],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"]
        )
        days = int(period_prompt.launch().split()[1])

        # Show example code
        self.helper.print_code("""
api.analyze()
   .stability(days=30)
   .execute()
""")

        # Execute stability analysis
        try:
            stability = (
                self.api.analyze()
                .stability(days=days)
                .execute()
            )
            self.helper.print_success(
                f"Found {len(stability['flaky_tests'])} flaky tests, "
                f"{len(stability['stable_tests'])} stable tests"
            )

            # Show flaky tests with details
            if stability['flaky_tests']:
                self.helper.format_output("\nTop Flaky Tests:", Style.INFO)
                test_choices = [f"{test.nodeid} (Flaky Rate: {test.flaky_rate:.2f})"
                              for test in stability['flaky_tests'][:5]]
                if test_choices:
                    flaky_test = Bullet(
                        "Select a test to see details:",
                        choices=test_choices,
                        bullet="→",
                        bullet_color=colors.bright(colors.foreground["cyan"]),
                        word_color=colors.bright(colors.foreground["white"]),
                        word_on_switch=colors.bright(colors.foreground["yellow"]),
                        background_on_switch=colors.background["black"]
                    ).launch()

            return stability
        except Exception as e:
            self.helper.print_error(f"Stability analysis failed: {str(e)}")
            return None

    def step_2_performance(self) -> Optional[Dict]:
        """Demo performance trend analysis."""
        self.helper.print_header("Step 2: Performance Analysis")
        self.helper.format_output("Now let's analyze test execution time trends...", Style.INFO)

        # Let user input performance threshold with Numbers
        threshold_prompt = Numbers(
            "Enter performance threshold (seconds):",
            type=float,
            word_color=colors.bright(colors.foreground["white"]),
            background_on_switch=colors.background["black"]
        )
        threshold = threshold_prompt.launch()

        # Show example code
        self.helper.print_code("""
api.analyze()
   .performance(threshold=10.0)
   .execute()
""")

        # Execute performance analysis
        try:
            performance = (
                self.api.analyze()
                .performance(threshold=threshold)
                .execute()
            )

            if performance['slow_tests']:
                self.helper.format_output(f"\nFound {len(performance['slow_tests'])} slow tests", Style.INFO)
                test_choices = [f"{test.nodeid} ({test.duration:.2f}s)"
                              for test in performance['slow_tests'][:5]]
                if test_choices:
                    slow_test = Bullet(
                        "Select a test to see performance details:",
                        choices=test_choices,
                        bullet="→",
                        bullet_color=colors.bright(colors.foreground["cyan"]),
                        word_color=colors.bright(colors.foreground["white"]),
                        word_on_switch=colors.bright(colors.foreground["yellow"]),
                        background_on_switch=colors.background["black"]
                    ).launch()

            return performance
        except Exception as e:
            self.helper.print_error(f"Performance analysis failed: {str(e)}")
            return None

    def step_3_health_metrics(self) -> Optional[Dict]:
        """Demo health metrics calculation."""
        self.helper.print_header("Step 3: Health Metrics")
        self.helper.format_output("Finally, let's calculate overall test health scores...", Style.INFO)

        # Let user choose metrics to analyze
        metrics_prompt = Bullet(
            "Choose metrics to analyze:",
            choices=[
                "All Metrics",
                "Stability Only",
                "Performance Only"
            ],
            bullet="→",
            bullet_color=colors.bright(colors.foreground["cyan"]),
            word_color=colors.bright(colors.foreground["white"]),
            word_on_switch=colors.bright(colors.foreground["yellow"]),
            background_on_switch=colors.background["black"]
        )
        metric_choice = metrics_prompt.launch()

        # Show example code
        self.helper.print_code("""
api.analyze()
   .health()
   .execute()
""")

        # Execute health analysis
        try:
            health = (
                self.api.analyze()
                .health()
                .execute()
            )

            self.helper.print_success(f"\nOverall Health Score: {health['overall_score']}/100")

            # Show recommendations with Bullet if any
            if health['recommendations']:
                rec_choices = [f"⚠️  {rec}" for rec in health['recommendations'][:5]]
                if rec_choices:
                    recommendation = Bullet(
                        "Health Recommendations:",
                        choices=rec_choices,
                        bullet="→",
                        bullet_color=colors.bright(colors.foreground["cyan"]),
                        word_color=colors.bright(colors.foreground["white"]),
                        word_on_switch=colors.bright(colors.foreground["yellow"]),
                        background_on_switch=colors.background["black"]
                    ).launch()

            # Update tour state
            self.helper.update_state("analyze", {
                "health_score": health['overall_score'],
                "recommendations": len(health['recommendations'])
            })

            return health
        except Exception as e:
            self.helper.print_error(f"Health analysis failed: {str(e)}")
            return None
