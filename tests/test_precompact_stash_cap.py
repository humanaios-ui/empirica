"""Tests for the pre-compact stash cap (MAX_PRECOMPACT_STASHES).

Every pre-compact run stashes uncommitted work and pops it at the end. A run
killed in between leaves its stash orphaned, and nothing bounded how many
accumulated. The cap makes `_stash_uncommitted_work` skip stashing once the
limit is reached, leaving the work in the working tree.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS = Path(__file__).parent.parent / "empirica" / "plugins" / "claude-code-integration" / "hooks"


def _load_pre_compact():
    """Import the hyphenated pre-compact.py hook as a module."""
    sys.path.insert(0, str(_HOOKS))
    try:
        spec = importlib.util.spec_from_file_location("pre_compact_under_test", _HOOKS / "pre-compact.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(_HOOKS))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway git repo with one commit, cwd set to it."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "test")
    (tmp_path / "tracked.txt").write_text("v1\n")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _precompact_stash_count(repo: Path) -> int:
    lines = _git(repo, "stash", "list", "--format=%s").splitlines()
    return sum(1 for line in lines if "empirica: pre-compact" in line)


def test_stashes_when_under_cap(repo):
    mod = _load_pre_compact()
    (repo / "tracked.txt").write_text("dirty\n")

    assert mod._stash_uncommitted_work("abcdef12") is True
    assert _precompact_stash_count(repo) == 1
    assert (repo / "tracked.txt").read_text() == "v1\n"


def test_skips_stash_at_cap_and_keeps_work_in_tree(repo, capsys):
    mod = _load_pre_compact()

    # Fill the stash list to the cap with real pre-compact stashes.
    for i in range(mod.MAX_PRECOMPACT_STASHES):
        (repo / "tracked.txt").write_text(f"orphan {i}\n")
        assert mod._stash_uncommitted_work(f"orphan{i:02d}") is True
    assert _precompact_stash_count(repo) == mod.MAX_PRECOMPACT_STASHES

    (repo / "tracked.txt").write_text("new work\n")
    assert mod._stash_uncommitted_work("newsess1") is False

    # No new stash was added, and the uncommitted work is still in the tree.
    assert _precompact_stash_count(repo) == mod.MAX_PRECOMPACT_STASHES
    assert (repo / "tracked.txt").read_text() == "new work\n"
    assert "pre-compact stash skipped" in capsys.readouterr().err


def test_non_precompact_stashes_do_not_count(repo):
    mod = _load_pre_compact()
    _git(repo, "stash", "push", "-q", "-m", "manual unrelated stash")
    (repo / "tracked.txt").write_text("dirty\n")

    assert mod._count_precompact_stashes() == 0
    assert mod._stash_uncommitted_work("abcdef12") is True
