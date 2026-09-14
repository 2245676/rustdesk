# ADR-001 — Upstream-first XN customization model

Status: Accepted

## Context
XN远控 is currently a customized RustDesk fork. Maintaining a fully independent remote-desktop core would significantly increase security, protocol, platform, and maintenance burden.

## Decision
RustDesk remains the upstream core. XN features should be implemented as a constrained custom layer and kept as isolated/replayable as practical.

## Reason
This preserves upstream improvements and reduces long-term maintenance while allowing XN-specific UX/product behavior.

## Alternatives
- Fully independent fork with no upstream integration.
- Rewrite remote-control core.

## Consequences
- Upstream drift must be monitored.
- XN changes touching upstream files need careful integration tests.
- Customization boundaries must remain documented.

## Forbidden
Coding Agents may not replace the upstream core or abandon upstream compatibility inside ordinary feature tasks.
