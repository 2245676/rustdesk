"""Exact-SHA gates for xn-release.yml; only prepare may create a Git ref."""

import json
import os
import re
import sys
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from urllib import error, request


REPOSITORY = "2245676/rustdesk"
SOURCE_REF = "refs/heads/xn-main"
SHA = re.compile(r"[0-9a-f]{40}")
NUMBER = re.compile(r"[1-9][0-9]{0,19}")
MANIFEST = Path("XN_RELEASE_TRACEABILITY.json")
EVIDENCE = Path("XN_RELEASE_PREPARATION.json")


class TraceabilityError(Exception):
    """A fixed diagnostic code, never a remote response or credential."""


def require(condition, code):
    if not condition:
        raise TraceabilityError(code)


def release_tag(run_id):
    require(isinstance(run_id, str) and NUMBER.fullmatch(run_id), "INVALID_RUN_ID")
    return f"xn-{run_id}"


@dataclass(frozen=True)
class Context:
    repository: str
    event: str
    source_ref: str
    source_sha: str
    run_id: str
    run_attempt: str

    @classmethod
    def from_env(cls, env):
        return cls(*(env.get(key, "") for key in (
            "GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_REF",
            "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
        )))

    def validate(self):
        require(self.repository == REPOSITORY, "WRONG_REPOSITORY")
        require(self.event == "workflow_dispatch", "WRONG_EVENT")
        require(self.source_ref == SOURCE_REF, "WRONG_SOURCE_REF")
        require(isinstance(self.source_sha, str) and SHA.fullmatch(self.source_sha),
                "INVALID_SOURCE_SHA")
        release_tag(self.run_id)
        require(isinstance(self.run_attempt, str) and NUMBER.fullmatch(self.run_attempt),
                "INVALID_RUN_ATTEMPT")

    @property
    def tag(self):
        return release_tag(self.run_id)

    def identity(self):
        self.validate()
        return {
            "schema_version": 1,
            "repository": self.repository,
            "run_id": self.run_id,
            "run_attempt": self.run_attempt,
            "source_ref": self.source_ref,
            "source_sha": self.source_sha,
            "release_tag": self.tag,
        }


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the Authorization header to a redirect destination.
        return None


class GitHub:
    def __init__(self, context, token):
        context.validate()
        require(bool(token) and "\n" not in token and "\r" not in token, "TOKEN_REQUIRED")
        self.context = context
        self._token = token
        self._opener = request.build_opener(NoRedirect())

    def _request(self, path, payload=None, missing_ok=False):
        req = request.Request(
            f"https://api.github.com/repos/{REPOSITORY}/{path}",
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "xn-release-traceability",
            },
            method="GET" if payload is None else "POST",
        )
        try:
            with self._opener.open(req, timeout=30) as response:
                return json.load(response)
        except error.HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            # No response bodies, URLs, exception reprs, or token are logged.
            raise TraceabilityError(f"GITHUB_HTTP_{exc.code}") from None
        except (error.URLError, TimeoutError, OSError, ValueError, HTTPException):
            raise TraceabilityError("GITHUB_REQUEST_FAILED") from None

    def get_commit(self):
        return self._request(f"git/commits/{self.context.source_sha}")

    def get_run(self):
        return self._request(f"actions/runs/{self.context.run_id}")

    def get_tag(self):
        return self._request(f"git/ref/tags/{self.context.tag}", missing_ok=True)

    def create_tag(self):
        # The sole mutation: create, never PATCH, PUT, DELETE, or force/update.
        return self._request("git/refs", {
            "ref": f"refs/tags/{self.context.tag}", "sha": self.context.source_sha,
        })

    def get_release(self):
        return self._request(f"releases/tags/{self.context.tag}", missing_ok=True)

    def get_assets(self, release_id):
        require(type(release_id) is int and release_id > 0, "INVALID_RELEASE_ID")
        assets = []
        for page in range(1, 101):
            batch = self._request(f"releases/{release_id}/assets?per_page=100&page={page}")
            require(isinstance(batch, list), "INVALID_RELEASE_ASSETS")
            assets.extend(batch)
            if len(batch) < 100:
                return assets
        raise TraceabilityError("ASSET_PAGINATION_LIMIT")


def verify_source(context, api):
    context.validate()
    commit = api.get_commit()
    require(isinstance(commit, dict) and commit.get("sha") == context.source_sha,
            "SOURCE_COMMIT_MISMATCH")
    run = api.get_run()
    require(isinstance(run, dict) and run.get("id") == int(context.run_id)
            and run.get("head_sha") == context.source_sha
            and run.get("head_branch") == "xn-main"
            and run.get("event") == context.event
            and run.get("run_attempt") == int(context.run_attempt)
            and run.get("path") == ".github/workflows/xn-release.yml"
            and run.get("repository", {}).get("full_name") == REPOSITORY,
            "BUILD_RUN_SOURCE_MISMATCH")


