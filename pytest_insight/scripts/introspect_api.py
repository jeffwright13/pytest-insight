"""
CLI and Python utility to introspect any API class and print or output Markdown documentation.

Usage (CLI):
    python introspect_api.py <module> <class> [--markdown] [output.md]
Example:
    python introspect_api.py pytest_insight.core.insights Insights --markdown api.md
    python introspect_api.py pytest_insight.core.insights Insights

Usage (Python):
    from pytest_insight.scripts.introspect_api import introspect_api
    print(introspect_api(MyClass, markdown=True))
"""

import importlib
import inspect
import sys
from typing import get_type_hints


def introspect_api(api_cls, markdown=False):
    """Return documentation for an API class as a string (Markdown or plain text)."""
    lines = []
    lines.append(
        f"# API: {api_cls.__name__}\n" if markdown else f"API: {api_cls.__name__}\n"
    )
    doc = inspect.getdoc(api_cls) or ""
    lines.append(doc)
    lines.append("\n## Methods\n" if markdown else "\nMethods:\n")
    for name, member in inspect.getmembers(api_cls, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        sig = inspect.signature(member)
        doc = inspect.getdoc(member) or ""
        type_hints = get_type_hints(member)
        params = []
        for param in sig.parameters.values():
            if param.name == "self":
                continue
            annotation = type_hints.get(param.name, "Any")
            default = (
                f" = {param.default!r}"
                if param.default != inspect.Parameter.empty
                else ""
            )
            if markdown:
                params.append(f"`{param.name}`: `{annotation}`{default}")
            else:
                params.append(f"{param.name}: {annotation}{default}")
        params_str = ", ".join(params)
        if markdown:
            lines.append(f"### `{name}({params_str})`")
            if doc:
                lines.append(f"{doc}\n")
        else:
            lines.append(f"- {name}({params_str})")
            if doc:
                lines.append(f"    {doc}\n")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python introspect_api.py <module> <class> [--markdown] [output.md]"
        )
        sys.exit(1)
    module_name, class_name = sys.argv[1:3]
    markdown = False
    output_file = None
    if "--markdown" in sys.argv:
        markdown = True
        idx = sys.argv.index("--markdown")
        if len(sys.argv) > idx + 1:
            output_file = sys.argv[idx + 1]
    elif len(sys.argv) > 3:
        output_file = sys.argv[3]
    mod = importlib.import_module(module_name)
    api_cls = getattr(mod, class_name)
    doc_str = introspect_api(api_cls, markdown=markdown)
    if output_file:
        with open(output_file, "w") as f:
            f.write(doc_str)
    else:
        print(doc_str)


if __name__ == "__main__":
    main()
