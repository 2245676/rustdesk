# XN远控 — System Invariants

These rules cannot be changed by ordinary implementation tasks.

1. **Upstream truth**
   - RustDesk remains the authoritative remote-session / transport / platform foundation unless an ADR explicitly changes this.

2. **Single custom shortcut store**
   - XN shortcut configuration must have one authoritative persistence path. Do not introduce a second store for the same data.

3. **Authorization truth**
   - XN UI must not create its own independent authorization state. Authorization state comes from the existing RustDesk session model.

4. **Unauthorized connection visibility**
   - An unauthorized incoming session must not be silently treated like an authorized unattended session. The local approval/visibility path must remain available.

5. **Artifact traceability**
   - Every released APK/EXE artifact must be traceable to the exact Git commit that produced it.
   - A release tag must not point to a different source commit than the artifact build SHA.

6. **No false PASS**
   - Build success does not imply behavioral verification.
   - Human acceptance is PASS only after an actual human performs the stated acceptance steps.

7. **Upstream integration safety**
   - Upstream updates must not silently overwrite XN behavior. Conflicts or behavior changes require review and verification.

8. **Secrets safety**
   - Signing keys, passwords, tokens, and private credentials must not be committed to the repository.

9. **Bug-fix regression rule**
   - XN behavior bugs should gain automated regression coverage where technically practical. If not practical, the task must define human verification.

10. **Release gate integrity**
   - Required gates in `TESTING_AND_RELEASE_GATES.md` cannot be bypassed by a Coding Agent for schedule convenience.
