# FollowEqualizer

GitHub follower manager: PyQt5 GUI (`src/main.py`) + headless CLI (`src/automation.py`) sharing `src/github_api.py`.
Exceptions live in `exclude_list.json` at the repo root and are read by the GUI, the CLI and the Actions workflow. Commit it after changes.

## Commands
- `pip install -r requirements.txt` - CLI deps only (PyGithub, python-dotenv); `requirements-gui.txt` adds PyQt5
- `python -m unittest discover -s tests -v` - fakes in `tests/fakes.py`, no network or token needed
- `GITHUB_TOKEN=$(gh auth token) python src/automation.py --dry-run` - live preview of both actions, no writes
- `gh workflow run automation.yml --repo sminerport/FollowEqualizer -f dry_run=true -f follow_back=true -f unfollow_nonfollowers=true` - dispatch in Actions; always pass `--repo` when outside the checkout
- `gh run list --workflow automation.yml --repo sminerport/FollowEqualizer` - check runs

## Branching and releases
- `dev` is the default branch, `main` is release-ready. Flow: feature → dev → main, every step a PR with a merge commit (squash disabled; never squash a promotion, it re-diverges `dev`). Merged branches auto-delete. `prod` was retired.
- Rulesets (same shape as ResumeCreatorAddIn): "Protect dev" (strict: head must be up to date) and "Protect main" (non-strict) both require PR + green `Tests passed` check, no force-push or deletion; "Protect release tags" guards `v*`. `main` is non-strict on purpose: each promotion leaves `dev` one merge commit behind with identical content.
- Promotion PR title: `Release vX.Y.Z` or `Promote ... to main`. Then `git tag -a vX.Y.Z -m "FollowEqualizer vX.Y.Z" && git push origin vX.Y.Z` on `main`; `release.yml` re-tests and creates a **draft** GitHub Release (source zip + SHA256SUMS). Publishing the draft is the manual gate.
- Scheduled workflows run from `dev`; keep `dev` in sync with `main` or the schedule runs stale code.
- Actions must be referenced by full commit SHA (`uses: owner/repo@<sha> # vX.Y.Z`); the repo's "require SHA pinning" setting rejects tag refs. Dependabot bumps pins weekly.
- `gh pr merge`, `gh api -X POST/PUT/DELETE`, `gh secret/variable set` and branch deletion are classifier-blocked for Claude: give the user the exact command to run with the `!` prefix.

## Automation gotchas
- Schedule is 09:00 UTC. Unfollow runs only if repo variable `SCHEDULE_UNFOLLOW=true` or ticked on a manual dispatch.
- `FOLLOW_EQUALIZER_TOKEN` must be a fine-grained PAT with Account → Followers: read and write. Expiry shows as HTTP 401 in the job summary.
- The keepalive step re-enables the workflow each run; GitHub disables cron workflows after 60 days without commits.
- GitHub silently ignores follows of spam-flagged accounts (204, no effect); a few "still to follow back" after a run is normal.
- Modules import flat (`from github_api import ...`); tests put `src/` on `sys.path`. Python 3.12 (`.python-version`), 3.10 still in the CI matrix.
