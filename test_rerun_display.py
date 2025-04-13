#!/usr/bin/env python
"""Test script to verify RerunTestGroup display in console output."""

import datetime
from typing import Any, Dict, List, Optional

from pytest_insight.core.models import TestResult, TestOutcome, RerunTestGroup, TestSession
from pytest_insight.core.analysis import Analysis
from pytest_insight.core.insights import Insights

def create_test_session_with_reruns():
    """Create a test session with rerun test groups for testing."""
    # Create a test session
    session = TestSession(
        sut_name="test-sut",
        session_id="test-session-id",
        session_start_time=datetime.datetime.now(),
        session_stop_time=datetime.datetime.now() + datetime.timedelta(seconds=60),
    )
    
    # Create some test results
    test1 = TestResult(
        nodeid="test_module.py::test_flaky_1",
        outcome=TestOutcome.RERUN,
        start_time=datetime.datetime.now(),
        duration=1.5,
    )
    
    test2 = TestResult(
        nodeid="test_module.py::test_flaky_1",
        outcome=TestOutcome.PASSED,
        start_time=datetime.datetime.now() + datetime.timedelta(seconds=2),
        duration=1.2,
    )
    
    test3 = TestResult(
        nodeid="test_module.py::test_flaky_2",
        outcome=TestOutcome.RERUN,
        start_time=datetime.datetime.now(),
        duration=2.1,
    )
    
    test4 = TestResult(
        nodeid="test_module.py::test_flaky_2",
        outcome=TestOutcome.RERUN,
        start_time=datetime.datetime.now() + datetime.timedelta(seconds=3),
        duration=2.0,
    )
    
    test5 = TestResult(
        nodeid="test_module.py::test_flaky_2",
        outcome=TestOutcome.FAILED,
        start_time=datetime.datetime.now() + datetime.timedelta(seconds=6),
        duration=1.8,
    )
    
    # Add test results to session
    session.test_results = [test1, test2, test3, test4, test5]
    
    # Create rerun groups
    group1 = RerunTestGroup(nodeid="test_module.py::test_flaky_1")
    group1.add_test(test1)
    group1.add_test(test2)
    
    group2 = RerunTestGroup(nodeid="test_module.py::test_flaky_2")
    group2.add_test(test3)
    group2.add_test(test4)
    group2.add_test(test5)
    
    # Add rerun groups to session
    session.rerun_test_groups = [group1, group2]
    
    return session

def format_rerun_test_groups(rerun_groups):
    """Format rerun test groups for console output."""
    formatted_groups = []
    for group in rerun_groups:
        formatted_tests = []
        for test in group.tests:
            formatted_tests.append({
                "outcome": test.outcome,
                "duration": test.duration,
                "start_time": test.start_time
            })
        
        formatted_groups.append({
            "nodeid": group.nodeid,
            "final_outcome": group.final_outcome,
            "attempts": len(group.tests),
            "tests": formatted_tests
        })
    
    return formatted_groups

class CustomInsights(Insights):
    """Custom Insights class that overrides console_summary to include rerun test groups."""
    
    def __init__(self, analysis, rerun_test_groups, flaky_test_count=1):
        """Initialize with an Analysis instance and custom rerun test groups."""
        super().__init__(analysis=analysis)
        self.custom_rerun_test_groups = format_rerun_test_groups(rerun_test_groups)
        self.flaky_test_count = flaky_test_count
    
    def console_summary(self) -> Dict[str, Any]:
        """Override console_summary to include rerun test groups."""
        # Get the original summary
        summary = super().console_summary()
        
        # Add our custom rerun test groups
        summary["rerun_test_groups"] = self.custom_rerun_test_groups
        summary["rerun_count"] = len(self.custom_rerun_test_groups)
        summary["flaky_test_count"] = self.flaky_test_count
        summary["most_flaky"] = [("test_module.py::test_flaky_1", {"flake_rate": 0.5})]
        
        return summary

def main():
    """Run the test."""
    print("Creating test session with rerun groups...")
    session = create_test_session_with_reruns()
    
    print(f"Created session with {len(session.test_results)} test results and {len(session.rerun_test_groups)} rerun groups")
    
    # Create an Analysis instance with the test session
    analysis = Analysis(sessions=[session])
    
    # Create our custom Insights instance with the rerun test groups
    insights = CustomInsights(
        analysis=analysis,
        rerun_test_groups=session.rerun_test_groups
    )
    
    # Get formatted console output
    output = insights.format_console_output(
        session_id=session.session_id,
        sut_name=session.sut_name,
    )
    
    # Print the output
    print("\n=== CONSOLE OUTPUT ===\n")
    print(output)
    print("\n=== END CONSOLE OUTPUT ===\n")

if __name__ == "__main__":
    main()
