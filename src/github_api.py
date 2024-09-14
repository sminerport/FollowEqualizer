from github import Github
import json


class GitHubManager:
    def __init__(self, token):
        self.g = Github(token)
        self.user = self.g.get_user()  # Could be changed to get_authenticated()
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
        # if self._cached_following is None:
        self._cached_following = [user for user in self.user.get_following()]
        return self._cached_following

    def get_followers(self):
        if self._cached_followers is None:
            self._cached_followers = [user for user in self.user.get_followers()]
        return self._cached_followers

    def get_non_followers(self, exclude_list=None):
        following = self.get_following()
        followers = self.get_followers()

        non_followers = [
            user
            for user in following
            if user not in followers and user.login not in exclude_list
        ]
        return non_followers

    def clear_internal_cache(self):
        self._cached_following = None
        self._cached_followers = None

    def get_starred_repos(self):
        return [repo for repo in self.user.get_starred()]

    def unfollow(self, user):
        # Use the authenticated user object to unfollow
        self.user.remove_from_following(user)

    def follow(self, user):
        # Use the authenticated user object to follow the specified user
        self.user.add_to_following(user)

    def unstar_repo(self, repo):
        self.user.remove_from_starred(repo)

    def load_exclude_list(self, path="exclude_list.json"):
        try:
            with open(path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            return {"users": [], "repos": []}

    def save_exclude_list(self, exclude_list, path="exclude_list.json"):
        with open(path, "w") as file:
            json.dump(exclude_list, file, indent=4)
