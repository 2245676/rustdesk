# XN远控 — Architecture

## 1. System Positioning
XN远控 is a customized fork of RustDesk. RustDesk remains the upstream transport, session, platform, and remote-desktop foundation. XN custom code currently focuses on mobile-control UX, Android branding, selected desktop connection-manager behavior, and CI/release automation.

## 2. Major Areas
### Upstream Core
- Rust core remote-desktop/session stack.
- Flutter application shell and shared UI.
- Platform integrations for Android / Windows / Linux / macOS / iOS / Web.
- Existing RustDesk build system and workflows.

### XN Custom Layer
- `flutter/lib/mobile/widgets/custom_shortcuts.dart`
  - custom shortcut data model
  - local persistence
  - shortcut execution
  - shortcut settings UI
- `flutter/lib/mobile/pages/remote_page.dart`
  - XN toolbar integration
  - shortcut rendering
  - keyboard / toolbar visibility behavior
  - one-row / two-row layout integration
- `flutter/lib/main.dart`
  - custom connection-manager startup/minimize behavior
- `flutter/lib/models/server_model.dart`
  - restore/show decision for authorized vs. unauthorized sessions
- Android branding/package changes
- GitHub Actions custom build / upstream sync automation

## 3. Control Flow
### Mobile shortcut execution
Settings UI -> `CustomShortcutStore` -> local RustDesk option storage -> toolbar -> `runCustomShortcut()` -> RustDesk input/session channel -> remote peer.

### Incoming desktop session window behavior
RustDesk server/session model -> connection authorization state -> XN show/minimize decision -> connection-manager window.

## 4. Persistence
XN shortcut configuration currently uses RustDesk local option storage through `bind.mainGetLocalOption` / `bind.mainSetLocalOption`.

## 5. Configuration
- Android package/application branding is configured in Gradle / AndroidManifest.
- CI behavior is configured under `.github/workflows/`.
- Signing secrets are external repository secrets and must never be committed.

## 6. Dependency Direction
Allowed:
- XN mobile UI -> existing RustDesk Flutter models / bridge APIs.
- XN persistence wrapper -> existing RustDesk local option binding.
- XN CI wrapper -> existing RustDesk reusable build workflow.

Forbidden without architecture review:
- Replacing RustDesk transport/session architecture inside a feature task.
- Creating a second remote-input stack beside RustDesk input APIs.
- Creating a second local configuration store for the same XN shortcut data.
- Duplicating authorization/session truth in XN UI state.
- Introducing a separate release mechanism that cannot map artifact -> commit SHA.

## 7. Architectural Invariants
See `SYSTEM_INVARIANTS.md`.

## 8. Upstream Boundary
RustDesk upstream changes must be treated as external architectural movement. XN customizations should remain isolated, reviewable, and replayable where practical. Large direct rewrites of upstream modules are discouraged unless accepted via ADR.

## 9. Known Architecture Risks
- Custom branch drift from upstream increases merge/rebase conflict risk.
- XN logic is currently embedded in upstream Flutter files rather than fully isolated behind extension seams.
- CI currently verifies Android custom artifacts but not all modified platform behavior.
- Custom UI text bypasses upstream i18n.

## 10. SSOT
- Current state: `PROJECT_STATE.md`
- Architecture: `ARCHITECTURE.md`
- Invariants: `SYSTEM_INVARIANTS.md`
- Decisions: `docs/adr/`
- Known issues: `KNOWN_ISSUES.md`
- AI execution rules: `AI_DEVELOPMENT_RULES.md`
- Test/release policy: `TESTING_AND_RELEASE_GATES.md`
