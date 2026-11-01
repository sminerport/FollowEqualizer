"""Tests for the GitHubManager utility class and the exclusions module."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the src and tests directories are on the path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fakes import FakeUser, install_fake_modules  # noqa: E402

install_fake_modules()

from exclusions import load_exclude_list, save_exclude_list  # noqa: E402
from github_api import GitHubManager  # noqa: E402


class GitHubManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = GitHubManager("token")
        # Replace internal user lists with controllable fakes
        self.manager.user._following = [FakeUser("a"), FakeUser("b")]
        self.manager.user._followers = [FakeUser("b"), FakeUser("c")]

    def test_requires_a_token(self):
        with self.assertRaises(ValueError):
            GitHubManager("")

    def test_get_non_followers(self):
        self.assertEqual(
            [u.login for u in self.manager.get_non_followers()], ["a"]
        )

    def test_get_non_followers_excludes_names(self):
        non_followers = self.manager.get_non_followers(["a"])
        self.assertEqual([u.login for u in non_followers], [])

    def test_get_non_followers_exclusion_is_case_insensitive(self):
        self.assertEqual(self.manager.get_non_followers(["A"]), [])
        self.assertEqual(self.manager.get_non_followers({"users": ["A"]}), [])

    def test_get_followers_not_followed(self):
        self.assertEqual(
            [u.login for u in self.manager.get_followers_not_followed()], ["c"]
        )
        self.assertEqual(self.manager.get_followers_not_followed(["C"]), [])

    def test_follow_and_unfollow_refresh_the_following_cache(self):
        self.assertEqual(len(self.manager.get_following()), 2)
        self.manager.follow(FakeUser("c"))
        self.assertEqual(len(self.manager.get_following()), 3)
        self.manager.unfollow(FakeUser("a"))
        self.assertEqual([u.login for u in self.manager.get_following()], ["b", "c"])

    def test_save_and_load_exclude_list(self):
        data = {"users": ["a"], "repos": ["r1"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ex.json")
            self.manager.save_exclude_list(data, path)
            loaded = self.manager.load_exclude_list(path)
            self.assertEqual(loaded, data)


class ExclusionsTest(unittest.TestCase):
    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                load_exclude_list(Path(tmp) / "missing.json"),
                {"users": [], "repos": []},
            )

    def test_missing_keys_default_to_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ex.json"
            path.write_text('{"users": ["a"]}')
            self.assertEqual(load_exclude_list(path), {"users": ["a"], "repos": []})

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ex.json"
            path.write_text("{ oops")
            with self.assertRaises(ValueError):
                load_exclude_list(path)

    def test_wrong_shape_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ex.json"
            path.write_text('["a", "b"]')
            with self.assertRaises(ValueError):
                load_exclude_list(path)
            path.write_text('{"users": "a"}')
            with self.assertRaises(ValueError):
                load_exclude_list(path)

    def test_save_strips_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "ex.json"  # parent dir is created
            save_exclude_list({"users": [" a ", "A", "", "b"], "repos": ["o/r", "o/r"]}, path)
            self.assertEqual(load_exclude_list(path), {"users": ["a", "b"], "repos": ["o/r"]})


if __name__ == "__main__":
    unittest.main()
