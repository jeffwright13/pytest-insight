"""API Introspection module for pytest-insight.

This module demonstrates how to use Python's introspection capabilities to
dynamically generate FastAPI endpoints from the pytest-insight API classes.
"""

import inspect
import re
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Type, get_type_hints

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, create_model

from pytest_insight.analysis import Analysis
from pytest_insight.comparison import Comparison

# Import API classes for introspection
from pytest_insight.core_api import InsightAPI
from pytest_insight.query import Query as PyTestQuery
from pytest_insight.storage import get_storage_instance

# Note: This file will be moved to pytest_insight/web_api/instrospect.py
# The imports above will remain the same, but this module will be accessed differently
# The new import path will be: from pytest_insight.web_api.instrospect import introspected_app

# ---- Utility Functions for Introspection ----

def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def create_endpoint_name(class_name: str, method_name: str) -> str:
    """Create an endpoint name from class and method names."""
    class_part = camel_to_snake(class_name)
    method_part = camel_to_snake(method_name)
    return f"{class_part}_{method_part}"


def create_parameter_model(method: Callable, prefix: str = "") -> Type[BaseModel]:
    """Create a Pydantic model with UI enhancements for method parameters."""
    sig = inspect.signature(method)
    type_hints = get_type_hints(method)

    field_definitions = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue

        param_type = type_hints.get(name, Any)
        default = ... if param.default == param.empty else param.default

        # Add UI hints based on parameter type and name
        field_info = {}

        # Date/time related parameters
        if name.endswith("_days") or name.endswith("_date"):
            field_info["description"] = f"Select number of {name.replace('_', ' ')}"
            field_info["ui_widget"] = "datepicker"

        # SUT related parameters
        elif "sut" in name.lower():
            field_info["description"] = "Select System Under Test"
            field_info["ui_widget"] = "dropdown"

        # Pattern related parameters
        elif "pattern" in name.lower():
            field_info["description"] = "Enter pattern (supports wildcards)"
            field_info["ui_widget"] = "text"

        # Boolean parameters
        elif param_type is bool:
            field_info["description"] = f"Toggle {name.replace('_', ' ')}"
            field_info["ui_widget"] = "toggle"

        field_definitions[name] = (param_type, Field(default, **field_info))

    model_name = f"{prefix}{method.__name__.capitalize()}Params"
    return create_model(model_name, **field_definitions)


# ---- API Categorization ----

