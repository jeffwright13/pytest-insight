"""
FastAPI app for the self-discovering, chainable API Explorer UI.
This is a placeholder. Integrate dynamic introspection and UI logic here.
"""

import importlib
import inspect
import os
from typing import Any, List, get_type_hints, Optional

import orjson
from fastapi import Body, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pytest_insight.core.storage import ProfileManager, get_profile_metadata, get_storage_instance
from pytest_insight.insight_api import InsightAPI

app = FastAPI(title="pytest-insight API Explorer")

# Set up Jinja2 templates
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@app.get("/", response_class=HTMLResponse)
def explorer_home(request: Request):
    """Serve the interactive API explorer UI."""
    return templates.TemplateResponse("explorer.html", {"request": request})


@app.get("/introspect")
def introspect_api(module: str, class_: str, markdown: bool = False):
    """Dynamically introspect any API class and return its structure as JSON or Markdown, grouped by facet and operation type."""
    try:
        mod = importlib.import_module(module)
        api_cls = getattr(mod, class_)
    except (ImportError, AttributeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    def categorize_method(name, doc):
        """Categorize method into analytics, filtering, or utility based on naming and docstring."""
        analytics_keywords = [
            "report",
            "summary",
            "trend",
            "insight",
            "aggregate",
            "metrics",
            "compare",
            "forecast",
            "pattern",
        ]
        filter_keywords = ["filter", "with_", "for_", "in_", "by_", "apply"]
        lname = name.lower()
        if any(kw in lname for kw in analytics_keywords):
            return "analytics"
        if any(lname.startswith(kw) for kw in filter_keywords):
            return "filtering"
        return "utility"

    def get_api_structure(api_cls):
        grouped = {"analytics": [], "filtering": [], "utility": []}
        for name, member in inspect.getmembers(api_cls, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            try:
                sig = inspect.signature(member)
            except (ValueError, TypeError):
                sig = None
            doc = inspect.getdoc(member) or ""
            type_hints = get_type_hints(member)
            params = []
            if sig:
                for param in sig.parameters.values():
                    if param.name == "self":
                        continue
                    annotation = str(type_hints.get(param.name, "Any"))
                    default = param.default if param.default != inspect.Parameter.empty else None
                    params.append(
                        {
                            "name": param.name,
                            "type": annotation,
                            "default": default,
                        }
                    )
                sig_str = str(sig)
            else:
                sig_str = "(builtin or unavailable)"
            category = categorize_method(name, doc)
            grouped[category].append(
                {
                    "name": name,
                    "params": params,
                    "signature": sig_str,
                    "doc": doc,
                }
            )
        return {
            "class": api_cls.__name__,
            "doc": inspect.getdoc(api_cls) or "",
            "analytics": grouped["analytics"],
            "filtering": grouped["filtering"],
            "utility": grouped["utility"],
        }

    api_struct = get_api_structure(api_cls)
    if markdown:
        return HTMLResponse(f"<pre>{introspect_api_markdown(api_cls, markdown=True)}</pre>")
    return JSONResponse(api_struct)


@app.get("/profiles")
def list_profiles():
    """List all available profiles with metadata."""
    pm = ProfileManager()
    pm.reload()
    meta = get_profile_metadata()
    if "error" in meta:
        return JSONResponse({"status": "error", "error": meta["error"]}, status_code=500)
    profiles = list(meta.get("profiles", {}).keys())
    return JSONResponse({"profiles": profiles})


@app.post("/profiles")
def create_profile(
    name: str = Body(...),
    type: str = Body("json"),
    path: str = Body(None),
):
    """Create a new storage profile with metadata."""
    pm = ProfileManager()
    try:
        profile = pm.create_profile(name, type, path)
        pm.reload()
        return JSONResponse({"status": "success", "profile": profile.to_dict()})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=400)


@app.get("/profiles/{name}")
def get_profile_metadata_endpoint(name: str):
    """Get metadata/details for a profile."""
    pm = ProfileManager()
    pm.reload()
    try:
        profile = pm.get_profile(name)
        return JSONResponse({"profile": profile.to_dict()})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=404)


@app.delete("/profiles/{name}")
def delete_profile(name: str):
    """Delete a storage profile."""
    pm = ProfileManager()
    try:
        pm.delete_profile(name)
        pm.reload()
        return JSONResponse({"status": "success", "profile": name})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=400)


