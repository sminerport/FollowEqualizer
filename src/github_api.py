from github import Auth, Github

from exclusions import DEFAULT_EXCLUDE_PATH
from exclusions import load_exclude_list as _load_exclude_list
from exclusions import save_exclude_list as _save_exclude_list


def _excluded_logins(exclude_list):
    """Lower-cased set of excluded user names. Accepts None, a list, or a dict."""
    if not exclude_list:
        return set()
    if isinstance(exclude_list, dict):
        exclude_list = exclude_list.get("users", [])
    return {name.lower() for name in exclude_list}


class GitHubManager:
    def __init__(self, token):
        if not token:
            raise ValueError("A GitHub token is required")
        self.g = Github(auth=Auth.Token(token))
        self.user = self.g.get_user()  # lazy: no request until an attribute is read
        self._cached_following = None
        self._cached_followers = None

    def get_repo_by_name(self, repo_name):
        """Fetch a repository by its full name (e.g., 'username/repo_name')"""
        try:
            return self.g.get_repo(repo_name)
        except Exception as e:
            print(f"Error fetching repository: {e}")
            return None

    def get_following(self):
        if self._cached_following is None:
            self._cached_following = list(self.user.get_following())
        return self._cached_following

    def get_followers(self):
        if self._cached_followers is None:
            self._cached_followers = list(self.user.get_followers())
        return self._cached_followers

    def get_non_followers(self, exclude_list=None):
        """Users you follow who do not follow you back, minus the exceptions."""
        excluded = _excluded_logins(exclude_list)
        follower_logins = {user.login.lower() for user in self.get_followers()}
        return [
            user
            for user in self.get_following()
            if user.login.lower() not in follower_logins
            and user.login.lower() not in excluded
        ]

    def get_followers_not_followed(self, exclude_list=None):
        """Users who follow you whom you do not follow back, minus the exceptions."""
        excluded = _excluded_logins(exclude_list)
        following_logins = {user.login.lower() for user in self.get_following()}
        return [
            user
            for user in self.get_followers()
            if user.login.lower() not in following_logins
            and user.login.lower() not in excluded
        ]

    def clear_internal_cache(self):
        self._cached_following = None
        self._cached_followers = None

    def get_starred_repos(self):
        return list(self.user.get_starred())

    def unfollow(self, user):
        self.user.remove_from_following(user)
        # The following list changed; refetch it next time it is needed.
        self._cached_following = None

    def follow(self, user):
        self.user.add_to_following(user)
        self._cached_following = None

    def unstar_repo(self, repo):
        self.user.remove_from_starred(repo)

    # Kept for backwards compatibility; the implementation lives in exclusions.py
    @staticmethod
    def load_exclude_list(path=DEFAULT_EXCLUDE_PATH):
        return _load_exclude_list(path)

    @staticmethod
    def save_exclude_list(exclude_list, path=DEFAULT_EXCLUDE_PATH):
        _save_exclude_list(exclude_list, path)
