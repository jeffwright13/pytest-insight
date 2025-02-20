# Expanding Pytest Plugin for Multi-SUT and Multi-Session Support

## Overview
The current Pytest plugin is designed to handle a single system under test (SUT) and a single test session. This limits its ability to provide historical insights across multiple test runs and different SUTs. To improve its utility, the plugin needs to be expanded to:

- Support multiple test sessions
- Support multiple SUTs
- Facilitate historical and statistical analysis of test data

The current data structures are well-organized for handling a single test session and a single system under test (SUT). To support multiple test sessions and multiple SUTs while maintaining clarity and usability, we need to introduce a hierarchical structure that groups test results based on their session and SUT.

## Current Implementation

### Data Structures
The plugin currently uses the following structures to store test results (see [Data Structure Definitions](#data_structures)
 for actual class definitions):

- TestResult
- TestResults
- RerunTestGroup
- OutputField
- OutputFields
- Results

### Workflow
1. **Test Start**: The plugin captures test execution events.
2. **Test Completion**: The results are stored in `test_results`.
3. **Session End**: The results are formatted and reported.

## Proposed Enhancements

We will introduce two new layers in the data model:
	1.	SUT-Level Grouping: A structure that groups test results by their corresponding SUT.
	2.	Session-Level Grouping: A structure that groups test results within a test session.






### New Data Structures

#### TestSession

A TestSession represents a single execution session for a given SUT. This is similar to Results but scoped to a single session.

```python
@dataclass
class TestSession:
    """
    Represents a single test session for a given SUT.

    'sut_name': The name of the system under test (SUT) for this session.
    'session_id': A unique identifier for the test session.
    'session_start_time': datetime object for the start time of the test session.
    'session_stop_time': datetime object for the end time of the test session.
    'session_duration': timedelta object with duration of the test session.
    'test_results': A collection of TestResult objects for all tests in the session.
    'output_fields': A collection of OutputField objects for all output fields in the session.
    'rerun_test_groups': A collection of RerunTestGroup objects for all rerun tests in the session.
    """

    sut_name: str
    session_id: str
    session_start_time: datetime
    session_stop_time: datetime
    session_duration: timedelta
    test_results: List[TestResult]
    output_fields: OutputFields
    rerun_test_groups: List[RerunTestGroup]

    @classmethod
    def from_file(cls, file_path: Path) -> "TestSession":
        with open(file_path, "rb") as f:
            test_info = pickle.load(f)

        return cls(
            sut_name=test_info["sut_name"],
            session_id=test_info["session_id"],
            session_start_time=test_info["session_start_time"],
            session_stop_time=test_info["session_stop_time"],
            session_duration=test_info["session_duration"],
            test_results=test_info["test_results"],
            output_fields=test_info["output_fields"],
            rerun_test_groups=test_info["rerun_test_groups"],
        )
```

#### SutGroup

A SUTGroup represents all test sessions associated with a particular SUT.

```python
@dataclass
class SUTGroup:
    """
    Represents a collection of test sessions for a single SUT.

    'sut_name': The name of the system under test.
    'sessions': A list of TestSession objects representing each session executed for this SUT.
    """

    sut_name: str
    sessions: List[TestSession] = field(default_factory=list)

    def add_session(self, session: TestSession) -> None:
        """Add a new session to the SUT."""
        self.sessions.append(session)
```

#### TestHistory

A TestHistory stores all SUTs and their corresponding test sessions.

```python
@dataclass
class TestHistory:
    """
    Represents historical test results across multiple SUTs.

    'sut_groups': A dictionary where keys are SUT names and values are SUTGroup objects.
    """

    sut_groups: Dict[str, SUTGroup] = field(default_factory=dict)

    def add_test_session(self, session: TestSession) -> None:
        """Adds a new test session to the appropriate SUT group."""
        if session.sut_name not in self.sut_groups:
            self.sut_groups[session.sut_name] = SUTGroup(sut_name=session.sut_name)
        self.sut_groups[session.sut_name].add_session(session)

    def get_sessions_for_sut(self, sut_name: str) -> List[TestSession]:
        """Returns all test sessions for a given SUT."""
        return self.sut_groups.get(sut_name, SUTGroup(sut_name=sut_name)).sessions
```

## Summary of Changes

| **Feature**            | **Current Structure** | **New Structure** |
|------------------------|----------------------|-------------------|
| **Single SUT** | `Results` holds all test results for a single SUT. | Introduced `SUTGroup` to manage multiple SUTs. |
| **Single Test Session** | `Results` contains all results for one session. | Introduced `TestSession` for each session. |
| **Multiple Sessions per SUT** | Not supported. | `SUTGroup` holds multiple `TestSession` objects. |
| **Multiple SUTs** | Not supported. | `TestHistory` groups multiple `SUTGroup` objects. |

---

The plugin should now:

1. **Identify the SUT under test** for each test session.
2. **Generate a unique session identifier** for each test session.
3. **Store test results** inside a `TestSession` object.
4. **Group sessions** inside their respective `SUTGroup`.
5. **Maintain a `TestHistory` object** to track all SUTs and sessions.

This modular approach will enable **historical analysis, trend identification, and statistical insights** across multiple SUTs and test sessions.
- Aggregate pass/fail rates across sessions.
- Track performance trends over time.


## Next Steps
1. Implement changes to the plugin’s session management.
2. Modify reporting to differentiate sessions and SUTs.
3. Develop historical data storage and retrieval.
4. Introduce visualization for trends.

This expansion will provide better insight into the performance of different SUTs over multiple test runs.


<a id="data_structures"></a>
### Data Structure Definitions

```python
@dataclass
class TestResult:
    """
    'TestResult': a single test result, which is a single test run of a single test

    'nodeid': pytestt node_id (fully-qualified test name)
    'outcome': outcome of the test (PASSED, FAILED, SKIPPED, etc.)
    'start_time': datetime object for the start time of the test
    'duration': duration of the test in microseconds
    'caplog': captured log output
    'capstderr': captured stderr output
    'capstdout': captured stdout output
    'longreprtext': any supplementary text output by the test
    'has_warning': whether the test resulted in a warning
    """

    nodeid: str = ""
    outcome: str = ""
    start_time: datetime = None
    duration: float = 0.0
    caplog: str = ""
    capstderr: str = ""
    capstdout: str = ""
    longreprtext: str = ""
    has_warning: bool = False


@dataclass
class TestResults:
    """
    A collection of TestResult objects, with convenience methods for accessing
    subsets of the collection.
    """

    test_results: List[TestResult] = field(default_factory=list)


@dataclass
class RerunTestGroup:
    """
    'RerunTestGroup': a single test that has been run multiple times using
     the 'pytest-rerunfailures' plugin

    'nodeid': fully-qualified test name (same for all tests in a RerunTestGroup)
    'final_outcome': final outcome of the test
    'final_test' TestResult object for the last test run in the group (outcome != RERUN)
    'forerunners': list of TestResult objects for all test that preceded final outcome
    """

    nodeid: str = ""
    final_outcome: str = ""
    final_test: TestResult = None
    forerunners: List[TestResult] = field(default_factory=list)
    full_test_list: List[TestResult] = field(default_factory=list)


@dataclass
class OutputField:
    """
    An 'output field' (aka a 'section') is a block of text that is displayed in the terminal
    output during a pytest run. It provides additional information about the test run:
    warnings, errors, etc.
    """

    name: str = ""
    content: str = ""


@dataclass
class OutputFields:
    """
    A collection of all available types of OutputField objects. Not all fields will
    be present in every test run. It depends on the plugins that are installed and
    which "-r" flags are specified. This plugin forces the use of "-r RA" to ensure
    any fields that are available are included in the output.

    'test_session_starts': the second output field, which contains the start time of each test
    'errors': the third output field, which contains the error output of each test
    'failures': the fourth output field, which contains the failure output of each test
    'passes': the fifth output field, which contains the pass output of each test
    'warnings_summary': the sixth output field, which contains a summary of warnings
    'rerun_test_summary': the seventh output field, which contains a summary of rerun tests
    'short_test_summary': the eighth output field, which contains a summary of test outcomes
    'lastline': the ninth output field, which contains the last line of terminal output
    """

    test_session_starts: OutputField
    errors: OutputField
    failures: OutputField
    passes: OutputField
    warnings_summary: OutputField
    rerun_test_summary: OutputField
    short_test_summary: OutputField
    lastline: OutputField


@dataclass
class Results:
    """
    'Results': a collection of all data collected during a test run, made nicely
    consumable by pytest-oof.

    'session_start_time': datetime object for the start time of the test session
    'session_stop_time': datetime object for the end time of the test session
    'session_duration': timedelta object with duration of the test session in μs
    'test_results': collection of TestResult objects for all tests in the test session
    'output_fields': collection of OutputField objects for all output fields in the
     test session's console-out
    'rerun_test_groups': collection of RerunTestGroup objects for all tests that were
     rerun during the test session
    """

    session_start_time: datetime
    session_stop_time: datetime
    session_duration: timedelta
    test_results: List[TestResult]
    output_fields: OutputFields
    rerun_test_groups: List[RerunTestGroup]

    @classmethod
    def from_file(
        cls,
        results_file_path: Path = RESULTS_FILE,
    ) -> "Results":
        # Retrieve test run data from 'results.pickle' file
        with open(results_file_path, "rb") as f:
            test_info = pickle.load(f)
        test_results = test_info["oof_test_results"]
        output_fields = test_info["oof_fields"]

        # Construct the instance using the data loaded from file
        return cls(
            session_start_time=test_info["oof_session_start_time"],
            session_stop_time=test_info["oof_session_stop_time"],
            session_duration=test_info["oof_session_duration"],
            test_results=test_results,
            output_fields=output_fields,
            rerun_test_groups=test_info["oof_rerun_test_groups"],
        )
```
# Separating data analysys from user interfaces...
is a good architectural suggestion. We can separate the concerns by creating distinct layers:

Core Library Layer - Analysis and insights engine
CLI Layer - User interface using Typer
Public API Layer - For other UIs to build upon
Here's a proposed restructuring:
```
HI LEVEL:
pytest-insight/
├── pytest_insight/
│   ├── core/          # Core analytics (test first)
│   ├── api/           # Public API (test second)
│   ├── cli/           # CLI code (moves last)
│   └── plugin.py      # Remains unchanged
├── tests/
│   ├── core/          # Core analytics tests
│   ├── api/           # API tests
│   └── integration/   # Cross-component tests


MID LEVEL:
pytest-insight/
├── pytest_insight/
│   ├── core/                    # Core analysis engine
│   │   ├── __init__.py
│   │   ├── analyzer.py          # Main analysis logic
│   │   ├── compare.py           # Comparison logic
│   │   ├── models.py            # Data models
│   │   ├── storage.py           # Storage mechanisms
│   │   └── filters.py           # Filtering logic
│   ├── cli/                     # CLI-specific code
│   │   ├── __init__.py
│   │   ├── app.py              # Typer app and commands
│   │   ├── formatters.py       # CLI output formatting
│   │   └── options.py          # CLI option definitions
│   ├── api/                    # Public API for other UIs
│   │   ├── __init__.py
│   │   └── insight.py          # Main API entry point
│   └── plugin.py               # pytest plugin (unchanged)
```

Here's how to start the separation:

```
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..core.models import TestSession
from ..core.storage import Storage

class InsightAnalyzer:
    """Core analysis engine for pytest-insight."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def get_test_history(
        self,
        sut: Optional[str] = None,
        timespan: Optional[timedelta] = None
    ) -> List[TestSession]:
        """Get filtered test history."""
        sessions = self.storage.load_sessions()

        if timespan:
            cutoff = datetime.now() - timespan
            sessions = [s for s in sessions if s.session_start_time > cutoff]

        if sut:
            sessions = [s for s in sessions if s.sut_name == sut]

        return sessions

    def analyze_failures(self, sessions: List[TestSession]) -> Dict:
        """Analyze failure patterns in sessions."""
        # Move existing failure analysis here
        ...

    def get_sut_summary(self, sut: str, timespan: Optional[timedelta] = None) -> Dict:
        """Get summary statistics for a SUT."""
        # Move existing summary logic here
````

```
from typing import Optional
from datetime import timedelta

from ..core.analyzer import InsightAnalyzer
from ..core.storage import get_storage_instance

class PytestInsight:
    """Public API for pytest-insight."""

    def __init__(self):
        self.storage = get_storage_instance()
        self.analyzer = InsightAnalyzer(self.storage)

    def get_history(self, sut: Optional[str] = None, days: int = 7):
        """Get test execution history."""
        return self.analyzer.get_test_history(
            sut=sut,
            timespan=timedelta(days=days)
        )

    def compare_suts(self, sut1: str, sut2: str, timespan: Optional[timedelta] = None):
        """Compare two SUTs."""
        return self.analyzer.compare_suts(sut1, sut2, timespan)

    def get_failure_analysis(self, sut: str, timespan: Optional[timedelta] = None):
        """Get failure analysis for a SUT."""
        sessions = self.analyzer.get_test_history(sut, timespan)
        return self.analyzer.analyze_failures(sessions)
```

```
import typer
from typing import Optional

from ..api.insight import PytestInsight
from .formatters import format_session_summary, format_comparison_results

app = typer.Typer()
insight = PytestInsight()

@app.command()
def history(
    sut: Optional[str] = None,
    days: int = 7,
    show_all: bool = False
):
    """Show test history."""
    results = insight.get_history(sut, days)
    formatted = format_session_summary(results, limit=None if show_all else 50)
    typer.echo(formatted)
```
Benefits of this restructuring:

Clear separation of concerns
Core logic is UI-agnostic
Easy to add new UIs (web, GUI, etc.)
Testable core functionality
Simplified CLI code
Public API for third-party integration
The lift would be moderate because:

Most logic already exists
Main work is moving code
Core analysis is already well-structured
CLI commands map cleanly to API methodsw

# Distributed Test Results Collection
This is a great question about scaling pytest-insight to handle distributed teams. Here's a proposed approach:

1. Storage Backend Options
We can modify the storage system to support multiple backends:
```
from abc import ABC, abstractmethod
from typing import List, Optional
from pytest_insight.models import TestSession

class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def save_session(self, session: TestSession) -> None:
        """Save a test session."""
        pass

    @abstractmethod
    def load_sessions(self) -> List[TestSession]:
        """Load all test sessions."""
        pass

class RemoteStorageConfig:
    """Configuration for remote storage."""
    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        team_id: Optional[str] = None
    ):
        self.url = url
        self.api_key = api_key
        self.team_id = team_id
