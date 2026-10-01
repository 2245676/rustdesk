"""Offline real-bare-Git controller tests and GET-only Actions regressions."""

import ast
import copy
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch
from urllib import error


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("release_traceability", ROOT / "scripts/xn/release_traceability.py")
rt = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = rt
SPEC.loader.exec_module(rt)
SOURCE = "d0d435e41b8da376b0fc4ee503f8129e55508c76"
LEGACY = "3f207e91f6061b637f704f94074ee487b030625f"
TAG = rt.release_tag(SOURCE)
CTX = rt.Context(rt.REPOSITORY, "push", f"refs/tags/{TAG}", "tag", TAG, SOURCE, "33714217274", "1")


def tag(sha=SOURCE, kind="commit", ref=CTX.source_ref):
    return {"ref": ref, "object": {"type": kind, "sha": sha}}


def asset(name, identity=1):
    return {"id": identity, "name": name, "state": "uploaded", "size": 123,
            "digest": "sha256:" + "a" * 64}


class FakeAPI:
    def __init__(self):
        self.tag = tag()
        self.run = {"id": int(CTX.run_id), "head_sha": SOURCE, "head_branch": TAG,
                    "event": "push", "run_attempt": 1, "path": ".github/workflows/xn-release.yml",
                    "repository": {"full_name": rt.REPOSITORY}}
        self.product = tag(ref=rt.PRODUCT_REF)
        self.comparison = {"status": "ahead", "behind_by": 0,
                           "base_commit": {"sha": SOURCE}, "merge_base_commit": {"sha": SOURCE}}
        self.release = {"id": 1, "tag_name": TAG, "draft": False, "target_commitish": "master"}
        self.assets = [asset("rustdesk-1.5.0-aarch64-signed.apk"), asset("rustdesk-1.5.0-x86_64.exe", 2)]
        self.reads = []
        self.on_assets = None

    def get_tag(self):
        self.reads.append("tag")
        return copy.deepcopy(self.tag)

    def get_run(self):
        self.reads.append("run")
        return self.run

    def get_product_head(self):
        self.reads.append("product")
        return self.product

    def compare_product(self, product_sha):
        self.reads.append("compare")
        return self.comparison

    def get_release(self):
        self.reads.append("release")
        return self.release

    def get_assets(self, release_id):
        self.reads.append("assets")
        if self.on_assets:
            self.on_assets(self)
        return self.assets


class ErrorAssertions:
    def assert_code(self, code, callback):
        with self.assertRaises(rt.TraceabilityError) as caught:
            callback()
        self.assertEqual(str(caught.exception), code)


