# XN tag-first exact-SHA releases — P0-01E FIX-02

Status: implementation for independent security review. No formal P0-01E PASS,
XN-002 closure, deployment, release approval or production readiness is claimed.
Scope is four added files: this document, xn-release.yml, release_traceability.py
and its focused test file. Product code and existing workflows are unchanged.

## Decision and audit basis

Latest fetched origin/xn-main at preparation start:
`1ea40e605049e75c9684d3ffb379a80f6d02455d`.
Origin/master remains `ab68b929ba9a6f84df4c490038a0cc6542338dcc`.
The committed governance and PROJECT_STATE explicitly record Main AI's
REWORK_REQUIRED decision for old delivery `029d65b1dddbcdc4f112e0552552e59a0e25e372`.
The four tag-first files are carried from reviewed implementation
`0b82df6d2f33e8e3c5012db2c5bebc36d410a698`. FIX-02 closes its authorization
drift gap: a newer product HEAD cannot replace the exact SHA approved by Main AI.

**The old Actions-precreate model was rejected.** The default GITHUB_TOKEN may
not create a tag at a product commit whose workflow history differs from master
because it lacks the required workflow-write capability. No elevated PAT,
workflows permission, custom repository token or App private key is introduced.

New authorization/source flow:

```text
local-plan freshly resolves origin/xn-main as S
  -> Main AI reviews and approves exact SHA S
  -> local-create --expected-sha S freshly resolves origin/xn-main again
  -> require fresh source == S, otherwise AUTHORIZED_SOURCE_CHANGED before tag writes
  -> pre-existing lightweight tag xn-release-<full source SHA>
  -> tag push event
  -> read-only Actions pre-build tag/source/product-history checks
  -> unchanged reusable build and existing-tag release asset publishing
  -> read-only final run/tag/asset/manifest verification
```

**Actions NEVER creates, moves or deletes XN release tags as a controller.**
The Python Actions call graph has only GET transport and no LocalGit dependency.
The wrapper never executes the local controller. Its prepare/verify tokens have
contents:read/actions:read; only the reusable build caller retains contents:write
for existing Release publishers. Missing/conflicting tags fail; there is no
Actions repair, force restore, delete/recreate or alternate-tag fallback.

