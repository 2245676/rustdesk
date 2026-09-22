# XN远控 — Project State

> SSOT for the current project state. Update this file when project facts change.

## Project
- Project: XN远控 (RustDesk customized fork)
- Upstream: rustdesk/rustdesk
- Current upstream baseline: `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`
- Current development branch: `xn-main`
- XN product features migrated to xn-main: NO (not yet migrated)
- Legacy custom branch: `custom-nav-controls`
- Safe restore branch: `restore/xn-remote-20260914-1909`
- Default repository branch: `master`
- Current phase: Phase 0 — Governance & Upstream Recovery

## Current Status
- Overall: BLOCKED for new feature development.
- Phase: Phase 0 — Governance & Upstream Recovery.
- xn-main established from clean upstream baseline.
- Clean upstream baseline verified PASS (P0-01A encoding fix PASS / closed, P0-01B clean baseline verification PASS).
- XN product features have NOT been migrated to xn-main.
- Next step: P0-01C — inventory and controlled re-application of XN customizations.

## Completed
- Fork established from RustDesk.
- Clean xn-main branch established from upstream SHA `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`.
- XN governance SSOT established on xn-main.
- P0-01A: PROJECT_STATE.md encoding normalized to UTF-8 without BOM (closed).
- P0-01B: Clean upstream baseline verification PASS on xn-main.

## In Progress
- Phase 0 governance closeout (P0-01A closed, P0-01B PASS, P0-01C pending).
- XN customization inventory and migration planning.

## Blocked
- XN product feature migration is blocked until P0-01C inventory / migration plan is approved.
- New feature development is STILL BLOCKED until Phase 0 recovery gates pass.

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
1. P0-01C — inventory and controlled re-application of XN customizations.
2. Plan XN customization migration in controlled groups.
3. Migrate mobile shortcut system.
4. Migrate connection-manager behavior.
5. Add Android + Windows build gates and XN regression coverage.

## Verification Baseline
- xn-main upstream baseline: SHA `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`
- Clean baseline diff: only XN governance files (no business-code changes)
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
- xn-main business-code comparison: NO XN business code is present yet; xn-main differs from pinned upstream baseline only by governance / SSOT files.

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
- Do NOT start migration until P0-01C is approved.
- Custom GitHub prereleases exist; they are not considered production releases.
