"""Headless follow / unfollow automation for FollowEqualizer.

Used by ``.github/workflows/automation.yml`` and runnable locally, e.g.:

    python src/automation.py --follow-back --dry-run

Exit codes: 0 success, 1 one or more actions failed, 2 bad usage / missing token.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from github import GithubException

from exclusions import DEFAULT_EXCLUDE_PATH, PROJECT_ROOT, load_exclude_list
from github_api import GitHubManager

# HTTP statuses that mean every further request would fail the same way:
# bad credentials / missing permission, forbidden or rate limited.
FATAL_STATUSES = {401, 403, 429}


@dataclass
class ActionResult:
    """Outcome of one action ("follow" or "unfollow") over a set of users."""

    action: str
    dry_run: bool
    succeeded: list = field(default_factory=list)  # logins acted on (or planned)
    failed: list = field(default_factory=list)  # (login, error message)
    aborted: str | None = None  # set when the run stopped early, with the reason

    @property
    def title(self) -> str:
        return {"follow": "Followed back", "unfollow": "Unfollowed"}[self.action]


def _apply(action: str, users, manager: GitHubManager, dry_run: bool) -> ActionResult:
    result = ActionResult(action=action, dry_run=dry_run)
    marker = "+" if action == "follow" else "-"
    ordered = sorted(users, key=lambda u: u.login.lower())

    for index, user in enumerate(ordered):
        login = user.login
        if dry_run:
            print(f"  [dry-run] would {action} {login}")
            result.succeeded.append(login)
            continue
        try:
            if action == "follow":
                manager.follow(user)
            else:
                manager.unfollow(user)
        except Exception as exc:  # one bad user must not abort the whole run...
            result.failed.append((login, str(exc)))
            print(f"  ! failed to {action} {login}: {exc}")
            # ...unless the error means every remaining request is doomed too.
            if isinstance(exc, GithubException) and exc.status in FATAL_STATUSES:
                remaining = len(ordered) - index - 1
                result.aborted = (
                    f"stopped after {login}: HTTP {exc.status}. Check the token's "
                    f"permissions and the API rate limit. {remaining} user(s) not attempted."
                )
                print(f"  ! {result.aborted}")
                break
        else:
            print(f"  {marker} {action}ed {login}")
            result.succeeded.append(login)
    return result


def follow_back(manager: GitHubManager, exclude_list, dry_run: bool = False) -> ActionResult:
    """Follow back users who follow you but whom you're not following."""
    users = manager.get_followers_not_followed(exclude_list)
    print(f"Follow back: {len(users)} user(s) to follow{' (dry run)' if dry_run else ''}")
    result = _apply("follow", users, manager, dry_run)
    print(f"Followed back {len(result.succeeded)} user(s).")
    return result


def unfollow_nonfollowers(
    manager: GitHubManager, exclude_list, dry_run: bool = False
) -> ActionResult:
    """Unfollow users you follow who do not follow you back."""
    users = manager.get_non_followers(exclude_list)
    print(f"Unfollow: {len(users)} non-follower(s){' (dry run)' if dry_run else ''}")
    result = _apply("unfollow", users, manager, dry_run)
    print(f"Unfollowed {len(result.succeeded)} user(s).")
    return result


def load_excludes(path) -> list:
    """Return the excluded user logins, warning loudly if the file is absent."""
    path = Path(path)
    if not path.exists():
        print(
            f"WARNING: exclude file {path} not found; no exceptions will be applied.",
            file=sys.stderr,
        )
        return []
    users = load_exclude_list(path)["users"]
    print(f"Loaded {len(users)} excluded user(s) from {path}")
    return users


def write_step_summary(results, path=None) -> None:
    """Append a Markdown report to the GitHub Actions job summary, if available."""
    path = path or os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return

    lines = ["## FollowEqualizer run", ""]
    for result in results:
        lines.append(f"### {result.title}{' (dry run)' if result.dry_run else ''}")
        lines.append("")
        if not result.succeeded and not result.failed:
            lines += ["Nothing to do.", ""]
            continue
        if result.succeeded:
            label = "Would act on" if result.dry_run else "Done"
            lines.append(f"- {label} ({len(result.succeeded)}): " + ", ".join(
                f"`{login}`" for login in result.succeeded
            ))
        if result.failed:
            lines.append(f"- Failed ({len(result.failed)}):")
            lines += [f"  - `{login}`: {error}" for login, error in result.failed]
        if result.aborted:
            lines.append(f"- **Run aborted**: {result.aborted}")
        lines.append("")

    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automate GitHub follow actions")
    parser.add_argument(
        "--follow-back",
        action="store_true",
        help="Follow back users who follow you",
    )
    parser.add_argument(
        "--unfollow-nonfollowers",
        action="store_true",
        help="Unfollow users who don't follow you back",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would change; make no API writes. "
        "On its own it previews both actions.",
    )
    parser.add_argument(
        "--exclude-file",
        default=str(DEFAULT_EXCLUDE_PATH),
        help="Path to the exclude list JSON file (default: exclude_list.json at the repo root)",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.follow_back or args.unfollow_nonfollowers):
        if args.dry_run:
            # "Just show me everything" is the natural meaning of a bare --dry-run
            args.follow_back = args.unfollow_nonfollowers = True
        else:
            parser.error("choose at least one of --follow-back / --unfollow-nonfollowers")

    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print(
            "GITHUB_TOKEN is not set. Put it in .env locally, or set the "
            "FOLLOW_EQUALIZER_TOKEN secret for the GitHub Actions workflow.",
            file=sys.stderr,
        )
        return 2

    try:
        exclude = load_excludes(args.exclude_file)
    except ValueError as exc:
        print(f"Refusing to run: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print("Dry run: no changes will be made.")

    manager = GitHubManager(token)
    results = []
    if args.follow_back:
        results.append(follow_back(manager, exclude, args.dry_run))
    if args.unfollow_nonfollowers:
        results.append(unfollow_nonfollowers(manager, exclude, args.dry_run))

    write_step_summary(results)

    failures = sum(len(result.failed) for result in results)
    if failures:
        print(f"{failures} action(s) failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
