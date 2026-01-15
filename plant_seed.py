#!/usr/bin/env python3
"""Clone or update repositories listed in repositories.yaml into ../."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

SRC_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = SRC_ROOT.parent
CONFIG_DIR = Path(__file__).resolve().parent / "config" / "seeds"
DEFAULT_SEED_BASENAME = "repositories"


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
class RepoSpec:
    name: str
    path: Path
    remote: str
    branch: str
    commit: str


@dataclass
class RepoPlan:
    spec: RepoSpec
    status: str
    steps: List[str]
    needs_action: bool


class SeedError(RuntimeError):
    pass


def relpath_from_src(path: Path) -> str:
    return os.path.relpath(path, SRC_ROOT)


def format_repo_label(path: Path) -> str:
    relative = relpath_from_src(path)
    if path == WORKSPACE_ROOT:
        return f"[root] {WORKSPACE_ROOT.name}"
    return relative


def ensure_within_workspace(path: Path) -> None:
    try:
        path.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise SeedError(f"Path escapes workspace root: {path}") from exc


def run(cmd: List[str], cwd: Path | None = None) -> str:
    if cmd and cmd[0] == "git":
        printable = " ".join(shlex.quote(part) for part in cmd)
        print(f"[git] {printable}", flush=True)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SeedError(result.stderr.strip() or "Command failed: " + " ".join(cmd))
    return result.stdout.strip()


def is_git_repository(path: Path) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "rev-parse",
            "--is-inside-work-tree",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def ensure_remote_origin(path: Path, remote_url: str) -> None:
    remotes = run(["git", "-C", str(path), "remote"], cwd=None).splitlines()
    remotes = [r.strip() for r in remotes if r.strip()]
    if "origin" in remotes:
        current_url = run(["git", "-C", str(path), "remote", "get-url", "origin"], cwd=None)
        if current_url != remote_url:
            run(["git", "-C", str(path), "remote", "set-url", "origin", remote_url], cwd=None)
    else:
        run(["git", "-C", str(path), "remote", "add", "origin", remote_url], cwd=None)


def git_fetch(path: Path) -> None:
    run(["git", "-C", str(path), "fetch", "--all", "--tags", "--prune"], cwd=None)


def git_checkout(path: Path, branch: str, commit: str) -> None:
    if branch and branch != "HEAD":
        run(["git", "-C", str(path), "checkout", "-B", branch, commit], cwd=None)
    else:
        run(["git", "-C", str(path), "checkout", "--detach", commit], cwd=None)


def git_reset_hard(path: Path, commit: str) -> None:
    run(["git", "-C", str(path), "reset", "--hard", commit], cwd=None)


def git_update_submodules(path: Path) -> None:
    run(
        ["git", "-C", str(path), "submodule", "update", "--init", "--recursive"],
        cwd=None,
    )


def clone_repo(remote: str, destination: Path) -> None:
    run(["git", "clone", remote, str(destination)])


def describe_remote_action(path: Path, remote_url: str) -> str | None:
    remotes = run(["git", "-C", str(path), "remote"], cwd=None).splitlines()
    remotes = [r.strip() for r in remotes if r.strip()]
    if "origin" not in remotes:
        return f"add origin pointing to {remote_url}"
    current_url = run(["git", "-C", str(path), "remote", "get-url", "origin"], cwd=None)
    if current_url != remote_url:
        return f"set origin URL to {remote_url}"
    return None


def get_repo_state(path: Path) -> tuple[str, str]:
    branch = run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"], cwd=None)
    commit = run(["git", "-C", str(path), "rev-parse", "HEAD"], cwd=None)
    return branch, commit


def load_seed(seed_path: Path) -> List[RepoSpec]:
    if not seed_path.exists():
        raise SeedError(f"Seed file not found: {seed_path}")
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    repositories = data.get("repositories")
    if not isinstance(repositories, list):
        raise SeedError("Seed file is missing a 'repositories' list")
    specs: List[RepoSpec] = []
    for entry in repositories:
        try:
            rel_path = Path(entry["path"])
            resolved = (SRC_ROOT / rel_path).resolve()
            ensure_within_workspace(resolved)
            specs.append(
                RepoSpec(
                    name=entry["name"],
                    path=resolved,
                    remote=entry["remote"],
                    branch=entry["branch"],
                    commit=entry["commit"],
                )
            )
        except KeyError as exc:
            raise SeedError(f"Missing key in seed entry: {entry}") from exc
        except Exception as exc:
            raise SeedError(f"Invalid entry in seed file: {entry}") from exc
    return specs


def plan_repo(spec: RepoSpec) -> RepoPlan:
    target = spec.path
    steps: List[str] = []
    needs_action = True
    if target.exists():
        if not is_git_repository(target):
            raise SeedError(f"Path exists but is not a git repo: {target}")
        current_branch, current_commit = get_repo_state(target)
        if current_branch == spec.branch and current_commit == spec.commit:
            summary_branch = current_branch or "HEAD"
            return RepoPlan(
                spec=spec,
                status="up-to-date",
                steps=[f"already on {summary_branch} @ {current_commit[:12]}"]
                if current_commit
                else ["already matches seed"],
                needs_action=False,
            )
        status = "update existing repo"
        remote_action = describe_remote_action(target, spec.remote)
        if remote_action:
            steps.append(remote_action)
        steps.append("fetch --all --tags --prune")
    else:
        status = "clone new repo"
        steps.append(f"clone from {spec.remote}")
    checkout_desc = (
        f"checkout branch {spec.branch} at {spec.commit[:12]}"
        if spec.branch and spec.branch != "HEAD"
        else f"checkout detached HEAD at {spec.commit[:12]}"
    )
    steps.append(checkout_desc)
    steps.append(f"reset --hard {spec.commit[:12]}")
    steps.append("update submodules (init --recursive)")
    return RepoPlan(spec=spec, status=status, steps=steps, needs_action=needs_action)


def show_plan(plans: List[RepoPlan]) -> None:
    print("Pending git actions:\n")
    for idx, plan in enumerate(plans, 1):
        label = format_repo_label(plan.spec.path)
        print(f"{idx}. {label} ({plan.status})")
        for step in plan.steps:
            print(f"   - {step}")
        print()


def confirm_execution() -> bool:
    try:
        response = input("Proceed with git operations? [y/N]: ")
    except EOFError:
        return False
    return response.strip().lower() in {"y", "yes"}


def ensure_repo(spec: RepoSpec) -> bool:
    target = spec.path
    if target.exists():
        if not is_git_repository(target):
            raise SeedError(f"Path exists but is not a git repo: {target}")
        current_branch, current_commit = get_repo_state(target)
        if current_branch == spec.branch and current_commit == spec.commit:
            return False
        ensure_remote_origin(target, spec.remote)
        git_fetch(target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        clone_repo(spec.remote, target)
    git_checkout(target, spec.branch, spec.commit)
    git_reset_hard(target, spec.commit)
    git_update_submodules(target)
    return True


IGNORED_ORPHANS = {"_raisin_seed"}


def find_orphan_repos(specs: List[RepoSpec]) -> List[Path]:
    tracked = {spec.path.resolve() for spec in specs}
    orphans: List[Path] = []
    for entry in SRC_ROOT.iterdir():
        if not entry.is_dir():
            continue
        if entry.name in IGNORED_ORPHANS:
            continue
        git_dir = entry / ".git"
        if git_dir.exists() and entry.resolve() not in tracked:
            ensure_within_workspace(entry)
            orphans.append(entry)
    return sorted(orphans)


def show_orphan_plan(orphans: List[Path]) -> None:
    if not orphans:
        # print("No extra git repositories detected in src/\n")
        return
    print("Repositories to be removed (not present in seed):\n")
    for idx, orphan in enumerate(orphans, 1):
        print(f"{idx}. {format_repo_label(orphan)}")
    print()


def delete_repo(path: Path) -> None:
    if not path.exists():
        return
    ensure_within_workspace(path)
    shutil.rmtree(path)


def main(argv: List[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        seed_arg = args[0] if args else None
        seed_path = resolve_seed_path(seed_arg)
        print(f"Using seed file: {seed_path}")
        specs = load_seed(seed_path)
        if not specs:
            print("No repositories to plant.")
            return 0
        plans = [plan_repo(spec) for spec in specs]
        orphan_repos = find_orphan_repos(specs)
        show_plan(plans)
        show_orphan_plan(orphan_repos)
        if not any(plan.needs_action for plan in plans):
            if not orphan_repos:
                print("All repositories already match the seed.")
                return 0
        if not confirm_execution():
            print("Aborted. No git commands executed.")
            return 0
        for plan in plans:
            label = format_repo_label(plan.spec.path)
            if not plan.needs_action:
                print(f"Skipping {label} (already matches seed).")
                continue
            print(f"Syncing {label} ...", end=" ")
            changed = ensure_repo(plan.spec)
            if changed:
                print("done")
            else:
                print("already up-to-date")
        for orphan in orphan_repos:
            label = format_repo_label(orphan)
            print(f"Removing {label} ...", end=" ")
            delete_repo(orphan)
            print("deleted")
        return 0
    except SeedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
