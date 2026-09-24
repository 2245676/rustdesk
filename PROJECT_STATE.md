# XN远控 — Project State

> SSOT for the current project state. Update this file when project facts change.

## Project
- Project: XN远控 (RustDesk customized fork)
- Upstream: rustdesk/rustdesk
- Current upstream baseline: `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`
- Current development branch: `xn-main`
- XN product features migrated to xn-main: PARTIAL — C1 Android brand/package identity migrated; C2/C3 pending
- Legacy custom branch: `custom-nav-controls`
- Safe restore branch: `restore/xn-remote-20260914-1909`
- Default repository branch: `master`
- Current phase: Phase 0 — Governance & Upstream Recovery

## Current Status
- Overall: BLOCKED for new feature development.
- Phase: Phase 0 — Governance & Upstream Recovery.
- xn-main established from clean upstream baseline.
- Clean upstream baseline verified PASS (P0-01A encoding fix PASS / closed, P0-01B clean baseline verification PASS).
- P0-01C inventory / migration matrix approved.
- C1 Android brand/package identity implementation PASS.
- C1 canonical Android build gate PASS.
- C1 Human Acceptance remains PENDING and may be completed during P0-01F final regression/acceptance.
- Next step: P0-01C-C2 — migrate the mobile shortcut/action system using a controlled reimplementation.

## Completed
- Fork established from RustDesk.
- Clean xn-main branch established from upstream SHA `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`.
- XN governance SSOT established on xn-main.
- P0-01A: PROJECT_STATE.md encoding normalized to UTF-8 without BOM (closed).
- P0-01B: Clean upstream baseline verification PASS on xn-main.
- P0-01C-INV: legacy XN customization inventory and migration matrix reviewed and accepted.
- P0-01C-C1 implementation: Android applicationId restored to `com.carriez.flutter_hbb.custom` and launcher label restored to `XN远控`.
- P0-01C-C1 build verification: Full Flutter CI Run `35882408942` completed SUCCESS; default bridge, Android arm64, Android armv7, and Android x86_64 jobs all PASS.

## In Progress
- Phase 0 controlled re-application of XN customizations.
- C1 Human Acceptance: PENDING.
- C2 mobile shortcut/action system: pending implementation.
- C3 authorized connection-manager behavior: pending redesign / security review.

## Blocked
- New feature development is STILL BLOCKED until Phase 0 recovery gates pass.
- Android advanced automation-coexistence work remains blocked until Phase 0 is released.
- C3 cannot be migrated as a direct legacy replay; it requires redesign and security review.

## Known Defects
- See `KNOWN_ISSUES.md`.

## Backlog
- i18n for XN-only UI strings.
- Macro timing / WAIT support.
- Windows custom build verification.
- Dedicated regression tests for XN custom behavior.
- `XN-MULTI-DISPLAY-01`: Android unified multi-monitor workspace. Do not start implementation until Phase 0 is released.
- Future product-direction decision: optimized personal remote-control client vs. broader managed-device platform.

## Next
1. P0-01C-C2 — controlled migration of the mobile shortcut/action system.
2. P0-01C-C3 — redesign and migrate authorized connection-manager behavior with security review.
3. P0-01D — repair upstream-sync automation.
4. P0-01E — repair exact-SHA release traceability.
5. P0-01F — Android + Windows regression, install verification, and Human Acceptance.

## Verification Baseline
- xn-main upstream baseline: SHA `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`
- Current C1 product commit: `f30fa4683ad67414e4f1ae3c87b121a7c8aba809`
- Legacy custom branch SHA: `4f3aea6c3b2c3f40a782412cc69369ad8490da0b`
- Restore branch SHA: `e31a5d103170f363a5f58ed2509549dcf040c3cc`

## P0-01B Verification Evidence
- Pinned upstream baseline: `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`
- Official upstream Full Flutter CI: Run ID `34827362039` — Conclusion: SUCCESS
- Official upstream CI: Run ID `34827361314` — Conclusion: SUCCESS
- Verified successful jobs include:
  - flutter bridge generation
  - Windows x64
  - Windows ARM64
  - Android arm64
  - Android armv7
  - Android x86_64

## P0-01C-C1 Verification Evidence
- C1 implementation commit: `f30fa4683ad67414e4f1ae3c87b121a7c8aba809`
- Product diff: only Android `applicationId` and application launcher label.
- Full Flutter CI validation Run ID: `35882408942` — Conclusion: SUCCESS
- Required jobs:
  - default bridge (Flutter 3.22.3 / `bridge-artifact`) — PASS
  - Android `aarch64-linux-android` — PASS
  - Android `armv7-linux-androideabi` — PASS
  - Android `x86_64-linux-android` — PASS
- Temporary Draft PRs #1 and #2 were closed without merge after validation.
- Temporary validation branch `ci/c1-gate-validation` is not part of product history and must not be merged into `xn-main`.

## Local Environment Note
- Local verification attempt used non-canonical tool versions (Flutter 3.47.1 / Rust 1.95) and therefore its Gradle / generated bridge / vcpkg failures are NOT treated as baseline code failures.
- Repository canonical workflow currently pins:
  - Rust 1.75
  - Flutter 3.24.5
  - Android Flutter 3.24.5
  - bridge Flutter 3.22.3
  - NDK r28c
  - vcpkg commit `9e593bb18ea69cc5095e012465dcd675a822ed0d`
- Local build environment alignment remains a setup concern, not a Phase 0 baseline blocker.

## Production
- No production deployment is declared by this repository governance state.
- Do NOT claim Phase 0 complete.
- Do NOT claim production ready.
- Controlled Phase 0 migration is in progress; do not start unrelated new product features.
- Custom GitHub prereleases exist; they are not considered production releases.
