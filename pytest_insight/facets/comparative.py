from pytest_insight.core.models import TestSession
from collections import defaultdict

class ComparativeInsight:
    """Compare across SUTs, code versions, environments, etc."""
    def __init__(self, sessions: list[TestSession]):
        self.sessions = sessions

    def compare_suts(self, sut_a, sut_b):
        """Compare reliability between two SUTs."""
        # Assume TestSession has .sut_name attribute
        results = {sut_a: {"sessions": 0, "passes": 0, "tests": 0}, sut_b: {"sessions": 0, "passes": 0, "tests": 0}}
        for s in self.sessions:
            if getattr(s, "sut_name", None) == sut_a:
                results[sut_a]["sessions"] += 1
                results[sut_a]["tests"] += len(s.test_results)
                results[sut_a]["passes"] += sum(t.outcome == "passed" for t in s.test_results)
            elif getattr(s, "sut_name", None) == sut_b:
                results[sut_b]["sessions"] += 1
                results[sut_b]["tests"] += len(s.test_results)
                results[sut_b]["passes"] += sum(t.outcome == "passed" for t in s.test_results)
        for k in [sut_a, sut_b]:
            if results[k]["tests"]:
                results[k]["reliability"] = results[k]["passes"] / results[k]["tests"]
            else:
                results[k]["reliability"] = None
        return results