def verify_tag(context, tag):
    context.validate()
    require(isinstance(tag, dict), "TAG_MISSING")
    require(tag.get("ref") == f"refs/tags/{context.tag}", "TAG_REF_MISMATCH")
    target = tag.get("object", {})
    # XN owns lightweight tags; annotated tags are rejected, never peeled/rewritten.
    require(target.get("type") == "commit", "TAG_NOT_LIGHTWEIGHT")
    require(target.get("sha") == context.source_sha, "TAG_SOURCE_MISMATCH")
    return target["sha"]


def prepare(context, api, evidence):
    evidence.update(context.identity(), status="PREPARING", tag_created=False,
                    tag_creation_attempted=False, traceability_verified=False)
    verify_source(context, api)
    tag = api.get_tag()
    if tag is None:
        evidence["tag_creation_attempted"] = True
        try:
            api.create_tag()
        except TraceabilityError:
            # A competing writer may have won the create. Fail this attempt even
            # for the same SHA; never retry writes or overwrite the winner.
            conflicting_tag = api.get_tag()
            if conflicting_tag is not None:
                evidence["observed_tag_sha"] = conflicting_tag.get("object", {}).get("sha")
                verify_tag(context, conflicting_tag)
            raise TraceabilityError("TAG_CREATE_FAILED") from None
        evidence["tag_created"] = True
    else:
        verify_tag(context, tag)
    tag_sha = verify_tag(context, api.get_tag())
    evidence.update(status="TAG_VERIFIED", tag_sha=tag_sha, traceability_verified=True)
    return evidence


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
    # The canonical reusable workflow builds both platforms. SBOM-only is no release.
    require(any(a["name"].endswith(".apk") for a in selected), "APK_ASSET_MISSING")
    require(any(a["name"].endswith(".exe") for a in selected), "EXE_ASSET_MISSING")
    return selected


def verify_release(context, api, build_result, tag_created):
    context.validate()
    require(build_result == "success",
            "TAG_CREATED_BUILD_FAILED" if tag_created else "BUILD_FAILED")
    verify_source(context, api)
    verify_tag(context, api.get_tag())
    release = api.get_release()
    require(isinstance(release, dict), "RELEASE_MISSING")
    require(release.get("tag_name") == context.tag, "RELEASE_TAG_MISMATCH")
    require(release.get("draft") is False, "RELEASE_NOT_PUBLISHED")
    assets = asset_evidence(api.get_assets(release.get("id")))
    # Read last, after the release/asset queries, to catch a concurrent ref change.
    tag_sha = verify_tag(context, api.get_tag())
    return dict(context.identity(), tag_sha=tag_sha, traceability_verified=True,
                release_id=release["id"], assets=assets)


def validate_manifest(manifest, context, expected):
    require(isinstance(manifest, dict)
            and json.dumps(manifest, sort_keys=True) == json.dumps(expected, sort_keys=True),
            "MANIFEST_MISMATCH")
    require(all(manifest.get(key) == value for key, value in context.identity().items())
            and manifest.get("tag_sha") == context.source_sha
            and manifest.get("traceability_verified") is True, "MANIFEST_MISMATCH")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if args not in (["prepare"], ["verify"]):
        print("USAGE: release_traceability.py prepare|verify", file=sys.stderr)
        return 1
    mode = args[0]
    evidence = {"schema_version": 1, "status": "NOT_VERIFIED",
                "traceability_verified": False, "tag_created": False}
    try:
        if mode == "verify":
            MANIFEST.unlink(missing_ok=True)
        context = Context.from_env(os.environ)
        context.validate()
        evidence.update(context.identity())
        evidence["tag_created"] = os.environ.get("TAG_CREATED") == "true"
        api = GitHub(context, os.environ.get("GH_TOKEN", ""))
        if mode == "prepare":
            output = os.environ.get("GITHUB_OUTPUT")
            require(bool(output), "GITHUB_OUTPUT_REQUIRED")
            prepare(context, api, evidence)
            write_json(EVIDENCE, evidence)
            with open(output, "a", encoding="utf-8") as stream:
                stream.write(f"source_sha={context.source_sha}\nrelease_tag={context.tag}\n"
                             f"tag_created={str(evidence['tag_created']).lower()}\n"
                             "tag_verified=true\n")
        else:
            manifest = verify_release(context, api, os.environ.get("BUILD_RESULT", ""),
                                      os.environ.get("TAG_CREATED") == "true")
            validate_manifest(manifest, context, manifest)
            write_json(MANIFEST, manifest)
            validate_manifest(json.loads(MANIFEST.read_text(encoding="utf-8")),
                              context, manifest)
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
    # Failure evidence is deliberately distinct from the success manifest.
    try:
        write_json(EVIDENCE if mode == "prepare" else Path("XN_RELEASE_FAILURE.json"), evidence)
    except OSError:
        print("EVIDENCE_WRITE_FAILED", file=sys.stderr)
    print(code, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
