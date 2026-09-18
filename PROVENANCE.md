# Provenance and release inventory

Initial source was extracted from a private operational repository on 2026-09-16. Only the Trac MCP adapter, compatibility broker and their fixture/protocol tests were selected. Operational evidence, gateway configuration, private environment registry, server history, credentials and unrelated worker/Android code were deliberately excluded.

Before first public release, the repository owner should confirm the copyright attribution in LICENSE and review any future third-party additions. The initial extracted Python files use Python standard library plus Trac APIs; no vendored third-party source is included.

## Capability reference review, 18 September 2026

The tool-surface expansion was compared with `nerpatech/trac-mcp-server` at
commit `59fd236f14b4f291f032d8f739d651ea49d35e0c`. That project is MIT
licensed, copyright 2026 nerpa.tech.

For this expansion, its README/tool documentation and architecture descriptions
were used as a capability/reference inventory. The broker/adapter
implementations in this repository were independently written against Trac's
public Python model APIs; no source code from nerpatech was copied into this
change.

The resulting mapping and deliberate differences are recorded in
`docs/NERPATECH_CAPABILITY_MATRIX.md`. In particular, Markdown/TracWiki
converter source was reviewed but not imported, and no new third-party parser
dependency was added.