class EndpointCategory:
    """Represents a category of related API endpoints."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.endpoints = []

    def add_endpoint(self, path: str, method: str, summary: str):
        """Add an endpoint to this category."""
        self.endpoints.append({
            "path": path,
            "method": method,
            "summary": summary
        })


def categorize_endpoints(api_class: Type, prefix: str = "") -> Dict[str, EndpointCategory]:
    """Categorize endpoints based on method name patterns."""
    categories = {
        "query": EndpointCategory("Query Operations", "Methods for querying and filtering test data"),
        "filter": EndpointCategory("Filtering Operations", "Methods for filtering test results"),
        "compare": EndpointCategory("Comparison Operations", "Methods for comparing test results"),
        "analyze": EndpointCategory("Analysis Operations", "Methods for analyzing test patterns"),
        "config": EndpointCategory("Configuration", "Methods for configuring the API"),
        "other": EndpointCategory("Other Operations", "Miscellaneous operations")
    }

    # Get all public methods
    methods = [
        method for name, method in inspect.getmembers(api_class, predicate=inspect.isfunction)
        if not name.startswith("_") and name not in ["__init__"]
    ]

    for method in methods:
        name = method.__name__
        endpoint_name = create_endpoint_name(api_class.__name__, name)
        path = f"/{endpoint_name}"

        # Determine category based on method name
        category_key = "other"
        if "query" in name or "find" in name or "get" in name or "list" in name:
            category_key = "query"
        elif "filter" in name or "with" in name:
            category_key = "filter"
        elif "compare" in name or "diff" in name or "between" in name:
            category_key = "compare"
        elif "analyze" in name or "report" in name or "insight" in name:
            category_key = "analyze"
        elif "config" in name or "profile" in name or "setting" in name:
            category_key = "config"

        categories[category_key].add_endpoint(path, "POST", f"{api_class.__name__}.{name}")

    # Remove empty categories
    return {k: v for k, v in categories.items() if v.endpoints}


# ---- Core API Router Generators ----

def generate_api_router(api_class: Type, prefix: str = "") -> Tuple[APIRouter, Dict[str, EndpointCategory]]:
    """Generate a FastAPI router from an API class with categorized endpoints."""
    router = APIRouter()

    # Categorize endpoints
    categories = categorize_endpoints(api_class, prefix)

    # Get all public methods that aren't special methods
    methods = [
        method for name, method in inspect.getmembers(api_class, predicate=inspect.isfunction)
        if not name.startswith("_") and name not in ["__init__"]
    ]

    for method in methods:
        # Create parameter model
        param_model = create_parameter_model(method, prefix)

        # Create endpoint path
        endpoint_name = create_endpoint_name(api_class.__name__, method.__name__)
        path = f"/{endpoint_name}"

        # Define endpoint function
        async def endpoint_function(params: param_model):
            # Create instance of API class
            api_instance = api_class()

            # Call method with parameters
            result = getattr(api_instance, method.__name__)(**params.dict(exclude_unset=True))

            # Return result
            return {"result": str(result)}

        # Determine category for tags
        category_tag = "Other Operations"
        for cat in categories.values():
            for ep in cat.endpoints:
                if ep["path"] == path:
                    category_tag = cat.name
                    break

        # Add endpoint to router
        router.add_api_route(
            path=path,
            endpoint=endpoint_function,
            methods=["POST"],
            response_model=Dict[str, Any],
            summary=f"{api_class.__name__}.{method.__name__}",
            description=method.__doc__,
            tags=[category_tag]
        )

    return router, categories


# ---- High-Level Operation Routers ----

def create_query_router() -> APIRouter:
    """Create a high-level query router with user-friendly endpoints."""
    router = APIRouter()

    class QueryParams(BaseModel):
        sut_name: Optional[str] = Field(None, description="System Under Test name")
        days: Optional[int] = Field(None, description="Number of days to look back", gt=0)
        test_pattern: Optional[str] = Field(None, description="Test pattern (supports wildcards)")
        profile_name: Optional[str] = Field(None, description="Storage profile name")

    @router.post("/execute")
    async def execute_query(params: QueryParams):
        """Execute a query with the specified parameters."""
        api = InsightAPI(profile_name=params.profile_name)
        query = api.query()

        if params.sut_name:
            query = query.for_sut(params.sut_name)
        if params.days:
            query = query.in_last_days(params.days)
        if params.test_pattern:
            query = query.filter_by_test().with_pattern(params.test_pattern).apply()

        results = query.execute()
        return {"results": results}

    @router.get("/available_suts")
    async def get_available_suts(profile_name: Optional[str] = None):
        """Get a list of available SUTs for the specified profile."""
        storage = get_storage_instance(profile_name=profile_name)
        suts = storage.get_available_suts()
        return {"suts": suts}

    return router


def create_comparison_router() -> APIRouter:
    """Create a high-level comparison router with user-friendly endpoints."""
    router = APIRouter()

    class ComparisonParams(BaseModel):
        base_sut: str = Field(..., description="Base SUT name")
        target_sut: str = Field(..., description="Target SUT name")
        test_pattern: Optional[str] = Field(None, description="Test pattern (supports wildcards)")
        base_profile: Optional[str] = Field(None, description="Base storage profile name")
        target_profile: Optional[str] = Field(None, description="Target storage profile name")

    @router.post("/execute")
    async def execute_comparison(params: ComparisonParams):
        """Execute a comparison with the specified parameters."""
        api = InsightAPI()
        comparison = api.compare()

        if params.base_profile:
            comparison = comparison.with_base_profile(params.base_profile)
        if params.target_profile:
            comparison = comparison.with_target_profile(params.target_profile)

        comparison = comparison.between_suts(params.base_sut, params.target_sut)

        if params.test_pattern:
            comparison = comparison.with_test_pattern(params.test_pattern)

        results = comparison.execute()
        return {"results": results}

    return router


def create_analysis_router() -> APIRouter:
    """Create a high-level analysis router with user-friendly endpoints."""
    router = APIRouter()

    class AnalysisParams(BaseModel):
        sut_name: Optional[str] = Field(None, description="System Under Test name")
        days: Optional[int] = Field(None, description="Number of days to look back", gt=0)
        profile_name: Optional[str] = Field(None, description="Storage profile name")

    @router.post("/health_report")
    async def generate_health_report(params: AnalysisParams):
        """Generate a health report for the specified SUT."""
        api = InsightAPI(profile_name=params.profile_name)
        analysis = api.analyze()

        if params.sut_name:
            analysis = analysis.for_sut(params.sut_name)
        if params.days:
            analysis = analysis.in_last_days(params.days)

        report = analysis.health_report()
        return {"report": report}

    @router.post("/stability_report")
    async def generate_stability_report(params: AnalysisParams):
        """Generate a stability report for the specified SUT."""
        api = InsightAPI(profile_name=params.profile_name)
        analysis = api.analyze()

        if params.sut_name:
            analysis = analysis.for_sut(params.sut_name)
        if params.days:
            analysis = analysis.in_last_days(params.days)

        report = analysis.tests().stability()
        return {"report": report}

    return router


# ---- Category Index Endpoints ----

def create_category_index(app: FastAPI, all_categories: Dict[str, Dict[str, EndpointCategory]]):
    """Create an index endpoint that shows all endpoint categories."""

    @app.get("/api/categories", tags=["API Index"])
    async def get_categories():
        """Get a list of all API endpoint categories."""
        result = {}

        for api_name, categories in all_categories.items():
            result[api_name] = {
                cat_name: {
                    "description": cat.description,
                    "endpoints": cat.endpoints
                } for cat_name, cat in categories.items()
            }

        return result

    # Create individual category endpoints with fixed parameters
    for api_name, categories in all_categories.items():
        for cat_name, category in categories.items():
            # Create a closure that captures the current values
            def make_endpoint(a_name=api_name, c_name=cat_name, cat=category):
                @app.get(f"/api/categories/{a_name}/{c_name}", tags=["API Index"])
                async def get_category_detail():
                    """Get details for a specific endpoint category."""
                    return {
                        "name": cat.name,
                        "description": cat.description,
                        "endpoints": cat.endpoints
                    }
                return get_category_detail

            # Execute the function to create and register the endpoint
            make_endpoint()

    # Add a debug endpoint to show all available category paths
    @app.get("/api/debug/categories", tags=["Debug"])
    async def debug_categories():
        """Debug endpoint to show all available category paths."""
        paths = []
        for api_name, categories in all_categories.items():
            for cat_name in categories.keys():
                paths.append(f"/api/categories/{api_name}/{cat_name}")
        return {"available_paths": paths}


# ---- Main FastAPI App ----

def create_introspected_api() -> FastAPI:
    """Create a FastAPI app with both introspected and high-level endpoints."""
    app = FastAPI(
        title="pytest-insight Dynamic API",
        description="Dynamically generated API from pytest-insight classes",
        version="0.1.0",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add a root endpoint that redirects to docs
    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/dashboard")

    # Add high-level operation routers
    app.include_router(
        create_query_router(),
        prefix="/api/operations/query",
        tags=["Query Operations"],
    )

    app.include_router(
        create_comparison_router(),
        prefix="/api/operations/comparison",
        tags=["Comparison Operations"],
    )

    app.include_router(
        create_analysis_router(),
        prefix="/api/operations/analysis",
        tags=["Analysis Operations"],
    )

    # Add low-level introspected routers with categorization
    all_categories = {}

    insight_router, insight_categories = generate_api_router(InsightAPI, prefix="insight_")
    all_categories["insight"] = insight_categories
    app.include_router(
        insight_router,
        prefix="/api/introspect",
        tags=["Introspect API"],
    )

    query_router, query_categories = generate_api_router(PyTestQuery, prefix="query_")
    all_categories["query"] = query_categories
    app.include_router(
        query_router,
        prefix="/api/introspect/query",
        tags=["Introspect Query"],
    )

    comparison_router, comparison_categories = generate_api_router(Comparison, prefix="comparison_")
    all_categories["comparison"] = comparison_categories
    app.include_router(
        comparison_router,
        prefix="/api/introspect/comparison",
        tags=["Introspect Comparison"],
    )

    analysis_router, analysis_categories = generate_api_router(Analysis, prefix="analysis_")
    all_categories["analysis"] = analysis_categories
    app.include_router(
        analysis_router,
        prefix="/api/introspect/analysis",
        tags=["Introspect Analysis"],
    )

    # Create category index endpoints
    create_category_index(app, all_categories)

    # Setup templates and static files

    # Create templates directory if it doesn't exist
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)

    # Create static directory if it doesn't exist
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)

    # Setup Jinja2 templates
    templates = Jinja2Templates(directory=str(templates_dir))
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Create dashboard template if it doesn't exist
    dashboard_template = templates_dir / "dashboard.html"
    if not dashboard_template.exists():
        with open(dashboard_template, "w") as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>pytest-insight Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { padding-top: 20px; }
        .card { margin-bottom: 20px; }
        .nav-link.active { font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">pytest-insight Dashboard</h1>

        <div class="row">
            <div class="col-md-3">
                <div class="card">
                    <div class="card-header">Operations</div>
                    <div class="card-body">
                        <ul class="nav flex-column">
                            <li class="nav-item">
                                <a class="nav-link active" href="#query-tab" data-bs-toggle="tab">Query</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="#compare-tab" data-bs-toggle="tab">Compare</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link" href="#analyze-tab" data-bs-toggle="tab">Analyze</a>
                            </li>
                        </ul>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">Recent Sessions</div>
                    <div class="card-body">
                        <div id="recent-sessions-list">Loading...</div>
                    </div>
                </div>
            </div>

            <div class="col-md-9">
                <div class="tab-content">
                    <div class="tab-pane active" id="query-tab">
                        <div class="card">
                            <div class="card-header">Query Test Sessions</div>
                            <div class="card-body">
                                <form id="query-form">
                                    <div class="mb-3">
                                        <label for="query-path" class="form-label">Test Path</label>
                                        <input type="text" class="form-control" id="query-path" placeholder="Path to test results">
                                    </div>
                                    <div class="mb-3">
                                        <label for="query-filter" class="form-label">Filter</label>
                                        <select class="form-select" id="query-filter">
                                            <option value="all">All Tests</option>
                                            <option value="failed">Failed Tests</option>
                                            <option value="passed">Passed Tests</option>
                                            <option value="skipped">Skipped Tests</option>
                                        </select>
                                    </div>
                                    <button type="submit" class="btn btn-primary">Execute Query</button>
                                </form>

                                <div class="mt-4">
                                    <h5>Results</h5>
                                    <div id="query-results">
                                        <p class="text-muted">Execute a query to see results</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="tab-pane" id="compare-tab">
                        <div class="card">
                            <div class="card-header">Compare Test Sessions</div>
                            <div class="card-body">
                                <form id="compare-form">
                                    <div class="mb-3">
                                        <label for="compare-base" class="form-label">Base Session</label>
                                        <select class="form-select" id="compare-base">
                                            <option value="">Select a session</option>
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label for="compare-target" class="form-label">Target Session</label>
                                        <select class="form-select" id="compare-target">
                                            <option value="">Select a session</option>
                                        </select>
                                    </div>
                                    <button type="submit" class="btn btn-primary">Compare</button>
                                </form>

                                <div class="mt-4">
                                    <h5>Comparison Results</h5>
                                    <div id="compare-results">
                                        <p class="text-muted">Execute a comparison to see results</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="tab-pane" id="analyze-tab">
                        <div class="card">
                            <div class="card-header">Analyze Test Sessions</div>
                            <div class="card-body">
                                <form id="analyze-form">
                                    <div class="mb-3">
                                        <label for="analyze-session" class="form-label">Session</label>
                                        <select class="form-select" id="analyze-session">
                                            <option value="">Select a session</option>
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label for="analyze-type" class="form-label">Analysis Type</label>
                                        <select class="form-select" id="analyze-type">
                                            <option value="health">Health Report</option>
                                            <option value="duration">Duration Analysis</option>
                                            <option value="failures">Failure Analysis</option>
                                        </select>
                                    </div>
                                    <button type="submit" class="btn btn-primary">Analyze</button>
                                </form>

                                <div class="mt-4">
                                    <h5>Analysis Results</h5>
                                    <div id="analyze-results">
                                        <p class="text-muted">Execute an analysis to see results</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Load recent sessions
        fetch('/api/operations/query/recent')
            .then(response => response.json())
            .then(data => {
                const sessionsList = document.getElementById('recent-sessions-list');
                if (data.sessions && data.sessions.length > 0) {
                    const ul = document.createElement('ul');
                    ul.className = 'list-group';

                    data.sessions.forEach(session => {
                        const li = document.createElement('li');
                        li.className = 'list-group-item';
                        li.innerHTML = `<a href="#" class="session-link" data-id="${session.id}">${session.name}</a>`;
                        ul.appendChild(li);
                    });

                    sessionsList.innerHTML = '';
                    sessionsList.appendChild(ul);
                } else {
                    sessionsList.innerHTML = '<p class="text-muted">No recent sessions found</p>';
                }
            })
            .catch(error => {
                console.error('Error fetching sessions:', error);
                document.getElementById('recent-sessions-list').innerHTML =
                    '<p class="text-danger">Error loading sessions</p>';
            });

        // Setup form submissions
        document.getElementById('query-form').addEventListener('submit', function(e) {
            e.preventDefault();
            const path = document.getElementById('query-path').value;
            const filter = document.getElementById('query-filter').value;

            fetch('/api/operations/query/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    path: path,
                    filter: filter
                }),
            })
            .then(response => response.json())
            .then(data => {
                const resultsDiv = document.getElementById('query-results');
                if (data.results) {
                    let html = '<table class="table table-striped">';
                    html += '<thead><tr><th>Test</th><th>Status</th><th>Duration</th></tr></thead>';
                    html += '<tbody>';

                    data.results.forEach(test => {
                        const statusClass = test.status === 'passed' ? 'text-success' :
                                          (test.status === 'failed' ? 'text-danger' : 'text-warning');

                        html += `<tr>
                            <td>${test.name}</td>
                            <td><span class="${statusClass}">${test.status}</span></td>
                            <td>${test.duration.toFixed(2)}s</td>
                        </tr>`;
                    });

                    html += '</tbody></table>';
                    resultsDiv.innerHTML = html;
                } else {
                    resultsDiv.innerHTML = '<p class="text-muted">No results found</p>';
                }
            })
            .catch(error => {
                console.error('Error executing query:', error);
                document.getElementById('query-results').innerHTML =
                    '<p class="text-danger">Error executing query</p>';
            });
        });

        // Similar event handlers for compare and analyze forms would go here
    </script>
</body>
</html>
            """)

    # Add dashboard routes
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request):
        """Interactive dashboard for exploring TestSessions."""
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @app.get("/api/operations/query/recent", tags=["Dashboard API"])
    async def get_recent_sessions():
        """Get a list of recent test sessions."""
        # Get the storage instance
        get_storage_instance()

        # Get recent sessions (placeholder implementation)
        try:
            # This is a simplified example - in a real implementation,
            # you would use the actual storage API to get recent sessions
            sessions = [
                {"id": "session1", "name": "Test Run 1 - March 29, 2025", "date": "2025-03-29"},
                {"id": "session2", "name": "Test Run 2 - March 28, 2025", "date": "2025-03-28"},
                {"id": "session3", "name": "Test Run 3 - March 27, 2025", "date": "2025-03-27"}
            ]
            return {"sessions": sessions}
        except Exception as e:
            return {"error": str(e), "sessions": []}

    @app.post("/api/operations/query/execute", tags=["Dashboard API"])
    async def execute_query(query: Dict[str, Any]):
        """Execute a query for test sessions."""
        # This is a placeholder implementation
        # In a real implementation, you would use the Query API to execute the query

        # Simulate some test results
        import random

        results = []
        for i in range(10):
            status = random.choice(["passed", "failed", "skipped"])
            if query.get("filter") != "all" and query.get("filter") != status:
                continue

            results.append({
                "name": f"test_function_{i}",
                "status": status,
                "duration": random.uniform(0.1, 2.0)
            })

        return {"results": results}

    return app


# Create the app
introspected_app = create_introspected_api()


def main():
    """Run the introspected API server."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Run pytest-insight introspected API server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")

    args = parser.parse_args()
    print(f"Starting pytest-insight introspected API server at http://{args.host}:{args.port}")
    print(f"API documentation: http://{args.host}:{args.port}/docs")

    uvicorn.run(introspected_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
