"""Load and save the exceptions ("exclude") list shared by the GUI and the CLI.

The file lives at the repository root as ``exclude_list.json`` so that the
GitHub Actions workflow honours the same exceptions you set in the desktop app.
Commit the file after changing it, otherwise the workflow will not see it.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXCLUDE_PATH = PROJECT_ROOT / "exclude_list.json"


def empty_exclude_list() -> dict:
    return {"users": [], "repos": []}


def load_exclude_list(path=DEFAULT_EXCLUDE_PATH) -> dict:
    """Return ``{"users": [...], "repos": [...]}`` read from *path*.

    A missing file yields empty lists. A file that exists but cannot be parsed,
    or that does not have the expected shape, raises ``ValueError`` so that a
    typo never silently turns into "no exceptions".
    """
    path = Path(path)
    if not path.exists():
        return empty_exclude_list()

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"{path} must contain a JSON object with 'users' and 'repos' lists"
        )

    result = empty_exclude_list()
    for key in ("users", "repos"):
        values = data.get(key, [])
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            raise ValueError(f"{path}: '{key}' must be a list of strings")
        result[key] = _dedupe(values)
    return result


def save_exclude_list(exclude_list: dict, path=DEFAULT_EXCLUDE_PATH) -> None:
    """Write *exclude_list* (``{"users": [...], "repos": [...]}``) to *path*."""
    path = Path(path)
    data = {
        "users": _dedupe(exclude_list.get("users", [])),
        "repos": _dedupe(exclude_list.get("repos", [])),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=4)
        fh.write("\n")


def _dedupe(values):
    """Strip whitespace and drop duplicates (GitHub names are case-insensitive)."""
    seen = set()
    result = []
    for value in values:
        value = value.strip()
        if value and value.lower() not in seen:
            seen.add(value.lower())
            result.append(value)
    return result
