# XN远控 — Project State

> SSOT for the current project state. Update this file when project facts change.

## Project
- Project: XN远控 (RustDesk customized fork)
- Upstream: rustdesk/rustdesk
- Current upstream baseline: `39d4f1854b6fc0ebf6df2477598b970e6d1f73bf`
- Current development branch: `xn-main`
- XN product features migrated to xn-main: C1/C2/C3 automated migration gates PASS; Human Acceptance remains pending for P0-01F
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
- C2A mobile custom shortcut core reimplementation PASS (including FIX-01 key normalization correction).
- C2B mobile custom shortcut UI integration PASS after independent review (0 findings / 0 blocking findings).
- C2C canonical CI / behavior gate PASS. Full Flutter CI Run `36450368096` completed SUCCESS; default bridge and Android arm64/armv7/x86_64 all PASS.
- C2 Human Acceptance remains PENDING and is deferred to P0-01F real-device regression/acceptance.
- C3A authorized Connection Manager behavior implementation and final independent security review PASS (0 findings / 0 blocking findings).
- C3 canonical Full Flutter CI Run `36728627973` completed SUCCESS; Windows x64/ARM64/i686 and canonical Flutter 3.22.3 bridge PASS.
- P0-01D preparation implementation and independent source/security review PASS on commit `4279287aa977556159626f09e8fe9c048946d1c6`; deployed by fast-forward to default branch `master` for activation testing.
- P0-01D live plan verification PASS. The original exact-commit tracking apply was safely blocked by GitHub's workflow-file permission boundary. Metadata-only tracking v2 was implemented, independently security-reviewed PASS (34/34 tests, 0 findings), and deployed to default branch `master` at `ab68b929ba9a6f84df4c490038a0cc6542338dcc`. Real metadata-v2 schedule/apply verification remains PENDING.
- P0-01E exact-SHA release traceability is VERIFIED / PASS. Live tag-first Release Run `36824489661` built from source `3685852e4ab2e60425aa5883e2fa0b64e963bca3`; the lightweight release tag and traceability manifest resolve to that exact SHA, and APK/EXE evidence was verified.

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
- C2 mobile shortcut/action system: implementation/review/CI PASS — C2A PASS; C2B PASS; C2C PASS. Human Acceptance remains PENDING for P0-01F.
- C3 authorized connection-manager behavior: automated implementation/security/canonical Windows CI gates PASS; Human Acceptance remains PENDING for P0-01F.
- P0-01D upstream-sync automation: metadata-v2 implementation/review/deployment PASS; original exact-commit apply blocker eliminated by design; real metadata-v2 schedule/apply verification PENDING.

## Blocked
- New feature development is STILL BLOCKED until Phase 0 recovery gates pass.
- Android advanced automation-coexistence work remains blocked until Phase 0 is released.

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
1. P0-01D — verify real metadata-v2 scheduled apply, resulting `upstream-tracking` metadata branch, token write capability, and protected-ref preservation.
2. P0-01F — Android + Windows regression, install verification, and Human Acceptance.

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

## P0-01C-C3A Verification Evidence
- C3A product baseline: `b0163b82391bb3031cff9a07680d11edcb55515e`.
- C3A accepted product head: `4aab9c59d731fe1377419eeccba191903fca64e2`.
- Final C3A product diff contains only `flutter/lib/main.dart` and `flutter/lib/models/server_model.dart`.
- `showCmWindow({bool isStartup = false})` signature remains unchanged; restore/minimize behavior is separated into dedicated helpers.
- Connection Manager startup policy is gated by `_cmWindowPolicyReady`; ServerModel does not mutate CM visibility/focus before startup window initialization completes.
- After startup helper completion, `onCmWindowInitialized()` marks policy ready and immediately applies current client state.
- `hideCm=false`: idle CM remains minimized instead of hidden; authorized-only sessions do not actively restore/show/focus the CM; unauthorized sessions restore/focus approval UI.
- Authorized auto-minimize timer is cancelled on unauthorized arrival and rechecks readiness, hide policy, and absence of unauthorized clients at fire time.
- `hideCm=true` semantics preserved; 500 ms / approximately 6-second zero-client close behavior preserved.
- Final independent Security Reviewer decision: PASS; findings 0; blocking findings 0; prior startup race F-01 CLOSED.
- Human window-behavior acceptance is not claimed here and remains for P0-01F.
- Canonical Full Flutter CI Run `36728627973` completed SUCCESS; Windows x64, Windows ARM64, i686 and default Flutter 3.22.3 bridge all PASS.

