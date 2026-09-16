# Trac MCP

A deliberately constrained Model Context Protocol (MCP) interface for Trac. It lets MCP clients work with explicitly approved Trac environments without exposing generic shell, SQL, filesystem, `trac-admin`, or destructive administration access.

This README is intended to be usable by both people and AI coding/operations agents. Commands state their assumptions; do not substitute production paths, users, or permissions without reviewing the security consequences.

## Status

The project is preparing its first `v0.1.0` release. The Python 3 MCP adapter and protocol tests are suitable for current Python 3 environments. `legacy/trac_broker_py2.py` is a compatibility broker for older Trac installations that still run under Python 2. Modern Trac/Python combinations have not yet been claimed as broker-compatible until independently validated.

## What it does

The MCP-facing Python 3 process communicates over a local Unix-domain socket with a broker that owns the actual Trac API access. This separates the modern MCP runtime from an older Trac runtime and avoids giving the MCP process direct filesystem access to Trac environments.

The interface is deliberately bounded. Environment IDs are explicitly allowlisted; guarded writes use revision/snapshot checks; creation/comment/upload operations use idempotency keys; and attachment names and sizes are bounded. There is no generic SQL, shell, arbitrary filesystem path, arbitrary `trac-admin`, or delete interface.

## Architecture

```text
MCP client / gateway
        |
        | stdio MCP
        v
Python 3 trac-mcp adapter
        |
        | local Unix-domain socket
        v
Trac compatibility broker
        |
        | Trac Python API
        v
explicitly allowlisted Trac environment(s)
```

The socket is a local trust boundary. Do not expose it directly to a network or to untrusted local users. Authentication and per-user authorization belong at the MCP client/gateway boundary.

## Requirements

### MCP adapter

- Python 3.10 or newer.
- A Unix-like system when using the supplied Unix-socket broker design.
- Local access to the configured broker Unix socket.
- `pip` or another PEP 517-capable Python installer for package installation.

The adapter does **not** require direct access to the Trac environment directory.

### Legacy compatibility broker

The supplied legacy broker is intended for installations where Trac itself still runs under Python 2. It requires:

- the Python interpreter used by the target Trac installation;
- the Trac Python package importable by that interpreter;
- filesystem/database permissions required by Trac for only the environments you explicitly configure;
- permission to create and serve the configured Unix socket.

Run the broker as a dedicated least-privilege account. Do not run it as root merely to bypass permissions.

## Quick start for development

These commands exercise the MCP adapter without connecting to a production Trac installation.

```sh
git clone <repository-url>
cd trac-mcp
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
python tests/test_trac_mcp_protocol.py
```

Expected result: the protocol test suite reports `OK`.

To verify the installed console entry point can start:

```sh
printf '' | trac-mcp
```

An empty standard input causes it to exit; this is a startup/package check, not an end-to-end Trac test.

If `python3 -m venv` reports that `ensurepip` is unavailable, install your operating system's Python venv package using its normal package-management procedure, then recreate the virtual environment. Do not work around this by running project development as root.

## Installation

### 1. Install the Python 3 adapter

For a system or service deployment, choose an installation location appropriate to your operating system. For development, use a virtual environment as shown above.

From a checked-out release:

```sh
python3 -m pip install .
```

Verify:

```sh
command -v trac-mcp
```

### 2. Configure the adapter

The adapter understands these environment variables:

| Variable | Meaning | Example |
| --- | --- | --- |
| `TRAC_MCP_SOCKET` | Unix socket used to reach the broker | `/run/trac-mcp/trac.sock` |
| `TRAC_MCP_ENVIRONMENTS` | Comma-separated public environment IDs exposed through MCP | `example,docs` |
| `TRAC_MCP_AUTHOR` | Default Trac history author where applicable | `MCP` |

Start from `examples/trac-mcp.env.example`. Environment IDs should be stable public labels; they do not need to reveal filesystem paths or host information.

### 3. Configure the legacy broker

The broker's `TRAC_MCP_ENVIRONMENTS` has a different form because it maps public IDs to local Trac paths:

```text
TRAC_MCP_ENVIRONMENTS=example=/srv/trac/example,docs=/srv/trac/docs
```

Only list environments that MCP is intended to reach. Use absolute paths. The public adapter should expose only the corresponding IDs (`example,docs`), not these paths.

Start from `examples/trac-broker.env.example`.

### 4. Run the broker

A generic systemd example is provided at `examples/systemd/trac-mcp-broker.service.example`. It deliberately uses placeholder installation paths and a generic `trac` service account. Review and adapt it rather than copying it blindly.

Before enabling a service, verify manually that:

1. the configured interpreter imports Trac;
2. the service account can access each intended Trac environment and no unintended environment;
3. the socket directory is writable by the broker and accessible by the adapter;
4. the environment file is not writable by untrusted users.

Then use your operating system's normal systemd workflow to install, enable, start, and inspect the service. System-level installation generally requires administrator privileges; source development and Git operations do not.

### 5. Connect an MCP client or gateway

Configure the MCP client to execute the installed `trac-mcp` command using stdio and supply the adapter environment variables. Exact configuration syntax varies between MCP clients, so this project does not provide a client-specific JSON fragment that might become stale.

The MCP process should run as an unprivileged account that can connect to the broker socket but does not need direct Trac filesystem access.

## Configuration rules

- Keep the adapter's public environment-ID allowlist and broker mapping synchronized.
- Never put credentials, private keys, tokens, personal data, production hostnames, or unnecessary infrastructure details in the repository.
- Do not expose arbitrary environment paths as MCP arguments.
- Treat a change to the environment allowlist as a security-sensitive configuration change.
- Keep the broker socket local and permission-restricted.
- Prefer a dedicated broker account with the minimum Trac permissions required.

