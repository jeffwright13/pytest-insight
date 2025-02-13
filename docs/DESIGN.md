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