## P0-01C-C2C Verification Evidence
- Full Flutter CI Run `36450368096` — event `pull_request` — conclusion SUCCESS.
- Temporary validation head: `8085fd2446f02ecdf90d3234d1e155a3191e5f6b` on `ci/c2-gate-validation`; the only validation-only change was caller `permissions: contents: write` required by the reusable workflow. It is not product history and must not be merged into `xn-main`.
- Required default bridge job (Flutter 3.22.3 / `bridge-artifact`) — PASS.
- Android `aarch64-linux-android` — PASS.
- Android `armv7-linux-androideabi` — PASS.
- Android `x86_64-linux-android` — PASS.
- Full workflow also completed Windows x64/ARM64, Linux, macOS and SBOM jobs successfully where enabled; configured web/iOS/universal APK/appimage/flatpak/publish jobs were skipped normally.
- C2 automated/canonical gate is PASS. Human Acceptance is not claimed here and remains PENDING for P0-01F.

## P0-01C-C2B Verification Evidence
- C2B implementation commits: `fe4ef49b5326fa7db5e7d7887e34b4c5ebc3a7f8`, `4f8ab9c6dcf0633144564c56f4918c0312bcde4a`, `4b78f5808ab832dfa207ccc616c6246a5af06146`.
- Final C2B diff from `e9016318...` contains only three product Dart files: `remote_page.dart`, `custom_shortcuts.dart`, `custom_shortcuts_settings.dart`.
- Temporary `analysis_options.yaml` scope violation was fully reverted; it is absent from the final C2B diff.
- Canonical Flutter 3.24.5 compatibility restored: `ReorderableListView.onReorder`, `DropdownButtonFormField.value`, and explicit `package:flutter/foundation.dart` import.
- Independent Reviewer decision: PASS; findings 0; blocking findings 0.
- Reviewer verified shortcut load/execution/settings CRUD/reorder/visibility/two-row layout/toolbar preferences/keyboard guards/view-only guards and preservation of current RemotePage session teardown, Wayland keyboard gate, Android actions overlay, focus, gesture/touch/mouse, chat/voice, orientation behavior.
- C2A persistence/execution invariants preserved; XN-006 and XN-007 remain OPEN.

## P0-01C-C2A Verification Evidence
- C2A core commit: `f3a227e7ac006f8b6403b76522db96b0e8e2b42f`
- C2A FIX-01 commit: `fafba46d0977678b9610c6a0b2ada5eb62bbbf78`
- Scope: new `custom_shortcuts.dart` core + focused test file only; no RemotePage/runtime integration yet.
- Preserved legacy shortcut types, six persistence keys, v1 fallback, five default shortcuts, visibility/icon metadata, text input, key/combination execution, and immediate `;`-split macro semantics.
- Macro WAIT/delay/ACK remains intentionally NOT implemented; timing risk remains backlog/known issue.
- FIX-01 corrected key normalization so lowercase canonical inputs normalize to `VK_*` while unknown multi-character keys preserve their original value.
- Focused test source contains 29 `test(...)` cases at accepted HEAD; local execution remains environment-limited by the non-canonical local Flutter/toolchain and missing generated bridge artifacts.
- C2A runtime regression surface: NONE until C2B wires the module into `remote_page.dart`.

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

## P0-01D Preparation / Deployment Evidence
- Reviewed preparation commit: `4279287aa977556159626f09e8fe9c048946d1c6` from base `3f207e91f6061b637f704f94074ee487b030625f`.
- Scope: four added files only — `.github/workflows/sync-upstream.yml`, `scripts/xn/sync_upstream.py`, `tests/xn/test_sync_upstream.py`, `docs/operations/upstream-sync.md`.
- Isolated tests: 19/19 PASS; independent source/security review PASS with 0 findings / 0 blocking findings.
- ACT-01 deployed the exact reviewed commit to default branch `master` by fast-forward; no new deployment commit was created.
- Workflow registered ACTIVE. No real workflow_dispatch/apply/schedule has yet been accepted as verified.
- Existing Full Flutter CI push run `36737578394` hit the pre-existing reusable-workflow caller permission startup failure; this is not introduced by P0-01D. Existing CI push run `36737576992` was normally triggered because the deployment added non-ignored `scripts/**` and `tests/**` paths.

