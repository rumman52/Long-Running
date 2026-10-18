## Purpose

Describe the problem and the intended behavior change.

## Design and compatibility

- What changed and why?
- Does this change affect authorization, persisted state, schemas, APIs, or retries?
- Are any limitations or migration steps required?

## Verification

- [ ] Tests added or updated, including failure paths.
- [ ] `pytest` passes.
- [ ] `ruff check src tests examples` passes.
- [ ] `mypy src/intent_integrity` passes.
- [ ] Relevant demo(s) run successfully.
- [ ] Documentation and changelog updated.

## Security review

- [ ] No secrets, credentials, or personal data added.
- [ ] Untrusted model/tool/file output cannot grant authorization or bypass validation.
- [ ] Blocked actions are proven not to invoke the underlying callback.
- [ ] Retry, duplicate-action, timeout, and ambiguous-outcome behavior considered.
- [ ] New dependencies and GitHub Actions reviewed for maintenance and supply-chain risk.
- [ ] Independent review requested for security-sensitive changes.

## Evidence and claims

State what was actually run, the environment, and any checks that could not be run. Do not equate passing CI with production qualification.
