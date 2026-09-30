"""Offline release state-machine and HTTP adapter regression tests.

Run: python -B -m unittest discover -s tests/xn -p test_release_traceability.py -v
No GitHub writes, tokens, third-party libraries, or real build are needed.
"""

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
LEGACY_TAG = "3f207e91f6061b637f704f94074ee487b030625f"
CTX = rt.Context(rt.REPOSITORY, "workflow_dispatch", rt.SOURCE_REF, SOURCE, "33714217274", "1")


def tag(sha=SOURCE, kind="commit"):
    return {"ref": f"refs/tags/{CTX.tag}", "object": {"type": kind, "sha": sha}}


def asset(name, identity=1):
    return {"id": identity, "name": name, "state": "uploaded", "size": 123,
            "digest": "sha256:" + "a" * 64}


class FakeGitHub:
    def __init__(self, existing=None):
        self.remote_tag = existing
        self.commit = {"sha": SOURCE}
        self.run = {"id": int(CTX.run_id), "head_sha": SOURCE, "head_branch": "xn-main",
                    "event": "workflow_dispatch", "run_attempt": 1,
                    "path": ".github/workflows/xn-release.yml",
                    "repository": {"full_name": rt.REPOSITORY}}
        self.release = {"id": 1, "tag_name": CTX.tag, "draft": False,
                        "target_commitish": "master", "name": "some misleading name"}
        self.assets = [asset("rustdesk-1.5.0-aarch64-signed.apk"),
                       asset("rustdesk-1.5.0-x86_64.exe", 2)]
        self.writes = []
        self.on_create = None
        self.on_assets = None

    def get_commit(self):
        return self.commit

    def get_run(self):
        return self.run

    def get_tag(self):
        return copy.deepcopy(self.remote_tag)

    def create_tag(self):
        self.writes.append(("create", CTX.tag, SOURCE))
        if self.on_create:
            return self.on_create(self)
        self.remote_tag = tag()
        return self.remote_tag

    def get_release(self):
        return self.release

    def get_assets(self, release_id):
        if self.on_assets:
            self.on_assets(self)
        return self.assets