## P0-01D Live Activation Blocker
- Live plan run `36744792281` PASS: mode=plan, result=PLAN_CREATE, apply skipped, no remote ref write.
- Live apply run `36746343185` FAILED safely with `AUTH_CAPABILITY_BLOCKED`.
- GitHub rejected creation of `refs/heads/upstream-tracking` at official upstream SHA `fada664df7a294d1d1a9ca3e7cd3637069122f17` because the GitHub App token lacks permission to create/update workflow history containing `.github/workflows/flutter-build.yml`.
- `upstream-tracking` remains absent; master/xn-main/legacy/restore/tags were unchanged.
- Decision: do not add a long-lived elevated PAT merely to mirror the exact upstream commit. Redesign the tracking branch as trusted metadata that records the exact official upstream SHA while remaining based on fork-owned history and using the default `GITHUB_TOKEN`.

## P0-01D Metadata V2 Evidence
- Metadata-v2 delivery commit: `ab68b929ba9a6f84df4c490038a0cc6542338dcc` on `ci/p0-01d-metadata-tracking-v2`; direct parent `4279287aa977556159626f09e8fe9c048946d1c6`.
- Independent Security Reviewer: PASS; tests 34/34; findings 0; blocking findings 0.
- Model: `upstream-tracking` is metadata-only. Each commit tree contains only `UPSTREAM_TRACKING.json`; the recorded official upstream SHA is metadata, not the tracking commit itself.
- This design intentionally avoids transmitting official upstream workflow-file history to the fork, so it does not require elevated workflows permission or a PAT.
- Reviewed commit is now deployed to default branch `master` at `ab68b929ba9a6f84df4c490038a0cc6542338dcc`.
- Real `refs/heads/upstream-tracking` is still absent. Real metadata-v2 apply/write capability and real `event=schedule` execution are not yet verified.

## P0-01E Review Status
- Initial exact-SHA release preparation commit `029d65b1dddbcdc4f112e0552552e59a0e25e372` completed 61/61 offline tests but Main AI review is REWORK_REQUIRED.
- Blocking finding: the design creates the release tag from Actions with the default `GITHUB_TOKEN`. GitHub ref creation can require Workflows write when the target commit's `.github/workflows/*` differs from the default branch; current `xn-main` and `master` do have workflow-file differences. The default Actions token cannot obtain that Workflows permission.
- Direction: Actions must not create/move the XN release tag. Redesign around a pre-existing immutable tag created by the authorized local release controller, then run the release workflow from that tag and verify exact tag/source identity before and after build.

## P0-01E FIX-01 Main AI Review
- Tag-first release implementation commit `0b82df6d2f33e8e3c5012db2c5bebc36d410a698` passed its coding-agent validation (65/65 tests, actionlint PASS), but Main AI review found one blocking authorization-drift gap before independent security review.
- The local controller correctly rejects xn-main movement after its own source lock and before push, but `local-create` independently re-locks the latest `origin/xn-main` and is not bound to the exact SHA previously approved by Main AI/plan. If xn-main advances between approval/plan and create start, an unapproved newer SHA could be tagged and immediately trigger the release workflow.
- Required fix: `local-create` must require an exact approved-SHA assertion and fail closed if freshly fetched `origin/xn-main` differs. The assertion is a guard only; it must never select or override the source commit.

## P0-01E FIX-02 Independent Security Review
- Reviewed delivery commit: `f22eba4dcbf2eb85dc1741ec4ad696239fc72516`, direct parent/current product baseline `1ea40e605049e75c9684d3ffb379a80f6d02455d`.
- Scope verified: one commit, four added files only — `.github/workflows/xn-release.yml`, `scripts/xn/release_traceability.py`, `tests/xn/test_release_traceability.py`, `docs/operations/xn-release.md`.
- Main AI independent source/security review: PASS; findings 0; blocking findings 0.
- FIX-02 authorization guard is accepted: `local-create --expected-sha S` freshly locks `origin/xn-main`, then requires the fresh source to equal S before any tag lookup/write. The expected SHA is an assertion only and cannot select an older, local-only, unrelated, or newer source.
- Race coverage is accepted: plan→approval→branch advance fails `AUTHORIZED_SOURCE_CHANGED`; movement after lock but before push fails `SOURCE_BRANCH_MOVED`; ordinary one-ref push is non-force and post-create exact-ref verification remains mandatory.
- Actions path remains tag-read-only before/after build; tag creation/movement/deletion is not reachable from Actions prepare/verify code. The wrapper triggers only on `xn-release-*` tag push and validates the exact full-SHA tag identity, run identity, and xn-main ancestry.
- GitHub's documented push semantics support workflows on tag pushes even when the workflow is not merged to the default branch; official RustDesk tag-run evidence also shows tag name in `head_branch` and tag commit in `head_sha` for this event model.
- Existing-tag release publication is consistent with GitHub's documented release semantics: `target_commitish` is ignored when the tag already exists; GitHub's workflow-scope release restriction applies to workflow-changing target SHAs without an existing ref. Live token/release behavior is still a required production gate.
- Test source at the reviewed commit contains 74 focused test cases. No check-run is attached to the delivery commit; Main AI review here is a source/security review, not an independent runtime re-execution claim.
- P0-01E overall remains IN PROGRESS. XN-002 remains OPEN until integration into xn-main, live local credential/tag creation verification, real tag-triggered build/release, exact tag/source verification, APK/EXE evidence, traceability manifest, and release gate review all pass.

