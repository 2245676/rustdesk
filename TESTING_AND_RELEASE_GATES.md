# XN远控 — Testing and Release Gates

## Testing Strategy
XN customizations must add focused verification on top of upstream RustDesk checks.

### Static / Compile
Protects syntax, type compatibility, generated bridge compatibility, and platform build integration.

### Unit / Logic
Protects XN custom data model, persistence parsing, shortcut normalization, and deterministic helper behavior.

### Regression
Protects previously fixed XN-specific bugs and behavior contracts.

### Platform Build
- Android: required for Android custom changes.
- Windows: required when desktop/shared code is modified.

### Integration
Required when XN changes cross Flutter <-> Rust bridge, session authorization state, release/tag mechanics, or upstream synchronization.

### Human Acceptance
Required for:
- Android real-device toolbar/keyboard behavior
- remote-control usability
- connection-manager foreground/minimize UX
- visual layout changes
- unattended access visibility expectations

AI cannot mark Human Acceptance PASS.

## Development Gates
### Gate 0 — Scope
Task Contract is complete.

### Gate 1 — Acceptance Criteria
Implementation satisfies the explicit contract.

### Gate 2 — Static / Analyze
Relevant formatter/analyzer/static checks PASS.

### Gate 3 — Unit / Logic
Relevant tests PASS.

### Gate 4 — XN Regression
XN-specific regression tests PASS, or task explicitly documents why automation is not practical.

### Gate 5 — Integration
Required cross-boundary verification PASS.

### Gate 6 — Build
Affected target builds PASS.
- Android changes -> Android build required.
- Shared desktop / connection-manager changes -> Windows build required.

### Gate 7 — Architecture Review
No unapproved architecture/invariant/SSOT drift.

### Gate 8 — Security Review
Required for HIGH/CRITICAL tasks affecting unattended access, credentials, signing, tokens, CI permissions, or release mechanics.

### Gate 9 — Human Acceptance
Required only where specified; remains BLOCKED until actual human confirmation.

### Gate 10 — Release Verification
For a release:
- artifact SHA/digest recorded where available
- build workflow run identified
- release/tag points to exact source commit
- required platform artifacts present

### Gate 11 — Rollback Verification
Required for high-risk release/automation changes where rollback is part of the contract.

## Merge Policy
A Coding Agent does not decide merge/release. The Orchestrator reviews evidence and declares PASS/BLOCKED.

## Release Policy
No XN production release is allowed while any blocking CRITICAL issue in `KNOWN_ISSUES.md` is OPEN.

## Current Missing Gates
- Dedicated XN regression suite.
- Windows build in custom release path.
- Verified upstream-sync automation.
- Correct artifact-to-source release tagging.
- Recorded human-acceptance procedure/results for current XN UX.
