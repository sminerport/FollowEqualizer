"""Unit tests for the headless automation script."""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fakes import FakeUser, install_fake_modules  # noqa: E402

install_fake_modules()

import automation  # noqa: E402
from automation import follow_back, load_excludes, unfollow_nonfollowers  # noqa: E402
from github_api import GitHubManager  # noqa: E402


def quiet(func, *args, **kwargs):
    """Run func while capturing stdout/stderr; return (result, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        result = func(*args, **kwargs)
    return result, out.getvalue(), err.getvalue()


class AutomationTest(unittest.TestCase):
    def setUp(self):
        self.manager = GitHubManager("token")
        # Followers: a, b, Keep.  Following: b, c, Protected.
        # => follow back a + Keep; unfollow c + Protected.
        self.manager.user._followers = [FakeUser("a"), FakeUser("b"), FakeUser("Keep")]
        self.manager.user._following = [
            FakeUser("b"),
            FakeUser("c"),
            FakeUser("Protected"),
        ]

    def test_follow_back(self):
        result, out, _ = quiet(follow_back, self.manager, [])
        self.assertEqual(sorted(self.manager.user.followed), ["Keep", "a"])
        self.assertNotIn("b", self.manager.user.followed)
        self.assertEqual(result.succeeded, ["a", "Keep"])  # sorted, case-insensitive
        self.assertEqual(result.failed, [])
        self.assertIn("+ followed a", out)  # usernames are printed for the log

    def test_follow_back_respects_exclusions_case_insensitively(self):
        result, _, _ = quiet(follow_back, self.manager, ["keep"])
        self.assertEqual(self.manager.user.followed, ["a"])
        self.assertEqual(result.succeeded, ["a"])

    def test_unfollow_nonfollowers(self):
        result, out, _ = quiet(unfollow_nonfollowers, self.manager, [])
        self.assertEqual(sorted(self.manager.user.unfollowed), ["Protected", "c"])
        self.assertNotIn("b", self.manager.user.unfollowed)
        self.assertEqual(result.succeeded, ["c", "Protected"])
        self.assertIn("- unfollowed c", out)

    def test_unfollow_respects_exclusions_case_insensitively(self):
        result, _, _ = quiet(unfollow_nonfollowers, self.manager, ["PROTECTED"])
        self.assertEqual(self.manager.user.unfollowed, ["c"])
        self.assertEqual(result.succeeded, ["c"])

    def test_dry_run_makes_no_changes(self):
        follow, out, _ = quiet(follow_back, self.manager, [], dry_run=True)
        unfollow, _, _ = quiet(unfollow_nonfollowers, self.manager, [], dry_run=True)
        self.assertEqual(self.manager.user.followed, [])
        self.assertEqual(self.manager.user.unfollowed, [])
        self.assertTrue(follow.dry_run and unfollow.dry_run)
        self.assertEqual(follow.succeeded, ["a", "Keep"])
        self.assertEqual(unfollow.succeeded, ["c", "Protected"])
        self.assertIn("[dry-run] would follow a", out)

    def test_one_failure_does_not_abort_the_run(self):
        self.manager.user.fail_on = {"a"}
        result, out, _ = quiet(follow_back, self.manager, [])
        self.assertEqual(self.manager.user.followed, ["Keep"])
        self.assertEqual(result.succeeded, ["Keep"])
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.failed[0][0], "a")
        self.assertIsNone(result.aborted)
        self.assertIn("failed to follow a", out)

    def test_auth_or_rate_limit_error_aborts_the_run(self):
        for status in (401, 403, 429):
            with self.subTest(status=status):
                self.manager.user.followed.clear()
                self.manager.user.fail_on = {"a": status}
                result, out, _ = quiet(follow_back, self.manager, [])
                # "a" sorts first, fails fatally, and "Keep" is never attempted
                self.assertEqual(self.manager.user.followed, [])
                self.assertEqual([login for login, _ in result.failed], ["a"])
                self.assertIn(f"HTTP {status}", result.aborted)
                self.assertIn("1 user(s) not attempted", result.aborted)
                self.assertIn("stopped after a", out)

    def test_other_http_errors_do_not_abort(self):
        self.manager.user.fail_on = {"a": 404}
        result, _, _ = quiet(follow_back, self.manager, [])
        self.assertEqual(self.manager.user.followed, ["Keep"])
        self.assertIsNone(result.aborted)


class LoadExcludesTest(unittest.TestCase):
    def test_missing_file_warns_and_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _, err = quiet(load_excludes, Path(tmp) / "nope.json")
        self.assertEqual(result, [])
        self.assertIn("WARNING", err)

    def test_reads_users_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ex.json"
            path.write_text('{"users": ["x", "y"], "repos": ["o/r"]}')
            result, out, _ = quiet(load_excludes, path)
        self.assertEqual(result, ["x", "y"])
        self.assertIn("Loaded 2 excluded user(s)", out)

    def test_malformed_file_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ex.json"
            path.write_text("{ not json")
            with self.assertRaises(ValueError):
                quiet(load_excludes, path)

    def test_unreadable_path_raises_value_error_not_oserror(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):  # a directory, not a file
                quiet(load_excludes, tmp)


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.exclude_path = Path(self.tmp.name) / "exclude_list.json"
        self.exclude_path.write_text('{"users": ["Protected"], "repos": []}')
        self.summary_path = Path(self.tmp.name) / "summary.md"
        self.env = mock.patch.dict(
            os.environ,
            {"GITHUB_TOKEN": "token", "GITHUB_STEP_SUMMARY": str(self.summary_path)},
        )
        self.env.start()

        self.manager = GitHubManager("token")
        self.manager.user._followers = [FakeUser("a"), FakeUser("b")]
        self.manager.user._following = [FakeUser("b"), FakeUser("c"), FakeUser("Protected")]
        self.factory = mock.patch.object(
            automation, "GitHubManager", return_value=self.manager
        )
        self.factory.start()

    def tearDown(self):
        self.factory.stop()
        self.env.stop()
        self.tmp.cleanup()

    def run_main(self, *argv):
        return quiet(automation.main, list(argv))

    def test_requires_an_action_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_main("--exclude-file", str(self.exclude_path))
        self.assertEqual(ctx.exception.code, 2)

    def test_dry_run_alone_previews_both_actions(self):
        code, out, _ = self.run_main("--dry-run", "--exclude-file", str(self.exclude_path))
        self.assertEqual(code, 0)
        self.assertEqual(self.manager.user.followed, [])
        self.assertEqual(self.manager.user.unfollowed, [])
        self.assertIn("would follow a", out)
        self.assertIn("would unfollow c", out)
        summary = self.summary_path.read_text()
        self.assertIn("### Followed back (dry run)", summary)
        self.assertIn("### Unfollowed (dry run)", summary)

    def test_directory_as_exclude_file_refuses_to_run(self):
        code, _, err = self.run_main("--follow-back", "--exclude-file", self.tmp.name)
        self.assertEqual(code, 2)
        self.assertIn("Refusing to run", err)
        self.assertEqual(self.manager.user.followed, [])

    def test_fatal_error_is_reported_in_summary(self):
        self.manager.user.fail_on = {"a": 403}
        code, _, _ = self.run_main("--follow-back", "--exclude-file", str(self.exclude_path))
        self.assertEqual(code, 1)
        self.assertIn("**Run aborted**", self.summary_path.read_text())

    def test_missing_token_exits_2(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": ""}):
            code, _, err = self.run_main("--follow-back")
        self.assertEqual(code, 2)
        self.assertIn("GITHUB_TOKEN", err)

    def test_malformed_exclude_file_refuses_to_run(self):
        self.exclude_path.write_text("{ nope")
        code, _, err = self.run_main("--unfollow-nonfollowers", "--exclude-file", str(self.exclude_path))
        self.assertEqual(code, 2)
        self.assertIn("Refusing to run", err)
        self.assertEqual(self.manager.user.unfollowed, [])

    def test_both_actions_apply_exclusions_and_write_summary(self):
        code, _, _ = self.run_main(
            "--follow-back",
            "--unfollow-nonfollowers",
            "--exclude-file",
            str(self.exclude_path),
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.manager.user.followed, ["a"])
        self.assertEqual(self.manager.user.unfollowed, ["c"])  # Protected is excluded
        summary = self.summary_path.read_text()
        self.assertIn("### Followed back", summary)
        self.assertIn("`a`", summary)
        self.assertIn("### Unfollowed", summary)
        self.assertIn("`c`", summary)
        self.assertNotIn("Protected", summary)

    def test_dry_run_end_to_end_changes_nothing(self):
        code, out, _ = self.run_main(
            "--follow-back",
            "--unfollow-nonfollowers",
            "--dry-run",
            "--exclude-file",
            str(self.exclude_path),
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.manager.user.followed, [])
        self.assertEqual(self.manager.user.unfollowed, [])
        self.assertIn("Dry run: no changes will be made.", out)
        self.assertIn("(dry run)", self.summary_path.read_text())

    def test_failures_give_nonzero_exit(self):
        self.manager.user.fail_on = {"c"}
        code, _, err = self.run_main("--unfollow-nonfollowers", "--exclude-file", str(self.exclude_path))
        self.assertEqual(code, 1)
        self.assertIn("1 action(s) failed", err)
        self.assertIn("Failed (1)", self.summary_path.read_text())


if __name__ == "__main__":
    unittest.main()
