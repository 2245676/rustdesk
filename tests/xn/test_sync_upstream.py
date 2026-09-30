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
            self.git(repo, "fetch", "--no-tags", str(self.builder),
                     "refs/heads/master" if repo == self.upstream else self.base)
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
            path = self.builder / ".github/workflows/flutter-build.yml"
            path.parent.mkdir(parents=True)
            path.write_text("name: official\non: workflow_dispatch\njobs: {}\n", encoding="utf-8")
        self.git(self.builder, "add", "data.txt", *([".github/workflows/flutter-build.yml"] if workflow else []))
        self.git(self.builder, "commit", "-m", value)
        return self.git(self.builder, "rev-parse", "HEAD")

    def set_ref(self, repo, ref, sha):
        self.git(repo, "update-ref", ref, sha)

    def refs(self, repo):
        output = self.git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
        return dict(row.split() for row in output.splitlines())

    def run_sync(self, mode="apply", **kwargs):
        return sync.run_sync(mode, CONTEXT, _test_remotes=(self.upstream, self.target), **kwargs)

    def seed(self, upstream, parent=None, previous=None):
        git = sync.Git(self.target, local_testing=True, token=None)
        commit = sync.create_metadata_commit(git, CONTEXT, upstream, previous, parent)
        self.set_ref(self.target, sync.TARGET_REF, commit)
        return commit

    def metadata(self, commit):
        return json.loads(self.git(self.target, "show", f"{commit}:{sync.METADATA_FILE}"))

    def raw_tracking(self, *, changes=None, raw=None, extra=False, mode="100644", parents=()):
        git = sync.Git(self.target, local_testing=True, token=None)
        value = sync.metadata_for(CONTEXT, self.base, None)
        value.update(changes or {})
        blob = git.run("hash-object", "-w", "--stdin", input_text=raw if raw is not None else json.dumps(value))
        entries = f"{mode} blob {blob}\t{sync.METADATA_FILE}\0"
        if extra:
            entries += f"100644 blob {blob}\textra.txt\0"
        tree = git.run("mktree", "-z", input_text=entries)
        parent_args = [argument for parent in parents for argument in ("-p", parent)]
        commit = git.run("commit-tree", "--no-gpg-sign", tree, *parent_args,
                         input_text="test metadata\n", extra_env={
                             "GIT_AUTHOR_NAME": sync.BOT_NAME, "GIT_AUTHOR_EMAIL": sync.BOT_EMAIL,
                             "GIT_COMMITTER_NAME": sync.BOT_NAME, "GIT_COMMITTER_EMAIL": sync.BOT_EMAIL})
        self.set_ref(self.target, sync.TARGET_REF, commit)
        return commit

    def assert_invalid(self):
        before = self.refs(self.target)
        self.assert_result(self.run_sync(), "TRACKING_METADATA_INVALID")
        self.assertEqual(self.refs(self.target), before)

    def assert_result(self, report, result):
        self.assertEqual(report["result"], result, report)
        self.assertEqual(report["protected_refs_unchanged"], True, report)
        self.assertEqual(sync.protected(self.refs(self.target)), self.initial)

    def test_first_creation_is_metadata_root_and_preserves_product_refs(self):
        report = self.run_sync()
        self.assert_result(report, "CREATED")
        self.assertIsNone(report["tracking_commit_before"])
        commit = report["tracking_commit_after"]
        self.assertNotEqual(commit, self.tip)
        self.assertEqual(self.refs(self.target)[sync.TARGET_REF], commit)
        self.assertEqual(self.git(self.target, "rev-list", "--parents", "-n", "1", commit), commit)
        self.assertEqual(self.git(self.target, "ls-tree", "-r", "--name-only", commit), sync.METADATA_FILE)
        self.assertEqual(self.metadata(commit), sync.metadata_for(CONTEXT, self.tip, None))
        self.assertEqual(report["tracked_upstream_after"], self.tip)
        self.assertEqual(report["xn_main_observed_sha"], self.base)

    def test_no_change_does_not_push(self):
        self.seed(self.tip)
        with patch.object(sync, "push_tracking", side_effect=AssertionError("Unexpected write")), \
                patch.object(sync, "create_metadata_commit", side_effect=AssertionError("Unexpected commit")):
            self.assert_result(self.run_sync(), "NO_CHANGE")

    def test_upstream_advance_creates_metadata_child(self):
        previous = self.seed(self.base)
        report = self.run_sync()
        self.assert_result(report, "UPDATED")
        self.assertEqual(report["tracking_commit_before"], previous)
        commit = report["tracking_commit_after"]
        self.assertEqual(self.git(self.target, "rev-list", "--parents", "-n", "1", commit), f"{commit} {previous}")
        self.assertEqual(self.metadata(commit)["previous_upstream_sha"], self.base)
        self.assertEqual(report["candidate_action"], "FAST_FORWARD_CANDIDATE")
        self.assertEqual(report["tracked_upstream_before"], self.base)
        self.assertEqual(report["tracked_upstream_after"], self.tip)

    def test_upstream_rollback_stops(self):
        self.seed(self.tip)
        self.set_ref(self.upstream, sync.SOURCE_REF, self.base)
        before = self.refs(self.target)
        self.assert_result(self.run_sync(), "UPSTREAM_DIVERGED")
        self.assertEqual(self.refs(self.target), before)

    def test_custom_tracking_commit_stops(self):
        self.git(self.builder, "checkout", "-b", "custom", self.base)
        custom = self.commit("custom XN change")
        self.seed(custom)
        before = self.refs(self.target)
        self.assert_result(self.run_sync(), "UPSTREAM_DIVERGED")
        self.assertEqual(self.refs(self.target), before)

    def test_plan_create_and_fast_forward_never_write_either_remote(self):
        with patch.object(sync, "push_tracking", side_effect=AssertionError("Plan wrote")):
            for tracking, expected in ((None, "PLAN_CREATE"), (self.base, "PLAN_FAST_FORWARD"),
                                       (self.tip, "NO_CHANGE")):
                if tracking:
                    self.seed(tracking)
                before = (self.refs(self.upstream), self.refs(self.target))
                with patch.object(sync, "create_metadata_commit", side_effect=AssertionError("Plan created commit")):
                    report = self.run_sync("plan")
                self.assert_result(report, expected)
                self.assertEqual(report["tracking_commit_before"], report["tracking_commit_after"])
                self.assertEqual(report["tracked_upstream_before"], report["tracked_upstream_after"])
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
        self.seed(self.base)
        owner = self

        class RacingGit(sync.Git):
            reads = 0

            def refs(self, remote):
                self.reads += 1
                if self.reads == 2:
                    owner.race_commit = owner.seed(owner.middle)
                return super().refs(remote)

        self.assert_result(self.run_sync(_git_class=RacingGit), "TRACKING_CHANGED")
        self.assertEqual(self.refs(self.target)[sync.TARGET_REF], self.race_commit)

    def test_tracking_changes_after_precheck_before_push_advertisement(self):
        # The hook must check the old metadata SHA for creation and update.
        for initial in (None, self.base):
            with self.subTest(initial=initial):
                if initial is None:
                    self.git(self.target, "update-ref", "-d", sync.TARGET_REF)
                else:
                    self.seed(initial)
                parent = self.refs(self.target).get(sync.TARGET_REF)
                owner = self

                class RacingGit(sync.Git):
                    def run(self, *args, **kwargs):
                        if args[0] == "push":
                            owner.race_commit = owner.seed(owner.middle, parent, initial)
                        return super().run(*args, **kwargs)

                report = self.run_sync(_git_class=RacingGit)
                self.assert_result(report, "TRACKING_CHANGED")
                self.assertEqual(self.refs(self.target)[sync.TARGET_REF], self.race_commit)

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
        self.assertIsNone(report["tracking_commit_after"])
        self.assertNotIn(token, json.dumps(report))
        self.assertIn("[REDACTED]", report["error"])

    def test_post_push_mismatch_is_not_success(self):
        owner = self

        class MismatchGit(sync.Git):
            reads = 0

            def refs(self, remote):
                self.reads += 1
                if self.reads == 3:
                    owner.race_commit = owner.seed(owner.middle)
                return super().refs(remote)

        report = self.run_sync(_git_class=MismatchGit)
        self.assert_result(report, "POST_PUSH_MISMATCH")
        self.assertEqual(report["tracking_commit_after"], self.race_commit)

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
        self.assertEqual(self.metadata(report["tracking_commit_after"])["upstream_sha"], self.middle)

    def test_protected_ref_concurrency_stops_write(self):
        owner = self

        class ChangedProtectedGit(sync.Git):
            reads = 0

            def refs(self, remote):
                self.reads += 1
                if self.reads == 2:
                    owner.set_ref(owner.target, "refs/heads/extra", owner.base)
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
                    "upstream_repository", "upstream_sha", "tracking_commit_before", "tracking_commit_after",
                    "tracked_upstream_before", "tracked_upstream_after",
                    "xn_main_observed_sha", "result", "error_classification", "protected_refs_unchanged"):
            self.assertIn(key, report)
            self.assertIn(key, summary.read_text(encoding="utf-8"))

    def test_cli_missing_mode_defaults_plan_and_invalid_mode_cannot_apply(self):
        with patch.object(sys, "argv", [str(SCRIPT), "--report", str(self.root / "cli.json")]), \
                patch.object(sync, "run_sync", return_value=self.run_sync("plan")) as run, \
                patch.object(sync, "write_report"), patch("builtins.print"):
            self.assertEqual(sync.main(), 0)
            self.assertEqual(run.call_args.args[0], "plan")
        for args in (("--mode", "invalid"), ("--remote", "https://evil.invalid"), ("--ref", "refs/heads/master")):
            with patch.object(sys, "argv", [str(SCRIPT), *args]), \
                    patch.object(sync, "run_sync", side_effect=AssertionError("Invalid CLI executed")), \
                    patch.object(sys, "stderr"):
                with self.assertRaises(SystemExit) as raised:
                    sync.main()
                self.assertEqual(raised.exception.code, 2)

    def test_metadata_bot_identity_message_and_no_signature(self):
        commit = self.run_sync()["tracking_commit_after"]
        identity = self.git(self.target, "show", "-s", "--format=%an <%ae>|%cn <%ce>|%s", commit)
        expected = f"{sync.BOT_NAME} <{sync.BOT_EMAIL}>"
        self.assertEqual(identity, f"{expected}|{expected}|chore(upstream): track {self.tip[:12]}")
        self.assertNotIn("gpgsig ", self.git(self.target, "cat-file", "commit", commit))

    def test_multiple_updates_keep_linear_metadata_only_history(self):
        root = self.seed(self.base)
        self.set_ref(self.upstream, sync.SOURCE_REF, self.middle)
        middle = self.run_sync()["tracking_commit_after"]
        self.set_ref(self.upstream, sync.SOURCE_REF, self.tip)
        report = self.run_sync()
        self.assert_result(report, "UPDATED")
        tip = report["tracking_commit_after"]
        self.assertEqual(self.git(self.target, "rev-list", "--reverse", tip).splitlines(), [root, middle, tip])
        self.assertEqual(self.metadata(tip)["previous_upstream_sha"], self.middle)
        for commit in (root, middle, tip):
            self.assertEqual(self.git(self.target, "ls-tree", "-r", "--name-only", commit), sync.METADATA_FILE)

    def test_missing_recorded_official_commit_stops(self):
        self.seed("f" * 40)
        self.assert_result(self.run_sync(), "UPSTREAM_DIVERGED")

    def test_malformed_json_rejected(self):
        self.raw_tracking(raw="{ malformed")
        self.assert_invalid()

    def test_duplicate_json_keys_rejected(self):
        value = json.dumps(sync.metadata_for(CONTEXT, self.base, None))
        self.raw_tracking(raw=value[:-1] + ', "schema_version": 1}')
        self.assert_invalid()

    def test_wrong_schema_and_json_types_rejected(self):
        for value in (2, True, "1"):
            with self.subTest(value=value):
                self.raw_tracking(changes={"schema_version": value})
                self.assert_invalid()

    def test_wrong_source_target_identity_or_ref_rejected(self):
        for field, value in (("upstream_repository", "evil/repo"), ("upstream_ref", "refs/heads/other"),
                             ("scheduler_repository", "other/fork")):
            with self.subTest(field=field):
                self.raw_tracking(changes={field: value})
                self.assert_invalid()

    def test_invalid_metadata_fields_rejected(self):
        for field, value in (("upstream_sha", "bad"), ("previous_upstream_sha", 1),
                             ("workflow_sha", None), ("run_id", "0"), ("run_attempt", 1),
                             ("event", "push"), ("credential", "must not be accepted")):
            with self.subTest(field=field):
                self.raw_tracking(changes={field: value})
                self.assert_invalid()

    def test_extra_tracking_tree_file_and_symlink_rejected(self):
        self.raw_tracking(extra=True)
        self.assert_invalid()
        self.raw_tracking(mode="120000")
        self.assert_invalid()

    def test_product_ancestor_hidden_under_metadata_tip_rejected(self):
        self.raw_tracking(parents=(self.base,))
        self.assert_invalid()

    def test_metadata_merge_history_and_wrong_previous_link_rejected(self):
        first = self.seed(self.base)
        second = self.seed(self.middle)
        self.raw_tracking(changes={"upstream_sha": self.tip, "previous_upstream_sha": self.middle},
                          parents=(first, second))
        self.assert_invalid()
        self.raw_tracking(changes={"upstream_sha": self.tip, "previous_upstream_sha": self.middle}, parents=(first,))
        self.assert_invalid()

    def test_old_source_mirror_tracking_rejected(self):
        self.set_ref(self.target, sync.TARGET_REF, self.base)
        self.assert_invalid()

    def test_pre_push_accepts_only_expected_metadata_update(self):
        metadata = self.seed(self.base)
        row = f"{metadata} {metadata} {sync.TARGET_REF} {'0' * 40}\n"
        self.assertTrue(sync.verify_push_input(row, "0" * 40, metadata))
        self.assertFalse(sync.verify_push_input(row, "0" * 40, self.tip))
        self.assertFalse(sync.verify_push_input(row + row, "0" * 40, metadata))
        self.assertFalse(sync.verify_push_input(row.replace(sync.TARGET_REF, sync.SCHEDULER_REF), "0" * 40, metadata))

    def test_post_push_remote_metadata_mismatch_is_failure(self):
        real_read = sync.read_metadata
        calls = 0

        def mismatching_read(git, commit):
            nonlocal calls
            calls += 1
            metadata = real_read(git, commit)
            if calls >= 2:
                metadata["upstream_sha"] = self.middle
            return metadata

        # Git creation, push and fetch are real. Only the returned content is
        # fault-injected to test the check after an otherwise correct OID match.
        with patch.object(sync, "read_metadata", side_effect=mismatching_read):
            report = self.run_sync()
        self.assert_result(report, "POST_PUSH_MISMATCH")
        self.assertEqual(self.metadata(report["tracking_commit_after"])["upstream_sha"], self.tip)

    def test_workflow_change_regression_metadata_push_succeeds(self):
        self.assertIn(".github/workflows/flutter-build.yml",
                      self.git(self.upstream, "diff", "--name-only", self.middle, self.tip))
        hooks = self.root / "server-hooks"
        hooks.mkdir()
        hook = hooks / "pre-receive"
        hook.write_text('#!/bin/sh\nwhile read old new ref; do\n'
                        '  for commit in $(git rev-list "$new" --not --all); do\n'
                        '    for path in $(git ls-tree -r --name-only "$commit"); do\n'
                        '      case "$path" in .github/workflows/*) echo "workflow permission denied" >&2; exit 1;; esac\n'
                        '    done\n'
                        '  done\n'
                        'done\nexit 0\n', encoding="utf-8")
        hook.chmod(0o700)
        self.git(self.target, "config", "core.hooksPath", str(hooks))
        source_git = sync.Git(self.upstream, local_testing=True, token=None)
        with self.assertRaises(sync.SyncError) as rejected:
            source_git.run("push", "--porcelain", str(self.target), f"{self.tip}:{sync.TARGET_REF}")
        self.assertIn("workflow permission denied", str(rejected.exception))
        self.assertEqual(self.refs(self.target), self.initial)
        report = self.run_sync()
        self.assert_result(report, "CREATED")
        commit = report["tracking_commit_after"]
        self.assertEqual(self.git(self.target, "ls-tree", "-r", "--name-only", commit), sync.METADATA_FILE)
        self.assertEqual(self.metadata(commit)["upstream_sha"], self.tip)
        self.assertNotIn(self.tip, self.git(self.target, "rev-list", "--all").splitlines())
        self.assertNotIn(".github/", self.git(self.target, "rev-list", "--objects", commit))
        target_git = sync.Git(self.target, local_testing=True, token=None)
        with self.assertRaises(sync.SyncError):
            target_git.run("cat-file", "-e", self.tip)
        previous = self.seed(self.middle)
        updated = self.run_sync()
        self.assert_result(updated, "UPDATED")
        child = updated["tracking_commit_after"]
        self.assertEqual(self.git(self.target, "rev-list", "--parents", "-n", "1", child), f"{child} {previous}")
        self.assertEqual(self.git(self.target, "ls-tree", "-r", "--name-only", child), sync.METADATA_FILE)
        self.assertEqual(self.metadata(child)["upstream_sha"], self.tip)
        with self.assertRaises(sync.SyncError):
            target_git.run("cat-file", "-e", self.tip)


if __name__ == "__main__":
    unittest.main()
