"""HTML report generator for pytest-insight."""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Union

import jinja2
from jinja2 import Environment, FileSystemLoader

from pytest_insight.core.models import TestOutcome, TestSession
from pytest_insight.core.storage import get_storage_instance


class HTMLReportGenerator:
    """Generate HTML reports from test sessions."""

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize the HTML report generator.

        Args:
            template_dir: Optional custom directory for templates.
                         If not provided, uses the default templates.
        """
        # Use default templates if not specified
        if template_dir is None:
            template_dir = os.path.join(os.path.dirname(__file__), "templates")

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self.env.filters["format_datetime"] = self._format_datetime
        self.env.filters["format_duration"] = self._format_duration
        self.env.filters["outcome_class"] = self._outcome_class
        self.env.filters["outcome_icon"] = self._outcome_icon

    def generate_report(
        self,
        output_path: str,
        profile_name: Optional[str] = None,
        session_ids: Optional[List[str]] = None,
        days: Optional[int] = None,
        title: Optional[str] = None,
    ) -> str:
        """Generate an HTML report for test sessions.

        Args:
            output_path: Path where the HTML report will be saved
            profile_name: Optional profile name to use (defaults to active profile)
            session_ids: Optional list of session IDs to include
            days: Optional number of days to include (most recent N days)
            title: Optional custom title for the report

        Returns:
            Path to the generated HTML report
        """
        # Get storage instance
        storage = get_storage_instance(profile_name=profile_name)

        # Load sessions
        if days is not None:
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=days)
            sessions = [s for s in storage.load_sessions() if s.session_start_time >= cutoff_date]
        else:
            sessions = storage.load_sessions()

        # Filter by session IDs if provided
        if session_ids:
            sessions = [s for s in sessions if s.session_id in session_ids]

        # Sort sessions by start time (newest first)
        sessions.sort(key=lambda s: s.session_start_time, reverse=True)

        # Prepare report data
        report_data = self._prepare_report_data(sessions, title)

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)

        # Create assets directory
        assets_dir = os.path.join(output_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        # Copy static assets
        self._copy_static_assets(assets_dir)

        # Render the report template
        template = self.env.get_template("report.html")
        html_content = template.render(**report_data)

        # Write the HTML report
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Generate JSON data file for interactive features
        json_path = os.path.join(output_dir, "report_data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data["test_data"], f)

        return output_path

    def _prepare_report_data(self, sessions: List[TestSession], title: Optional[str] = None) -> Dict:
        """Prepare data for the HTML report template.

        Args:
            sessions: List of TestSession objects
            title: Optional custom title for the report

        Returns:
            Dictionary of data for the template
        """
        # Collect all test results
        all_tests = []
        for session in sessions:
            for test in session.test_results:
                test_info = {
                    "session_id": session.session_id,
                    "sut_name": session.sut_name,
                    "session_start": session.session_start_time.isoformat(),
                    "nodeid": test.nodeid,
                    "outcome": test.outcome.name,
                    "duration": test.duration,
                    "start_time": test.start_time.isoformat(),
                    "has_error": bool(test.longreprtext),
                    "has_output": bool(test.capstdout or test.capstderr),
                    "has_logs": bool(test.caplog),
                }
                all_tests.append(test_info)

        # Calculate summary statistics
        total_tests = len(all_tests)
        passed_tests = sum(1 for t in all_tests if t["outcome"] == "PASSED")
        failed_tests = sum(1 for t in all_tests if t["outcome"] == "FAILED")
        skipped_tests = sum(1 for t in all_tests if t["outcome"] == "SKIPPED")
        error_tests = sum(1 for t in all_tests if t["outcome"] == "ERROR")

        # Calculate pass rate
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Generate default title if not provided
        if title is None:
            title = f"Test Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Prepare session data
        session_data = []
        for session in sessions:
            session_info = {
                "id": session.session_id,
                "sut_name": session.sut_name,
                "start_time": session.session_start_time.isoformat(),
                "duration": session.session_duration,
                "test_count": len(session.test_results),
                "passed": sum(1 for t in session.test_results if t.outcome == TestOutcome.PASSED),
                "failed": sum(1 for t in session.test_results if t.outcome == TestOutcome.FAILED),
                "skipped": sum(1 for t in session.test_results if t.outcome == TestOutcome.SKIPPED),
                "error": sum(1 for t in session.test_results if t.outcome == TestOutcome.ERROR),
            }
            session_data.append(session_info)

        # Prepare test data for detailed view
        test_data = []
        for session in sessions:
            for test in session.test_results:
                test_info = {
                    "session_id": session.session_id,
                    "sut_name": session.sut_name,
                    "nodeid": test.nodeid,
                    "outcome": test.outcome.name,
                    "duration": test.duration,
                    "start_time": test.start_time.isoformat(),
                    "error": test.longreprtext,
                    "stdout": test.capstdout,
                    "stderr": test.capstderr,
                    "logs": test.caplog,
                }
                test_data.append(test_info)

        return {
            "title": title,
            "generated_at": datetime.now().isoformat(),
            "sessions": sessions,
            "session_data": session_data,
            "test_data": test_data,
            "summary": {
                "total_sessions": len(sessions),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "skipped_tests": skipped_tests,
                "error_tests": error_tests,
                "pass_rate": pass_rate,
            },
        }

    def _copy_static_assets(self, assets_dir: str) -> None:
        """Copy static assets to the output directory.

        Args:
            assets_dir: Directory where assets will be copied
        """
        # Get the path to static assets
        static_dir = os.path.join(os.path.dirname(__file__), "static")

        # Copy all files from static directory to assets directory
        if os.path.exists(static_dir):
            for filename in os.listdir(static_dir):
                src = os.path.join(static_dir, filename)
                dst = os.path.join(assets_dir, filename)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)

    def _format_datetime(self, dt: Union[str, datetime]) -> str:
        """Format a datetime object or ISO string as a human-readable string.

        Args:
            dt: Datetime object or ISO format string

        Returns:
            Formatted datetime string
        """
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _format_duration(self, duration: float) -> str:
        """Format a duration in seconds as a human-readable string.

        Args:
            duration: Duration in seconds

        Returns:
            Formatted duration string
        """
        if duration < 0.001:
            return f"{duration * 1000000:.0f} μs"
        elif duration < 1:
            return f"{duration * 1000:.1f} ms"
        else:
            return f"{duration:.2f} s"

    def _outcome_class(self, outcome: str) -> str:
        """Get the CSS class for a test outcome.

        Args:
            outcome: Test outcome name

        Returns:
            CSS class name
        """
        outcome = outcome.upper()
        if outcome == "PASSED":
            return "success"
        elif outcome in ("FAILED", "ERROR"):
            return "danger"
        elif outcome == "SKIPPED":
            return "warning"
        elif outcome == "XFAILED":
            return "secondary"
        elif outcome == "XPASSED":
            return "info"
        else:
            return "light"

    def _outcome_icon(self, outcome: str) -> str:
        """Get the icon for a test outcome.

        Args:
            outcome: Test outcome name

        Returns:
            Icon HTML
        """
        outcome = outcome.upper()
        if outcome == "PASSED":
            return '<i class="bi bi-check-circle-fill text-success"></i>'
        elif outcome == "FAILED":
            return '<i class="bi bi-x-circle-fill text-danger"></i>'
        elif outcome == "ERROR":
            return '<i class="bi bi-exclamation-triangle-fill text-danger"></i>'
        elif outcome == "SKIPPED":
            return '<i class="bi bi-skip-forward-fill text-warning"></i>'
        elif outcome == "XFAILED":
            return '<i class="bi bi-dash-circle-fill text-secondary"></i>'
        elif outcome == "XPASSED":
            return '<i class="bi bi-check-circle text-info"></i>'
        else:
            return '<i class="bi bi-question-circle-fill"></i>'


def generate_html_report(
    output_path: str,
    profile_name: Optional[str] = None,
    session_ids: Optional[List[str]] = None,
    days: Optional[int] = None,
    title: Optional[str] = None,
) -> str:
    """Generate an HTML report for test sessions.

    Args:
        output_path: Path where the HTML report will be saved
        profile_name: Optional profile name to use (defaults to active profile)
        session_ids: Optional list of session IDs to include
        days: Optional number of days to include (most recent N days)
        title: Optional custom title for the report

    Returns:
        Path to the generated HTML report
    """
    generator = HTMLReportGenerator()
    return generator.generate_report(
        output_path=output_path,
        profile_name=profile_name,
        session_ids=session_ids,
        days=days,
        title=title,
    )