```

2. Implement Multiple Storage Options
Local JSON (existing):
```
class JSONStorage(StorageBackend):
    """Local JSON file storage."""
    # ... existing implementation ...
```

Remote REST API:
```
import requests
from typing import List
from pytest_insight.models import TestSession

class RemoteStorage(StorageBackend):
    """Remote API storage backend."""

    def __init__(self, config: RemoteStorageConfig):
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }

    def save_session(self, session: TestSession) -> None:
        response = requests.post(
            f"{self.config.url}/api/v1/sessions",
            headers=self.headers,
            json=session.dict()
        )
        response.raise_for_status()

    def load_sessions(self) -> List[TestSession]:
        response = requests.get(
            f"{self.config.url}/api/v1/sessions",
            headers=self.headers
        )
        response.raise_for_status()
        return [TestSession(**data) for data in response.json()]
```

Database Storage:
```
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class DatabaseStorage(StorageBackend):
    """SQL database storage backend."""

    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(bind=self.engine)
```

3. Configuration
Add storage configuration to pytest options:
```
def pytest_addoption(parser):
    """Add pytest-insight specific options."""
    group = parser.getgroup("insight", "pytest-insight")
    group.addoption(
        "--insight-storage",
        default="local",
        choices=["local", "remote", "database"],
        help="Storage backend to use"
    )
    group.addoption(
        "--insight-remote-url",
        help="Remote storage URL"
    )
    group.addoption(
        "--insight-api-key",
        help="API key for remote storage"
    )
