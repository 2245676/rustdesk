# ADR-002 — Release artifacts must map to exact source commit

Status: Accepted

## Context
A custom APK release was observed whose tag pointed to a different commit than the custom branch SHA that produced the artifact.

## Decision
Every XN release artifact must map to the exact Git commit used by its build workflow. Release tags must point to that exact source commit.

## Reason
Without this, builds are not reliably reproducible, auditable, or debuggable.

## Consequences
- Release workflows must create/update tags using the build SHA, not the repository default branch implicitly.
- Release verification must inspect the resulting tag ref.

## Forbidden
Publishing an artifact under a tag that resolves to a different source commit than the build SHA.
