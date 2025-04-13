
# Pytest-Insight: Using tox to Test Multiple Dependency Levels

This guide shows how to configure `tox` to test different installation "flavors" of your plugin (core, visualize, dev, all).

---

## ✅ 1. Define your `tox.ini`

```ini
[tox]
envlist = core, visualize, dev, all
isolated_build = True

[testenv]
commands =
    pytest tests/

[testenv:core]
description = Core plugin only
deps =
    .  # this installs just the base dependencies

[testenv:visualize]
description = Plugin + visualization extras
deps =
    .[visualize]

[testenv:dev]
description = Plugin + development extras
deps =
    .[dev]

[testenv:all]
description = All extras
deps =
    .[all]
```

> 🔧 Make sure your `tests/` folder exists and has at least a basic test to validate installation.

---

## 🧪 2. Run tox

To run all environments:

```bash
tox
```

Or to test just one:

```bash
tox -e visualize
```

---

## 🚀 3. Extra: use `uv` in your tox environments

If you want to use `uv` instead of pip inside each tox environment, override `install_command`:

```ini
[testenv]
install_command = uv pip install {opts} {packages}
```

> ⚠️ `uv` must already be installed in the host environment running tox.

---

## 📦 4. Optional: Create a `tox-gh-actions` matrix

Example `tox.ini` for GitHub Actions:

```ini
[tox]
envlist = py38-core, py38-visualize, py39-all

[testenv]
deps = .[dev]
commands = pytest

[testenv:py38-core]
basepython = python3.8
deps = .

[testenv:py38-visualize]
basepython = python3.8
deps = .[visualize]

[testenv:py39-all]
basepython = python3.9
deps = .[all]
```

GitHub Actions workflow:

```yaml
jobs:
  test:
    strategy:
      matrix:
        python-version: [3.8, 3.9]
        tox-env: [core, visualize, all]

    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install tox
        run: pip install tox
      - name: Run tests
        run: tox -e py${{ matrix.python-version }}-${{ matrix.tox-env }}
```

---

## 💡 Summary

- `tox` validates optional dependencies like `core`, `visualize`, `dev`, and `all`.
- Use `deps = .[extra]` to test install flavors.
- `uv` works in `tox` by overriding the install command.
- GitHub Actions can test Python versions + flavors via matrix strategy.

---

# 🛠️ Using `uv` to Build and Test Optional Dependencies

## 1. Define optional dependencies in `pyproject.toml`

\`\`\`toml
[project.optional-dependencies]
visualize = [
    "streamlit>=1.22.0",
    "pandas>=1.5.0",
    "plotly>=5.13.0",
    "scikit-learn>=1.2.0",
    "fastapi>=0.95.0",
    "uvicorn>=0.20.0",
    "requests>=2.28.0",
    "python-multipart>=0.0.6",
]

dev = [
    "hatch>=1.14.0",
    "build>=0.10.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.10.0",
    "pytest-rerunfailures>=12.0",
    "pre-commit>=3.3.0",
    "black>=23.3.0",
    "isort>=5.12.0",
    "pyflakes>=3.0.0",
    "ruff>=0.0.270",
]

all = [
    "pytest-insight[visualize,dev]",
]
\`\`\`

## 2. Build your project with `uv`

Run this command from the project root:

\`\`\`bash
uv build
\`\`\`

This creates `dist/*.whl` and `dist/*.tar.gz` files with the correct metadata for optional dependencies.

## 3. Install and test the builds locally

\`\`\`bash
# Install just the core package
uv pip install dist/pytest_insight-<version>.whl

# With visualization extras
uv pip install dist/pytest_insight-<version>.whl[visualize]

# With dev tools
uv pip install dist/pytest_insight-<version>.whl[dev]

# All extras
uv pip install dist/pytest_insight-<version>.whl[all]
\`\`\`

Or directly from source:

\`\`\`bash
uv pip install .[visualize]
uv pip install .[dev]
uv pip install .[all]
\`\`\`

## 4. Document the install levels

In your `README.md`, document the install options:

\`\`\`md
## Installation

\`\`\`bash
# Core install
pip install pytest-insight

# With visual features
pip install pytest-insight[visualize]

# For development
pip install pytest-insight[dev]

# Everything
pip install pytest-insight[all]
\`\`\`
\`\`\`
