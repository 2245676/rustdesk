# XN远控 — Known Issues

| ID | Severity | Blocking | Status | Issue | Found | Plan |
|---|---|---:|---|---|---|---|
| XN-001 | CRITICAL | Yes | OPEN | Scheduled upstream sync is not functioning as designed because the workflow exists only on a non-default branch; no scheduled runs were observed. | Governance review 2026-09-14 | Move/enable scheduler from an eligible default-branch workflow and verify an actual scheduled/manual sync path. |
| XN-002 | CRITICAL | Yes | OPEN | Latest custom Release tag points to `master` commit rather than the custom branch build SHA; artifact/source traceability is broken. | Governance review 2026-09-14 | Fix release/tag creation to target exact `${GITHUB_SHA}` / custom commit and verify by inspecting Git tag ref. |
| XN-003 | HIGH | Yes | OPEN | `custom-nav-controls` is materially behind current upstream RustDesk (`199` commits at review time). | Governance review 2026-09-14 | Preserve current state, create a clean upstream-based XN branch, replay custom changes with verification. |
| XN-004 | HIGH | Yes | OPEN | Custom desktop behavior is modified but current custom CI is Android-only. | Governance review 2026-09-14 | Add Windows build verification before release. |
| XN-005 | HIGH | Yes | OPEN | XN custom behavior lacks dedicated regression tests. | Governance review 2026-09-14 | Add focused tests for shortcut persistence/execution and connection-manager behavior where practical. |
| XN-006 | MEDIUM | No | OPEN | XN-only UI strings are hard-coded Chinese and bypass upstream i18n. | Governance review 2026-09-14 | Integrate with RustDesk localization system. |
| XN-007 | MEDIUM | No | OPEN | Macro execution sends steps immediately with no wait/ack semantics; latency-sensitive macros may race. | Governance review 2026-09-14 | Define and test delay/WAIT semantics in a separate task. |
| XN-008 | MEDIUM | No | OPEN | Custom and master branches are unprotected. | Governance review 2026-09-14 | Add branch protection / required checks after CI gates are established. |
| XN-009 | MEDIUM | No | OPEN | Documentation states daily upstream sync works, but runtime evidence contradicts it. | Governance review 2026-09-14 | Correct docs and keep PROJECT_STATE / KNOWN_ISSUES as SSOT until fixed. |

Status meanings: OPEN / DEFERRED / BLOCKED / FIXED / VERIFIED. `FIXED` is not `VERIFIED`.