## Testing

Run the Python 3 protocol suite from the repository root:

```sh
python tests/test_trac_mcp_protocol.py
```

GitHub Actions also installs the package and checks the `trac-mcp` entry point on the supported Python matrix.

The legacy fixture test is intentionally separate because it needs a disposable Trac environment compatible with the legacy broker:

```sh
python tests/trac_broker_fixture_test.py
```

**Never point a fixture or destructive validation workflow at a production Trac environment.** Automated protocol tests, disposable-fixture testing, and production verification are different levels of evidence and should be reported separately.

## Verifying a deployment

A safe deployment check should proceed from least invasive to more integrated:

1. confirm package installation and `trac-mcp` startup;
2. confirm broker service/socket health;
3. list the exposed environment IDs and verify the allowlist is exact;
4. perform read-only operations against a disposable or test environment;
5. test guarded writes only in a disposable/test environment;
6. verify denied environments and unsupported generic operations fail closed;
7. only then consider bounded read-only production verification.

Do not use production mutation as an installation test.

## Troubleshooting

### Adapter cannot connect to the socket

Check that `TRAC_MCP_SOCKET` is identical for adapter and broker, the broker is running, and the adapter account has permission to connect. Do not make the socket world-writable as a shortcut.

### Environment is reported as unknown or denied

Check both sides of the allowlist. The adapter needs the public ID and the broker needs a matching `id=/absolute/path` mapping. A failure for an unconfigured ID is expected security behaviour.

### Broker cannot import Trac

Run the configured broker interpreter directly and test `import trac`. Older Trac installations may use a dedicated Python environment. Use that environment rather than changing the server's global Python merely for this project.

### Permission denied on a Trac environment

Verify the broker service account and the target environment's intended ownership/permissions. Do not run the broker as root to make the error disappear.

### Python virtual environment cannot be created

Install the appropriate OS package providing Python's `venv`/`ensurepip` support. This is a host prerequisite, not a reason to develop as root.

## Upgrading

For a source deployment:

```sh
git fetch --tags
# Review the release notes before selecting a new release.
python -m pip install .
python tests/test_trac_mcp_protocol.py
```

Back up deployment configuration before changing it. Review `CHANGELOG.md` for configuration or compatibility changes. If the broker changes, validate it against a disposable Trac environment before replacing a production broker.

## Uninstalling

Remove the Python package using the same Python environment used to install it:

```sh
python -m pip uninstall trac-mcp
```

For a system deployment, separately disable/remove any broker service and its configuration/socket runtime files according to your operating system practices. Do not remove Trac environments or their data as part of uninstalling this MCP adapter.

## Security model and reporting

The constrained interface is intentional. Requests to add generic shell, SQL, arbitrary filesystem access, unrestricted `trac-admin`, or destructive operations should receive explicit security review rather than being treated as ordinary convenience features.

See `SECURITY.md` for vulnerability reporting and `PROVENANCE.md` for the initial source/provenance audit.

## Development and contributions

Read `CONTRIBUTING.md` before submitting changes. Keep commits focused, run the documented tests, and update documentation whenever requirements, installation, configuration, public behaviour, security boundaries, or compatibility change.

AI-assisted contributions are permitted subject to the disclosure, review, testing, confidentiality, and provenance requirements in `CONTRIBUTING.md`.

## Guidance for AI agents

AI agents working with this repository should follow the same instructions as human contributors and additionally:

1. Read this README, `AGENTS.md`, `SECURITY.md`, `CONTRIBUTING.md`, and relevant tests before modifying code.
2. Treat examples as placeholders, not evidence about a live deployment.
3. Never infer or invent production hostnames, paths, credentials, users, environment IDs, or service configuration.
4. Do routine source, Git, build, lint, and test work as the normal repository owner, not root.
5. Use privileged execution only for a narrowly scoped system operation that genuinely requires it and only when authorized.
6. Inspect Git status/history before changes and preserve unrelated work.
7. Run relevant automated tests and distinguish those results from integration/production validation.
8. Update this README when a change affects setup, requirements, configuration, operation, compatibility, or troubleshooting.
9. Before publishing/pushing, check tracked content **and commit metadata/history** for secrets, personal email addresses, private infrastructure details, or unintended operational data.
10. Do not weaken the project's bounded security model merely to make a test or deployment succeed.

`AGENTS.md` contains the concise repository rules intended for coding-agent discovery. This README remains the authoritative human-readable setup and operational guide.

## Repository layout

```text
src/trac_mcp/                  Python 3 MCP adapter
legacy/trac_broker_py2.py      legacy Trac/Python 2 compatibility broker
tests/                         protocol and broker fixture tests
examples/                      generic environment/systemd examples
.github/workflows/             CI configuration
SECURITY.md                    vulnerability/security policy
CONTRIBUTING.md                contribution and AI-assistance policy
PROVENANCE.md                  source/provenance record
CHANGELOG.md                   release history
RELEASE_CHECKLIST.md           release-readiness record
```

## Known limitations

- The included compatibility broker targets legacy Trac/Python 2 deployments; modern broker compatibility needs explicit validation before being claimed.
- Client/gateway authentication is outside this repository's scope.
- The supplied systemd and environment files are examples and require local review.
- Production deployment cannot be proven solely by CI; validate against an appropriate disposable Trac environment first.

## Licence and authorship

Copyright (c) 2026 Kelly McLellan.

Licensed under the MIT License. See `LICENSE`.