@app.post("/profiles/active")
def set_active_profile(
    name: Optional[str] = Body(None),
    name_query: Optional[str] = Query(None)
):
    # Prefer JSON body, fallback to query param
    active_name = name or name_query
    if not active_name:
        return JSONResponse({"status": "error", "error": "Missing profile name"}, status_code=422)
    pm = ProfileManager()
    try:
        pm.switch_profile(active_name)
        return JSONResponse({"status": "success", "active_profile": active_name})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=400)


@app.get("/profiles/active")
def get_active_profile():
    """Get the currently active profile name."""
    pm = ProfileManager()
    pm.reload()
    try:
        profile = pm.get_active_profile()
        # Return just the name, not the dict
        return JSONResponse({"active_profile": profile.name})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=404)


class ChainStep(BaseModel):
    name: str
    params: List[Any]


class ExecuteChainRequest(BaseModel):
    profile: str
    module: str
    class_: str
    chain: List[ChainStep]


class IntrospectChainRequest(BaseModel):
    profile: str
    module: str
    class_: str
    chain: List[ChainStep]


@app.post("/introspect_chain")
def introspect_chain(req: IntrospectChainRequest = Body(...)):
    """Introspect the next valid methods/properties after executing the current chain."""
    try:
        mod = importlib.import_module(req.module)
        api_cls = getattr(mod, req.class_)
        # Instantiate API object, passing profile if supported
        try:
            api_obj = api_cls(profile=req.profile)
        except TypeError:
            api_obj = api_cls()
        obj = api_obj
        for step in req.chain:
            attr = getattr(obj, step.name, None)
            if attr is None:
                return JSONResponse(
                    {"error": f"Attribute or method '{step.name}' not found."},
                    status_code=400,
                )
            if callable(attr):
                obj = attr(*step.params)
            elif not step.params:
                obj = attr
            else:
                return JSONResponse(
                    {"error": f"'{step.name}' is not callable and does not accept parameters."},
                    status_code=400,
                )
        # Now introspect next valid methods/properties
        methods = []
        props = []
        for name in dir(obj):
            if name.startswith("_"):
                continue
            member = getattr(obj, name)
            doc = inspect.getdoc(member) or ""
            if callable(member):
                try:
                    sig = str(inspect.signature(member))
                except (ValueError, TypeError):
                    sig = "(builtin or unavailable)"
                methods.append({"name": name, "signature": sig, "doc": doc})
            else:
                props.append({"name": name, "doc": doc})
        return JSONResponse({"methods": methods, "properties": props})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/execute_chain")
def execute_chain(req: ExecuteChainRequest = Body(...)):
    """Execute a chain of API calls and return the result. Supports both method and property access."""
    try:
        mod = importlib.import_module(req.module)
        api_cls = getattr(mod, req.class_)
        # Instantiate API object, passing profile if supported
        try:
            api_obj = api_cls(profile=req.profile)
        except TypeError:
            api_obj = api_cls()
        obj = api_obj
        for step in req.chain:
            attr = getattr(obj, step.name, None)
            if attr is None:
                return JSONResponse(
                    {"error": f"Attribute or method '{step.name}' not found."},
                    status_code=400,
                )
            if callable(attr):
                obj = attr(*step.params)
            elif not step.params:  # property access
                obj = attr
            else:
                return JSONResponse(
                    {"error": f"'{step.name}' is not callable and does not accept parameters."},
                    status_code=400,
                )
        # Try to jsonify the result, fallback to str
        try:
            return HTMLResponse(f"<pre>{orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode()}</pre>")
        except Exception:
            return HTMLResponse(f"<pre>{str(obj)}</pre>")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/profile_stats")
def profile_stats(profile: str = Query(None), filtered: bool = Query(False)):
    """
    Return stats for the given profile (or active profile if not given).
    If filtered=True, returns stats for the current filtered set of sessions (if supported).
    """
    profile_manager = ProfileManager()
    if not profile:
        prof = profile_manager.get_active_profile()
    else:
        prof = profile_manager.get_profile(profile)
    # Use the correct storage backend
    storage = get_storage_instance(profile_name=prof.name)
    sessions = storage.load_sessions()
    api = InsightAPI(sessions)
    # Gather stats
    summary = api.summary_report()
    # SUTs and testing systems
    suts = set()
    systems = set()
    for sess in sessions:
        suts.add(getattr(sess, "sut", None))
        systems.add(getattr(sess, "testing_system", None))
    # Remove None
    suts.discard(None)
    systems.discard(None)
    return JSONResponse(
        {
            "profile": prof.name,
            "total_sessions": len(sessions),
            "suts": sorted(list(suts)),
            "num_suts": len(suts),
            "testing_systems": sorted(list(systems)),
            "num_testing_systems": len(systems),
            "summary": summary,
        }
    )
