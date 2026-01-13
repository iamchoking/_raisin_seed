#!/usr/bin/env python3
"""Snapshot every git repository under ../ into repositories.yaml."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

SRC_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(__file__).resolve().parent / "config" / "seeds"
DEFAULT_SEED_BASENAME = "repositories"
SKIP_NAMES = {"_raisin_seed", ".git"}


def normalize_seed_filename(raw_name: str | None) -> str:
    name = (raw_name or DEFAULT_SEED_BASENAME).strip()
    if not name:
        name = DEFAULT_SEED_BASENAME
    if not name.lower().endswith(".yaml"):
        name += ".yaml"
    return name


def resolve_seed_path(raw_name: str | None) -> Path:
    return CONFIG_DIR / normalize_seed_filename(raw_name)


@dataclass
class RepoSnapshot:
    """Lightweight container for the metadata we care about."""

    name: str
    path: str
    remote: str
    branch: str
    commit: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "remote": self.remote,
            "branch": self.branch,
            "commit": self.commit,
        }


def run_git(repo_path: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def is_git_repository(path: Path) -> bool:
    try:
        return run_git(path, "rev-parse", "--is-inside-work-tree", check=False) == "true"
    except FileNotFoundError as exc:  # git missing
        raise RuntimeError("git executable not found") from exc


def select_remote(path: Path) -> str:
    remotes_raw = run_git(path, "remote", check=False)
    remotes = [r.strip() for r in remotes_raw.splitlines() if r.strip()]
    if not remotes:
        raise RuntimeError(f"Repository {path} has no configured remotes")
    if "origin" in remotes:
        return "origin"
    return remotes[0]


def current_branch(path: Path) -> str:
    branch = run_git(path, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    if branch and branch != "HEAD":
        return branch
    # In detached HEAD we just return literal HEAD so plant_seed knows to detach too.
    return "HEAD"


def collect_repo_metadata(path: Path) -> RepoSnapshot:
    remote_name = select_remote(path)
    remote_url = run_git(path, "remote", "get-url", remote_name)
    branch = current_branch(path)
    commit = run_git(path, "rev-parse", "HEAD")
    rel_path = path.relative_to(SRC_ROOT).as_posix()
    return RepoSnapshot(name=path.name, path=rel_path, remote=remote_url, branch=branch, commit=commit)


def discover_repositories() -> List[RepoSnapshot]:
    repos: List[RepoSnapshot] = []
    for entry in sorted(SRC_ROOT.iterdir()):
        if entry.name in SKIP_NAMES or entry.name.startswith("."):
            continue
        if not entry.is_dir():
            continue
        if not is_git_repository(entry):
            continue
        repos.append(collect_repo_metadata(entry))
    return repos


def build_seed_payload(entries: Iterable[RepoSnapshot]) -> dict:
    return {"repositories": [repo.to_dict() for repo in entries]}


def write_seed_file(seed_path: Path, payload: dict) -> None:
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def index_repositories(payload: dict) -> Dict[str, dict]:
    repositories = payload.get("repositories")
    mapping: Dict[str, dict] = {}
    if not isinstance(repositories, list):
        return mapping
    for entry in repositories:
        if not isinstance(entry, dict):
            continue
        path_value = entry.get("path")
        if isinstance(path_value, str):
            mapping[path_value] = entry
    return mapping


def load_existing_seed(seed_path: Path) -> Dict[str, dict]:
    if not seed_path.exists():
        return {}
    try:
        data = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Warning: {seed_path.name} is not valid JSON; treating as empty snapshot.")
        return {}
    if not isinstance(data, dict):
        return {}
    return index_repositories(data)


def format_repo_state(repo: dict) -> str:
    branch = repo.get("branch") or "HEAD"
    commit = repo.get("commit") or "unknown"
    return f"{branch} @ {commit[:12]}"


def format_field_value(field: str, value: str | None) -> str:
    if not value:
        return "?"
    return value[:12] if field == "commit" else value


def summarize_seed_changes(old_map: Dict[str, dict], new_map: Dict[str, dict]) -> List[str]:
    changes: List[str] = []
    old_paths = set(old_map)
    new_paths = set(new_map)

    for path in sorted(new_paths - old_paths):
        changes.append(f"+ {path}: {format_repo_state(new_map[path])}")

    for path in sorted(old_paths - new_paths):
        changes.append(f"- {path}: removed from seed")

    for path in sorted(old_paths & new_paths):
        old_entry = old_map[path]
        new_entry = new_map[path]
        diffs = []
        for field in ("remote", "branch", "commit"):
            old_value = old_entry.get(field)
            new_value = new_entry.get(field)
            if old_value != new_value:
                diffs.append(
                    f"{field} {format_field_value(field, old_value)} -> {format_field_value(field, new_value)}"
                )
        if diffs:
            diff_text = ", ".join(diffs)
            changes.append(f"~ {path}: {diff_text}")

    return changes


def show_pending_changes(changes: List[str]) -> None:
    print("Pending repositories.yaml updates:")
    for line in changes:
        print(f"  {line}")


def confirm_execution() -> bool:
    try:
        response = input("Apply these changes? [y/N]: ")
    except EOFError:
        return False
    return response.strip().lower() in {"y", "yes"}


def main(argv: List[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    seed_arg = args[0] if args else None
    seed_path = resolve_seed_path(seed_arg)
    print(f"Using seed file: {seed_path}")
    repos = discover_repositories()
    if not repos:
        print("No git repositories detected under", SRC_ROOT)
        return 1
    payload = build_seed_payload(repos)
    current_snapshot = load_existing_seed(seed_path)
    next_snapshot = index_repositories(payload)
    changes = summarize_seed_changes(current_snapshot, next_snapshot)
    if not changes:
        print(f"{seed_path.name} already up to date; no changes written.")
        print(f"Detected {len(repos)} repositories.")
        return 0
    show_pending_changes(changes)
    if not confirm_execution():
        print(f"Aborted. {seed_path.name} left unchanged.")
        return 0
    write_seed_file(seed_path, payload)
    print(f"Captured {len(repos)} repositories into {seed_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
