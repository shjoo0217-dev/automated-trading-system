"""Durable private Git storage, independent of the Codex/runner filesystem.

Uses the checkout action's short-lived GITHUB_TOKEN credential. No force push.
"""
import argparse
import os
import shutil
import subprocess
from pathlib import Path


def git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["restore", "save"])
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    state = args.state.resolve()
    worktree = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "kirs-state-store"
    branch = "kirs-data-state"
    if args.mode == "restore":
        remote = git("ls-remote", "--heads", "origin", branch, cwd=repo)
        if remote.stdout.strip():
            git("fetch", "origin", branch, "--depth=1", cwd=repo)
            git("worktree", "add", "--detach", str(worktree), "FETCH_HEAD", cwd=repo)
        else:
            git("worktree", "add", "--detach", str(worktree), "HEAD", cwd=repo)
        if (worktree / "runtime").exists():
            shutil.copytree(worktree / "runtime", state, dirs_exist_ok=True)
        state.mkdir(parents=True, exist_ok=True)
        return
    if not worktree.exists() or not state.exists():
        raise RuntimeError("Restore step/state missing; refusing blind persistence")
    if sum(p.stat().st_size for p in state.rglob("*") if p.is_file()) > 110_000_000:
        raise RuntimeError("Persistent storage cap exceeded")
    target = worktree / "runtime"
    shutil.copytree(state, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".lock", "staging", "*.tmp"))
    git("config", "user.name", "investment-data-bot", cwd=worktree)
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=worktree)
    git("add", "--", "runtime", cwd=worktree)
    if git("diff", "--cached", "--quiet", cwd=worktree, check=False).returncode == 0:
        print("No state changes")
        return
    git("commit", "-m", f"Checkpoint investment pipeline run {os.getenv('GITHUB_RUN_ID', 'manual')}", cwd=worktree)
    result = git("push", "origin", f"HEAD:refs/heads/{branch}", cwd=worktree, check=False)
    if result.returncode:
        # Never print potentially credential-bearing remote output.
        raise RuntimeError("State push failed or remote changed; no force push performed")
    print("State and immutable archive persisted to private branch " + branch)


if __name__ == "__main__": main()
