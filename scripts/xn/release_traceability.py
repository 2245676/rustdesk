"""Tag-first XN releases: local ref creation and strictly read-only Actions gates."""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from urllib import error, request


REPOSITORY = "2245676/rustdesk"
PRODUCT_REF = "refs/heads/xn-main"
TRACKING_REF = "refs/remotes/origin/xn-main"
SHA = re.compile(r"[0-9a-f]{40}")
NUMBER = re.compile(r"[1-9][0-9]{0,19}")
MANIFEST = Path("XN_RELEASE_TRACEABILITY.json")
PREPARATION = Path("XN_RELEASE_PREPARATION.json")
FAILURE = Path("XN_RELEASE_FAILURE.json")


class TraceabilityError(Exception):
    """Fixed error classification; never include transport output or credentials."""


def require(condition, code):
    if not condition:
        raise TraceabilityError(code)


def validate_sha(sha):
    require(isinstance(sha, str) and SHA.fullmatch(sha), "INVALID_SOURCE_SHA")
    return sha


def release_tag(source_sha):
    return "xn-release-" + validate_sha(source_sha)


def validate_origin(urls):
    allowed = {
        "https://github.com/2245676/rustdesk", "https://github.com/2245676/rustdesk.git",
        "git@github.com:2245676/rustdesk", "git@github.com:2245676/rustdesk.git",
        "ssh://git@github.com/2245676/rustdesk", "ssh://git@github.com/2245676/rustdesk.git",
    }
    require(len(urls) == 1 and urls[0] in allowed, "WRONG_ORIGIN_REPOSITORY")


