"""Unit tests for the automation helper functions."""

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.modules['dotenv'] = types.SimpleNamespace(load_dotenv=lambda *a, **k: None)

class FakeUser:
    def __init__(self, login):
        self.login = login
        self._following = []
        self._followers = []
        self.followed = []
        self.unfollowed = []

    def get_following(self):
        return self._following

    def get_followers(self):
        return self._followers

    def add_to_following(self, user):
        self.followed.append(user.login)
        if user not in self._following:
            self._following.append(user)

    def remove_from_following(self, user):
        self.unfollowed.append(user.login)
        if user in self._following:
            self._following.remove(user)

    def __eq__(self, other):
        return isinstance(other, FakeUser) and self.login == getattr(other, "login", None)

    def __hash__(self):
        return hash(self.login)

class FakeGithub:
    def __init__(self, token):
        self._user = FakeUser("me")
        self._users = {"me": self._user}

    def get_user(self, login=None):
        if login is None:
            return self._user
        if login not in self._users:
            self._users[login] = FakeUser(login)
        return self._users[login]

sys.modules['github'] = types.SimpleNamespace(Github=FakeGithub)

from github_api import GitHubManager
from automation import follow_back, unfollow_nonfollowers

class AutomationTest(unittest.TestCase):
    def setUp(self):
        self.manager = GitHubManager("token")
        self.manager.user._followers = [FakeUser("a"), FakeUser("b")]
        self.manager.user._following = [FakeUser("b"), FakeUser("c")]

    def test_follow_back(self):
        follow_back(self.manager, [])
        self.assertIn("a", self.manager.user.followed)
        self.assertNotIn("b", self.manager.user.followed)

    def test_unfollow_nonfollowers(self):
        unfollow_nonfollowers(self.manager, [])
        self.assertIn("c", self.manager.user.unfollowed)
        self.assertNotIn("b", self.manager.user.unfollowed)

if __name__ == '__main__':
    unittest.main()
