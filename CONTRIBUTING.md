# Contributing

Thank you for helping improve Intent Integrity. Contributions should preserve the project's central security boundary: untrusted agent/model output proposes actions, while trusted host code authorizes and validates them.

## Before opening a change

1. Read the [README](README.md), [architecture](docs/ARCHITECTURE.md), [runtime guide](docs/RUNTIME_GUIDE.md), and [threat model](docs/THREAT_MODEL.md).
2. For security-sensitive changes, read [SECURITY.md](SECURITY.md) and do not disclose vulnerabilities in a public issue.
3. Open an issue first for large API changes, new runtime dependencies, changes to authorization semantics, or changes that may alter persisted event formats.
4. Keep pull requests focused. Explain the threat or user problem, the design choice, compatibility impact, and any remaining limitations.

## Development setup

Requires Python 3.11 or newer and Git.

    python -m venv .venv
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    python examples/basic_validation.py
    python examples/long_running_task.py
    pytest
    ruff check src tests examples benchmarks
    mypy src/intent_integrity

The demos use local temporary state and fake callbacks. They must not perform real external side effects.

## Required checks

Before requesting review:

- Add or update tests for behavior changes, failure paths, and security boundaries.
- Run the test suite, Ruff, and mypy; report any command that could not be run.
- Update documentation, schemas, examples, and the changelog where applicable.
- Do not weaken fail-closed behavior, approval requirements, evidence freshness checks, or duplicate-action protections without a documented design review.
- Do not add credentials, real personal data, production endpoints, or secrets to tests or examples.
- For changes to dependencies, justify the need, prefer maintained packages, review licenses and known vulnerabilities, and keep the dependency set minimal.
- For consequential-action paths, test both the blocked case and the permitted case, and prove that blocked calls never reach the underlying callback.
- Do not claim universal drift detection, complete MCP conformance, or production security certification without independently verifiable evidence.

## Pull-request review

Use the pull-request template. Reviewers should check correctness, backwards compatibility, authorization boundaries, prompt-injection exposure, logging of sensitive data, exception/retry behavior, test quality, and documentation. Security-sensitive changes should receive an independent review before release.

The maintainer may request a smaller change, additional tests, or a design note. Passing CI is necessary but is not proof of security.

## Licensing and contributions

Contributions accepted into the project are subject to the project license in [LICENSE](LICENSE). Do not submit code unless you have the right to contribute it and can accept those terms. No Contributor License Agreement is currently established; do not assume one exists.