## P0-01E Integration Gate
- Reviewed delivery `f22eba4dcbf2eb85dc1741ec4ad696239fc72516` was integrated byte-for-byte through integration commit `698767d7a08cf10cfe5e26d2e2f4d3da7690357a`.
- Main AI independently verified the integration branch was exactly one fast-forward commit from `ff92f085944e3af325adf5f00e66ef54037059b1`, with exactly four added files and identical blob SHAs to the reviewed delivery.
- `xn-main` was advanced with a non-force fast-forward to `698767d7a08cf10cfe5e26d2e2f4d3da7690357a`.
- Coding-agent integration evidence: 74/74 focused tests PASS, actionlint PASS, diff check PASS, worktree clean. No real release tag or GitHub Release was created during integration.
- P0-01E overall remains IN PROGRESS. The next gate is a separately authorized live tag-first release: read-only local-plan, Main-AI approval of the exact current xn-main SHA, then `local-create --expected-sha <approved SHA>`, followed by verification of the resulting tag-triggered build/release, APK/EXE evidence and traceability manifest.
- XN-002 remains OPEN until that live release gate passes.

## P0-01E Live Release Verification — FINAL PASS
- Main AI decision: **P0-01E = PASS / VERIFIED**.
- Authorized release source: `3685852e4ab2e60425aa5883e2fa0b64e963bca3`.
- Release tag: `xn-release-3685852e4ab2e60425aa5883e2fa0b64e963bca3`; Git ref type `commit`; final tag SHA exactly equals the authorized source SHA.
- Live Actions Run `36824489661`: event `push`, head branch exact release tag, head SHA exact authorized source, overall conclusion SUCCESS.
- Required release gates: `prepare-release` SUCCESS, canonical reusable build graph SUCCESS for enabled jobs, `verify-release` SUCCESS. Preparation log emitted `TAG_VERIFIED`; final verification log emitted `RELEASE_TRACEABILITY_VERIFIED`.
- GitHub Release ID `400697717`: published, draft=false, prerelease=true, exact release tag. `target_commitish=master` is retained only as GitHub Release metadata and is not accepted as source identity; the pre-existing Git tag is the authoritative source ref.
- Traceability artifact `xn-release-traceability-36824489661-1` was independently downloaded and inspected. It contains only `XN_RELEASE_TRACEABILITY.json`; manifest source SHA and tag SHA both equal `3685852e4ab2e60425aa5883e2fa0b64e963bca3`, `traceability_verified=true`, release ID matches, and all 7 manifest APK/EXE entries match the real Release assets by ID/name/size/SHA256.
- Verified release assets include 4 signed APKs and 3 EXEs; all are uploaded and non-empty with SHA256 digests recorded by GitHub.
- Release operation did not modify `master`, `xn-main`, `custom-nav-controls`, or `restore/xn-remote-20260914-1909`; no unexpected XN release tag or additional tag-triggered Actions run was observed.
- No force, tag deletion, tag movement, or retag operation was used.
- XN-002 is now eligible for VERIFIED status. The historical broken release/tag remains preserved as evidence; verification is based on the new exact-SHA release path, not rewriting history.

## P0-01F Automated Regression Gate
- Coding-agent automated acceptance preparation: READY_FOR_HUMAN_ACCEPTANCE.
- Current xn-main at automated check: `6123a0c8d15891cfa4ab9c02a3326380ed6f766b`; verified release product source: `3685852e4ab2e60425aa5883e2fa0b64e963bca3`.
- Product/runtime/build code did not change after the verified release source; only governance files changed.
- Release Run `36824489661`, Android build gates, and Windows build gates were re-verified PASS.
- Local acceptance artifacts prepared and hash-verified: universal Android APK SHA256 matched the verified Release asset and package metadata reported `com.carriez.flutter_hbb.custom` / label `XN远控`; Windows x64 EXE SHA256 matched the verified Release asset and PE architecture is x64. Windows Authenticode status is NotSigned and is recorded as evidence, not treated as a blocker by the current release contract.
- P0-01F automated portion = PASS. Human Acceptance remains PENDING and must be completed by the user on real Android and Windows devices.