The historical mismatch remains an explicit regression:
build source `d0d435e41b8da376b0fc4ee503f8129e55508c76` versus tag target
`3f207e91f6061b637f704f94074ee487b030625f` must fail TAG_SOURCE_MISMATCH.
[Historical run](https://github.com/2245676/rustdesk/actions/runs/33714217274),
[tag ref](https://api.github.com/repos/2245676/rustdesk/git/ref/tags/custom-33714217274),
[Release](https://github.com/2245676/rustdesk/releases/tag/custom-33714217274).
Its old Android-only caller supplied a new run-id tag but no explicit target;
the pinned softprops publisher omitted target_commitish, so GitHub's create-release
API selected the default branch for the absent tag. The fix uses an existing tag;
Release target_commitish/name/filename are never accepted as source identity.

## Local controller

Run from the intended trusted fork checkout with Git and Python 3.10+:

```text
python -B scripts/xn/release_traceability.py local-plan
```

There are no --sha/--source/--ref/--tag/--remote options, no version/run-id tag
inputs, and no source/tag environment overrides. The only source is freshly
resolved refs/remotes/origin/xn-main. Current checkout HEAD, local xn-main and
old plan output are not source selectors.
local-plan accepts no arguments. local-create requires exactly
--expected-sha followed by a full lowercase 40-character hex SHA. This is an
authorization guard, never a source selector. Missing, malformed, uppercase,
short or positional SHA inputs and all extra arguments are rejected before Git.

Both the expanded fetch and push destinations of origin must be the one fixed
2245676/rustdesk GitHub repository. Credential-bearing URLs, wrong hosts/repos,
multiple destinations and redirects are rejected. HTTPS and normal GitHub Git
SSH URLs are supported. `git remote get-url` expands URL rewrites before validation.
Git diagnostics are captured and replaced by fixed error classifications; tokens,
headers, API bodies and credential URLs are not printed.

Every plan/create invocation performs a fresh exact-ref fetch:

```text
git fetch --no-tags --no-write-fetch-head --refmap= --recurse-submodules=no origin refs/heads/xn-main:refs/remotes/origin/xn-main
```

Then resolve the tracking ref as a full lowercase 40-character commit, confirm
its Git object type, and compare the live remote product ref with that SHA.
The source must already exist at origin/xn-main: an external upstream commit or
an unpushed local commit is never a release candidate. No source branch is pushed.

Plan stdout is JSON with repository, source ref/SHA, computed tag and current tag
SHA. It reports READY_TO_CREATE for absence or ALREADY_VERIFIED for the same
source. A conflicting raw ref fails TAG_SOURCE_MISMATCH. Annotated tags do not
match the commit object and are never peeled or rewritten.

**Plan has zero remote writes, zero local tag/product-branch/worktree writes and
no evidence-file writes.** The mandatory fetch can update the local object cache
and origin/xn-main tracking ref; this unavoidable Git cache refresh is the only
local write needed to satisfy fresh-source resolution. FETCH_HEAD, tag following,
configured extra refmaps and recursive submodule fetching are disabled.

The future live command is:

```text
python -B scripts/xn/release_traceability.py local-create --expected-sha <approved-full-40-character-SHA>
```

**Do not execute it during PREP.** It is a separately authorized live release
action, because a successful remote tag push immediately triggers the build.
It freshly fetches/re-locks origin/xn-main and compares that source with the exact
approved SHA S. A difference fails AUTHORIZED_SOURCE_CHANGED before any tag lookup
or write, including when the fresh source already has a release tag. An older,
unpushed local or unrelated remote SHA cannot override the fetched source.
After equality succeeds, the tag is derived from the fresh source, and only exact
approved S can receive the tag. If the branch advanced between plan/approval and
create, run a new plan and obtain a new exact-SHA approval before retrying.

After the authorization guard passes, an existing same-source tag returns
ALREADY_VERIFIED without push. A conflicting
tag fails without any remote mutation. On absence, revalidate both origin URLs,
the local tracking ref and remote product HEAD. Movement after the source lock
and before push still fails SOURCE_BRANCH_MOVED. Then perform one ordinary push:

```text
git push --porcelain --no-follow-tags --recurse-submodules=no origin <source_sha>:refs/tags/xn-release-<source_sha>
```

There is no force/lease/plus/delete/mirror/all/wildcard mode. Only a new-tag
porcelain result is accepted. A concurrent same-source winner is a safe
TAG_PUSH_RACE failure for this attempt; a different-source winner is rejected
by Git as TAG_PUSH_FAILED. After acknowledged creation, an exact ls-remote read
must still equal source_sha or POST_CREATE_TAG_MISMATCH fails. No remote cleanup
or rollback is automatic. A push timeout/failure is not proof of no tag creation;
Main AI must inspect remote evidence before considering another attempt.

Git hooks, fsmonitor, interactive credentials, inherited Git tracing/config
environment, redirects, mirror mode and implicit tag following are disabled.
Arguments use subprocess arrays with no shell. Local controller modes reject
GITHUB_ACTIONS=true. The local Git credential capability still requires a
separate live gate; read-only fetch/plan and local fixtures do not prove it.
No credential or repository setting is changed by this implementation.

## Tag-push Actions gates

Trigger is only `push.tags: ['xn-release-*']`. There is no workflow_dispatch,
branch-push trigger, default-branch registration copy or master deployment.
The broad pattern is only event routing; prepare rejects malformed names.

Before checkout and in Python, require repository 2245676/rustdesk, event push,
ref_type tag, full lowercase source SHA, ref_name `xn-release-<source SHA>`, and
ref `refs/tags/xn-release-<source SHA>`. Read the exact tag through GET Git refs;
it must be a lightweight commit ref equal to github.sha. Prepare also verifies
the run's repository, workflow path, id/attempt, push event, head_sha and
head_branch equal to the computed tag name.

Read the current xn-main Git ref through REST. Equal SHA passes directly. For
an older tag, compare `<source SHA>...<current xn-main SHA>`: require ahead,
behind_by zero, and both base commit and merge base equal to source SHA.
This accepts normal product advancement after tag creation and rejects a
master-only/legacy-only/restore-only/unrelated commit outside product ancestry.
A shared ancestor legitimately in xn-main history remains eligible.
Prepare re-reads the tag last and emits tag_verified only on full success.

Build needs successful prepare and its tag_verified output, then calls the
unchanged local flutter-build.yml with upload-artifact true, upload-tag
github.ref_name and secrets inherit. Local reusable workflows come from the
caller commit; their github context/default source checkouts use the tag event
commit. Wrapper checkouts explicitly pin github.sha with credential persistence
off. No checkout of master and no arbitrary ref selection is introduced.

Final verification runs even on build failure/skip/cancellation after successful
preparation and uploads failure evidence. It reports BUILD_FAILED and preserves
the tag/run; it never removes or corrects a release tag. A successful build must
also pass run identity, current product ancestry, existing exact tag, published
Release tag name, and paginated asset checks. Require uploaded nonempty RustDesk
APK **and** EXE; SBOM-only, pending/empty assets, missing Release or wrong tag fail.
The tag is re-read after the asset queries to detect external modification.

Success writes XN_RELEASE_TRACEABILITY.json with schema_version, repository,
run_id, run_attempt, source_ref (the full tag ref), source_sha, release_tag,
tag_sha, event, release_id, assets, traceability_verified=true and the observed
xn-main SHA. Asset evidence includes ids/names/sizes and API digests when present.
Identity and round-trip contents are checked. A failed verification/retry removes
the local success manifest and uploads separate failure evidence; a successful
retry removes stale failure evidence. Manifest artifact names include run/attempt.
API metadata is not a substitute for later downloaded binary/content validation.

Concurrency is serialized per tag without cancelling a previous run. Reruns can
reuse the same immutable tag/source. ALREADY_VERIFIED does not send another tag
push event: Main AI decides whether a failed existing run should be rerun.

## Immutability boundary and unchanged publishers

Existing softprops/action-gh-release steps still receive the pre-existing tag
and create/reuse the Release/upload assets under that tag. They are not a tag
controller; target_commitish does not select source. No upstream publishing steps
are rewritten by this preparation.

An administrator can still delete/rewrite a tag while a build is in progress.
Tag immutability during publication is an operational requirement; pre/post reads
are detection gates, not an atomic lock against administrators. The unchanged
publisher's Release API must never be relied on to create a missing tag. An
externally deleted tag can violate that publishing precondition; final checks
fail on an observed mismatch/missing tag, and Main AI must investigate any partial
assets/Release. No force restore, delete/recreate, fallback or false success is
implemented. Hard cancellation/infrastructure failure may prevent a final job;
retain preparation/run evidence and do not infer release success without final
verification. Repository protection decisions remain outside PREP.

## Deployment and live gate — Main AI only

1. Obtain independent security review and Main AI acceptance of the exact delivery
   commit. Review current governance and release gates; keep XN-002 OPEN until
   actual verified evidence supports closure.
2. Integrate the reviewed four files into xn-main through the authorized process.
   Confirm the resulting product source includes the wrapper/helper and repeat
   focused tests/actionlint. No master registration copy is necessary.
3. Use a trusted local checkout of this fork and run local-plan. Main AI reviews
   the returned source SHA S, review/CI/acceptance gates and local credential policy,
   then explicitly approves that exact full SHA S.
   Do not tag the old pre-integration source, which does not contain the workflow.
4. Invoke local-create --expected-sha S only under that live authorization. The
   controller freshly fetches xn-main and rejects any source != S with
   AUTHORIZED_SOURCE_CHANGED before tag writes. Only approved S may be tagged;
   branch drift requires a new plan and Main AI approval. This task did **not**
   execute it. Preserve stdout/remote tag evidence; confirm the exact source SHA
   and tag-push run before observing build.
5. Validate final run/manifest/tag and actual APK/EXE digests/content/signatures,
   then Main AI decides release status; human device acceptance remains separate.

Real local credential write capability, real GitHub tag push and real release
build/publish remain NOT RUN in PREP. No production deployment or real-device
acceptance was executed. The old delivery branch/worktree and its untracked
P0-01F-PREP-NOTES.md are preserved; this task neither edits nor republishes them.

## Tests and rollback

```text
python -B -m unittest discover -s tests/xn -p test_release_traceability.py -v
actionlint -shellcheck= -pyflakes= .github/workflows/xn-release.yml
git diff --check
```

Controller integration tests use real temporary bare Git repositories for fetch,
SHA resolution, ls-remote, ordinary push, server rejection, competing writers,
post-create changes, and exact ref preservation. Only the fixed GitHub identity
check is substituted for each known fixture transport; no production bypass or
test-mode CLI is shipped. Destination validation is separately exercised with
real Git URL configuration. Actions tests use a GET-only fake/HTTP mock and
real-history ancestry fixtures; AST call-graph checks guard against reintroducing
the old Actions tag-creation path. None of these tests contacts GitHub to write.
The CLI entry-point regression plans S, advances remote xn-main to S2, then calls
local-create --expected-sha S: AUTHORIZED_SOURCE_CHANGED, no release tag, and all
remote refs unchanged by create. Guard tests also cover wrong, older, unpushed
local and unrelated remote SHAs, fresh-source success and existing-tag handling.

Main AI-reviewed rollback removes/reverts the four newly deployed files from
product history and stops new controller executions. Preserve all existing tags,
Releases, assets, manifests and runs. Do not repoint/delete historical tags or
restore the rejected Actions-precreate model as a fallback. Decide failed or
partially published candidate handling from captured evidence.

Regression surface: only four additions; no existing product/runtime path or
existing workflow changed. Future authorized tag execution uses the canonical
full reusable build, including its enabled Android/Windows/other targets. Platform
builds and human tests are NOT RUN here. Existing unrelated legacy/nightly/tag
publishers remain outside this new XN route and are not certified by these gates.
Relative to FIX-01, only local-create input validation and approval comparison
change behavior; local-plan remains fresh and read-only. The wrapper and all
Actions prepare/verify code are unchanged. This is the first substantive fix
iteration; adversarial review covers plan -> approval -> branch drift -> create.

Primary semantics:

- [Push events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push) and [workflow revision selection](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows).
- [Reusable caller context](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations) and [same-revision local workflow calls](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).
- [Compare commits REST API](https://docs.github.com/en/rest/commits/commits#compare-two-commits), [ordinary Git push](https://git-scm.com/docs/git-push), [exact-ref fetch](https://git-scm.com/docs/git-fetch).
- [Release API existing-tag semantics](https://docs.github.com/en/rest/releases/releases#create-a-release), [pinned publisher source](https://github.com/softprops/action-gh-release/blob/de2c0eb89ae2a093876385947365aca7b0e5f844/src/github.ts).
