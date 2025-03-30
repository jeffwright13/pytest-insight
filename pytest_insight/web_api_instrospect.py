"""API Introspection module for pytest-insight.

This module demonstrates how to use Python's introspection capabilities to
dynamically generate FastAPI endpoints from the pytest-insight API classes.
"""

import inspect
import re
from typing import Any, Callable, Dict, Type, get_type_hints

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel, create_model

from pytest_insight.analysis import Analysis
from pytest_insight.comparison import Comparison
from pytest_insight.core_api import InsightAPI
from pytest_insight.core_api import Query as PyTestQuery


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def create_endpoint_name(class_name: str, method_name: str) -> str:
    """Create an endpoint name from class and method names."""
    class_part = camel_to_snake(class_name)
    method_part = camel_to_snake(method_name)
    return f"{class_part}_{method_part}"


def create_parameter_model(method: Callable, prefix: str = "") -> Type[BaseModel]:
    """Create a Pydantic model for method parameters."""
    sig = inspect.signature(method)
    type_hints = get_type_hints(method)

    # Filter out self parameter
    params = {
        name: (type_hints.get(name, Any), ... if param.default == param.empty else param.default)
        for name, param in sig.parameters.items()
        if name != "self"
    }

    # Create model name based on method name
    model_name = f"{prefix}{method.__name__.capitalize()}Params"

    # Create and return the model
    return create_model(model_name, **params)


def generate_api_router(api_class: Type, prefix: str = "") -> APIRouter:
    """Generate a FastAPI router from an API class."""
    router = APIRouter()

    # Get all public methods that aren't special methods
    methods = [
        method
        for name, method in inspect.getmembers(api_class, predicate=inspect.isfunction)
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
            result = getattr(api_instance, method.__name__)(**params.dict())

            # Return result
            return {"result": str(result)}

        # Add endpoint to router
        router.add_api_route(
            path=path,
            endpoint=endpoint_function,
            methods=["POST"],
            response_model=Dict[str, Any],
            summary=f"{api_class.__name__}.{method.__name__}",
            description=method.__doc__,
        )

    return router


def create_introspected_api() -> FastAPI:
    """Create a FastAPI app with introspected endpoints."""
    app = FastAPI(
        title="pytest-insight Introspected API",
        description="Dynamically generated API from pytest-insight classes",
        version="0.1.0",
    )

    # Add routers for each API class
    app.include_router(
        generate_api_router(InsightAPI, prefix="insight_"),
        prefix="/api/introspect",
        tags=["introspect"],
    )

    app.include_router(
        generate_api_router(PyTestQuery, prefix="query_"),
        prefix="/api/introspect/query",
        tags=["query"],
    )

    app.include_router(
        generate_api_router(Comparison, prefix="comparison_"),
        prefix="/api/introspect/comparison",
        tags=["comparison"],
    )

    app.include_router(
        generate_api_router(Analysis, prefix="analysis_"),
        prefix="/api/introspect/analysis",
        tags=["analysis"],
    )

    return app


# Create the app
introspected_app = create_introspected_api()


def main():
    import uvicorn

    uvicorn.run(introspected_app, host="0.0.0.0", port=8001)


# Example usage:
if __name__ == "__main__":
    main()
