import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

from github_api import GitHubManager


def follow_back(github_manager: GitHubManager, exclude_list):
    """Follow back users who follow you but whom you're not following."""
    followers = github_manager.get_followers()
    following = github_manager.get_following()

    followers_set = {u.login for u in followers}
    following_set = {u.login for u in following}

    to_follow = [
        login for login in followers_set - following_set if login not in exclude_list
    ]

    for login in to_follow:
        user = github_manager.g.get_user(login)
        github_manager.follow(user)

    print(f"Followed back {len(to_follow)} user(s).")


def unfollow_nonfollowers(github_manager: GitHubManager, exclude_list):
    """Unfollow users you follow who do not follow you back."""
    non_followers = github_manager.get_non_followers(exclude_list)
    for user in non_followers:
        github_manager.unfollow(user)
    print(f"Unfollowed {len(non_followers)} user(s).")


def load_excludes(path: str):
    if not path:
        return []
    manager = GitHubManager("dummy")  # token not used for loading file
    data = manager.load_exclude_list(path)Add commentMore actions
    return data.get("users", [])


def main():
    parser = argparse.ArgumentParser(description="Automate GitHub follow actions")
    parser.add_argument(
        "--follow-back",
        action="store_true",
        help="Follow back users who follow you",
    )
    parser.add_argument(
        "--unfollow-nonfollowers",
        action="store_true",
        help="Unfollow users who don't follow you",
    )
    parser.add_argument(
        "--exclude-file",
        default="exclude_list.json",
        help="Path to exclude list JSON file",
    )
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set")

    manager = GitHubManager(token)

    exclude = load_excludes(args.exclude_file)

    if args.follow_back:
        follow_back(manager, exclude)

    if args.unfollow_nonfollowers:
        unfollow_nonfollowers(manager, exclude)


if __name__ == "__main__":
    main()
