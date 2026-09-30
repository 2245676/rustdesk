# XN exact-SHA release preparation (P0-01E)

Status: implementation for independent review, not an approved release or deployment.
Only `.github/workflows/xn-release.yml`, `scripts/xn/release_traceability.py`,
`tests/xn/test_release_traceability.py`, and this document are delivery scope.
No product code or existing workflow is changed.

## Evidence audit — 2026-10-01 (Asia/Tokyo)

Fresh fetch baseline:

| Remote ref | Commit |
| --- | --- |
| origin/xn-main | `8a53b64c54672b9a7ad344c4b5ee00384d0741f4` |
| origin/master | `ab68b929ba9a6f84df4c490038a0cc6542338dcc` |

The committed governance on xn-main (AGENTS, PROJECT_STATE, ARCHITECTURE,
SYSTEM_INVARIANTS, KNOWN_ISSUES, AI_DEVELOPMENT_RULES, TESTING_AND_RELEASE_GATES,
ADR-002) establishes artifact traceability and reserves deployment, release,
independent review and human acceptance to Main AI/reviewer/human. XN-002 remains
open; this preparation does not change governance status.

Read-only GitHub REST observations:

| Evidence | Observed value |
| --- | --- |
| [Build run 33714217274](https://github.com/2245676/rustdesk/actions/runs/33714217274) | push; custom-nav-controls; success; source `d0d435e41b8da376b0fc4ee503f8129e55508c76` |
| Run workflow path | `.github/workflows/build-custom-apk.yml` |
| [Git ref](https://api.github.com/repos/2245676/rustdesk/git/ref/tags/custom-33714217274) | lightweight tag; commit `3f207e91f6061b637f704f94074ee487b030625f` |
| [Release](https://github.com/2245676/rustdesk/releases/tag/custom-33714217274) | id 381728948; tag custom-33714217274; target_commitish master |
| Release assets | 1.4.9 signed APKs: aarch64, armv7, universal, x86_64 |

The legacy caller at the run's exact SHA passed `custom-${{ github.run_id }}` and
`android-only: true` to its local reusable build. Source checkout did not specify
a different ref. All active publishing steps passed TAG_NAME but omitted
target_commitish; there was no explicit tag preparation.
The pinned softprops action maps target_commitish only from its optional input,
and supplies that optional value to GitHub's create-release API. With no existing
tag and no explicit target, GitHub creates the tag on the repository default
branch. This explains the observed master tag despite the custom branch build.
The mismatch is replayed offline and must produce `TAG_SOURCE_MISMATCH`, even
when release name or target_commitish misleadingly matches the build SHA.

Primary semantic references:

- [Pinned action source](https://github.com/softprops/action-gh-release/blob/de2c0eb89ae2a093876385947365aca7b0e5f844/src/github.ts), [input parsing](https://github.com/softprops/action-gh-release/blob/de2c0eb89ae2a093876385947365aca7b0e5f844/src/util.ts).
- [Create release API](https://docs.github.com/en/rest/releases/releases#create-a-release): target_commitish selects a missing tag's target; an existing tag controls identity.
- [Reusable workflow context](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations): github context belongs to the caller.
- [Local reusable workflow revision](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows): a local `./.github/workflows/...` call uses the caller's commit.
- [workflow_dispatch event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch): SHA is the selected branch/tag's last commit; ref is that branch/tag. `ref_name` is its short name.
- [Manual registration/dispatch](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow): registration requires the workflow in the default branch; dispatch can select another branch.

`workflow_call` declares the reusable workflow interface; it does not replace the
caller's push/dispatch event, SHA or ref with a new source identity. Consequently,
the XN wrapper's workflow_dispatch on xn-main yields github.sha at the selected
xn-main revision, github.ref `refs/heads/xn-main`, and github.ref_name `xn-main`
through the reusable workflow. Its default checkout checks out that event commit.
The wrapper's own checkouts explicitly pin github.sha.

## Current and legacy publish path inventory

At the audit baseline, current flutter-build has 16 active softprops publishing
steps, all using `${{ env.TAG_NAME }}` derived from inputs.upload-tag:

| Job | Publishing step(s) |
| --- | --- |
| generate-sbom | Publish Release (SBOM) |
| build-for-windows-flutter | Publish Release (EXE/MSI) |
| build-for-windows-sciter | Publish Release (EXE) |
| build-for-macOS | Publish DMG package |
| publish_unsigned | Publish unsigned app |
| build-rustdesk-android | Publish signed apk package; Publish unsigned apk package |
| build-rustdesk-android-universal | Publish signed apk package; Publish unsigned apk package |
| build-rustdesk-linux | Publish debian/rpm package; Publish archlinux package |
| build-rustdesk-linux-drm | Publish debian package |
| build-rustdesk-linux-sciter | Publish debian package |
| build-appimage | Publish appimage package |
| build-flatpak | Publish flatpak package |
| build-rustdesk-web | Publish web (job currently disabled) |

The commented iOS publisher is inactive. Build upload-artifact steps preserve CI
outputs but do not create release tags. UPLOAD_ARTIFACT derives from the caller's
boolean input; TAG_NAME derives from its upload-tag input. Local bridge and
third-party Windows helper reusable calls use the same caller revision and
publish workflow artifacts rather than selecting the XN release tag.

Legacy build-custom-apk publishes automatically on custom-nav-controls push and
manual dispatch; it exists at the historical source, not current xn-main.
Legacy flutter-tag and current flutter-tag pass github.ref_name (push version
tags or manual branch ref); manual branch dispatch is therefore not an XN-safe
release entry point. Current flutter-nightly passes fixed `nightly` on schedule
or dispatch; flutter-ci passes upload-artifact false. Playground uses its own
fixed nightly publishing paths. fdroid publishes a version-text asset under
`fdroid-version`. These existing paths remain outside this wrapper and are not
certified as exact-SHA XN release routes. Main AI must use xn-release for XN
APK/EXE delivery; switching entry points is not a traceability fallback.

## State machine and permissions

1. Reject repository/event/ref outside 2245676/rustdesk, workflow_dispatch,
   refs/heads/xn-main before checkout and again in Python. There are no dispatch
   inputs for source, tag or release options.
2. Derive `source_sha` from GITHUB_SHA and tag `xn-<GITHUB_RUN_ID>`. Validate a
   complete lowercase SHA and positive numeric run/attempt. Confirm the exact
   Git commit through REST; confirm the build run's repository, event, path,
   head branch, head SHA, run id and attempt through REST.
3. prepare-release has contents:write and actions:read. On tag absence, POST
   Git refs with `refs/tags/xn-<run_id>` and exact source_sha. Existing lightweight
   tags must already equal source_sha. Annotated tags are rejected. No ref
   update, force, deletion, branch fallback or alternative tag is available.
4. Re-read remote tag after create/existing check. Only a verified successful
   prepare job emits the build gate outputs. Build needs that job, its success
   and `tag_verified=true`, and passes its tag to the unchanged flutter-build
   with upload-artifact true and secrets inherit. Build contents:write is needed
   for the existing publishers and SBOM job.
5. verify-release runs after build, including build failure/cancellation/skip
   when preparation succeeded. Failure never emits a success manifest. With
   successful build, recheck run source, tag, published release.tag_name and
   paginated release assets; require uploaded nonempty RustDesk APK and EXE.
   Re-read tag last. Release target_commitish is deliberately ignored as source
   truth. Verification has contents:read/actions:read only.
6. Write XN_RELEASE_TRACEABILITY.json, validate identity and round-trip contents,
   then preserve it as an Actions artifact. It contains the required schema/run/
   source/tag fields plus release id and asset ids, names, sizes and API digests
   where available. API digest metadata is not local binary content verification.
   Failure evidence is uploaded separately; any manifest from a failed check or
   failed retry is removed locally to avoid a misleading success artifact.
   Manifest artifact name includes run
   attempt; tag stays stable across retries of the same run/source.

Preparation uses only the default short-lived github.token; it does not read
signing secrets. HTTP URLs are fixed to api.github.com and the fixed repository;
redirects are disabled. Credentials are passed through GH_TOKEN, never CLI
arguments, credential-bearing Git URLs, evidence or error text. Only fixed error
codes are logged. Checkouts disable credential persistence. The build retains
the upstream signing/logging behavior; this preparation does not claim an
independent security approval for unchanged upstream steps.

## Failures, retries and concurrency

Existing wrong tags fail TAG_SOURCE_MISMATCH without writes. If another writer
wins after the absence query, the create fails safely: read the winner for
evidence, then fail this attempt, even if the winner has the same source. Retry
only after investigation; a later preparation can accept that exact source tag.
Creation failures/uncertain HTTP outcomes are not automatically retried. Failure
evidence records creation attempted, acknowledged creation, and a subsequently
observed tag SHA where available; a network failure is not proof of no mutation.

When tag creation is acknowledged but build fails, the final job reports
TAG_CREATED_BUILD_FAILED and retains the tag and preparation evidence. Existing
tags with failed builds report BUILD_FAILED. Manual decisions about retained
tags/partial releases belong to Main AI. No cleanup of remote state is automatic.
Same-run concurrency is serialized without cancel-in-progress. Distinct runs use
different tags. Successful jobs from earlier attempts may have published partial
assets for the same immutable source; asset content still needs live verification.

Precreate solves the observed implicit default-branch selection without changing
flutter-build. External actors with repository write access can still delete or
rewrite tags while the upstream publisher runs; no multi-job REST workflow can
make remote state atomic against them. Pre/post checks reject observed changes;
do not interpret a final failure as proof that no partial assets were uploaded.
Tag protection/immutable releases are separate repository-setting decisions,
not silently applied here. Tags must be treated as immutable during release.

## Deployment procedure — Main AI only, NOT executed in PREP

1. Obtain independent source/security review and Main AI acceptance of the exact
   delivery commit. Check committed governance and outstanding release gates.
2. Deploy the reviewed four-file implementation to xn-main through the approved
   integration process. Re-run offline tests and static workflow validation at
   the resulting product SHA; do not deploy the entire xn-main tree to master.
3. Install the **identical bytes** of xn-release.yml as the registration copy on
   default branch master via a separate reviewed change. It remains the full
   wrapper with the same gates; dispatch on master fails before checkout. Its
   local reusable reference must remain valid in the registration branch. The
   script is needed in xn-main execution context; registration-only master does
   not need a runnable source script because its branch is rejected first.
4. Read both committed workflow blobs and compare SHA-256/bytes. Record master
   registration commit, xn-main execution commit, delivery commit and matching
   workflow hash in deployment evidence. Every later wrapper edit must update
   both copies in the same approved deployment window and repeat this comparison.
   There is no auto-sync, merge or mutation of master in this preparation.
5. Confirm the registered workflow is available. Only after release authorization,
   dispatch xn-release.yml explicitly with ref xn-main, with no inputs. This is
   a real release build, not a safe PREP test; do not dispatch delivery/master/
   legacy refs as a substitute. Manual dispatch alone does not grant production
   acceptance. Observe exact run SHA, preparation tag, all build jobs, manifest,
   tag ref and APK/EXE content/digests before Main AI makes a release decision.

Until both branch copies are deployed and reviewed, the delivery-branch file is
an implementation artifact, not an operationally registered XN workflow. No
live build, real tag, real release, APK/EXE upload or deployment was used to test
this preparation. Actual token write capability and real-device acceptance remain
unverified; there is no claim that XN-002 or Phase 0 is formally closed.

## Offline validation and rollback

Run from repository root with Python 3.10+ and Git available:

```text
python -B -m unittest discover -s tests/xn -p test_release_traceability.py -v
actionlint -shellcheck= -pyflakes= .github/workflows/xn-release.yml
git diff --check
```

Tests use an in-memory remote state machine and mocked HTTP transport, covering
context rejection, exact creation, idempotency, conflicts, races, uncertain writes,
post-build tag changes, asset presence, manifest mismatches, token-safe diagnostics,
failed retry evidence and workflow graph gates. They never create GitHub refs or
releases. actionlint validates YAML, expressions and the local reusable interface;
it does not prove live Actions/token/signing capability or inspect binary content.

Rollback is a Main AI-reviewed revert/removal of the new wrapper/script/tests/docs
in the deployed branches, with registration/execution bytes checked afterward.
Stop dispatching new XN releases during rollback; preserve existing tags, assets,
manifests and run evidence. Do not restore the legacy publisher as a safe fallback
or repoint/delete tags. If a real release fails traceability, quarantine its use
and have Main AI decide asset/release handling from captured evidence.

Regression surface: four added files only; no existing file or runtime path is
modified. The new wrapper selects the existing full reusable build rather than
the old Android-only caller, so authorized live execution includes Windows and
the reusable workflow's other enabled targets. Platform builds and human tests
were not run in PREP.
