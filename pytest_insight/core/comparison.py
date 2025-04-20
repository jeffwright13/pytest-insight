"""Comparison logic for SUTs, versions, etc.

This module provides functions for comparing reliability and metrics between different systems under test (SUTs), versions, or configurations.
"""

from .models import TestSession


def compare_suts(sessions: list[TestSession], sut_a: str, sut_b: str):
    """
    Compare reliability between two SUTs.

    Args:
        sessions (list[TestSession]): List of test sessions to analyze.
        sut_a (str): Name of the first SUT.
        sut_b (str): Name of the second SUT.

    Returns:
        dict: Dictionary mapping SUT names to reliability scores.
    """
    # Placeholder: implement real logic
    return {sut_a: 0.95, sut_b: 0.90}
