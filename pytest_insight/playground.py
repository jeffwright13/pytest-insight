import json
import os
from datetime import datetime, timedelta

import pytest

from pytest_insight.models import TestOutcome, TestResult, RerunTestGroup, TestSession, TestHistory
from pytest_insight.query.comparison import Comparison, ComparisonError, ComparisonResult
from pytest_insight.query.query import Query, QueryError, QueryResult, QueryTestFilter, InvalidQueryParameterError
from pytest_insight.storage import JSONStorage, StorageType, get_storage_instance

# Load storage file and get TestSession instances
# -----------------------------------------------
filepath = "/Users/jwr003/.pytest_insight/gems-qa-auto.json"
storage = get_storage_instance(file_path=filepath)
sessions = storage.load_sessions()
print(f"Loaded {len(sessions)} test sessions from {filepath}")

# Query test sessions with a filter
# ---------------------------------
q = Query()

# Build filters progressively
sut_q = q.for_sut("qa-ref-openjdk17-qa")
sut_q_results = sut_q.execute(sessions)

# Use sut_q as the base, not q
sut_q_warnings_yes = sut_q.having_warnings()
sut_q_warnings_no = sut_q.having_warnings(False)

# Execute the derived queries
sut_q_warnings_yes_results = sut_q_warnings_yes.execute(sessions)
warnings = [r for s in sut_q_warnings_yes_results.sessions for r in s.test_results if r.has_warning]
print(f"Found {len(warnings)} test results with warnings")
sut_q_warnings_no_results = sut_q_warnings_no.execute(sessions)
no_warnings = [r for s in sut_q_warnings_no_results.sessions for r in s.test_results if not r.has_warning]
print(f"Found {len(no_warnings)} test results without warnings")




pass