```

4. Example Server Implementation
A simple FastAPI server to collect results:
```
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

app = FastAPI()

@app.post("/api/v1/sessions")
def create_session(session: TestSession, db: Session = Depends(get_db)):
    """Save a test session."""
    db_session = models.Session(**session.dict())
    db.add(db_session)
    db.commit()
    return {"status": "success"}

@app.get("/api/v1/sessions")
def list_sessions(db: Session = Depends(get_db)) -> List[TestSession]:
    """Get all test sessions."""
    return db.query(models.Session).all()
```

Usage Examples
Local Team (Shared Database):
`pytest --insight --insight-storage=database --insight-db-url="postgresql://localhost/insight_db"`
Remote Team (API Server):
`pytest --insight --insight-storage=remote --insight-remote-url="https://insight.company.com" --insight-api-key="YOUR_KEY"`
Mixed Mode (Local + Remote Sync):
```
# Run tests with local storage
pytest --insight

# Sync results to remote server
insight sync --remote-url="https://insight.company.com" --api-key="YOUR_KEY"
```

Next Steps
1. Authentication/Authorization
  Team-based access control
  API key management
  Role-based permissions
2. Data Synchronization
  Conflict resolution
  Incremental updates
  Offline support
3. Server Deployment
  Docker containers
  Database migrations
  Backup/restore



# Command Structure Hierarchy

insight
├── session                        # Session management
│   ├── run                      # Run new test session
│   │   ├── --sut              # SUT name
│   │   └── <pytest_args>      # Additional pytest arguments
│   │
│   └── show <id>              # Show session details
│       ├── --time            # Time window
│       └── --verbose         # Show all details
│
├── history                       # Historical views
│   └── list                    # List test sessions
│       ├── --time            # Time window (e.g., 7d, 24h)
│       ├── --by-sut         # Group by SUT
│       ├── --sut            # Filter by specific SUT
│       └── --all            # Show all entries (vs 50)
│
├── sut                           # SUT operations
│   └── list                    # List available SUTs
│
└── analytics                     # Analysis operations
    ├── summary                 # Show summary statistics
    │   ├── --sut            # Filter by SUT
    │   └── --days           # Time window in days
    │
    ├── compare                # Compare test results
    │   ├── --base           # Base (session/SUT/date)
    │   ├── --target        # Target (session/SUT/date)
    │   ├── --mode          # session/sut/period
    │   └── --time          # Time window
    │
    ├── analyze                # Analyze SUT metrics
    │   ├── --sut            # SUT to analyze
    │   ├── --metric        # Metric to analyze
    │   └── --days          # Time window in days
    │
    └── failures               # Show failure patterns
        ├── --sut            # SUT to analyze
        └── --nodeid        # Show specific test history

---
One way to slice/dice the commands is to group them by the level of abstraction they operate on. Here's a proposed hierarchy:

SUT
 └── TestSession
      └── TestResult

insight
├── sut                     # SUT-level operations
│   ├── list               # List all SUTs
│   ├── show <sut>         # Show SUT details
│   ├── compare            # Compare SUTs
│   └── analyze            # Analyze SUT trends
│
├── session                 # Session-level operations
│   ├── run                # Run new session (launches Pytest)
│   ├── list               # List sessions
│   ├── show <id>          # Show session details
│   └── compare            # Compare sessions
│
└── test                    # Test-level operations
    ├── list               # List all tests
    ├── show <nodeid>      # Show test details
    ├── history            # Show test history
    └── trends             # Show test trends