class LocalController(ErrorAssertions, unittest.TestCase):
    """All writes are confined to fresh, disposable local Git repositories."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xn-tag-first-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.author = self.root / "author"
        self.client = self.root / "client"
        self.run_git(self.root, "init", "--bare", str(self.remote))
        self.run_git(self.root, "init", str(self.author))
        self.run_git(self.author, "config", "user.name", "Offline XN test")
        self.run_git(self.author, "config", "user.email", "xn-test@example.invalid")
        self.run_git(self.author, "commit", "--allow-empty", "-m", "root")
        self.ancestor = self.run_git(self.author, "rev-parse", "HEAD")
        self.run_git(self.author, "branch", "-M", "xn-main")
        self.run_git(self.author, "commit", "--allow-empty", "-m", "product")
        self.source = self.run_git(self.author, "rev-parse", "HEAD")
        self.run_git(self.author, "remote", "add", "origin", str(self.remote))
        self.run_git(self.author, "push", "origin", "refs/heads/xn-main:refs/heads/xn-main",
                     f"{self.ancestor}:refs/heads/master", f"{self.ancestor}:refs/tags/keep-me")
        self.run_git(self.remote, "symbolic-ref", "HEAD", "refs/heads/xn-main")
        self.run_git(self.root, "clone", "--no-tags", str(self.remote), str(self.client))
        self.git = rt.LocalGit(self.client)
        self.target = "refs/tags/" + rt.release_tag(self.source)
        # Only identity validation is substituted for a known fixture transport.
        # Fetch/resolve/ls-remote/push/ref checks all execute real Git, without mocks.
        def fixture_origin(urls):
            rt.require(urls == [str(self.remote)], "WRONG_ORIGIN_REPOSITORY")
        self.origin_patch = patch.object(rt, "validate_origin", side_effect=fixture_origin)
        self.origin_patch.start()
        self.addCleanup(self.origin_patch.stop)

    @staticmethod
    def run_git(cwd, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
        if result.returncode != 0:
            raise AssertionError("Fixture Git command failed: " + result.stderr)
        return result.stdout.strip()

    def refs(self, cwd):
        return self.run_git(cwd, "show-ref")

    def update_tag(self, sha):
        self.run_git(self.remote, "update-ref", self.target, sha)

    def cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(rt, "LocalGit", return_value=self.git), redirect_stdout(stdout), redirect_stderr(stderr):
            result = rt.main(args)
        return result, stdout.getvalue(), stderr.getvalue()

    def assert_guard_rejects(self, expected):
        before = self.refs(self.remote)
        with patch.object(self.git, "push_release_tag", side_effect=AssertionError("must not push")):
            result, stdout, stderr = self.cli(["local-create", "--expected-sha", expected])
        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "AUTHORIZED_SOURCE_CHANGED\n")
        self.assertEqual(self.refs(self.remote), before)
        self.assertFalse(any("refs/tags/xn-release-" in row for row in before.splitlines()))

    def test_cli_plan_approval_then_remote_advance_rejected_zero_writes(self):
        result, stdout, stderr = self.cli(["local-plan"])
        self.assertEqual((result, stderr), (0, ""))
        approved = json.loads(stdout)["source_sha"]
        self.assertEqual(approved, self.source)
        self.run_git(self.author, "commit", "--allow-empty", "-m", "unapproved-advance")
        fresh = self.run_git(self.author, "rev-parse", "HEAD")
        self.run_git(self.author, "push", "origin", "refs/heads/xn-main")
        self.assert_guard_rejects(approved)
        self.assertEqual(self.run_git(self.client, "rev-parse", rt.TRACKING_REF), fresh)
        self.assertIsNone(self.git.remote_sha(self.target))
        self.assertIsNone(self.git.remote_sha("refs/tags/" + rt.release_tag(fresh)))

    def test_cli_correct_guard_creates_only_fresh_source_tag(self):
        self.run_git(self.author, "commit", "--allow-empty", "-m", "new-approved-source")
        fresh = self.run_git(self.author, "rev-parse", "HEAD")
        self.run_git(self.author, "push", "origin", "refs/heads/xn-main")
        before = set(self.refs(self.remote).splitlines())
        self.assertEqual(self.run_git(self.client, "rev-parse", rt.TRACKING_REF), self.source)
        with patch.dict(os.environ, {"SOURCE_SHA": self.ancestor, "GITHUB_SHA": self.source}):
            result, stdout, stderr = self.cli(["local-create", "--expected-sha", fresh])
        evidence = json.loads(stdout)
        self.assertEqual((result, stderr), (0, ""))
        self.assertEqual(evidence["source_sha"], fresh)
        self.assertEqual(evidence["release_tag"], "xn-release-" + fresh)
        self.assertEqual(evidence["status"], "CREATED_AND_VERIFIED")
        self.assertEqual(set(self.refs(self.remote).splitlines()) - before,
                         {f"{fresh} refs/tags/xn-release-{fresh}"})
        self.assertTrue(before <= set(self.refs(self.remote).splitlines()))
        self.assertIsNone(self.git.remote_sha(self.target))

    def test_wrong_expected_sha_zero_tag_writes(self):
        self.assert_guard_rejects("a" * 40 if self.source != "a" * 40 else "b" * 40)

    def test_expected_sha_cannot_select_older_commit(self):
        self.assert_guard_rejects(self.ancestor)

    def test_expected_sha_cannot_select_unpushed_local_commit(self):
        self.run_git(self.client, "config", "user.name", "test")
        self.run_git(self.client, "config", "user.email", "test@example.invalid")
        self.run_git(self.client, "commit", "--allow-empty", "-m", "unapproved-local")
        local_only = self.run_git(self.client, "rev-parse", "HEAD")
        self.assert_guard_rejects(local_only)
        self.assertEqual(self.run_git(self.client, "rev-parse", rt.TRACKING_REF), self.source)

    def test_expected_sha_cannot_select_unrelated_remote_commit(self):
        self.run_git(self.author, "checkout", "--orphan", "unrelated")
        self.run_git(self.author, "commit", "--allow-empty", "-m", "unrelated")
        unrelated = self.run_git(self.author, "rev-parse", "HEAD")
        self.run_git(self.author, "push", "origin", "refs/heads/unrelated")
        self.assert_guard_rejects(unrelated)

    def test_guard_checked_even_if_fresh_source_tag_already_exists(self):
        self.update_tag(self.source)
        before = self.refs(self.remote)
        result, stdout, stderr = self.cli(["local-create", "--expected-sha", self.ancestor])
        self.assertEqual((result, stdout, stderr), (1, "", "AUTHORIZED_SOURCE_CHANGED\n"))
        self.assertEqual(self.refs(self.remote), before)

    def test_source_only_from_fresh_origin_not_checkout_or_environment(self):
        self.run_git(self.client, "config", "user.name", "test")
        self.run_git(self.client, "config", "user.email", "test@example.invalid")
        self.run_git(self.client, "commit", "--allow-empty", "-m", "unreleased-local")
        self.run_git(self.author, "commit", "--allow-empty", "-m", "remote-advanced")
        fresh = self.run_git(self.author, "rev-parse", "HEAD")
        self.run_git(self.author, "push", "origin", "refs/heads/xn-main")
        before_head = self.run_git(self.client, "rev-parse", "HEAD")
        with patch.dict(os.environ, {"SOURCE_SHA": LEGACY, "RELEASE_TAG": "evil", "INPUT_SOURCE": LEGACY,
                                     "GITHUB_SHA": LEGACY, "GITHUB_REF": "refs/heads/master"}):
            plan = rt.local_release("local-plan", self.git)
        self.assertEqual(plan["source_sha"], fresh)
        self.assertEqual(plan["release_tag"], "xn-release-" + fresh)
        self.assertEqual(self.run_git(self.client, "rev-parse", "HEAD"), before_head)
        self.assertEqual(self.run_git(self.client, "rev-parse", rt.TRACKING_REF), fresh)

    def test_plan_no_remote_or_local_tag_branch_or_worktree_write(self):
        before_remote, before_local = self.refs(self.remote), self.refs(self.client)
        before_files = sorted(p.name for p in self.client.iterdir())
        result = rt.local_release("local-plan", self.git)
        self.assertEqual(result["status"], "READY_TO_CREATE")
        self.assertEqual(self.refs(self.remote), before_remote)
        self.assertEqual(self.refs(self.client), before_local)
        self.assertEqual(sorted(p.name for p in self.client.iterdir()), before_files)
        self.assertFalse((self.client / ".git/FETCH_HEAD").exists())

    def test_create_exact_commit_only_target_ref_changes(self):
        before = self.refs(self.remote).splitlines()
        before_local = self.refs(self.client)
        result = rt.local_release("local-create", self.git, expected_sha=self.source)
        self.assertEqual(result["status"], "CREATED_AND_VERIFIED")
        self.assertEqual(self.run_git(self.remote, "cat-file", "-t", self.target), "commit")
        self.assertEqual(self.run_git(self.remote, "rev-parse", self.target), self.source)
        after = self.refs(self.remote).splitlines()
        self.assertEqual(set(after) - set(before), {f"{self.source} {self.target}"})
        self.assertEqual(set(before) - set(after), set())
        self.assertEqual(self.refs(self.client), before_local)

    def test_existing_exact_tag_idempotent_no_push(self):
        self.update_tag(self.source)
        before = self.refs(self.remote)
        with patch.object(self.git, "push_release_tag", side_effect=AssertionError("must not push")):
            for mode in ("local-plan", "local-create"):
                self.assertEqual(rt.local_release(mode, self.git, expected_sha=self.source if mode == "local-create" else None)["status"], "ALREADY_VERIFIED")
        self.assertEqual(self.refs(self.remote), before)

    def test_conflicting_tag_never_rewrites(self):
        self.update_tag(self.ancestor)
        before = self.refs(self.remote)
        for mode in ("local-plan", "local-create"):
            self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.local_release(mode, self.git, expected_sha=self.source if mode == "local-create" else None))
        self.assertEqual(self.refs(self.remote), before)

    def test_annotated_tag_rejected_without_peeling_or_rewriting(self):
        name = rt.release_tag(self.source)
        self.run_git(self.author, "tag", "-a", name, self.source, "-m", "annotated")
        self.run_git(self.author, "push", "origin", f"refs/tags/{name}")
        before = self.refs(self.remote)
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertEqual(self.refs(self.remote), before)

    def test_race_different_tag_before_push_fails_and_preserves_winner(self):
        original = self.git.push_release_tag
        def competing_writer(source):
            self.update_tag(self.ancestor)
            original(source)
        with patch.object(self.git, "push_release_tag", side_effect=competing_writer):
            self.assert_code("TAG_PUSH_FAILED", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertEqual(self.run_git(self.remote, "rev-parse", self.target), self.ancestor)

    def test_race_same_source_before_push_fails_this_attempt(self):
        original = self.git.push_release_tag
        def competing_writer(source):
            self.update_tag(source)
            original(source)
        with patch.object(self.git, "push_release_tag", side_effect=competing_writer):
            self.assert_code("TAG_PUSH_RACE", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertEqual(self.run_git(self.remote, "rev-parse", self.target), self.source)

    def test_server_rejection_no_remote_changes(self):
        hook = self.remote / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        before = self.refs(self.remote)
        self.assert_code("TAG_PUSH_FAILED", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertEqual(self.refs(self.remote), before)

    def test_post_create_change_fails_and_does_not_restore(self):
        original = self.git.push_release_tag
        def external_change(source):
            original(source)
            self.update_tag(self.ancestor)
        with patch.object(self.git, "push_release_tag", side_effect=external_change):
            self.assert_code("POST_CREATE_TAG_MISMATCH", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertEqual(self.run_git(self.remote, "rev-parse", self.target), self.ancestor)

    def test_push_does_not_follow_tags_mirror_or_run_local_hooks(self):
        self.run_git(self.client, "config", "user.name", "test")
        self.run_git(self.client, "config", "user.email", "test@example.invalid")
        self.run_git(self.client, "tag", "-a", "do-not-publish", "-m", "extra")
        self.run_git(self.client, "config", "push.followTags", "true")
        self.run_git(self.client, "config", "remote.origin.mirror", "true")
        sentinel = self.root / "local-hook-ran"
        hook = self.client / ".git/hooks/pre-push"
        hook.write_text(f'#!/bin/sh\necho bad > "{sentinel.as_posix()}"\nexit 1\n', encoding="utf-8")
        hook.chmod(0o755)
        before = self.refs(self.remote).splitlines()
        self.assertEqual(rt.local_release("local-create", self.git, expected_sha=self.source)["status"], "CREATED_AND_VERIFIED")
        self.assertFalse(sentinel.exists())
        self.assertEqual(set(self.refs(self.remote).splitlines()) - set(before), {f"{self.source} {self.target}"})
        self.assertTrue((self.client / ".git/refs/tags/do-not-publish").exists())

    def test_remote_branch_changes_after_lock_fail_before_push(self):
        original = self.git.push_release_tag
        def advance(source):
            self.run_git(self.author, "commit", "--allow-empty", "-m", "advance")
            self.run_git(self.author, "push", "origin", "refs/heads/xn-main")
            original(source)
        with patch.object(self.git, "push_release_tag", side_effect=advance):
            self.assert_code("SOURCE_BRANCH_MOVED", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertIsNone(self.git.remote_sha(self.target))

    def test_local_fake_tracking_ref_cannot_select_unpushed_commit(self):
        self.run_git(self.client, "config", "user.name", "test")
        self.run_git(self.client, "config", "user.email", "test@example.invalid")
        self.run_git(self.client, "commit", "--allow-empty", "-m", "local-only")
        local_only = self.run_git(self.client, "rev-parse", "HEAD")
        self.run_git(self.client, "update-ref", rt.TRACKING_REF, local_only)
        self.assert_code("SOURCE_FETCH_FAILED", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertIsNone(self.git.remote_sha("refs/tags/" + rt.release_tag(local_only)))

    def test_fetch_failure_has_no_tag_mutation(self):
        self.run_git(self.remote, "update-ref", "-d", rt.PRODUCT_REF)
        before = self.refs(self.remote)
        self.assert_code("SOURCE_FETCH_FAILED", lambda: rt.local_release("local-create", self.git, expected_sha=self.source))
        self.assertEqual(self.refs(self.remote), before)

    def test_configured_fetch_refmap_cannot_update_other_local_refs(self):
        self.run_git(self.client, "config", "--add", "remote.origin.fetch", "+refs/heads/*:refs/heads/mirror/*")
        before = self.refs(self.client)
        rt.local_release("local-plan", self.git)
        self.assertEqual(self.refs(self.client), before)

    def test_effective_url_rewrite_rejected_before_fetch(self):
        self.run_git(self.client, "remote", "set-url", "origin", "https://github.com/2245676/rustdesk.git")
        self.run_git(self.client, "config", f"url.{self.remote}.insteadOf", "https://github.com/2245676/rustdesk.git")
        self.origin_patch.stop()
        before = self.refs(self.remote)
        self.assert_code("WRONG_ORIGIN_REPOSITORY", self.git.lock_source)
        self.assertEqual(self.refs(self.remote), before)

    def test_real_push_url_to_other_repo_rejected_without_network(self):
        self.run_git(self.client, "remote", "set-url", "origin", "https://github.com/2245676/rustdesk.git")
        self.run_git(self.client, "config", "remote.origin.pushurl", "https://github.com/2245676/other.git")
        self.origin_patch.stop()
        self.assert_code("WRONG_ORIGIN_REPOSITORY", self.git.check_origin)

    def test_membership_head_ancestor_and_unrelated_real_git_history(self):
        self.run_git(self.author, "checkout", "--orphan", "unrelated")
        self.run_git(self.author, "commit", "--allow-empty", "-m", "unrelated")
        unrelated = self.run_git(self.author, "rev-parse", "HEAD")
        self.run_git(self.author, "push", "origin", "refs/heads/unrelated")
        for source, valid in ((self.source, True), (self.ancestor, True), (unrelated, False)):
            context = replace(CTX, source_sha=source, ref_name=rt.release_tag(source),
                              source_ref="refs/tags/" + rt.release_tag(source))
            api = FakeAPI()
            api.product = tag(self.source, ref=rt.PRODUCT_REF)
            base = self.run_git(self.remote, "merge-base", source, self.source) if valid else None
            api.comparison = {"status": "ahead" if valid else "diverged", "behind_by": 0 if valid else 1,
                              "base_commit": {"sha": source}, "merge_base_commit": {"sha": base}}
            if valid:
                self.assertEqual(rt.verify_membership(context, api), self.source)
            else:
                self.assert_code("SOURCE_NOT_IN_XN_MAIN", lambda: rt.verify_membership(context, api))


class OriginSecurity(ErrorAssertions, unittest.TestCase):
    def test_only_fixed_repository_urls_accepted(self):
        for url in ("https://github.com/2245676/rustdesk.git", "git@github.com:2245676/rustdesk.git",
                    "ssh://git@github.com/2245676/rustdesk.git"):
            rt.validate_origin([url])
        for urls in ([], ["https://github.com/2245676/other"], ["https://evil.invalid/2245676/rustdesk.git"],
                     ["https://token@github.com/2245676/rustdesk.git"], ["file:///tmp/rustdesk.git"],
                     ["https://github.com/2245676/rustdesk.git?secret"],
                     ["https://github.com/2245676/rustdesk.git"] * 2):
            self.assert_code("WRONG_ORIGIN_REPOSITORY", lambda: rt.validate_origin(urls))

    def test_push_url_checked_separately(self):
        git = rt.LocalGit()
        with patch.object(git, "_git", side_effect=["https://github.com/2245676/rustdesk.git",
                                                   "https://credential@evil.invalid/repo"]):
            self.assert_code("WRONG_ORIGIN_REPOSITORY", git.check_origin)

    def test_local_controller_rejected_in_actions(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(rt.subprocess, "run") as run, redirect_stderr(output):
            self.assertEqual(rt.main(["local-create", "--expected-sha", SOURCE]), 1)
            run.assert_not_called()
        self.assertEqual(output.getvalue(), "LOCAL_CONTROLLER_FORBIDDEN_IN_ACTIONS\n")

    def test_cli_accepts_no_source_tag_remote_ref_options(self):
        with patch.object(rt.subprocess, "run") as run, redirect_stderr(io.StringIO()):
            for option in ("--sha", "--source", "--ref", "--tag", "--remote", "--force", "--force-with-lease"):
                self.assertEqual(rt.main(["local-create", option, "anything"]), 1)
            run.assert_not_called()

    def test_cli_missing_invalid_expected_sha_and_extra_args_rejected_before_git(self):
        invalid = [[], ["local-create"], ["local-create", SOURCE],
                   ["local-create", "--expected-sha"], ["local-create", "--expected-sha=" + SOURCE],
                   ["local-create", "--expected-sha", SOURCE, "extra"],
                   ["local-create", "--expected-sha", SOURCE, "--expected-sha", SOURCE],
                   ["local-plan", "--expected-sha", SOURCE], ["local-plan", SOURCE]]
        invalid.extend(["local-create", "--expected-sha", sha] for sha in
                       ("", SOURCE.upper(), SOURCE[:8], "g" * 40, SOURCE + "\n", " " + SOURCE))
        with patch.object(rt.subprocess, "run") as run, redirect_stderr(io.StringIO()):
            for args in invalid:
                with self.subTest(args=args):
                    self.assertEqual(rt.main(args), 1)
            run.assert_not_called()

    def test_direct_controller_cannot_bypass_guard_or_override_plan(self):
        git = rt.LocalGit()
        with patch.object(git, "lock_source", side_effect=AssertionError("must not fetch")):
            for expected in (None, "", SOURCE.upper(), SOURCE[:8], "g" * 40):
                self.assert_code("INVALID_EXPECTED_SHA", lambda: rt.local_release("local-create", git, expected_sha=expected))
            self.assert_code("INVALID_LOCAL_ARGUMENT", lambda: rt.local_release("local-plan", git, expected_sha=SOURCE))

    def test_local_git_errors_and_trace_variables_not_exposed(self):
        git = rt.LocalGit()
        result = subprocess.CompletedProcess([], 1, "private-url-secret", "token-header-secret")
        with patch.dict(os.environ, {"GIT_TRACE": "1", "GIT_TRACE_CURL": "1", "GIT_CONFIG_COUNT": "1", "GIT_DIR": "other"}), patch.object(rt.subprocess, "run", return_value=result) as run:
            self.assert_code("LOCAL_GIT_FAILED", lambda: git._git("rev-parse", rt.TRACKING_REF))
        env = run.call_args.kwargs["env"]
        self.assertNotIn("GIT_TRACE", env)
        self.assertNotIn("GIT_TRACE_CURL", env)
        self.assertNotIn("GIT_CONFIG_COUNT", env)
        self.assertNotIn("GIT_DIR", env)
        self.assertFalse(run.call_args.kwargs.get("shell", False))


class ActionsGates(ErrorAssertions, unittest.TestCase):
    def test_valid_tag_push(self):
        result = rt.prepare(CTX, FakeAPI())
        self.assertEqual(result["tag_sha"], SOURCE)
        self.assertTrue(result["traceability_verified"])

    def test_wrong_repository(self):
        self.assert_code("WRONG_REPOSITORY", lambda: replace(CTX, repository="other/repo").validate())

    def test_dispatch_rejected(self):
        self.assert_code("WRONG_EVENT", lambda: replace(CTX, event="workflow_dispatch").validate())

    def test_branch_push_rejected(self):
        self.assert_code("WRONG_REF_TYPE", lambda: replace(CTX, ref_type="branch", source_ref=rt.PRODUCT_REF).validate())

    def test_wrong_tag_and_suffix_sha_mismatch(self):
        for name in ("nightly", "xn-release-" + LEGACY, "xn-release-" + SOURCE[:8], "xn-release-" + SOURCE + "\n"):
            self.assert_code("TAG_IDENTITY_MISMATCH", lambda: replace(CTX, ref_name=name).validate())

    def test_ref_name_and_full_ref_must_agree(self):
        self.assert_code("TAG_IDENTITY_MISMATCH", lambda: replace(CTX, source_ref="refs/heads/" + TAG).validate())

    def test_invalid_sha(self):
        for sha in ("master", SOURCE[:8], SOURCE.upper(), SOURCE + "\n", "g" * 40):
            self.assert_code("INVALID_SOURCE_SHA", lambda: replace(CTX, source_sha=sha).validate())

    def test_deterministic_full_sha_tag_git_valid(self):
        self.assertEqual(TAG, "xn-release-" + SOURCE)
        self.assertEqual(replace(CTX, run_id="1", run_attempt="2").tag, TAG)
        result = subprocess.run(["git", "check-ref-format", CTX.source_ref], capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_invalid_run_and_attempt(self):
        for value in ("0", "01", "1\n", "../x", "1" * 21):
            self.assert_code("INVALID_RUN_ID", lambda: replace(CTX, run_id=value).validate())
            self.assert_code("INVALID_RUN_ATTEMPT", lambda: replace(CTX, run_attempt=value).validate())

    def test_annotated_tag_rejected(self):
        self.assert_code("TAG_NOT_LIGHTWEIGHT", lambda: rt.verify_tag(CTX, tag(kind="tag")))

    def test_tag_ref_mismatch(self):
        self.assert_code("TAG_REF_MISMATCH", lambda: rt.verify_tag(CTX, tag(ref="refs/tags/other")))

    def test_legacy_defect_regression_ignores_misleading_metadata(self):
        api = FakeAPI()
        api.tag = tag(LEGACY)
        api.release.update(target_commitish=SOURCE, name=SOURCE)
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.prepare(CTX, api))

    def test_missing_tag_never_created(self):
        api = FakeAPI()
        api.tag = None
        self.assert_code("TAG_MISSING", lambda: rt.prepare(CTX, api))
        self.assertEqual(api.reads, ["tag"])

    def test_run_source_and_tag_identity(self):
        for key, value in (("head_sha", LEGACY), ("head_branch", "xn-main"), ("event", "workflow_dispatch"),
                           ("id", 1), ("run_attempt", 2), ("repository", {"full_name": "other/repo"}),
                           ("path", "legacy.yml")):
            api = FakeAPI()
            api.run[key] = value
            self.assert_code("BUILD_RUN_SOURCE_MISMATCH", lambda: rt.prepare(CTX, api))

    def test_xn_main_ancestor_passes_after_branch_advances(self):
        api = FakeAPI()
        api.product = tag("b" * 40, ref=rt.PRODUCT_REF)
        self.assertEqual(rt.prepare(CTX, api)["xn_main_sha"], "b" * 40)
        self.assertIn("compare", api.reads)

    def test_nonancestor_or_divergent_comparison_rejected(self):
        for changes in ({"status": "behind"}, {"status": "diverged"}, {"status": "identical"},
                        {"behind_by": 1}, {"base_commit": {"sha": LEGACY}},
                        {"merge_base_commit": {"sha": LEGACY}}):
            api = FakeAPI()
            api.product = tag("b" * 40, ref=rt.PRODUCT_REF)
            api.comparison.update(changes)
            self.assert_code("SOURCE_NOT_IN_XN_MAIN", lambda: rt.prepare(CTX, api))

    def test_prepare_rechecks_remote_tag(self):
        api = FakeAPI()
        with patch.object(api, "get_tag", side_effect=[tag(), tag(LEGACY)]):
            self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.prepare(CTX, api))

    def test_final_tag_changed_or_deleted(self):
        api = FakeAPI()
        api.tag = tag(LEGACY)
        self.assert_code("POST_BUILD_TAG_MISMATCH", lambda: rt.verify_release(CTX, api, "success"))
        api.tag = None
        self.assert_code("TAG_MISSING", lambda: rt.verify_release(CTX, api, "success"))

    def test_final_tag_read_after_asset_queries(self):
        api = FakeAPI()
        rt.verify_release(CTX, api, "success")
        self.assertEqual(api.reads[-2:], ["assets", "tag"])
        api.on_assets = lambda remote: setattr(remote, "tag", tag(LEGACY))
        self.assert_code("POST_BUILD_TAG_MISMATCH", lambda: rt.verify_release(CTX, api, "success"))

    def test_release_target_commitish_ignored(self):
        api = FakeAPI()
        for metadata in ("master", "other", LEGACY):
            api.release["target_commitish"] = metadata
            self.assertTrue(rt.verify_release(CTX, api, "success")["traceability_verified"])

    def test_release_missing_wrong_tag_or_draft(self):
        for release, code in ((None, "RELEASE_MISSING"),
                              ({"tag_name": "nightly", "draft": False}, "RELEASE_TAG_MISMATCH"),
                              ({"tag_name": TAG, "draft": True}, "RELEASE_NOT_PUBLISHED")):
            api = FakeAPI()
            api.release = release
            self.assert_code(code, lambda: rt.verify_release(CTX, api, "success"))

    def test_both_apk_and_exe_required_not_sbom(self):
        api = FakeAPI()
        api.assets = [asset("rustdesk.sbom.json")]
        self.assert_code("APK_ASSET_MISSING", lambda: rt.verify_release(CTX, api, "success"))
        api.assets = [asset("rustdesk-1.5.0.apk")]
        self.assert_code("EXE_ASSET_MISSING", lambda: rt.verify_release(CTX, api, "success"))

    def test_pending_empty_or_unexpected_asset_rejected(self):
        for key, value in (("state", "new"), ("size", 0), ("id", None), ("name", "other.apk")):
            api = FakeAPI()
            api.assets[0][key] = value
            self.assert_code("APK_ASSET_MISSING", lambda: rt.verify_release(CTX, api, "success"))

    def test_manifest_exact_source_tag_and_event(self):
        manifest = rt.verify_release(CTX, FakeAPI(), "success")
        for key in ("schema_version", "repository", "run_id", "run_attempt", "source_ref", "source_sha",
                    "release_tag", "tag_sha", "event", "release_id", "assets", "traceability_verified"):
            self.assertIn(key, manifest)
        self.assertEqual(manifest["source_ref"], "refs/tags/" + TAG)
        self.assertEqual(manifest["source_sha"], manifest["tag_sha"])
        self.assertEqual(manifest["event"], "push")
        rt.validate_manifest(json.loads(json.dumps(manifest)), CTX, manifest)

    def test_manifest_mismatches_rejected(self):
        original = rt.verify_release(CTX, FakeAPI(), "success")
        for key, value in (("source_sha", LEGACY), ("tag_sha", LEGACY), ("source_ref", rt.PRODUCT_REF),
                           ("event", "workflow_dispatch"), ("assets", []), ("schema_version", True),
                           ("traceability_verified", False), ("release_id", 2)):
            self.assert_code("MANIFEST_MISMATCH", lambda: rt.validate_manifest(dict(original, **{key: value}), CTX, original))

    def test_build_failure_retains_tag_and_has_no_mutation_path(self):
        api = FakeAPI()
        for status in ("failure", "cancelled", "skipped", ""):
            self.assert_code("BUILD_FAILED", lambda: rt.verify_release(CTX, api, status))
        self.assertEqual(api.tag, tag())
        self.assertEqual(api.reads, [])


class GetOnlyAdapter(ErrorAssertions, unittest.TestCase):
    def setUp(self):
        self.api = rt.ActionsGitHub(CTX, "never-log-test-token")

    def test_only_get_fixed_host_repo_no_body_or_redirect(self):
        methods = [self.api.get_run, self.api.get_tag, self.api.get_product_head,
                   lambda: self.api.compare_product("b" * 40), self.api.get_release,
                   lambda: self.api.get_assets(1)]
        for method in methods:
            response = io.BytesIO(b"[]" if method == methods[-1] else b"{}")
            with patch.object(self.api._opener, "open", return_value=response) as call:
                method()
            req = call.call_args.args[0]
            self.assertEqual(req.method, "GET")
            self.assertIsNone(req.data)
            self.assertTrue(req.full_url.startswith("https://api.github.com/repos/2245676/rustdesk/"))
            self.assertNotIn("never-log-test-token", req.full_url)
        self.assertIsNone(rt.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid"))

    def test_404_absent_only_on_tag_and_release(self):
        failure = error.HTTPError("never-log-test-token", 404, "secret-body", {}, None)
        with patch.object(self.api._opener, "open", side_effect=failure):
            self.assertIsNone(self.api.get_tag())
            self.assertIsNone(self.api.get_release())
            self.assert_code("GITHUB_HTTP_404", self.api.get_product_head)

    def test_errors_do_not_log_token_headers_url_or_body(self):
        for code in (401, 403, 422, 500):
            failure = error.HTTPError("never-log-test-token", code, "secret-response-body", {}, None)
            with patch.object(self.api._opener, "open", side_effect=failure):
                self.assert_code(f"GITHUB_HTTP_{code}", self.api.get_tag)
        for failure in (error.URLError("never-log-test-token"), IncompleteRead(b"never-log-test-token", 50)):
            with patch.object(self.api._opener, "open", side_effect=failure):
                self.assert_code("GITHUB_REQUEST_FAILED", self.api.get_tag)

    def test_assets_paginate_and_release_id_validated(self):
        page = [asset("rustdesk-1.5.0.apk", n + 1) for n in range(100)]
        with patch.object(self.api, "_get", side_effect=[page, [asset("rustdesk-1.5.0.exe", 101)]]) as call:
            self.assertEqual(len(self.api.get_assets(1)), 101)
        self.assertEqual(call.call_args_list[-1].args[0], "releases/1/assets?per_page=100&page=2")
        with patch.object(self.api, "_get") as call:
            for value in (None, 0, True, "../git/refs"):
                self.assert_code("INVALID_RELEASE_ID", lambda: self.api.get_assets(value))
            call.assert_not_called()


class ActionsCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xn-actions-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        keys = ("GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_REF_TYPE", "GITHUB_REF_NAME",
                "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")
        values = (CTX.repository, CTX.event, CTX.source_ref, CTX.ref_type, CTX.ref_name, SOURCE, CTX.run_id, "1")
        env = dict(zip(keys, values), GH_TOKEN="never-log-test-token", GITHUB_ACTIONS="true",
                   GITHUB_OUTPUT=str(self.root / "outputs"), BUILD_RESULT="success")
        for item in (patch.dict(os.environ, env, clear=True),
                     patch.object(rt, "MANIFEST", self.root / "XN_RELEASE_TRACEABILITY.json"),
                     patch.object(rt, "PREPARATION", self.root / "XN_RELEASE_PREPARATION.json"),
                     patch.object(rt, "FAILURE", self.root / "XN_RELEASE_FAILURE.json")):
            item.start()
            self.addCleanup(item.stop)

    def run_main(self, mode, api):
        output = io.StringIO()
        with patch.object(rt, "ActionsGitHub", return_value=api), patch.object(rt, "LocalGit", side_effect=AssertionError("Actions must not enter local controller")), redirect_stdout(output), redirect_stderr(output):
            code = rt.main([mode])
        self.assertNotIn("never-log-test-token", output.getvalue())
        return code, output.getvalue()

    def test_prepare_success_outputs_tag_verify_only(self):
        self.assertEqual(self.run_main("prepare", FakeAPI())[0], 0)
        self.assertEqual((self.root / "outputs").read_text(), "tag_verified=true\n")
        self.assertEqual(json.loads(rt.PREPARATION.read_text())["source_ref"], CTX.source_ref)

    def test_prepare_failure_no_build_outputs(self):
        api = FakeAPI()
        api.tag = tag(LEGACY)
        code, output = self.run_main("prepare", api)
        self.assertEqual(code, 1)
        self.assertEqual(output, "TAG_SOURCE_MISMATCH\n")
        self.assertFalse((self.root / "outputs").exists())

    def test_failed_retry_removes_success_manifest_preserves_failure(self):
        api = FakeAPI()
        self.assertEqual(self.run_main("verify", api)[0], 0)
        os.environ["BUILD_RESULT"] = "failure"
        code, output = self.run_main("verify", api)
        self.assertEqual(code, 1)
        self.assertEqual(output, "BUILD_FAILED\n")
        self.assertFalse(rt.MANIFEST.exists())
        self.assertEqual(json.loads(rt.FAILURE.read_text())["source_sha"], SOURCE)
        self.assertEqual(api.tag, tag())

    def test_manifest_tamper_fails_and_removes_success_file(self):
        original = rt.write_json
        def tamper(path, value):
            original(path, dict(value, tag_sha=LEGACY) if path == rt.MANIFEST else value)
        with patch.object(rt, "write_json", side_effect=tamper):
            code, output = self.run_main("verify", FakeAPI())
        self.assertEqual((code, output), (1, "MANIFEST_MISMATCH\n"))
        self.assertFalse(rt.MANIFEST.exists())

    def test_successful_retry_removes_stale_failure_evidence(self):
        os.environ["BUILD_RESULT"] = "failure"
        self.assertEqual(self.run_main("verify", FakeAPI())[0], 1)
        os.environ["BUILD_RESULT"] = "success"
        self.assertEqual(self.run_main("verify", FakeAPI())[0], 0)
        self.assertFalse(rt.FAILURE.exists())

    def test_input_environment_does_not_override_actions_identity(self):
        os.environ.update(INPUT_SOURCE=LEGACY, INPUT_TAG="nightly", SOURCE_SHA=LEGACY)
        self.assertEqual(self.run_main("prepare", FakeAPI())[0], 0)
        self.assertEqual(json.loads(rt.PREPARATION.read_text())["source_sha"], SOURCE)


class StaticContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/xn-release.yml").read_text()
        cls.source = (ROOT / "scripts/xn/release_traceability.py").read_text()
        cls.tree = ast.parse(cls.source)
        sections = re.split(r"^  (prepare-release|build|verify-release):\n", cls.workflow, flags=re.M)
        cls.jobs = dict(zip(sections[1::2], sections[2::2]))

    def test_only_tag_push_trigger_no_dispatch_or_branch_push(self):
        trigger = self.workflow.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertEqual(trigger.strip(), "push:\n    tags:\n      - 'xn-release-*'")
        self.assertNotIn("workflow_dispatch", self.workflow)
        self.assertNotIn("branches:", trigger)
        self.assertNotIn("inputs:", self.workflow)

    def test_build_requires_success_and_verification_then_uses_same_tag(self):
        build = self.jobs["build"]
        self.assertIn("needs: prepare-release", build)
        self.assertIn("needs.prepare-release.result == 'success'", build)
        self.assertIn("needs.prepare-release.outputs.tag_verified == 'true'", build)
        self.assertNotIn("always()", build)
        self.assertIn("uses: ./.github/workflows/flutter-build.yml", build)
        self.assertIn("upload-artifact: true", build)
        self.assertIn("upload-tag: ${{ github.ref_name }}", build)
        self.assertIn("secrets: inherit", build)

    def test_prepare_verify_readonly_and_pin_checkout(self):
        for job in ("prepare-release", "verify-release"):
            self.assertIn("contents: read", self.jobs[job])
            self.assertIn("actions: read", self.jobs[job])
            self.assertNotIn("contents: write", self.jobs[job])
            self.assertNotIn("secrets.", self.jobs[job])
        self.assertEqual(self.workflow.count("contents: write"), 1)
        self.assertEqual(self.workflow.count("ref: ${{ github.sha }}"), 2)
        self.assertEqual(self.workflow.count("persist-credentials: false"), 2)
        for forbidden in ("actions: write", "CUSTOM_REPO_TOKEN", "PAT", "workflows:"):
            self.assertNotIn(forbidden, self.workflow)

    def test_final_verify_always_after_build_and_evidence_uploaded(self):
        verify = self.jobs["verify-release"]
        self.assertIn("needs: [prepare-release, build]", verify)
        self.assertIn("always() && needs.prepare-release.result == 'success'", verify)
        self.assertIn("BUILD_RESULT: ${{ needs.build.result }}", verify)
        self.assertIn("XN_RELEASE_TRACEABILITY.json", verify)
        self.assertIn("XN_RELEASE_FAILURE.json", verify)

    def test_actions_call_graph_has_no_local_or_tag_mutation(self):
        nodes = {n.name: n for n in self.tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        pending, seen = ["actions_main", "ActionsGitHub"], set()
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            for node in ast.walk(nodes[name]):
                if isinstance(node, ast.Name) and node.id in nodes:
                    pending.append(node.id)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ("create_tag", "push_release_tag", "_git", "local_release"))
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotIn(node.value, ("POST", "PATCH", "PUT", "DELETE"))
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id, ("subprocess", "LocalGit", "local_release"))
        self.assertNotIn("LocalGit", seen)
        self.assertNotIn("local_release", seen)
        self.assertNotIn("create_tag", self.source)
        self.assertNotIn("git/refs", self.source)
        self.assertNotIn("local-create", self.workflow)

    def test_local_push_single_ref_without_force_or_wildcards(self):
        local = next(n for n in self.tree.body if isinstance(n, ast.ClassDef) and n.name == "LocalGit")
        push = next(n for n in local.body if isinstance(n, ast.FunctionDef) and n.name == "push_release_tag")
        literals = [n.value for n in ast.walk(push) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        for forbidden in ("--force", "--force-with-lease", "--delete", "--mirror", "--all", "--tags", "+"):
            self.assertNotIn(forbidden, literals)


if __name__ == "__main__":
    unittest.main()
