# XN远控 — Project State

> SSOT for the current project state. Update this file when project facts change.

## Project
- Project: XN远控 (RustDesk customized fork)
- Upstream: rustdesk/rustdesk
- Current upstream baseline in custom branch history: RustDesk 1.4.9 / commit `6c578292e8ebbbec708b76986ba8c4bc7c509747`
- Current development branch: `custom-nav-controls`
- Current branch HEAD: governance initialization commit after `d0d435e41b8da376b0fc4ee503f8129e55508c76`
- Current business-code baseline: `d0d435e41b8da376b0fc4ee503f8129e55508c76`
- Default repository branch: `master`
- Current phase: Phase 0 — Governance & Upstream Recovery

## Current Status
- Overall: BLOCKED for new feature development.
- Android custom build: last verified GitHub Actions run succeeded on 2026-09-03 for business-code commit `d0d435e...`.
- Windows custom build: NOT VERIFIED in current custom CI path.
- Upstream sync automation: NOT WORKING as designed; scheduled workflow is not loaded from the default branch.
- Release traceability: BROKEN; latest custom release tag points to `master` instead of the custom build SHA.
- Upstream divergence at governance review: custom branch business-code baseline was 13 commits ahead of fork `master`, 121 behind fork `master`, and 199 behind current upstream `rustdesk/rustdesk master` on 2026-09-14.

## Completed
- Fork established from RustDesk.
- Android app branding customized to `XN远控`.
- Android applicationId changed to `com.carriez.flutter_hbb.custom`.
- Custom mobile shortcut system implemented: key, combination, macro, text, icon, visibility, ordering, toolbar options, and two-row layout.
- Authorized connection-manager minimization behavior implemented on custom branch.
- Custom Android signed APK build workflow exists and has produced successful builds.
- Initial governance SSOT established in repository.

## In Progress
- Phase 0 governance initialization closeout.
- Upstream recovery plan.
- CI / release traceability remediation.

## Blocked
- New feature development is blocked until Phase 0 recovery gates pass.

## Known Defects
- See `KNOWN_ISSUES.md`.

## Backlog
- i18n for XN-only UI strings.
- Macro timing / WAIT support.
- Windows custom build verification.
- Dedicated regression tests for XN custom behavior.
- `XN-MULTI-DISPLAY-01`: Android unified multi-monitor workspace. Product direction: foldable-first unified canvas is the preferred primary interaction for unfolded devices, preserving monitor-relative geometry and allowing pan/zoom plus direct interaction across the combined remote desktop. Single-monitor switching and overview/thumbnail navigation remain secondary/fallback modes. Do not start implementation until Phase 0 is released.
- Future product-direction decision: optimized personal remote-control client vs. broader managed-device platform.

## Next
1. Preserve current working custom branch with an immutable archive tag/branch.
2. Establish a clean XN integration branch from current upstream RustDesk.
3. Reapply XN custom changes in controlled groups.
4. Repair upstream sync and release traceability.
5. Add Android + Windows build gates and XN regression coverage.

## Verification Baseline
- Android CI build: PASS, GitHub Actions run `33714217274`, 2026-09-03, against `d0d435e...`.
- Android signing: PASS in the same run.
- Windows build: NOT RUN / NOT VERIFIED for current custom branch.
- Dedicated XN regression tests: MISSING.
- Scheduled upstream sync: 0 successful scheduled runs observed.
- Human acceptance: NOT RECORDED in governance SSOT.
- Production release: none declared by this governance state.

## Production
- No production deployment is declared by this repository governance state.
- Custom GitHub prereleases exist; they are not considered production releases.
