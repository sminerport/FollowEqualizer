import sys
import types
import unittest
import tempfile
import os
from pathlib import Path

# Ensure the src directory is on the path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Provide a minimal fake 'github' module to allow importing GitHubManager
class FakeUser:
    def __init__(self, login):
        self.login = login
        self._following = []
        self._followers = []
        self.unfollowed = []
        self.followed = []

    def get_following(self):
        return self._following

    def get_followers(self):
        return self._followers

    def remove_from_following(self, user):
        self.unfollowed.append(user.login)
        if user in self._following:
            self._following.remove(user)

    def add_to_following(self, user):
        self.followed.append(user.login)
        if user not in self._following:
            self._following.append(user)

    def get_starred(self):
        return []

    def remove_from_starred(self, repo):
        pass

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
        # Return existing or create new fake user
        if login not in self._users:
            self._users[login] = FakeUser(login)
        return self._users[login]

sys.modules['github'] = types.SimpleNamespace(Github=FakeGithub)

from github_api import GitHubManager

class GitHubManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = GitHubManager("token")
        # Replace internal user with a controllable FakeUser
        self.manager.user._following = [FakeUser("a"), FakeUser("b")]
        self.manager.user._followers = [FakeUser("b"), FakeUser("c")]

    def test_get_non_followers_excludes_names(self):
        non_followers = self.manager.get_non_followers(["a"])
        self.assertEqual([u.login for u in non_followers], [])

    def test_save_and_load_exclude_list(self):
        data = {"users": ["a"], "repos": ["r1"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ex.json")
            self.manager.save_exclude_list(data, path)
            loaded = self.manager.load_exclude_list(path)
            self.assertEqual(loaded, data)

if __name__ == '__main__':
    unittest.main()
