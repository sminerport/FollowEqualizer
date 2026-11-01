"""Minimal stand-ins for PyGithub so the tests never touch the network."""

import sys
import types


class FakeGithubException(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


class FakeUser:
    def __init__(self, login, fail_on=()):
        self.login = login
        self._following = []
        self._followers = []
        self.followed = []
        self.unfollowed = []
        # Logins whose follow / unfollow should raise, to exercise error handling.
        # Either a set of logins (HTTP 500) or a {login: status} dict.
        self.fail_on = fail_on

    def _raise_if_failing(self, login):
        if isinstance(self.fail_on, dict):
            if login in self.fail_on:
                raise FakeGithubException(
                    f"simulated HTTP {self.fail_on[login]} for {login}",
                    status=self.fail_on[login],
                )
        elif login in self.fail_on:
            raise FakeGithubException(f"simulated API failure for {login}")

    def get_following(self):
        return list(self._following)

    def get_followers(self):
        return list(self._followers)

    def get_starred(self):
        return []

    def remove_from_starred(self, repo):
        pass

    def add_to_following(self, user):
        self._raise_if_failing(user.login)
        self.followed.append(user.login)
        if user not in self._following:
            self._following.append(user)

    def remove_from_following(self, user):
        self._raise_if_failing(user.login)
        self.unfollowed.append(user.login)
        if user in self._following:
            self._following.remove(user)

    def __eq__(self, other):
        return isinstance(other, FakeUser) and self.login == other.login

    def __hash__(self):
        return hash(self.login)

    def __repr__(self):
        return f"FakeUser({self.login!r})"


class FakeAuthToken:
    def __init__(self, token):
        self.token = token


class FakeGithub:
    def __init__(self, login_or_token=None, auth=None, **kwargs):
        self.auth = auth
        self._user = FakeUser("me")
        self._users = {"me": self._user}

    def get_user(self, login=None):
        if login is None:
            return self._user
        return self._users.setdefault(login, FakeUser(login))


def install_fake_modules():
    """Register fake ``github`` and ``dotenv`` modules before importing src code."""
    sys.modules["github"] = types.SimpleNamespace(
        Github=FakeGithub,
        Auth=types.SimpleNamespace(Token=FakeAuthToken),
        GithubException=FakeGithubException,
    )
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *a, **k: None)
