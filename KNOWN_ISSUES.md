# XN远控 — Known Issues

| ID | Severity | Blocking | Status | Issue | Found | Plan |
|---|---|---:|---|---|---|---|
| XN-001 | CRITICAL | Yes | OPEN | Upstream sync scheduler is on the default branch. The exact-commit tracking design was blocked by workflow-file permissions; metadata-only tracking v2 is now reviewed and deployed, but real scheduled apply/write verification is still pending. | Governance review 2026-09-14; live activation 2026-10-01 | Observe a real scheduled metadata-v2 apply, verify `upstream-tracking` metadata, default-token write capability, and unchanged protected refs; then close only with evidence. |
| XN-002 | CRITICAL | Yes | VERIFIED | Historical custom Release `custom-33714217274` had a tag/source mismatch. The replacement tag-first XN release path now binds authorization to an exact xn-main SHA and verifies the pre-existing tag before and after build. Live Release Run `36824489661` proved source/tag/manifest identity at `3685852e4ab2e60425aa5883e2fa0b64e963bca3` with 4 APK + 3 EXE assets. | Governance review 2026-09-14; live verification 2026-10-01 | VERIFIED. Preserve historical evidence; future XN releases must use the exact-SHA tag-first route and Gate 10 verification. |
| XN-003 | HIGH | Yes | OPEN | `custom-nav-controls` is materially behind current upstream RustDesk (`199` commits at review time). | Governance review 2026-09-14 | Preserve current state, create a clean upstream-based XN branch, replay custom changes with verification. |
| XN-004 | HIGH | Yes | OPEN | Custom desktop behavior is modified but current custom CI is Android-only. | Governance review 2026-09-14 | Add Windows build verification before release. |
| XN-005 | HIGH | Yes | OPEN | XN custom behavior lacks dedicated regression tests. | Governance review 2026-09-14 | Add focused tests for shortcut persistence/execution and connection-manager behavior where practical. |
| XN-006 | MEDIUM | No | OPEN | XN-only UI strings are hard-coded Chinese and bypass upstream i18n. | Governance review 2026-09-14 | Integrate with RustDesk localization system. |
| XN-007 | MEDIUM | No | OPEN | Macro execution sends steps immediately with no wait/ack semantics; latency-sensitive macros may race. | Governance review 2026-09-14 | Define and test delay/WAIT semantics in a separate task. |
| XN-008 | MEDIUM | No | OPEN | Custom and master branches are unprotected. | Governance review 2026-09-14 | Add branch protection / required checks after CI gates are established. |
| XN-009 | MEDIUM | No | OPEN | Documentation states daily upstream sync works, but runtime evidence contradicts it. | Governance review 2026-09-14 | Correct docs and keep PROJECT_STATE / KNOWN_ISSUES as SSOT until fixed. |

Status meanings: OPEN / DEFERRED / BLOCKED / FIXED / VERIFIED. `FIXED` is not `VERIFIED`.
