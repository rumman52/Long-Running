# Reproducible Demos

The examples demonstrate local validation and recovery behavior. They use fake callbacks and/or temporary local SQLite databases; they do not contact external providers, publish reports, merge pull requests, or perform real-world side effects.

## Environment

- Python 3.11–3.14 is the supported CI range.
- Git is required to clone the repository.
- No API keys or external service accounts are required for the examples.
- The standard demo installation resolves the development dependencies declared in pyproject.toml. A fully pinned environment lockfile is not currently committed, so dependency resolution is not guaranteed to be byte-for-byte identical across dates.

## Fresh checkout

    git clone https://github.com/rumman52/Long-Running.git
    cd Long-Running
    python -m venv .venv

On macOS/Linux:

    source .venv/bin/activate

On Windows PowerShell:

    .venv\Scripts\Activate.ps1

Then install and run:

    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python examples/basic_validation.py
    python examples/long_running_task.py
    pytest
    ruff check src tests examples
    mypy src/intent_integrity

## Expected behavior

- basic_validation.py prints a structured validation result. It validates a sample action and does not execute that action.
- long_running_task.py demonstrates a blocked publish without approval, local checkpoint/recovery, invalidated assumptions, and an approved fake callback.
- pytest runs the automated suite.
- Ruff and mypy perform linting and static type checks.

Timestamps and generated identifiers can vary between runs. Reproducibility means that the same documented scenario and constraints can be rerun and checked, not that every printed byte is identical.

## Security boundary

Do not replace the fake callbacks with live external operations when running these examples. Real integrations need host authentication, a trusted approval/evidence source, provider-specific outcome reconciliation, and complete mediation of every consequential tool route.