class LocalGit:
    """No source/ref/remote overrides. Only the local controller can call push."""

    def __init__(self, cwd=None):
        require(os.environ.get("GITHUB_ACTIONS") != "true", "LOCAL_CONTROLLER_FORBIDDEN_IN_ACTIONS")
        self.cwd = Path.cwd() if cwd is None else Path(cwd)

    def _git(self, *args, code="LOCAL_GIT_FAILED"):
        # Suppress inherited tracing/config injection; capture all Git diagnostics.
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        command = ["git", "-c", f"core.hooksPath={os.devnull}",
                   "-c", "core.fsmonitor=false", "-c", "credential.interactive=false",
                   "-c", "http.followRedirects=false", "-c", "push.followTags=false",
                   "-c", "remote.origin.mirror=false", *args]
        try:
            result = subprocess.run(command, cwd=self.cwd, env=env, capture_output=True,
                                    text=True, encoding="utf-8", errors="replace", timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            raise TraceabilityError(code) from None
        require(result.returncode == 0, code)
        return result.stdout.strip()

    def check_origin(self):
        # get-url expands insteadOf/pushInsteadOf; validate every actual destination.
        validate_origin(self._git("remote", "get-url", "--all", "origin").splitlines())
        validate_origin(self._git("remote", "get-url", "--push", "--all", "origin").splitlines())

    def remote_sha(self, ref):
        rows = self._git("ls-remote", "--refs", "origin", ref).splitlines()
        require(len(rows) <= 1, "AMBIGUOUS_REMOTE_REF")
        if not rows:
            return None
        fields = rows[0].split()
        require(len(fields) == 2 and fields[1] == ref, "REMOTE_REF_MISMATCH")
        return validate_sha(fields[0])

    def lock_source(self):
        self.check_origin()
        # Fetch only the product ref, with no tag writes, implicit refmaps or FETCH_HEAD.
        self._git("fetch", "--no-tags", "--no-write-fetch-head", "--refmap=",
                  "--recurse-submodules=no", "origin",
                  f"{PRODUCT_REF}:{TRACKING_REF}", code="SOURCE_FETCH_FAILED")
        source_sha = validate_sha(self._git("rev-parse", "--verify", TRACKING_REF))
        require(self._git("cat-file", "-t", source_sha) == "commit", "SOURCE_NOT_COMMIT")
        require(self.remote_sha(PRODUCT_REF) == source_sha, "SOURCE_BRANCH_MOVED")
        return source_sha

    def push_release_tag(self, source_sha):
        validate_sha(source_sha)
        self.check_origin()
        require(self._git("rev-parse", "--verify", TRACKING_REF) == source_sha
                and self.remote_sha(PRODUCT_REF) == source_sha, "SOURCE_BRANCH_MOVED")
        refspec = f"{source_sha}:refs/tags/{release_tag(source_sha)}"
        output = self._git("push", "--porcelain", "--no-follow-tags", "--recurse-submodules=no",
                           "origin", refspec, code="TAG_PUSH_FAILED")
        updates = [row.split("\t") for row in output.splitlines() if "\t" in row]
        require(len(updates) == 1 and updates[0][:2] == ["*", refspec], "TAG_PUSH_RACE")


def local_release(mode, git):
    require(mode in ("local-plan", "local-create"), "INVALID_LOCAL_MODE")
    source_sha = git.lock_source()
    tag = release_tag(source_sha)
    tag_ref = f"refs/tags/{tag}"
    current = git.remote_sha(tag_ref)
    result = {"schema_version": 1, "repository": REPOSITORY, "source_ref": PRODUCT_REF,
              "source_sha": source_sha, "release_tag": tag, "tag_sha": current}
    if current is not None:
        require(current == source_sha, "TAG_SOURCE_MISMATCH")
        return dict(result, status="ALREADY_VERIFIED")
    if mode == "local-plan":
        return dict(result, status="READY_TO_CREATE")
    # An ordinary one-ref push cannot overwrite a tag created by a competing writer.
    git.push_release_tag(source_sha)
    require(git.remote_sha(tag_ref) == source_sha, "POST_CREATE_TAG_MISMATCH")
    return dict(result, tag_sha=source_sha, status="CREATED_AND_VERIFIED")


@dataclass(frozen=True)
class Context:
    repository: str
    event: str
    source_ref: str
    ref_type: str
    ref_name: str
    source_sha: str
    run_id: str
    run_attempt: str

    @classmethod
    def from_env(cls, env):
        return cls(*(env.get(key, "") for key in (
            "GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_REF_TYPE",
            "GITHUB_REF_NAME", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
        )))

    def validate(self):
        require(self.repository == REPOSITORY, "WRONG_REPOSITORY")
        require(self.event == "push", "WRONG_EVENT")
        require(self.ref_type == "tag", "WRONG_REF_TYPE")
        validate_sha(self.source_sha)
        require(self.ref_name == self.tag and self.source_ref == f"refs/tags/{self.tag}",
                "TAG_IDENTITY_MISMATCH")
        require(isinstance(self.run_id, str) and NUMBER.fullmatch(self.run_id), "INVALID_RUN_ID")
        require(isinstance(self.run_attempt, str) and NUMBER.fullmatch(self.run_attempt),
                "INVALID_RUN_ATTEMPT")

    @property
    def tag(self):
        return release_tag(self.source_sha)

    def identity(self):
        self.validate()
        return {"schema_version": 1, "repository": self.repository, "event": self.event,
                "run_id": self.run_id, "run_attempt": self.run_attempt,
                "source_ref": self.source_ref, "source_sha": self.source_sha,
                "release_tag": self.tag}


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ActionsGitHub:
    """GET-only API. No mutation method or dependency on LocalGit."""

    def __init__(self, context, token):
        context.validate()
        require(bool(token) and "\n" not in token and "\r" not in token, "TOKEN_REQUIRED")
        self.context = context
        self._token = token
        self._opener = request.build_opener(NoRedirect())

    def _get(self, path, missing_ok=False):
        req = request.Request(f"https://api.github.com/repos/{REPOSITORY}/{path}", method="GET",
                              headers={"Authorization": f"Bearer {self._token}",
                                       "Accept": "application/vnd.github+json",
                                       "X-GitHub-Api-Version": "2022-11-28",
                                       "User-Agent": "xn-release-traceability"})
        try:
            with self._opener.open(req, timeout=30) as response:
                return json.load(response)
        except error.HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            raise TraceabilityError(f"GITHUB_HTTP_{exc.code}") from None
        except (error.URLError, TimeoutError, OSError, ValueError, HTTPException):
            raise TraceabilityError("GITHUB_REQUEST_FAILED") from None

    def get_run(self):
        return self._get(f"actions/runs/{self.context.run_id}")

    def get_tag(self):
        return self._get(f"git/ref/tags/{self.context.tag}", missing_ok=True)

    def get_product_head(self):
        return self._get("git/ref/heads/xn-main")

    def compare_product(self, product_sha):
        validate_sha(product_sha)
        return self._get(f"compare/{self.context.source_sha}...{product_sha}")

    def get_release(self):
        return self._get(f"releases/tags/{self.context.tag}", missing_ok=True)

    def get_assets(self, release_id):
        require(type(release_id) is int and release_id > 0, "INVALID_RELEASE_ID")
        assets = []
        for page in range(1, 101):
            batch = self._get(f"releases/{release_id}/assets?per_page=100&page={page}")
            require(isinstance(batch, list), "INVALID_RELEASE_ASSETS")
            assets.extend(batch)
            if len(batch) < 100:
                return assets
        raise TraceabilityError("ASSET_PAGINATION_LIMIT")


def verify_tag(context, tag, mismatch="TAG_SOURCE_MISMATCH"):
    context.validate()
    require(isinstance(tag, dict), "TAG_MISSING")
    require(tag.get("ref") == context.source_ref, "TAG_REF_MISMATCH")
    target = tag.get("object", {})
    require(isinstance(target, dict) and target.get("type") == "commit", "TAG_NOT_LIGHTWEIGHT")
    require(target.get("sha") == context.source_sha, mismatch)
    return target["sha"]


def verify_run(context, api):
    run = api.get_run()
    require(isinstance(run, dict) and run.get("id") == int(context.run_id)
            and run.get("head_sha") == context.source_sha and run.get("head_branch") == context.tag
            and run.get("event") == "push" and run.get("run_attempt") == int(context.run_attempt)
            and run.get("path") == ".github/workflows/xn-release.yml"
            and run.get("repository", {}).get("full_name") == REPOSITORY,
            "BUILD_RUN_SOURCE_MISMATCH")


def verify_membership(context, api):
    head = api.get_product_head()
    require(isinstance(head, dict) and head.get("ref") == PRODUCT_REF
            and head.get("object", {}).get("type") == "commit", "INVALID_PRODUCT_REF")
    product_sha = validate_sha(head["object"].get("sha"))
    if product_sha != context.source_sha:
        comparison = api.compare_product(product_sha)
        require(isinstance(comparison, dict) and comparison.get("status") == "ahead"
                and comparison.get("behind_by") == 0
                and comparison.get("base_commit", {}).get("sha") == context.source_sha
                and comparison.get("merge_base_commit", {}).get("sha") == context.source_sha,
                "SOURCE_NOT_IN_XN_MAIN")
    return product_sha


def prepare(context, api):
    context.validate()
    verify_tag(context, api.get_tag())
    verify_run(context, api)
    product_sha = verify_membership(context, api)
    tag_sha = verify_tag(context, api.get_tag())
    return dict(context.identity(), status="TAG_VERIFIED", tag_sha=tag_sha,
                xn_main_sha=product_sha, traceability_verified=True)


def asset_evidence(assets):
    require(isinstance(assets, list), "INVALID_RELEASE_ASSETS")
    selected = []
    for asset in assets:
        require(isinstance(asset, dict), "INVALID_RELEASE_ASSETS")
        name = asset.get("name", "")
        if (isinstance(name, str) and re.fullmatch(r"rustdesk-[A-Za-z0-9._-]+\.(apk|exe)", name)
                and asset.get("state") == "uploaded"
                and type(asset.get("size")) is int and asset["size"] > 0
                and type(asset.get("id")) is int and asset["id"] > 0):
            selected.append({key: asset.get(key) for key in ("id", "name", "size", "digest")})
    require(any(a["name"].endswith(".apk") for a in selected), "APK_ASSET_MISSING")
    require(any(a["name"].endswith(".exe") for a in selected), "EXE_ASSET_MISSING")
    return selected


def verify_release(context, api, build_result):
    context.validate()
    require(build_result == "success", "BUILD_FAILED")
    verify_run(context, api)
    verify_tag(context, api.get_tag(), "POST_BUILD_TAG_MISMATCH")
    product_sha = verify_membership(context, api)
    release = api.get_release()
    require(isinstance(release, dict), "RELEASE_MISSING")
    require(release.get("tag_name") == context.tag, "RELEASE_TAG_MISMATCH")
    require(release.get("draft") is False, "RELEASE_NOT_PUBLISHED")
    assets = asset_evidence(api.get_assets(release.get("id")))
    tag_sha = verify_tag(context, api.get_tag(), "POST_BUILD_TAG_MISMATCH")
    return dict(context.identity(), tag_sha=tag_sha, traceability_verified=True,
                xn_main_sha=product_sha, release_id=release["id"], assets=assets)


def validate_manifest(manifest, context, expected):
    require(isinstance(manifest, dict)
            and json.dumps(manifest, sort_keys=True) == json.dumps(expected, sort_keys=True),
            "MANIFEST_MISMATCH")
    require(all(manifest.get(key) == value for key, value in context.identity().items())
            and manifest.get("tag_sha") == context.source_sha
            and manifest.get("traceability_verified") is True, "MANIFEST_MISMATCH")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def actions_main(mode):
    evidence = {"schema_version": 1, "status": "NOT_VERIFIED", "traceability_verified": False}
    try:
        if mode == "verify":
            MANIFEST.unlink(missing_ok=True)
            FAILURE.unlink(missing_ok=True)
        context = Context.from_env(os.environ)
        context.validate()
        evidence.update(context.identity())
        api = ActionsGitHub(context, os.environ.get("GH_TOKEN", ""))
        if mode == "prepare":
            output = os.environ.get("GITHUB_OUTPUT")
            require(bool(output), "GITHUB_OUTPUT_REQUIRED")
            evidence = prepare(context, api)
            write_json(PREPARATION, evidence)
            with open(output, "a", encoding="utf-8") as stream:
                stream.write("tag_verified=true\n")
        else:
            manifest = verify_release(context, api, os.environ.get("BUILD_RESULT", ""))
            validate_manifest(manifest, context, manifest)
            write_json(MANIFEST, manifest)
            validate_manifest(json.loads(MANIFEST.read_text(encoding="utf-8")), context, manifest)
        print("TAG_VERIFIED" if mode == "prepare" else "RELEASE_TRACEABILITY_VERIFIED")
        return 0
    except TraceabilityError as exc:
        code = str(exc)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        code = "INVALID_RESPONSE_OR_LOCAL_IO"
    evidence.update(status=code, traceability_verified=False)
    if mode == "verify":
        try:
            MANIFEST.unlink(missing_ok=True)
        except OSError:
            print("MANIFEST_CLEANUP_FAILED", file=sys.stderr)
    try:
        write_json(PREPARATION if mode == "prepare" else FAILURE, evidence)
    except OSError:
        print("EVIDENCE_WRITE_FAILED", file=sys.stderr)
    print(code, file=sys.stderr)
    return 1


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args in (["prepare"], ["verify"]):
        return actions_main(args[0])
    if args not in (["local-plan"], ["local-create"]):
        print("USAGE: release_traceability.py local-plan|local-create|prepare|verify", file=sys.stderr)
        return 1
    try:
        print(json.dumps(local_release(args[0], LocalGit()), sort_keys=True))
        return 0
    except TraceabilityError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError):
        print("LOCAL_CONTROLLER_FAILED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