class Gates(unittest.TestCase):
    def assert_code(self, code, callback):
        with self.assertRaises(rt.TraceabilityError) as caught:
            callback()
        self.assertEqual(str(caught.exception), code)

    def test_valid_xn_main(self):
        CTX.validate()
        rt.verify_source(CTX, FakeGitHub())

    def test_wrong_repository(self):
        self.assert_code("WRONG_REPOSITORY", lambda: replace(CTX, repository="rustdesk/rustdesk").validate())

    def test_master_rejected(self):
        self.assert_code("WRONG_SOURCE_REF", lambda: replace(CTX, source_ref="refs/heads/master").validate())

    def test_legacy_branch_rejected(self):
        self.assert_code("WRONG_SOURCE_REF", lambda: replace(CTX, source_ref="refs/heads/custom-nav-controls").validate())

    def test_tag_ref_rejected(self):
        self.assert_code("WRONG_SOURCE_REF", lambda: replace(CTX, source_ref="refs/tags/xn-main").validate())

    def test_wrong_event(self):
        for event in ("push", "pull_request", "workflow_call", "schedule", ""):
            with self.subTest(event=event):
                self.assert_code("WRONG_EVENT", lambda: replace(CTX, event=event).validate())

    def test_invalid_source_sha(self):
        for sha in ("", "master", SOURCE[:8], SOURCE.upper(), SOURCE + "\n", "g" * 40):
            with self.subTest(sha=sha):
                self.assert_code("INVALID_SOURCE_SHA", lambda: replace(CTX, source_sha=sha).validate())

    def test_full_sha_must_be_remote_commit(self):
        api = FakeGitHub()
        api.commit["sha"] = LEGACY_TAG
        self.assert_code("SOURCE_COMMIT_MISMATCH", lambda: rt.prepare(CTX, api, {}))
        self.assertEqual(api.writes, [])

    def test_build_run_identity_verified(self):
        for key, value in (("id", 1), ("head_sha", LEGACY_TAG), ("head_branch", "master"),
                           ("event", "push"), ("run_attempt", 2), ("path", "legacy.yml"),
                           ("repository", {"full_name": "other/repo"})):
            api = FakeGitHub()
            api.run[key] = value
            with self.subTest(key=key):
                self.assert_code("BUILD_RUN_SOURCE_MISMATCH", lambda: rt.prepare(CTX, api, {}))
                self.assertEqual(api.writes, [])

    def test_computed_tag_deterministic_and_git_valid(self):
        self.assertEqual(CTX.tag, "xn-33714217274")
        self.assertEqual(replace(CTX, run_attempt="2").tag, CTX.tag)
        result = subprocess.run(["git", "check-ref-format", f"refs/tags/{CTX.tag}"], capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_bad_run_ids_rejected(self):
        for run_id in ("0", "01", "1\n", "../master", "1;evil", "1" * 21):
            self.assert_code("INVALID_RUN_ID", lambda: rt.release_tag(run_id))

    def test_invalid_attempt(self):
        self.assert_code("INVALID_RUN_ATTEMPT", lambda: replace(CTX, run_attempt="0").validate())

    def test_absent_tag_creates_exact_source(self):
        api, evidence = FakeGitHub(), {}
        rt.prepare(CTX, api, evidence)
        self.assertEqual(api.writes, [("create", CTX.tag, SOURCE)])
        self.assertEqual(evidence["tag_sha"], SOURCE)
        self.assertTrue(evidence["tag_created"])
        self.assertTrue(evidence["traceability_verified"])

    def test_existing_same_source_idempotent(self):
        api, evidence = FakeGitHub(tag()), {}
        rt.prepare(CTX, api, evidence)
        rt.prepare(CTX, api, evidence)
        self.assertEqual(api.writes, [])
        self.assertFalse(evidence["tag_created"])

    def test_existing_wrong_source_never_updates(self):
        api = FakeGitHub(tag(LEGACY_TAG))
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.prepare(CTX, api, {}))
        self.assertEqual(api.writes, [])
        self.assertEqual(api.remote_tag, tag(LEGACY_TAG))

    def test_annotated_tag_rejected(self):
        self.assert_code("TAG_NOT_LIGHTWEIGHT", lambda: rt.verify_tag(CTX, tag(kind="tag")))

    def test_wrong_tag_ref_rejected(self):
        wrong = tag()
        wrong["ref"] += "-other"
        self.assert_code("TAG_REF_MISMATCH", lambda: rt.verify_tag(CTX, wrong))

    def test_create_race_wrong_source_fails_safely(self):
        api = FakeGitHub()
        def race(remote):
            remote.remote_tag = tag(LEGACY_TAG)
            raise rt.TraceabilityError("GITHUB_HTTP_422")
        api.on_create = race
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.prepare(CTX, api, {}))
        self.assertEqual(len(api.writes), 1)
        self.assertEqual(api.remote_tag, tag(LEGACY_TAG))

    def test_create_race_same_source_fails_this_attempt(self):
        api = FakeGitHub()
        def race(remote):
            remote.remote_tag = tag()
            raise rt.TraceabilityError("GITHUB_HTTP_422")
        api.on_create = race
        self.assert_code("TAG_CREATE_FAILED", lambda: rt.prepare(CTX, api, {}))
        self.assertEqual(len(api.writes), 1)

    def test_creation_failure(self):
        api = FakeGitHub()
        api.on_create = lambda _: (_ for _ in ()).throw(rt.TraceabilityError("GITHUB_HTTP_403"))
        self.assert_code("TAG_CREATE_FAILED", lambda: rt.prepare(CTX, api, {}))
        self.assertIsNone(api.remote_tag)

    def test_uncertain_create_preserves_observed_remote_evidence(self):
        api, evidence = FakeGitHub(), {}
        def timeout_after_remote_create(remote):
            remote.remote_tag = tag()
            raise rt.TraceabilityError("GITHUB_REQUEST_FAILED")
        api.on_create = timeout_after_remote_create
        self.assert_code("TAG_CREATE_FAILED", lambda: rt.prepare(CTX, api, evidence))
        self.assertTrue(evidence["tag_creation_attempted"])
        self.assertEqual(evidence["observed_tag_sha"], SOURCE)
        self.assertFalse(evidence["traceability_verified"])
        self.assertEqual(api.remote_tag, tag())

    def test_post_create_mismatch_no_build_output(self):
        api, evidence = FakeGitHub(), {}
        api.on_create = lambda remote: setattr(remote, "remote_tag", tag(LEGACY_TAG))
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.prepare(CTX, api, evidence))
        self.assertFalse(evidence["traceability_verified"])
        self.assertTrue(evidence["tag_created"])

    def test_post_create_disappearance(self):
        api = FakeGitHub()
        api.on_create = lambda _: None
        self.assert_code("TAG_MISSING", lambda: rt.prepare(CTX, api, {}))

    def test_remote_changed_after_prepare_final_verify_fails(self):
        api = FakeGitHub()
        rt.prepare(CTX, api, {})
        api.remote_tag = tag(LEGACY_TAG)
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.verify_release(CTX, api, "success", True))

    def test_remote_changed_during_final_asset_queries(self):
        api = FakeGitHub(tag())
        api.on_assets = lambda remote: setattr(remote, "remote_tag", tag(LEGACY_TAG))
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.verify_release(CTX, api, "success", False))

    def test_final_tag_missing(self):
        self.assert_code("TAG_MISSING", lambda: rt.verify_release(CTX, FakeGitHub(), "success", True))

    def test_release_tag_and_source_match(self):
        manifest = rt.verify_release(CTX, FakeGitHub(tag()), "success", True)
        self.assertEqual(manifest["release_tag"], CTX.tag)
        self.assertEqual(manifest["source_sha"], manifest["tag_sha"])
        self.assertTrue(manifest["traceability_verified"])
        self.assertEqual(len(manifest["assets"]), 2)

    def test_target_commitish_metadata_does_not_override_tag_truth(self):
        api = FakeGitHub(tag())
        api.release["target_commitish"] = LEGACY_TAG
        self.assertTrue(rt.verify_release(CTX, api, "success", False)["traceability_verified"])

    def test_legacy_defect_reproduction(self):
        api = FakeGitHub(tag(LEGACY_TAG))
        api.release.update(target_commitish=SOURCE, name=SOURCE)
        self.assert_code("TAG_SOURCE_MISMATCH", lambda: rt.verify_release(CTX, api, "success", False))

    def test_missing_release(self):
        api = FakeGitHub(tag())
        api.release = None
        self.assert_code("RELEASE_MISSING", lambda: rt.verify_release(CTX, api, "success", False))

    def test_wrong_release_tag(self):
        api = FakeGitHub(tag())
        api.release["tag_name"] = "nightly"
        self.assert_code("RELEASE_TAG_MISMATCH", lambda: rt.verify_release(CTX, api, "success", False))

    def test_draft_release_rejected(self):
        api = FakeGitHub(tag())
        api.release["draft"] = True
        self.assert_code("RELEASE_NOT_PUBLISHED", lambda: rt.verify_release(CTX, api, "success", False))

    def test_expected_android_and_windows_assets_required(self):
        api = FakeGitHub(tag())
        api.assets = [asset("rustdesk.sbom.json")]
        self.assert_code("APK_ASSET_MISSING", lambda: rt.verify_release(CTX, api, "success", False))
        api.assets = [asset("rustdesk-1.5.0.apk")]
        self.assert_code("EXE_ASSET_MISSING", lambda: rt.verify_release(CTX, api, "success", False))

    def test_pending_or_empty_asset_rejected(self):
        api = FakeGitHub(tag())
        for key, value in (("state", "new"), ("size", 0), ("id", None), ("name", "other.apk")):
            api.assets = [asset("rustdesk-1.5.0.apk"), asset("rustdesk-1.5.0.exe", 2)]
            api.assets[0][key] = value
            self.assert_code("APK_ASSET_MISSING", lambda: rt.verify_release(CTX, api, "success", False))

    def test_manifest_roundtrip(self):
        manifest = rt.verify_release(CTX, FakeGitHub(tag()), "success", True)
        rt.validate_manifest(json.loads(json.dumps(manifest)), CTX, manifest)

    def test_manifest_mismatch_rejected(self):
        original = rt.verify_release(CTX, FakeGitHub(tag()), "success", True)
        for key, value in (("source_sha", LEGACY_TAG), ("tag_sha", LEGACY_TAG),
                           ("traceability_verified", False), ("run_id", "1"),
                           ("release_tag", "nightly"), ("schema_version", True),
                           ("assets", []), ("release_id", 2)):
            modified = dict(original, **{key: value})
            self.assert_code("MANIFEST_MISMATCH", lambda: rt.validate_manifest(modified, CTX, original))

    def test_build_failure_preserves_tag_and_never_passes(self):
        api = FakeGitHub()
        rt.prepare(CTX, api, {})
        for result in ("failure", "cancelled", "skipped", ""):
            self.assert_code("TAG_CREATED_BUILD_FAILED", lambda: rt.verify_release(CTX, api, result, True))
        self.assertEqual(api.remote_tag, tag())
        self.assertEqual(api.writes, [("create", CTX.tag, SOURCE)])

    def test_preexisting_tag_build_failure(self):
        self.assert_code("BUILD_FAILED", lambda: rt.verify_release(CTX, FakeGitHub(tag()), "failure", False))

    def test_no_arbitrary_cli_source_or_tag(self):
        for args in (["prepare", "--source-sha", SOURCE], ["verify", "--tag", "anything"]):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(rt.main(args), 1)

    def test_user_input_environment_cannot_override_source_or_tag(self):
        env = dict(zip(("GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_SHA",
                        "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"),
                       (CTX.repository, CTX.event, CTX.source_ref, SOURCE, CTX.run_id, "1")))
        env.update(INPUT_SOURCE_SHA=LEGACY_TAG, INPUT_TAG="nightly", RELEASE_TAG="master")
        context = rt.Context.from_env(env)
        self.assertEqual(context.source_sha, SOURCE)
        self.assertEqual(context.tag, CTX.tag)


