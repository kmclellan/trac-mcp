# Repository agent instructions

These instructions apply to AI coding/operations agents working on `trac-mcp`. Human contributors should also follow the same safety and validation principles.

## Read first

Before changing the repository, read `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `PROVENANCE.md`, and the tests relevant to the change. The README is the authoritative human-readable installation/configuration guide; keep it accurate.

## Development safety

- Run routine Git, source editing, dependency, build, lint, packaging, and test work as the normal repository owner, never root.
- Use privileged execution only for a narrowly scoped system operation that genuinely requires it and only when the task authorizes that operation. Never use root to bypass an ordinary permission/dependency failure.
- Inspect `git status` and recent history before editing. Preserve unrelated work and make focused commits.
- Keep temporary files and backups outside the repository.
- Never commit credentials, tokens, private keys, personal email addresses, live configuration, private host/domain/IP information, production Trac paths/environment names, messages, or user data.
- Examples must remain generic and must not encode a maintainer's live infrastructure.

## Security boundaries

Preserve the deliberately constrained architecture. Do not add generic shell, SQL, arbitrary filesystem, unrestricted `trac-admin`, destructive delete, or arbitrary-environment access without explicit design/security review. Environment access must remain allowlisted. Do not make sockets or configuration world-accessible to solve permission failures.

## Validation

Run the relevant automated tests after changes. At minimum for adapter/protocol changes run:

```sh
python tests/test_trac_mcp_protocol.py
```

When package/entry-point behaviour changes, install/test the package in an isolated environment where practical. Legacy broker fixture testing must use a disposable Trac environment, never production. Report automated, fixture/integration, and production validation separately.

## Documentation contract

A feature is not complete when it changes requirements, installation, configuration, operation, compatibility, security behaviour, upgrade/uninstall steps, or troubleshooting unless `README.md` and other relevant documentation are updated in the same change.

Instructions should be both human-readable and AI-compatible: state prerequisites, execution context/user, commands, expected result, safety constraints, and verification. Avoid relying on unstated local knowledge.

## Pre-push privacy and provenance check

Before pushing or publishing, inspect both current tracked content **and reachable Git commit metadata/history**. Confirm there are no secrets, personal email addresses, private infrastructure identifiers, operational paths/configuration, or unintended third-party material. Git commit identity for this repository should use the maintainer's GitHub privacy-preserving noreply address; public copyright/authorship may use the maintainer's real name.

Do not rewrite shared/public history casually. If sensitive data has entered history, stop and use a deliberate sanitization procedure with verification.

## Contributions and AI assistance

Follow `CONTRIBUTING.md`, including its AI-assistance disclosure/provenance requirements. Never send confidential project or deployment material to an external AI service merely to complete a contribution.
