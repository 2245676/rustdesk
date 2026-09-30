"""Exercise real Git objects and refs in disposable repositories only."""

from dataclasses import replace
import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/xn/sync_upstream.py"
SPEC = importlib.util.spec_from_file_location("sync_upstream", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)
CONTEXT = sync.Context(sync.REPOSITORY, sync.SCHEDULER_REF, "workflow_dispatch", "a" * 40, "123", "1")


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xn-sync-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.builder = self.root / "builder"
        self.upstream = self.root / "upstream.git"
        self.target = self.root / "target.git"
        self.git(self.root, "init", "--initial-branch=master", str(self.builder))
        self.base = self.commit("base")
        self.middle = self.commit("middle")
        self.tip = self.commit("tip", workflow=True)
        for repo in (self.upstream, self.target):
            self.git(self.root, "init", "--bare", str(repo))
            self.git(repo, "fetch", "--no-tags", str(self.builder), "refs/heads/master")
        self.set_ref(self.upstream, sync.SOURCE_REF, self.tip)
        for ref in ("refs/heads/master", "refs/heads/xn-main", "refs/heads/custom-nav-controls",
                    "refs/heads/restore/snapshot", "refs/heads/ci/c3-gate-validation", "refs/tags/preserved"):
            self.set_ref(self.target, ref, self.base)
        self.initial = self.refs(self.target)

    def git(self, directory, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
        command = ["git", "-c", "user.name=Isolated Test", "-c", "user.email=test@example.invalid",
                   "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
                   "-C", str(directory), *args]
        result = subprocess.run(command, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def commit(self, value, workflow=False):
        (self.builder / "data.txt").write_text(value, encoding="utf-8")
        if workflow:
            path = self.builder / ".github/workflows/official.yml"
            path.parent.mkdir(parents=True)
            path.write_text("name: official\non: workflow_dispatch\njobs: {}\n", encoding="utf-8")
        self.git(self.builder, "add", "data.txt", *( [".github/workflows/official.yml"] if workflow else []))
        self.git(self.builder, "commit", "-m", value)
        return self.git(self.builder, "rev-parse", "HEAD")

    def set_ref(self, repo, ref, sha):
        self.git(repo, "update-ref", ref, sha)

    def refs(self, repo):
        output = self.git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
        return dict(row.split() for row in output.splitlines())

    def run_sync(self, mode="apply", **kwargs):
        return sync.run_sync(mode, CONTEXT, _test_remotes=(self.upstream, self.target), **kwargs)

    def assert_result(self, report, result):
        self.assertEqual(report["result"], result, report)
        self.assertEqual(report["protected_refs_unchanged"], True, report)
        self.assertEqual(sync.protected(self.refs(self.target)), self.initial)

    def test_first_creation_preserves_every_other_ref_and_official_workflow(self):
        report = self.run_sync()
        self.assert_result(report, "CREATED")
        self.assertIsNone(report["tracking_before"])
        self.assertEqual(report["tracking_after"], self.tip)
        self.assertEqual(self.refs(self.target)[sync.TARGET_REF], self.tip)
        original = self.git(self.upstream, "show", f"{self.tip}:.github/workflows/official.yml")
        actual = self.git(self.target, "show", f"{sync.TARGET_REF}:.github/workflows/official.yml")
        self.assertEqual(actual, original)
        self.assertEqual(report["xn_main_observed_sha"], self.base)

    def test_no_change_does_not_push(self):
        self.set_ref(self.target, sync.TARGET_REF, self.tip)
        with patch.object(sync, "push_tracking", side_effect=AssertionError("Unexpected write")):
            self.assert_result(self.run_sync(), "NO_CHANGE")

    def test_fast_forward_uses_exact_upstream_commit(self):
        self.set_ref(self.target, sync.TARGET_REF, self.base)
        report = self.run_sync()
        self.assert_result(report, "UPDATED")
        self.assertEqual(report["tracking_before"], self.base)
        self.assertEqual(self.refs(self.target)[sync.TARGET_REF], self.tip)

    def test_upstream_rollback_stops(self):
        self.set_ref(self.target, sync.TARGET_REF, self.tip)
        self.set_ref(self.upstream, sync.SOURCE_REF, self.base)
        before = self.refs(self.target)
        self.assert_result(self.run_sync(), "UPSTREAM_DIVERGED")
        self.assertEqual(self.refs(self.target), before)

    def test_custom_tracking_commit_stops(self):
        self.git(self.builder, "checkout", "-b", "custom", self.base)
        custom = self.commit("custom XN change")
        self.git(self.target, "fetch", str(self.builder), "refs/heads/custom")
        self.set_ref(self.target, sync.TARGET_REF, custom)
        before = self.refs(self.target)
        self.assert_result(self.run_sync(), "UPSTREAM_DIVERGED")
        self.assertEqual(self.refs(self.target), before)

    def test_plan_create_and_fast_forward_never_write_either_remote(self):
        with patch.object(sync, "push_tracking", side_effect=AssertionError("Plan wrote")):
            for tracking, expected in ((None, "PLAN_CREATE"), (self.base, "PLAN_FAST_FORWARD"),
                                       (self.tip, "NO_CHANGE")):
                if tracking:
                    self.set_ref(self.target, sync.TARGET_REF, tracking)
                before = (self.refs(self.upstream), self.refs(self.target))
                self.assert_result(self.run_sync("plan"), expected)
                self.assertEqual((self.refs(self.upstream), self.refs(self.target)), before)

    def test_source_target_and_ref_overrides_rejected_before_git(self):
        with patch.object(sync.Git, "run", side_effect=AssertionError("Must reject before Git")):
            for field, value in (("source_url", "https://evil.invalid/repo.git"),
                                 ("target_url", sync.SOURCE_URL), ("source_ref", "refs/heads/xn-main"),
                                 ("target_ref", "refs/heads/master")):
                report = self.run_sync(config=replace(sync.Config(), **{field: value}))
                self.assertEqual(report["result"], "CONFIG_REJECTED")

    def test_wrong_repository_branch_event_and_mode_rejected(self):
        for field, value in (("repository", "other/fork"), ("ref", "refs/heads/xn-main"),
                             ("event", "push"), ("workflow_sha", "invalid")):
            report = sync.run_sync("apply", replace(CONTEXT, **{field: value}))
            self.assertEqual(report["result"], "CONTEXT_REJECTED")
        self.assertEqual(self.run_sync("invalid")["result"], "MODE_REJECTED")
        self.assertEqual(self.refs(self.target), self.initial)

    def test_tracking_changes_before_precheck(self):
        self.set_ref(self.target, sync.TARGET_REF, self.base)
        owner = self

        class RacingGit(sync.Git):
            reads = 0

            def refs(self, remote):
                self.reads += 1
                if self.reads == 2:
                    owner.set_ref(owner.target, sync.TARGET_REF, owner.middle)
                return super().refs(remote)

        self.assert_result(self.run_sync(_git_class=RacingGit), "TRACKING_CHANGED")
        self.assertEqual(self.refs(self.target)[sync.TARGET_REF], self.middle)

    def test_tracking_changes_after_precheck_before_push_advertisement(self):
        # Advancing to another ancestor would ordinarily still allow a FF push.
        # The trusted pre-push hook must reject this unexpected old SHA.
        for initial in (None, self.base):
            with self.subTest(initial=initial):
                if initial is None:
                    self.git(self.target, "update-ref", "-d", sync.TARGET_REF)
                else:
                    self.set_ref(self.target, sync.TARGET_REF, initial)
                owner = self

                class RacingGit(sync.Git):
                    def run(self, *args, **kwargs):
                        if args[0] == "push":
                            owner.set_ref(owner.target, sync.TARGET_REF, owner.middle)
                        return super().run(*args, **kwargs)

                report = self.run_sync(_git_class=RacingGit)
                self.assert_result(report, "TRACKING_CHANGED")
                self.assertEqual(self.refs(self.target)[sync.TARGET_REF], self.middle)

    def test_fetch_failure_is_not_success(self):
        self.git(self.upstream, "update-ref", "-d", sync.SOURCE_REF)
        report = self.run_sync()
        self.assertEqual(report["result"], "FETCH_FAILED", report)
        self.assertNotIn(report["result"], sync.SUCCESS)
        self.assertEqual(self.refs(self.target), self.initial)

    def test_permission_rejection_keeps_history_and_redacts_errors(self):
        token = "test-secret-token"
        hooks = self.root / "server-hooks"
        hooks.mkdir()
        hook = hooks / "pre-receive"
        hook.write_text(f'#!/bin/sh\necho "refusing to allow workflow permission: {token}" >&2\nexit 1\n',
                        encoding="utf-8")
        hook.chmod(0o700)
        self.git(self.target, "config", "core.hooksPath", str(hooks))
        report = self.run_sync(token=token)
        self.assert_result(report, "AUTH_CAPABILITY_BLOCKED")
        self.assertIsNone(report["tracking_after"])
        self.assertNotIn(token, json.dumps(report))
        self.assertIn("[REDACTED]", report["error"])

    def test_post_push_mismatch_is_not_success(self):
        owner = self

        class MismatchGit(sync.Git):
            reads = 0

            def refs(self, remote):
                self.reads += 1
                if self.reads == 3:
                    owner.set_ref(owner.target, sync.TARGET_REF, owner.middle)
                return super().refs(remote)

        report = self.run_sync(_git_class=MismatchGit)
        self.assert_result(report, "POST_PUSH_MISMATCH")
        self.assertEqual(report["tracking_after"], self.middle)

    def test_upstream_sha_stays_locked_when_source_advances(self):
        self.set_ref(self.upstream, sync.SOURCE_REF, self.middle)
        owner = self

        class MovingSourceGit(sync.Git):
            def refs(self, remote):
                owner.set_ref(owner.upstream, sync.SOURCE_REF, owner.tip)
                return super().refs(remote)

        report = self.run_sync(_git_class=MovingSourceGit)
        self.assert_result(report, "CREATED")
        self.assertEqual(report["upstream_sha"], self.middle)
        self.assertEqual(self.refs(self.target)[sync.TARGET_REF], self.middle)

    def test_protected_ref_concurrency_stops_write(self):
        owner = self

        class ChangedProtectedGit(sync.Git):
            reads = 0

            def refs(self, remote):
                self.reads += 1
                if self.reads == 2:
                    owner.set_ref(owner.target, "refs/heads/master", owner.middle)
                return super().refs(remote)

        report = self.run_sync(_git_class=ChangedProtectedGit)
        self.assertEqual(report["result"], "PROTECTED_REFS_CHANGED", report)
        self.assertFalse(report["protected_refs_unchanged"])
        self.assertNotIn(sync.TARGET_REF, self.refs(self.target))

    def test_token_scoped_to_target_push_environment_only(self):
        captured = []
        token = "secret-credential"

        def fake_run(command, **kwargs):
            captured.append((command, kwargs["env"]))
            return subprocess.CompletedProcess(command, 0, stdout="")

        with patch.object(sync.subprocess, "run", side_effect=fake_run), patch.dict(os.environ, {
                "XN_GITHUB_TOKEN": token, "GITHUB_TOKEN": token, "GIT_TRACE_CURL": "1",
                "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraheader",
                "GIT_CONFIG_VALUE_0": "unsafe"}):
            git = sync.Git(self.root, local_testing=False, token=token)
            git.run("fetch", sync.SOURCE_URL, sync.SOURCE_REF)
            git.run("push", sync.TARGET_URL, f"{self.tip}:{sync.TARGET_REF}", authenticated=True)
        self.assertNotIn("GIT_CONFIG_COUNT", captured[0][1])
        self.assertEqual(captured[1][1]["GIT_CONFIG_KEY_0"], f"http.{sync.TARGET_URL}.extraheader")
        for command, env in captured:
            self.assertNotIn(token, " ".join(command))
            self.assertNotIn("GIT_TRACE_CURL", env)
            self.assertNotIn("XN_GITHUB_TOKEN", env)
            self.assertNotIn("GITHUB_TOKEN", env)
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        self.assertNotIn(encoded, sync.redact(encoded, token))

    def test_shallow_and_non_commit_history_rejected(self):
        git = sync.Git(self.upstream, local_testing=True, token=None)
        blob = self.git(self.upstream, "rev-parse", f"{self.tip}:data.txt")
        with self.assertRaises(sync.SyncError) as raised:
            git.verify_history(blob)
        self.assertEqual(raised.exception.classification, "OBJECT_INVALID")
        (self.upstream / "shallow").write_text(self.tip + "\n", encoding="utf-8")
        with self.assertRaises(sync.SyncError) as raised:
            git.verify_history(self.tip)
        self.assertEqual(raised.exception.classification, "INCOMPLETE_HISTORY")

    def test_report_and_summary_have_required_observations(self):
        report = self.run_sync("plan")
        output, summary = self.root / "report.json", self.root / "summary.md"
        sync.write_report(report, output, summary)
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)
        self.assertEqual(report["auth_capability_live"], "NOT_VERIFIED")
        for key in ("repository", "workflow_sha", "run_id", "run_attempt", "event", "mode",
                    "upstream_repository", "upstream_sha", "tracking_before", "tracking_after",
                    "xn_main_observed_sha", "result", "error_classification", "protected_refs_unchanged"):
            self.assertIn(key, report)
            self.assertIn(key, summary.read_text(encoding="utf-8"))

    def test_cli_missing_mode_defaults_plan_and_invalid_mode_cannot_apply(self):
        with patch.object(sys, "argv", [str(SCRIPT), "--report", str(self.root / "cli.json")]), \
                patch.object(sync, "run_sync", return_value=self.run_sync("plan")) as run, \
                patch.object(sync, "write_report"), patch("builtins.print"):
            self.assertEqual(sync.main(), 0)
            self.assertEqual(run.call_args.args[0], "plan")
        with patch.object(sys, "argv", [str(SCRIPT), "--mode", "invalid"]), \
                patch.object(sync, "run_sync", side_effect=AssertionError("Invalid mode executed")), \
                patch.object(sys, "stderr"):
            with self.assertRaises(SystemExit) as raised:
                sync.main()
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