class Adapter(unittest.TestCase):
    def setUp(self):
        self.api = rt.GitHub(CTX, "secret-test-token-never-log")

    def test_only_fixed_create_payload_no_force(self):
        with patch.object(self.api, "_request", return_value=tag()) as call:
            self.api.create_tag()
        call.assert_called_once_with("git/refs", {"ref": f"refs/tags/{CTX.tag}", "sha": SOURCE})

    def test_http_request_method_and_credentials(self):
        response = io.BytesIO(json.dumps(tag()).encode())
        with patch.object(self.api._opener, "open", return_value=response) as call:
            self.api.create_tag()
        req = call.call_args.args[0]
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.full_url, "https://api.github.com/repos/2245676/rustdesk/git/refs")
        self.assertEqual(json.loads(req.data), {"ref": f"refs/tags/{CTX.tag}", "sha": SOURCE})
        self.assertNotIn("secret-test-token", req.full_url)

    def test_404_only_means_absent_for_tag_or_release(self):
        failure = error.HTTPError("private", 404, "hidden", {}, None)
        with patch.object(self.api._opener, "open", side_effect=failure):
            self.assertIsNone(self.api.get_tag())
            self.assertIsNone(self.api.get_release())
            with self.assertRaisesRegex(rt.TraceabilityError, "GITHUB_HTTP_404"):
                self.api.get_commit()

    def test_read_errors_never_treated_as_absent(self):
        for code in (401, 403, 422, 500):
            failure = error.HTTPError("private", code, "hidden", {}, None)
            with patch.object(self.api._opener, "open", side_effect=failure):
                with self.assertRaisesRegex(rt.TraceabilityError, f"GITHUB_HTTP_{code}"):
                    self.api.get_tag()

    def test_token_and_response_not_in_error(self):
        failure = error.HTTPError("secret-test-token-never-log", 403, "secret-test-token-never-log", {}, None)
        out = io.StringIO()
        with patch.object(self.api._opener, "open", side_effect=failure), redirect_stderr(out), redirect_stdout(out):
            try:
                self.api.get_tag()
            except rt.TraceabilityError as exc:
                print(str(exc))
        self.assertEqual(out.getvalue(), "GITHUB_HTTP_403\n")

    def test_network_error_sanitized(self):
        with patch.object(self.api._opener, "open", side_effect=error.URLError("secret-test-token-never-log")):
            with self.assertRaisesRegex(rt.TraceabilityError, "^GITHUB_REQUEST_FAILED$"):
                self.api.get_tag()

    def test_incomplete_http_response_fails_without_logging_payload(self):
        failure = IncompleteRead(b"secret-test-token-never-log", 50)
        with patch.object(self.api._opener, "open", side_effect=failure):
            with self.assertRaisesRegex(rt.TraceabilityError, "^GITHUB_REQUEST_FAILED$"):
                self.api.get_tag()

    def test_redirects_disabled(self):
        self.assertIsNone(rt.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid"))

    def test_assets_paginate(self):
        page1 = [asset("rustdesk-1.5.0.apk", n + 1) for n in range(100)]
        page2 = [asset("rustdesk-1.5.0.exe", 101)]
        with patch.object(self.api, "_request", side_effect=[page1, page2]) as call:
            self.assertEqual(len(self.api.get_assets(1)), 101)
        self.assertEqual(call.call_args_list[1].args[0], "releases/1/assets?per_page=100&page=2")

    def test_invalid_release_id_no_request(self):
        with patch.object(self.api, "_request") as call:
            for value in (None, True, 0, "1/../../git/refs"):
                with self.assertRaises(rt.TraceabilityError):
                    self.api.get_assets(value)
            call.assert_not_called()

    def test_context_checked_before_client_exists(self):
        with self.assertRaisesRegex(rt.TraceabilityError, "WRONG_REPOSITORY"):
            rt.GitHub(replace(CTX, repository="other/repo"), "token")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = dict(zip(("GITHUB_REPOSITORY", "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_SHA",
                            "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"),
                           (CTX.repository, CTX.event, CTX.source_ref, CTX.source_sha, CTX.run_id, CTX.run_attempt)))
        self.env.update(GH_TOKEN="do-not-print-me", GITHUB_OUTPUT=str(self.root / "outputs"))
        self.patches = [patch.dict(os.environ, self.env, clear=True),
                        patch.object(rt, "MANIFEST", self.root / "XN_RELEASE_TRACEABILITY.json"),
                        patch.object(rt, "EVIDENCE", self.root / "XN_RELEASE_PREPARATION.json")]
        self.old_cwd = os.getcwd()
        os.chdir(self.root)
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        os.chdir(self.old_cwd)
        self.temp.cleanup()

    def run_main(self, mode, api):
        output = io.StringIO()
        with patch.object(rt, "GitHub", return_value=api), redirect_stdout(output), redirect_stderr(output):
            code = rt.main([mode])
        self.assertNotIn("do-not-print-me", output.getvalue())
        return code, output.getvalue()

    def test_prepare_success_publishes_outputs_only_after_verify(self):
        code, _ = self.run_main("prepare", FakeGitHub())
        self.assertEqual(code, 0)
        outputs = (self.root / "outputs").read_text()
        self.assertIn("tag_verified=true", outputs)
        self.assertIn(f"release_tag={CTX.tag}", outputs)
        self.assertTrue(json.loads(rt.EVIDENCE.read_text())["tag_created"])

    def test_prepare_failure_has_no_build_outputs_and_keeps_evidence(self):
        code, output = self.run_main("prepare", FakeGitHub(tag(LEGACY_TAG)))
        self.assertEqual(code, 1)
        self.assertEqual(output, "TAG_SOURCE_MISMATCH\n")
        self.assertFalse((self.root / "outputs").exists())
        self.assertFalse(json.loads(rt.EVIDENCE.read_text())["traceability_verified"])

    def test_missing_output_path_checked_before_mutation(self):
        os.environ.pop("GITHUB_OUTPUT")
        api = FakeGitHub()
        code, _ = self.run_main("prepare", api)
        self.assertEqual(code, 1)
        self.assertEqual(api.writes, [])

    def test_verify_success_and_failed_retry_cannot_leave_pass_manifest(self):
        os.environ.update(BUILD_RESULT="success", TAG_CREATED="true")
        api = FakeGitHub(tag())
        self.assertEqual(self.run_main("verify", api)[0], 0)
        manifest = json.loads(rt.MANIFEST.read_text())
        self.assertEqual(manifest["tag_sha"], manifest["source_sha"])
        os.environ["BUILD_RESULT"] = "failure"
        code, output = self.run_main("verify", api)
        self.assertEqual(code, 1)
        self.assertEqual(output, "TAG_CREATED_BUILD_FAILED\n")
        self.assertFalse(rt.MANIFEST.exists())
        failure = json.loads((self.root / "XN_RELEASE_FAILURE.json").read_text())
        self.assertEqual(failure["source_sha"], SOURCE)
        self.assertTrue(failure["tag_created"])
        self.assertEqual(api.remote_tag, tag())

    def test_manifest_tampering_fails_and_removes_success_file(self):
        os.environ.update(BUILD_RESULT="success", TAG_CREATED="true")
        original_write = rt.write_json
        def tamper(path, value):
            if path == rt.MANIFEST:
                value = dict(value, tag_sha=LEGACY_TAG)
            original_write(path, value)
        with patch.object(rt, "write_json", side_effect=tamper):
            code, output = self.run_main("verify", FakeGitHub(tag()))
        self.assertEqual(code, 1)
        self.assertEqual(output, "MANIFEST_MISMATCH\n")
        self.assertFalse(rt.MANIFEST.exists())
        failure = json.loads((self.root / "XN_RELEASE_FAILURE.json").read_text())
        self.assertFalse(failure["traceability_verified"])


class WorkflowContract(unittest.TestCase):
    """Check graph safety alongside actionlint's YAML/expression/type validation."""

    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/xn-release.yml").read_text()
        sections = re.split(r"^  (prepare-release|build|verify-release):\n", cls.workflow, flags=re.M)
        cls.jobs = dict(zip(sections[1::2], sections[2::2]))

    def test_dispatch_has_no_free_source_or_tag_inputs(self):
        trigger = self.workflow.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertEqual(trigger.strip(), "workflow_dispatch:")

    def test_build_gated_on_successful_tag_verification(self):
        build = self.jobs["build"]
        self.assertIn("needs: prepare-release", build)
        self.assertIn("needs.prepare-release.result == 'success'", build)
        self.assertIn("needs.prepare-release.outputs.tag_verified == 'true'", build)
        self.assertNotIn("always()", build)
        self.assertIn("uses: ./.github/workflows/flutter-build.yml", build)
        self.assertIn("upload-artifact: true", build)
        self.assertIn("upload-tag: ${{ needs.prepare-release.outputs.release_tag }}", build)
        self.assertIn("secrets: inherit", build)

    def test_verify_runs_on_failed_build_and_preserves_evidence(self):
        verify = self.jobs["verify-release"]
        self.assertIn("needs: [prepare-release, build]", verify)
        self.assertIn("always() && needs.prepare-release.result == 'success'", verify)
        self.assertIn("BUILD_RESULT: ${{ needs.build.result }}", verify)
        self.assertIn("TAG_CREATED: ${{ needs.prepare-release.outputs.tag_created }}", verify)
        self.assertIn("XN_RELEASE_TRACEABILITY.json", verify)
        self.assertIn("XN_RELEASE_FAILURE.json", verify)

    def test_exact_checkout_credentials_and_least_permissions(self):
        self.assertEqual(self.workflow.count("ref: ${{ github.sha }}"), 2)
        self.assertEqual(self.workflow.count("persist-credentials: false"), 2)
        self.assertIn("contents: write", self.jobs["prepare-release"])
        self.assertIn("actions: read", self.jobs["prepare-release"])
        self.assertNotIn("contents: write", self.jobs["verify-release"])
        self.assertNotIn("secrets.", self.jobs["prepare-release"])
        self.assertNotIn("secrets.", self.jobs["verify-release"])

    def test_no_publish_or_other_ref_event_in_wrapper(self):
        self.assertNotIn("softprops/action-gh-release", self.workflow)
        self.assertNotIn("schedule:", self.workflow)
        self.assertNotIn("push:", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)


if __name__ == "__main__":
    unittest.main()
