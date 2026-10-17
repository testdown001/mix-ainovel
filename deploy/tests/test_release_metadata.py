"""Offline metadata regressions: python3 -m unittest discover -s deploy/tests."""

from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


HELPER = Path(__file__).resolve().parents[1] / "scripts" / "release_metadata.py"
SHELL_HELPER = HELPER.with_name("prepare_release_metadata.sh")
SPEC = importlib.util.spec_from_file_location("release_metadata", HELPER)
metadata = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metadata)


class ReleaseMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "deploy").mkdir()
        self.env_file = self.root / "deploy" / ".env"
        self.env_file.write_bytes(b"SECRET_KEY=secret$literal\r\n# comment\r\nMYSQL_PASSWORD='leave this alone'\r\n")
        self.env_file.chmod(0o640)
        self.release_file = self.root / "deploy" / ".release.env"
        self.environment = {
            key: value for key, value in os.environ.items()
            if key not in metadata.KEYS and key != "ENV_FILE"
        }

    def cli(self, mode, *extra, environ=None):
        return subprocess.run(
            ["python3", str(HELPER), mode, "--root", str(self.root), *extra],
            check=True, capture_output=True, text=True, env={**self.environment, **(environ or {})},
        ).stdout

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True).stdout.strip()

    def init_git(self):
        self.git("init", "-b", "feature/quote'$HOME")
        self.git("config", "user.name", "Metadata Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.root / ".gitignore").write_text(".env\n/deploy/.release.env\n")
        (self.root / "tracked.txt").write_text("committed\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")

    def test_clean_dirty_sha_branch_and_utc_time(self):
        self.init_git()
        value = metadata.collect_build(self.root)
        self.assertEqual(value["APP_GIT_COMMIT"], self.git("rev-parse", "HEAD"))
        self.assertEqual(value["APP_GIT_BRANCH"], "feature/quote'$HOME")
        self.assertEqual(value["APP_GIT_DIRTY"], "false")
        self.assertTrue(value["APP_GIT_COMMIT_TIME"].endswith("Z"))
        self.assertEqual(datetime.fromisoformat(value["APP_BUILT_AT"].replace("Z", "+00:00")).tzinfo, timezone.utc)
        (self.root / "tracked.txt").write_text("changed\n")
        self.assertEqual(metadata.collect_build(self.root)["APP_GIT_DIRTY"], "true")

    def test_missing_git_is_unknown_not_invented(self):
        value = metadata.collect_build(self.root)
        self.assertEqual(value["APP_GIT_COMMIT"], "")
        self.assertEqual(value["APP_GIT_DIRTY"], "")
        self.assertTrue(value["APP_BUILD_ID"])

    def test_failed_or_timed_out_git_status_is_unknown_not_clean(self):
        self.init_git()
        original = metadata.subprocess.run
        for failure in (subprocess.CalledProcessError(1, "git"), subprocess.TimeoutExpired("git", 10)):
            def run(command, **kwargs):
                if "status" in command:
                    raise failure
                return original(command, **kwargs)
            with self.subTest(failure=type(failure).__name__), patch.object(metadata.subprocess, "run", side_effect=run):
                value = metadata.collect_build(self.root)
                self.assertEqual(value["APP_GIT_DIRTY"], "")
                self.assertEqual(value["APP_GIT_COMMIT"], self.git("rev-parse", "HEAD"))
                self.assertIsNone(metadata.image_metadata(value)["git_dirty"])

    def test_detached_head_has_no_invented_branch(self):
        self.init_git()
        self.git("checkout", "--detach", "HEAD")
        self.assertEqual(metadata.collect_build(self.root)["APP_GIT_BRANCH"], "")

    def test_build_is_unique_and_never_deploys(self):
        original = self.env_file.read_bytes()
        self.cli("build")
        first = metadata.read_metadata(self.release_file)
        self.cli("build")
        second = metadata.read_metadata(self.release_file)
        self.assertNotEqual(first["APP_BUILD_ID"], second["APP_BUILD_ID"])
        self.assertEqual(second["APP_DEPLOYED_AT"], "")
        self.assertEqual(self.env_file.read_bytes(), original)

    def test_image_json_is_safe_and_missing_args_are_unknown(self):
        self.assertTrue(all(value is None for value in metadata.image_metadata({}).values()))
        branch = "feature/'$(touch /tmp/never)'$HOME"
        value = metadata.image_metadata({"APP_GIT_BRANCH": branch, "APP_GIT_DIRTY": "false", "APP_BUILD_ID": "unique-build"})
        self.assertEqual(json.loads(json.dumps(value))["git_branch"], branch)
        self.assertIs(value["git_dirty"], False)
        self.assertEqual(value["build_id"], "unique-build")
        self.assertNotIn("deployed_at", value)

    def test_image_cli_writes_only_allowlisted_build_fields(self):
        target = self.root / "release-info.json"
        subprocess.run(["python3", str(HELPER), "image", "--file", str(target)], check=True,
                       env={"PATH": os.environ["PATH"], "APP_BUILD_ID": "a-build", "SECRET_KEY": "never-include", "APP_DEPLOYED_AT": "not-image-data"})
        self.assertEqual(json.loads(target.read_text())["build_id"], "a-build")
        self.assertNotIn("never-include", target.read_text())
        self.assertNotIn("not-image-data", target.read_text())

    def test_image_mode_works_from_docker_tmp_path(self):
        # In the Dockerfile the helper lives at /tmp/release_metadata.py, not
        # inside deploy/scripts; a shallow ancestor chain must not crash.
        with tempfile.NamedTemporaryFile(prefix="release-metadata-", suffix=".py", dir="/tmp") as script:
            Path(script.name).write_bytes(HELPER.read_bytes())
            target = self.root / "image.json"
            subprocess.run(["python3", script.name, "image", "--file", str(target)], check=True)
            self.assertIn("build_id", json.loads(target.read_text()))

    def test_deploy_preserves_secret_bytes_mode_and_ownership(self):
        original = self.env_file.read_bytes()
        original_stat = self.env_file.stat()
        self.cli("build")
        self.cli("deploy", environ={"APP_BUILD_ID": "actual-image-build"})
        value = metadata.read_metadata(self.release_file)
        self.assertEqual(value["APP_DEPLOYED_BUILD_ID"], "actual-image-build")
        self.assertTrue(self.env_file.read_bytes().startswith(original))
        self.assertIn(b"APP_DEPLOYED_BUILD_ID=actual-image-build\r\n", self.env_file.read_bytes())
        new_stat = self.env_file.stat()
        self.assertEqual(stat.S_IMODE(original_stat.st_mode), stat.S_IMODE(new_stat.st_mode))
        self.assertEqual((original_stat.st_uid, original_stat.st_gid), (new_stat.st_uid, new_stat.st_gid))
        self.assertNotIn("secret", self.release_file.read_text().lower().replace("contains no credentials", ""))

    def test_deploy_updates_only_existing_keys_and_new_event(self):
        self.env_file.write_bytes(b"SECRET_KEY=untouched\nexport APP_DEPLOYED_AT =old\nAPP_DEPLOYMENT_ID=old\nAPP_DEPLOYED_BUILD_ID=old\nTAIL=value")
        self.cli("deploy", environ={"APP_BUILD_ID": "image-one"})
        first = metadata.read_metadata(self.release_file)
        self.cli("deploy", environ={"APP_BUILD_ID": "image-one"})
        second = metadata.read_metadata(self.release_file)
        self.assertNotEqual(first["APP_DEPLOYMENT_ID"], second["APP_DEPLOYMENT_ID"])
        self.assertEqual(second["APP_DEPLOYED_BUILD_ID"], "image-one")
        self.assertTrue(self.env_file.read_bytes().startswith(b"SECRET_KEY=untouched\n"))
        self.assertTrue(self.env_file.read_bytes().endswith(b"TAIL=value"))
        self.assertNotIn(b"=old", self.env_file.read_bytes())

    def test_load_is_read_only_and_missing_file_does_not_clear_env(self):
        self.assertEqual(self.cli("load"), "")
        self.cli("build")
        before = (self.release_file.read_bytes(), self.release_file.stat().st_mtime_ns)
        self.cli("load")
        self.assertEqual(before, (self.release_file.read_bytes(), self.release_file.stat().st_mtime_ns))

    def test_rollback_event_never_reads_host_git_or_guesses_build(self):
        self.init_git()
        self.cli("build")
        before = metadata.read_metadata(self.release_file)
        self.cli("deploy", environ={"APP_BUILD_ID": "old-image-build"})
        value = metadata.read_metadata(self.release_file)
        self.assertEqual(value["APP_GIT_COMMIT"], before["APP_GIT_COMMIT"])
        self.assertEqual(value["APP_DEPLOYED_BUILD_ID"], "old-image-build")
        self.cli("deploy", environ={"APP_BUILD_ID": ""})
        self.assertEqual(metadata.read_metadata(self.release_file)["APP_DEPLOYED_BUILD_ID"], "")

    def test_root_env_fallback(self):
        root_env = self.root / ".env"
        self.env_file.rename(root_env)
        self.cli("deploy", environ={"APP_BUILD_ID": "image"})
        self.assertIn(b"APP_DEPLOYED_BUILD_ID=image", root_env.read_bytes())

    def test_shell_export_roundtrip_does_not_execute_branch(self):
        self.init_git()
        exports = self.cli("build")
        result = subprocess.run(["bash", "-c", exports + '\nprintf "%s" "$APP_GIT_BRANCH"'],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, "feature/quote'$HOME")
        self.assertEqual(metadata.read_metadata(self.release_file)["APP_GIT_BRANCH"], result.stdout)

    def test_sourced_helper_combines_build_and_deploy(self):
        scripts = self.root / "deploy" / "scripts"
        scripts.mkdir()
        shutil.copy(HELPER, scripts / HELPER.name)
        shutil.copy(SHELL_HELPER, scripts / SHELL_HELPER.name)
        result = subprocess.run(["bash", "-c", 'set -euo pipefail; source "$1" build; build="$APP_BUILD_ID"; source "$1" deploy; test "$build" = "$APP_DEPLOYED_BUILD_ID"; source "$1" load; printf "%s" "$APP_DEPLOYMENT_ID"', "test", str(scripts / SHELL_HELPER.name)], check=True, capture_output=True, text=True, env=self.environment)
        self.assertEqual(len(result.stdout), 32)
        self.assertIn(result.stdout.encode(), self.env_file.read_bytes())

    def test_sourced_helper_without_argument_builds_but_never_deploys(self):
        scripts = self.root / "deploy" / "scripts"
        scripts.mkdir()
        shutil.copy(HELPER, scripts / HELPER.name)
        shutil.copy(SHELL_HELPER, scripts / SHELL_HELPER.name)
        original = self.env_file.read_bytes()
        result = subprocess.run(["bash", "-c", 'set -euo pipefail; helper="$1"; set --; source "$helper"; test -n "$APP_BUILD_ID"; test -z "${APP_DEPLOYED_AT:-}"', "test", str(scripts / SHELL_HELPER.name)], check=True, capture_output=True, text=True, env=self.environment)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.env_file.read_bytes(), original)

    def test_sourced_helper_propagates_failure_without_partial_exports(self):
        scripts = self.root / "deploy" / "scripts"
        scripts.mkdir()
        shutil.copy(HELPER, scripts / HELPER.name)
        shutil.copy(SHELL_HELPER, scripts / SHELL_HELPER.name)
        original = self.env_file.read_bytes()
        # An invalid mode and a failed metadata subprocess must both return
        # nonzero to a caller using set -e, without inventing a release event.
        cases = (
            'source "$1" invalid-mode; status=$?; test "$status" -ne 0; test -z "${APP_BUILD_ID:-}"',
            'python3() { return 42; }; source "$1" build; status=$?; test "$status" -eq 42; test -z "${APP_BUILD_ID:-}"',
        )
        for script in cases:
            subprocess.run(["bash", "-c", 'set -uo pipefail; ' + script, "test", str(scripts / SHELL_HELPER.name)], check=True, capture_output=True, text=True, env=self.environment)
        self.assertFalse(self.release_file.exists())
        self.assertEqual(self.env_file.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
