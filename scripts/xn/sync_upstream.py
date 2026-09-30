"""Observe an official candidate; optionally advance a metadata-only tracking ref."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


REPOSITORY = "2245676/rustdesk"
SOURCE_URL = "https://github.com/rustdesk/rustdesk.git"
SOURCE_REF = "refs/heads/master"
TARGET_URL = "https://github.com/2245676/rustdesk.git"
TARGET_REF = "refs/heads/upstream-tracking"
SCHEDULER_REF = "refs/heads/master"
PRODUCT_REF = "refs/heads/xn-main"
METADATA_FILE = "UPSTREAM_TRACKING.json"
BOT_NAME = "XN Upstream Tracker"
BOT_EMAIL = "xn-upstream-tracker@users.noreply.github.com"
METADATA_KEYS = {"schema_version", "upstream_repository", "upstream_ref", "upstream_sha",
                 "previous_upstream_sha", "scheduler_repository", "workflow_sha",
                 "run_id", "run_attempt", "event"}
SHA = re.compile(r"[0-9a-f]{40}\Z")
SUCCESS = {"PLAN_CREATE", "PLAN_FAST_FORWARD", "NO_CHANGE", "CREATED", "UPDATED"}


class SyncError(Exception):
    def __init__(self, classification: str, message: str):
        super().__init__(message)
        self.classification = classification


@dataclass(frozen=True)
class Config:
    source_url: str = SOURCE_URL
    source_ref: str = SOURCE_REF
    target_url: str = TARGET_URL
    target_ref: str = TARGET_REF

    def validate(self) -> None:
        if self != Config():
            raise SyncError("CONFIG_REJECTED", "Only the fixed official source and tracking target are allowed")


@dataclass(frozen=True)
class Context:
    repository: str
    ref: str
    event: str
    workflow_sha: str
    run_id: str
    run_attempt: str

    @classmethod
    def from_environment(cls) -> Context:
        return cls(
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_REF", ""),
            os.environ.get("GITHUB_EVENT_NAME", ""),
            os.environ.get("XN_WORKFLOW_SHA", ""),
            os.environ.get("GITHUB_RUN_ID", ""),
            os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        )

    def validate(self) -> None:
        if (self.repository != REPOSITORY or self.ref != SCHEDULER_REF
                or self.event not in {"schedule", "workflow_dispatch"}
                or not SHA.fullmatch(self.workflow_sha)
                or not self.run_id.isdecimal() or not self.run_attempt.isdecimal()):
            raise SyncError("CONTEXT_REJECTED", "Expected the target repository, master and an allowed Actions event")


def redact(message: str, token: str | None) -> str:
    if token:
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        for secret in (token, encoded):
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://[REDACTED]@", message)
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", message)[:4000]


class Git:
    def __init__(self, directory: Path, *, local_testing: bool, token: str | None):
        self.directory = directory
        self.local_testing = local_testing
        self.token = token

    def run(self, *args: str, authenticated: bool = False,
            hooks: Path | None = None, extra_env: dict[str, str] | None = None,
            input_text: str | None = None) -> str:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("GIT_")
               and key not in {"XN_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "CUSTOM_REPO_TOKEN"}}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        env.update(extra_env or {})
        if authenticated and self.token and not self.local_testing:
            encoded = base64.b64encode(f"x-access-token:{self.token}".encode()).decode()
            env.update(GIT_CONFIG_COUNT="1",
                       GIT_CONFIG_KEY_0=f"http.{TARGET_URL}.extraheader",
                       GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {encoded}")
        command = ["git", "-c", f"core.hooksPath={hooks or self.directory / 'disabled-hooks'}",
                   "-c", "credential.helper=", "-c", "protocol.allow=never",
                   "-c", "protocol.https.allow=always", "-c", "http.followRedirects=false",
                   "-c", "fetch.recurseSubmodules=false", "-c", "fetch.fsckObjects=true",
                   "-c", "transfer.fsckObjects=true", "-c", "push.followTags=false",
                   "-c", "commit.gpgsign=false"]
        if self.local_testing:
            command += ["-c", "protocol.file.allow=always"]
        command += ["-C", str(self.directory), *args]
        try:
            result = subprocess.run(command, env=env, text=True, encoding="utf-8",
                                    errors="replace", stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=600, check=False, input=input_text)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SyncError("GIT_FAILED", redact(str(error), self.token)) from error
        if result.returncode:
            raise SyncError("GIT_FAILED", redact(result.stdout, self.token))
        return result.stdout.strip()

    def refs(self, remote: str) -> dict[str, str]:
        refs: dict[str, str] = {}
        for line in self.run("ls-remote", "--refs", "--heads", "--tags", remote).splitlines():
            parts = line.split()
            if len(parts) != 2 or not SHA.fullmatch(parts[0]) or parts[1] in refs:
                raise SyncError("REMOTE_INVALID", "Invalid or duplicate advertised ref")
            refs[parts[1]] = parts[0]
        return refs

    def fetch(self, remote: str, refspec: str) -> None:
        try:
            self.run("fetch", "--no-tags", "--no-write-fetch-head", remote, refspec)
        except SyncError as error:
            raise SyncError(classify_failure(str(error), "FETCH_FAILED"), str(error)) from error

    def verify_history(self, *commits: str) -> None:
        if self.run("rev-parse", "--is-shallow-repository") != "false":
            raise SyncError("INCOMPLETE_HISTORY", "Shallow history is not permitted")
        for commit in commits:
            if not SHA.fullmatch(commit) or self.run("cat-file", "-t", commit) != "commit":
                raise SyncError("OBJECT_INVALID", "Expected a full commit object ID")
        self.run("fsck", "--connectivity-only", "--no-dangling", *commits)

    def is_ancestor(self, before: str, after: str) -> bool:
        # merge-base output distinguishes an ancestor from unrelated or rewritten history.
        try:
            return self.run("merge-base", before, after) == before
        except SyncError:
            return False


def classify_failure(message: str, fallback: str) -> str:
    lowered = message.lower()
    if "tracking_race" in lowered or "cannot lock ref" in lowered or "fetch first" in lowered:
        return "TRACKING_CHANGED"
    if any(word in lowered for word in (
            "permission", "denied", "authentication", "refusing to allow", "403", "401",
            "could not read username", "not authorized", "workflow scope")):
        return "AUTH_CAPABILITY_BLOCKED"
    return fallback


def protected(refs: dict[str, str]) -> dict[str, str]:
    return {ref: sha for ref, sha in refs.items() if ref != TARGET_REF}


def verify_push_input(text: str, expected_before: str, expected_metadata: str) -> bool:
    if expected_before != "0" * 40 and not SHA.fullmatch(expected_before):
        return False
    if not SHA.fullmatch(expected_metadata):
        return False
    rows = [row.split() for row in text.splitlines() if row.strip()]
    return (len(rows) == 1 and len(rows[0]) == 4
            and rows[0][1] == expected_metadata and rows[0][2] == TARGET_REF
            and rows[0][3] == expected_before)


def push_tracking(git: Git, target: str, before: str | None, metadata_commit: str) -> None:
    hooks = git.directory.parent / "trusted-hooks"
    hooks.mkdir()
    hook = hooks / "pre-push"
    hook.write_text('#!/bin/sh\nexec "$XN_SYNC_PYTHON" "$XN_SYNC_SCRIPT" --verify-push\n', encoding="utf-8")
    hook.chmod(0o700)
    try:
        git.run("push", "--porcelain", target, f"{metadata_commit}:{TARGET_REF}",
                authenticated=True, hooks=hooks, extra_env={
                    "XN_SYNC_PYTHON": sys.executable,
                    "XN_SYNC_SCRIPT": str(Path(__file__).resolve()),
                    "XN_EXPECTED_TRACKING": before or "0" * 40,
                    "XN_EXPECTED_METADATA": metadata_commit,
                })
    except SyncError as error:
        raise SyncError(classify_failure(str(error), "PUSH_FAILED"), str(error)) from error


def metadata_for(context: Context, upstream: str, previous: str | None) -> dict:
    return {
        "schema_version": 1, "upstream_repository": "rustdesk/rustdesk",
        "upstream_ref": SOURCE_REF, "upstream_sha": upstream,
        "previous_upstream_sha": previous, "scheduler_repository": REPOSITORY,
        "workflow_sha": context.workflow_sha, "run_id": context.run_id,
        "run_attempt": context.run_attempt, "event": context.event,
    }


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate metadata key")
        result[key] = value
    return result


def validate_metadata(value: object) -> dict:
    if (not isinstance(value, dict) or set(value) != METADATA_KEYS
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["upstream_repository"] != "rustdesk/rustdesk"
            or value["upstream_ref"] != SOURCE_REF or value["scheduler_repository"] != REPOSITORY
            or not isinstance(value["upstream_sha"], str) or not SHA.fullmatch(value["upstream_sha"])
            or (value["previous_upstream_sha"] is not None
                and (not isinstance(value["previous_upstream_sha"], str)
                     or not SHA.fullmatch(value["previous_upstream_sha"])))
            or not isinstance(value["workflow_sha"], str) or not SHA.fullmatch(value["workflow_sha"])
            or any(not isinstance(value[key], str) or not re.fullmatch(r"[1-9][0-9]*", value[key])
                   for key in ("run_id", "run_attempt"))
            or value["event"] not in ("schedule", "workflow_dispatch")):
        raise SyncError("TRACKING_METADATA_INVALID", "Unexpected metadata schema, identity or field value")
    return value


def read_metadata(git: Git, commit: str) -> dict:
    tree = git.run("ls-tree", "-z", commit)
    entry = re.fullmatch(r"100644 blob ([0-9a-f]{40})\tUPSTREAM_TRACKING\.json\x00", tree)
    if not entry:
        raise SyncError("TRACKING_METADATA_INVALID", "Tracking tree must contain only the regular metadata file")
    blob = entry[1]
    if int(git.run("cat-file", "-s", blob)) > 16384:
        raise SyncError("TRACKING_METADATA_INVALID", "Metadata exceeds the size limit")
    try:
        value = json.loads(git.run("cat-file", "blob", blob), object_pairs_hook=unique_object)
    except ValueError as error:
        raise SyncError("TRACKING_METADATA_INVALID", "Metadata is not valid unambiguous JSON") from error
    return validate_metadata(value)


def read_tracking(git: Git, target: str, commit: str) -> dict:
    git.fetch(target, commit)
    git.verify_history(commit)
    previous_commit = None
    previous_metadata = None
    # Checking every ancestor prevents a metadata-looking tip from hiding product
    # or workflow trees in its history. Such a history is not a metadata branch.
    for line in git.run("rev-list", "--reverse", "--parents", commit).splitlines():
        row = line.split()
        if (len(row) not in (1, 2) or not all(SHA.fullmatch(sha) for sha in row)
                or row[1:] != ([] if previous_commit is None else [previous_commit])):
            raise SyncError("TRACKING_METADATA_INVALID", "Tracking history must be one root followed by a linear chain")
        metadata = read_metadata(git, row[0])
        if metadata["previous_upstream_sha"] != (previous_metadata["upstream_sha"]
                                                  if previous_metadata else None):
            raise SyncError("TRACKING_METADATA_INVALID", "Metadata does not link to the previous recorded upstream")
        previous_commit, previous_metadata = row[0], metadata
    if previous_commit != commit or previous_metadata is None:
        raise SyncError("TRACKING_METADATA_INVALID", "Missing metadata history")
    return previous_metadata


def create_metadata_commit(git: Git, context: Context, upstream: str,
                           previous: str | None, parent: str | None) -> str:
    metadata = validate_metadata(metadata_for(context, upstream, previous))
    blob = git.run("hash-object", "-w", "--stdin",
                   input_text=json.dumps(metadata, ensure_ascii=True, indent=2) + "\n")
    # NUL framing avoids platform text-pipe newline conversion becoming part
    # of the filename (notably CRLF on Windows).
    tree = git.run("mktree", "-z", input_text=f"100644 blob {blob}\t{METADATA_FILE}\0")
    commit = git.run("commit-tree", "--no-gpg-sign", tree, *(["-p", parent] if parent else []),
                     input_text=f"chore(upstream): track {upstream[:12]}\n", extra_env={
                         "GIT_AUTHOR_NAME": BOT_NAME, "GIT_AUTHOR_EMAIL": BOT_EMAIL,
                         "GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": BOT_EMAIL,
                     })
    git.verify_history(commit)
    if (read_metadata(git, commit) != metadata
            or git.run("rev-list", "--parents", "-n", "1", commit).split()
            != [commit, *([parent] if parent else [])]):
        raise SyncError("TRACKING_METADATA_INVALID", "Generated metadata commit is not the expected root or child")
    return commit


def run_sync(mode: str, context: Context, *, config: Config = Config(),
             token: str | None = None,
             _test_remotes: tuple[Path, Path] | None = None,
             _git_class: type[Git] = Git) -> dict:
    report = {
        "repository": context.repository, "workflow_sha": context.workflow_sha,
        "run_id": context.run_id, "run_attempt": context.run_attempt, "event": context.event,
        "mode": mode, "upstream_repository": "rustdesk/rustdesk", "upstream_sha": None,
        "tracking_commit_before": None, "tracking_commit_after": None,
        "tracked_upstream_before": None, "tracked_upstream_after": None, "xn_main_observed_sha": None,
        "result": "FAILED", "error_classification": None, "error": None,
        "protected_refs_unchanged": None, "candidate_action": None,
        "candidate_label": "候选上游版本", "compare": None,
        "auth_capability_live": "NOT_VERIFIED",
    }
    before_refs: dict[str, str] | None = None
    try:
        config.validate()
        context.validate()
        if mode not in {"plan", "apply"}:
            raise SyncError("MODE_REJECTED", "Mode must be plan or apply")
        source, target = config.source_url, config.target_url
        if _test_remotes is not None:
            if any(not isinstance(path, Path) or not path.is_absolute() or not path.is_dir()
                   for path in _test_remotes):
                raise SyncError("CONFIG_REJECTED", "Test remotes must be existing absolute local paths")
            source, target = map(str, _test_remotes)
        with tempfile.TemporaryDirectory(prefix="xn-upstream-") as directory:
            scratch = Path(directory) / "objects.git"
            scratch.mkdir()
            git = _git_class(scratch, local_testing=_test_remotes is not None, token=token)
            git.run("init", "--bare", ".")
            try:
                git.fetch(source, f"{SOURCE_REF}:refs/xn/source")
                upstream = git.run("rev-parse", "refs/xn/source")
                report["upstream_sha"] = upstream
                git.verify_history(upstream)
                before_refs = git.refs(target)
                before = before_refs.get(TARGET_REF)
                report.update(tracking_commit_before=before, tracking_commit_after=before,
                              xn_main_observed_sha=before_refs.get(PRODUCT_REF))
                previous = read_tracking(git, target, before)["upstream_sha"] if before else None
                report.update(tracked_upstream_before=previous, tracked_upstream_after=previous)
                action = ("CREATE" if before is None else "NO_CHANGE" if previous == upstream
                          else "FAST_FORWARD_CANDIDATE" if git.is_ancestor(previous, upstream) else "DIVERGED")
                report["candidate_action"] = action
                report["compare"] = {
                    "base": report["xn_main_observed_sha"], "head": upstream,
                    "upstream_commit_url": f"https://github.com/rustdesk/rustdesk/commit/{upstream}",
                    "fork_compare_url": (f"https://github.com/{REPOSITORY}/compare/"
                                         f"{report['xn_main_observed_sha']}...{upstream}"
                                         if report["xn_main_observed_sha"] else None),
                }
                if action == "DIVERGED":
                    raise SyncError("UPSTREAM_DIVERGED", "Recorded upstream is not an ancestor of the locked official commit")
                expected_commit = before
                expected_metadata = None
                if mode == "apply" and action != "NO_CHANGE":
                    if _test_remotes is None and not token:
                        raise SyncError("AUTH_CAPABILITY_BLOCKED", "The Actions GITHUB_TOKEN is required for writing")
                    current = git.refs(target)
                    if current.get(TARGET_REF) != before:
                        raise SyncError("TRACKING_CHANGED", "Tracking changed before push")
                    if protected(current) != protected(before_refs):
                        raise SyncError("PROTECTED_REFS_CHANGED", "Protected refs changed before push")
                    expected_metadata = metadata_for(context, upstream, previous)
                    expected_commit = create_metadata_commit(git, context, upstream, previous, before)
                    # The hook also checks the receive-pack advertisement. Ordinary Git
                    # push then uses the server's old-OID comparison for the final race.
                    push_tracking(git, target, before, expected_commit)
                after_refs = git.refs(target)
                report["tracking_commit_after"] = after_refs.get(TARGET_REF)
                report["protected_refs_unchanged"] = protected(before_refs) == protected(after_refs)
                if not report["protected_refs_unchanged"]:
                    raise SyncError("PROTECTED_REFS_CHANGED", "Protected refs changed during this observation")
                if report["tracking_commit_after"] != expected_commit:
                    raise SyncError("POST_PUSH_MISMATCH" if mode == "apply" else "TRACKING_CHANGED",
                                    "Observed tracking SHA does not match the expected result")
                if expected_commit:
                    try:
                        observed_metadata = read_tracking(git, target, expected_commit)
                    except SyncError as error:
                        if mode == "apply" and expected_metadata:
                            raise SyncError("POST_PUSH_MISMATCH", "Remote metadata could not be verified") from error
                        raise
                    report["tracked_upstream_after"] = observed_metadata["upstream_sha"]
                    if expected_metadata and observed_metadata != expected_metadata:
                        raise SyncError("POST_PUSH_MISMATCH", "Remote metadata does not match the locked candidate and previous record")
                    if mode == "plan" and report["tracked_upstream_after"] != previous:
                        raise SyncError("TRACKING_CHANGED", "Recorded upstream changed during plan")
                report["result"] = ("NO_CHANGE" if action == "NO_CHANGE" else "PLAN_FAST_FORWARD"
                                    if mode == "plan" and action == "FAST_FORWARD_CANDIDATE" else f"PLAN_{action}"
                                    if mode == "plan" else "CREATED" if action == "CREATE" else "UPDATED")
                if expected_metadata is not None and _test_remotes is None:
                    report["auth_capability_live"] = "WRITE_VERIFIED"
            except SyncError:
                if before_refs is not None:
                    try:
                        observed = git.refs(target)
                    except SyncError:
                        report.update(tracking_commit_after=None, tracked_upstream_after=None,
                                      protected_refs_unchanged=None)
                    else:
                        report["tracking_commit_after"] = observed.get(TARGET_REF)
                        report["tracked_upstream_after"] = None
                        report["protected_refs_unchanged"] = protected(before_refs) == protected(observed)
                        if report["tracking_commit_after"]:
                            try:
                                report["tracked_upstream_after"] = read_tracking(
                                    git, target, report["tracking_commit_after"])["upstream_sha"]
                            except SyncError:
                                report["tracked_upstream_after"] = None
                raise
    except SyncError as error:
        report.update(result=error.classification, error_classification=error.classification,
                      error=redact(str(error), token))
    return report


def write_report(report: dict, path: Path, summary: Path | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if summary:
        lines = ["### 候选上游版本", "", "此报告不表示产品整合或产品验证通过。", ""]
        for key in ("repository", "workflow_sha", "run_id", "run_attempt", "event", "mode",
                    "upstream_repository", "upstream_sha", "tracking_commit_before", "tracking_commit_after",
                    "tracked_upstream_before", "tracked_upstream_after", "candidate_action", "auth_capability_live",
                    "xn_main_observed_sha", "result", "error_classification", "protected_refs_unchanged"):
            value = html.escape(str(report[key])).replace("`", "&#96;")
            lines.append(f"- {key}: <code>{value}</code>")
        if report["compare"]:
            lines += ["", f"Compare metadata: <code>{html.escape(json.dumps(report['compare']))}</code>"]
        if report["error"]:
            lines += ["", f"Sanitized error: <pre>{html.escape(report['error'])}</pre>"]
        with summary.open("a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")


def main() -> int:
    if sys.argv[1:] == ["--verify-push"]:
        ok = verify_push_input(sys.stdin.read(), os.environ.get("XN_EXPECTED_TRACKING", ""),
                               os.environ.get("XN_EXPECTED_METADATA", ""))
        if not ok:
            print("TRACKING_RACE: advertised tracking changed or unexpected refspec", file=sys.stderr)
        return 0 if ok else 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "apply"), default="plan")
    parser.add_argument("--report", type=Path, default=Path("upstream-sync-report.json"))
    args = parser.parse_args()
    report = run_sync(args.mode, Context.from_environment(), token=os.environ.get("XN_GITHUB_TOKEN"))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    write_report(report, args.report, Path(summary) if summary else None)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["result"] in SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
