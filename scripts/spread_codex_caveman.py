#!/usr/bin/env python3
"""Apply caveman Codex auto-start config across many git repos."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_HOOKS_PATH = REPO_ROOT / ".codex" / "hooks.json"
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".next",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
}
CAVEMAN_MARKER = "CAVEMAN MODE ACTIVE."


@dataclass
class RepoResult:
    repo: Path
    hooks_status: str
    config_status: str


def load_template_session_start() -> list[dict]:
    data = json.loads(TEMPLATE_HOOKS_PATH.read_text())
    return data["hooks"]["SessionStart"]


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def find_git_repos(roots: list[Path]) -> list[Path]:
    repos: set[Path] = set()
    for root in roots:
        if is_git_repo(root):
            repos.add(root.resolve())
            continue

        for current_root, dirnames, _ in os.walk(root):
            current = Path(current_root)
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
            if is_git_repo(current):
                repos.add(current.resolve())
                dirnames[:] = []

    return sorted(repos)


def ensure_caveman_session_start(
    hooks_path: Path,
    template_session_start: list[dict],
    *,
    apply: bool,
) -> str:
    if hooks_path.exists():
        data = json.loads(hooks_path.read_text())
        status = "unchanged"
    else:
        data = {}
        status = "created"

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{hooks_path} has non-object 'hooks'")

    session_start = hooks.setdefault("SessionStart", [])
    if not isinstance(session_start, list):
        raise ValueError(f"{hooks_path} has non-array 'hooks.SessionStart'")

    has_caveman = any(
        CAVEMAN_MARKER in hook.get("command", "")
        for entry in session_start
        if isinstance(entry, dict)
        for hook in entry.get("hooks", [])
        if isinstance(hook, dict)
    )
    if not has_caveman:
        session_start.extend(copy.deepcopy(template_session_start))
        status = "created" if status == "created" else "updated"

    if apply and status != "unchanged":
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_path.write_text(json.dumps(data, indent=2) + "\n")

    return status


def ensure_hooks_enabled(config_path: Path, *, apply: bool) -> str:
    feature_line = "hooks = true\n"
    if not config_path.exists():
        if apply:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("[features]\n" + feature_line)
        return "created"

    text = config_path.read_text()
    lines = text.splitlines(keepends=True)
    section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*$")
    key_pattern = re.compile(r"^(\s*)(hooks|codex_hooks)\s*=\s*(.+?)(\s*(#.*)?)?\n?$")

    feature_start: int | None = None
    feature_end = len(lines)
    for index, line in enumerate(lines):
        match = section_pattern.match(line.strip())
        if not match:
            continue
        if feature_start is not None and feature_end == len(lines):
            feature_end = index
        if match.group(1).strip() == "features":
            feature_start = index
            feature_end = len(lines)

    if feature_start is None:
        new_text = text
        if new_text and not new_text.endswith("\n"):
            new_text += "\n"
        if new_text and not new_text.endswith("\n\n"):
            new_text += "\n"
        new_text += "[features]\n" + feature_line
        if apply:
            config_path.write_text(new_text)
        return "updated"

    hooks_index: int | None = None
    hooks_match: re.Match[str] | None = None
    deprecated_indexes: list[int] = []
    deprecated_indent = ""
    for index in range(feature_start + 1, feature_end):
        match = key_pattern.match(lines[index])
        if not match:
            continue
        key = match.group(2)
        if key == "hooks" and hooks_index is None:
            hooks_index = index
            hooks_match = match
        elif key == "codex_hooks":
            deprecated_indexes.append(index)
            if not deprecated_indent:
                deprecated_indent = match.group(1)

    updated = False
    if hooks_index is None:
        if deprecated_indexes:
            lines[deprecated_indexes[0]] = f"{deprecated_indent}hooks = true\n"
            for index in reversed(deprecated_indexes[1:]):
                del lines[index]
        else:
            lines.insert(feature_end, feature_line)
        updated = True
    else:
        assert hooks_match is not None
        current_value = hooks_match.group(3).strip().lower()
        if current_value != "true":
            lines[hooks_index] = f"{hooks_match.group(1)}hooks = true\n"
            updated = True
        if deprecated_indexes:
            for index in reversed(deprecated_indexes):
                del lines[index]
            updated = True

    if not updated:
        return "unchanged"

    if apply:
        config_path.write_text("".join(lines))
    return "updated"


def process_repo(repo: Path, template_session_start: list[dict], *, apply: bool) -> RepoResult:
    codex_dir = repo / ".codex"
    hooks_status = ensure_caveman_session_start(
        codex_dir / "hooks.json",
        template_session_start,
        apply=apply,
    )
    config_status = ensure_hooks_enabled(codex_dir / "config.toml", apply=apply)
    return RepoResult(repo=repo, hooks_status=hooks_status, config_status=config_status)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spread caveman Codex auto-start config across many git repos.",
    )
    parser.add_argument(
        "roots",
        nargs="+",
        help="Repo path or parent directory to scan for git repos.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Default mode is dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roots = [Path(root).expanduser().resolve() for root in args.roots]
    missing = [root for root in roots if not root.exists()]
    if missing:
        for root in missing:
            print(f"Missing path: {root}", file=sys.stderr)
        return 2

    template_session_start = load_template_session_start()
    repos = find_git_repos(roots)
    if not repos:
        print("No git repos found.")
        return 0

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"{mode}: {len(repos)} repo(s)")

    failures = 0
    for repo in repos:
        try:
            result = process_repo(repo, template_session_start, apply=args.apply)
            print(
                f"{repo}: hooks={result.hooks_status}, config={result.config_status}"
            )
        except (ValueError, json.JSONDecodeError) as exc:
            failures += 1
            print(f"{repo}: error={exc}", file=sys.stderr)

    if not args.apply:
        print("Pass --apply to write changes.")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
