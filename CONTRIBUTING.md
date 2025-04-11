# Contributing to Pytest-Insight

Welcome! We're excited to have you contribute to **Pytest-Insight**. This document outlines the steps for setting up your development environment and contributing effectively. For detailed instructions, refer to [GitHub’s guide on creating pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).


---

## Setting Up Your Development Environment

We recommend using [`uv`](https://github.com/tingley/uv) for managing virtual environments. However, you may also use `pip` if you prefer.

---

### Using `uv`

1. **Install `uv`**:

Follow the instructions at https://docs.astral.sh/uv/getting-started/installation/ for your development environment (Linux, Mac, Windows). If you're contributing, we assume you can figure this out yourself. :-)

2. **Create a Virtual Environment**:
    ```bash
    uv venv --python <3.9|3.10|3.11|3.12|3.13> --prompt uv-pytest-insight
    source .venv/bin/activate
    ```

3. **Install All Dependencies**:
    ```bash
    uv pip install -e '.[all]'
    ```

4. **Verify the Setup (ensure the necessary tools are installed)**:

    ```bash
    uv pip list
    ```

---

## Pre-Commit Hooks

We use pre-commit to ensure consistent code formatting and quality. Once your environment is set up, install the hooks:

```bash
pre-commit install
```

Run the hooks on all files to validate your changes:

```bash
pre-commit run --all-files
```

The hooks will automatically check and fix issues related to:

- Code formatting (black)
- Import sorting (isort)
- Linting (ruff)
- Common errors (e.g., trailing whitespace, YAML validation)

---

## Submitting a Pull Request

1. **Branch From `master`**:
    ```bash
    git checkout master
    git pull
    git checkout -b my-branch
    ```

2. **Make Changes**:
    - Make your changes and ensure they pass the pre-commit hooks.
    - Add tests for new functionality or bug fixes.

3. **Run Tests**:
    ```bash
    pytest
    ```
    Ensure all tests pass before submitting your pull request.
    > **Note**: We haven't written any tests yet, but they're coming (and that's how you know we're real devs). :-)

4. **Commit Your Changes**:
    ```bash
    git add .
    git commit -m "Your commit message"
    ```
    > **Note**: Use a descriptive commit message that explains the changes you made.

5. **Rebase with `master`**:
    ```bash
    git pull --rebase origin master
    ```
    Resolve any conflicts that arise, save, recommit, and then continue.

6. **Push Your Changes**:
    ```bash
    git push origin my-branch
    ```
    > **Note**: Replace `my-branch` with the name of your branch.

7. **Create Pull Request**:
    - Go to the repository on GitHub.
    - Click on the "New Pull Request" button.
    - Select your branch and create the pull request.
