# Security Policy

## Reporting a vulnerability

**Do not report exploitable vulnerabilities in a public GitHub issue, pull request, discussion, or social post.**

1. If the repository shows GitHub's **Report a vulnerability** action, use it to submit a private security advisory.
2. If private reporting is not available, contact the repository maintainer through a private contact method listed on the maintainer's GitHub profile. Include a link to this repository and ask for a private channel before sending exploit details.
3. If you cannot establish a private channel, send only a minimal public message asking the maintainer to contact you privately. Do not publish a proof of concept or sensitive details.

The repository has no published security response SLA or bug-bounty program. The maintainer will make a reasonable effort to acknowledge reports, assess severity, coordinate remediation, and communicate a fix or mitigation. Please allow time for triage before public disclosure.

## What to include

- A concise description of the vulnerability and its security impact.
- Affected commit, tag, file, API, and configuration, if known.
- Minimal reproduction steps or a proof of concept that does not access real users' data or systems.
- Required preconditions, likely exploitability, and any suggested mitigation.
- Your preferred contact method for follow-up.

Do not include access tokens, credentials, private user data, or unrelated third-party information in the report.

## Scope and known limitations

The project is an early engineering scaffold for validating agent actions. In particular:

- A host that exposes an unguarded tool route can bypass this library's checks.
- A validation decision does not prove an external side effect succeeded.
- The SQLite hash chain is tamper-evident against some accidental or partial changes, not tamper-proof against an attacker who can rewrite the whole database.
- The project is not a production security certification or a universal semantic drift detector.

Please report security-relevant bypasses, authorization defects, unsafe recovery/retry behavior, evidence-validation flaws, and vulnerabilities in the repository's own code. Do not probe third-party systems or run destructive tests against infrastructure you do not own or have permission to test.
