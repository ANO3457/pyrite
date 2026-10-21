"""Tests for WorktreeService: per-user git worktree management."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from pyrite.services.git_service import GitService
from pyrite.services.worktree_service import WorktreeInfo, WorktreeService
from pyrite.storage.database import PyriteDB


def _clean_git_env() -> dict[str, str]:
    """Env for a git subprocess isolated from any parent git process (e.g.
    pre-commit's pytest-check hook, itself a child of `git commit`, which
    sets GIT_DIR/GIT_INDEX_FILE/GIT_AUTHOR_* for its hook subprocesses --
    without this, a relative GIT_INDEX_FILE resolves against the wrong
    repo when `cwd` differs from the outer repo root)."""
    env = os.environ.copy()
    for var in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_AUTHOR_DATE",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "GIT_COMMITTER_DATE",
        "GIT_EDITOR",
    ):
        env.pop(var, None)
    return env


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    env = _clean_git_env()
    # `--initial-branch=main` is load-bearing: GitService hardcodes "main" as
    # the integration branch (merge_branch/reset_to_main), but bare `git init`
    # uses the host's `init.defaultBranch`, which is `master` on GitHub's
    # runners. Without this, six tests fail in CI only, with
    # "pathspec 'main' did not match any file(s) known to git", while passing
    # on any machine configured with init.defaultBranch=main.
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=str(path),
        capture_output=True,
        check=True,
        env=env,
        timeout=120,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
        env=env,
        timeout=120,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
        env=env,
        timeout=120,
    )
    # Create initial commit
    (path / "README.md").write_text("# Test KB\n")
    subprocess.run(
        ["git", "add", "."], cwd=str(path), capture_output=True, check=True, env=env, timeout=120
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(path),
        capture_output=True,
        check=True,
        env=env,
        timeout=120,
    )


def _make_config(kb_path: Path, kb_name: str = "test"):
    """Create a minimal PyriteConfig with one KB."""
    from pyrite.config import KBConfig, PyriteConfig, Settings

    kb = KBConfig(name=kb_name, path=kb_path, kb_type="generic")
    return PyriteConfig(
        knowledge_bases=[kb],
        settings=Settings(index_path=Path(tempfile.mkdtemp()) / "index.db"),
    )


class TestGitServiceEnvIsolation:
    """GitService subprocess calls must not inherit a parent git process's
    GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE / GIT_AUTHOR_* env vars.

    Root cause of the full-suite-only flake in this file: pre-commit's
    pytest-check hook runs `pytest tests/` as a child of `git commit`,
    which sets GIT_INDEX_FILE=.git/index (a path relative to the outer
    pyrite repo root) and GIT_AUTHOR_*/GIT_EDITOR for every hook
    subprocess. Any test that shells out to `git` with a different `cwd`
    and no explicit `env=` override inherits these vars, so the relative
    GIT_INDEX_FILE resolves against the wrong repo -- corrupting the
    fake tmp_path repo's git state (reproduced directly: `git commit`
    fails with a non-zero exit because it's reading/writing the outer
    repo's index, not the tmp_path repo's).
    """

    def test_reset_to_main_survives_leaked_parent_git_env(self, tmp_path, monkeypatch):
        """The same leak class as worktree_add, but exercised through
        WorktreeService.reset_to_main -> GitService/raw subprocess calls in
        worktree_service.py itself (_find_repo_root, reset_to_main)."""
        monkeypatch.setenv("GIT_DIR", str(tmp_path / "unrelated" / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "unrelated"))
        monkeypatch.setenv("GIT_INDEX_FILE", ".git/index")

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "kb").mkdir()
        (repo / "kb" / ".gitkeep").write_text("")
        _init_git_repo(repo)

        db = PyriteDB(tmp_path / "index.db")
        config = _make_config(repo / "kb", "test-kb")
        svc = WorktreeService(config, db)

        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt_path = Path(wt.worktree_path)

        (wt_path / "kb" / "temp.md").write_text("temp\n")
        env = _clean_git_env()
        subprocess.run(
            ["git", "add", "."], cwd=str(wt_path), capture_output=True, env=env, timeout=120
        )
        subprocess.run(
            ["git", "commit", "-m", "temp"],
            cwd=str(wt_path),
            capture_output=True,
            env=env,
            timeout=120,
        )

        result = svc.reset_to_main("test-kb", user_id=1)
        assert result.status == "active"
        assert not (wt_path / "kb" / "temp.md").exists()
        db.close()

    def test_worktree_add_survives_leaked_parent_git_env(self, tmp_path, monkeypatch):
        """Simulates running under a parent git process (e.g. a pre-commit
        hook) that has set GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE pointing
        elsewhere. GitService.worktree_add must still operate on the repo
        it was actually told to, not the leaked one."""
        monkeypatch.setenv("GIT_DIR", str(tmp_path / "unrelated" / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "unrelated"))
        monkeypatch.setenv("GIT_INDEX_FILE", ".git/index")

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        wt_path = tmp_path / "worktrees" / "alice"
        success, msg = GitService.worktree_add(repo, wt_path, "user/alice")

        assert success, msg
        assert wt_path.exists()
        assert (wt_path / "README.md").exists()


class TestGitServiceWorktree:
    """Test GitService worktree static methods against a real git repo."""

    def test_worktree_add_creates_directory(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        wt_path = tmp_path / "worktrees" / "alice"
        success, msg = GitService.worktree_add(repo, wt_path, "user/alice")

        assert success, msg
        assert wt_path.exists()
        assert (wt_path / "README.md").exists()

    def test_worktree_add_idempotent_existing_branch(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        wt1 = tmp_path / "wt1"
        success, _ = GitService.worktree_add(repo, wt1, "user/alice")
        assert success

        # Remove worktree but keep branch
        GitService.worktree_remove(repo, wt1, force=True)

        # Re-add with same branch name
        wt2 = tmp_path / "wt2"
        success, msg = GitService.worktree_add(repo, wt2, "user/alice")
        assert success, msg

    def test_worktree_list(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        GitService.worktree_add(repo, tmp_path / "wt-a", "user/alice")
        GitService.worktree_add(repo, tmp_path / "wt-b", "user/bob")

        worktrees = GitService.worktree_list(repo)
        # Main repo + 2 worktrees
        assert len(worktrees) >= 3
        branches = [wt.get("branch", "") for wt in worktrees]
        assert any("user/alice" in b for b in branches)
        assert any("user/bob" in b for b in branches)

    def test_worktree_remove(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        wt_path = tmp_path / "wt-remove"
        GitService.worktree_add(repo, wt_path, "user/temp")

        success, msg = GitService.worktree_remove(repo, wt_path)
        assert success, msg
        assert not wt_path.exists()

    def test_merge_branch_success(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        # Create a branch with a change
        wt_path = tmp_path / "wt-merge"
        GitService.worktree_add(repo, wt_path, "user/alice")
        (wt_path / "alice.md").write_text("# Alice's entry\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            ["git", "commit", "-m", "Alice's change"],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )

        # Merge into main
        success, msg = GitService.merge_branch(repo, "user/alice", into="main")
        assert success, msg
        assert (repo / "alice.md").exists()

    def test_merge_branch_conflict(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        # Create conflicting changes
        wt_path = tmp_path / "wt-conflict"
        GitService.worktree_add(repo, wt_path, "user/alice")

        # Change README on alice's branch
        (wt_path / "README.md").write_text("# Alice's version\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            ["git", "commit", "-m", "Alice changes README"],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )

        # Change README on main
        (repo / "README.md").write_text("# Main's version\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(repo),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            ["git", "commit", "-m", "Main changes README"],
            cwd=str(repo),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )

        # Merge should fail
        success, msg = GitService.merge_branch(repo, "user/alice", into="main")
        assert not success
        assert "conflict" in msg.lower() or "Merge" in msg

    def test_diff_branches(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        wt_path = tmp_path / "wt-diff"
        GitService.worktree_add(repo, wt_path, "user/alice")
        (wt_path / "new-entry.md").write_text("# New entry\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add entry"],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )

        success, diff = GitService.diff_branches(repo, "main", "user/alice")
        assert success
        assert "new-entry.md" in diff

        success, stat = GitService.diff_branches(repo, "main", "user/alice", stat_only=True)
        assert success
        assert "new-entry.md" in stat


class TestWorktreeService:
    """Test WorktreeService lifecycle against a real git repo + DB."""

    @pytest.fixture
    def setup(self, tmp_path):
        """Create a git repo, KB config, and PyriteDB."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        # Create a KB directory inside the repo
        kb_dir = repo / "kb"
        kb_dir.mkdir()
        (kb_dir / "test-entry.md").write_text(
            "---\nid: test-entry\ntitle: Test\ntype: note\n---\nBody\n"
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=str(repo),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add KB"],
            cwd=str(repo),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )

        config = _make_config(kb_dir, "test-kb")
        db = PyriteDB(tmp_path / "index.db")
        svc = WorktreeService(config, db)
        return {"repo": repo, "kb_dir": kb_dir, "config": config, "db": db, "svc": svc}

    def test_ensure_worktree_creates(self, setup):
        svc = setup["svc"]
        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")

        assert isinstance(wt, WorktreeInfo)
        assert wt.username == "alice"
        assert wt.kb_name == "test-kb"
        assert wt.branch == "user/alice"
        assert wt.status == "active"
        assert Path(wt.worktree_path).exists()

    def test_ensure_worktree_idempotent(self, setup):
        svc = setup["svc"]
        wt1 = svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt2 = svc.ensure_worktree("test-kb", user_id=1, username="alice")
        assert wt1.id == wt2.id
        assert wt1.worktree_path == wt2.worktree_path

    def test_get_worktree(self, setup):
        svc = setup["svc"]
        assert svc.get_worktree("test-kb", user_id=1) is None

        svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt = svc.get_worktree("test-kb", user_id=1)
        assert wt is not None
        assert wt.username == "alice"

    def test_list_worktrees(self, setup):
        svc = setup["svc"]
        svc.ensure_worktree("test-kb", user_id=1, username="alice")
        svc.ensure_worktree("test-kb", user_id=2, username="bob")

        wts = svc.list_worktrees("test-kb")
        assert len(wts) == 2
        names = {wt.username for wt in wts}
        assert names == {"alice", "bob"}

    def test_submit(self, setup):
        svc = setup["svc"]
        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")

        # Make a change in the worktree
        wt_path = Path(wt.worktree_path)
        (wt_path / "kb" / "new.md").write_text(
            "---\nid: new\ntitle: New\ntype: note\n---\nNew entry\n"
        )

        result = svc.submit("test-kb", user_id=1)
        assert result.status == "submitted"
        assert result.submitted_at is not None

    def test_get_submissions(self, setup):
        svc = setup["svc"]
        svc.ensure_worktree("test-kb", user_id=1, username="alice")
        svc.ensure_worktree("test-kb", user_id=2, username="bob")

        # Make changes and submit alice only
        wt = svc.get_worktree("test-kb", user_id=1)
        (Path(wt.worktree_path) / "kb" / "a.md").write_text(
            "---\nid: a\ntitle: A\ntype: note\n---\n"
        )
        svc.submit("test-kb", user_id=1)

        subs = svc.get_submissions("test-kb")
        assert len(subs) == 1
        assert subs[0].username == "alice"

    def test_reject(self, setup):
        svc = setup["svc"]
        svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt = svc.get_worktree("test-kb", user_id=1)
        (Path(wt.worktree_path) / "kb" / "a.md").write_text(
            "---\nid: a\ntitle: A\ntype: note\n---\n"
        )
        svc.submit("test-kb", user_id=1)

        result = svc.reject("test-kb", user_id=1, feedback="Needs more detail")
        assert result.status == "rejected"
        assert result.feedback == "Needs more detail"

    def test_merge(self, setup):
        svc = setup["svc"]
        repo = setup["repo"]

        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt_path = Path(wt.worktree_path)

        # Add a new file in the worktree
        (wt_path / "kb" / "alice-entry.md").write_text(
            "---\nid: alice-entry\ntitle: Alice Entry\ntype: note\n---\nAlice wrote this\n"
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            ["git", "commit", "-m", "Alice's entry"],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )

        success, msg = svc.merge("test-kb", user_id=1)
        assert success, msg
        # File should now exist in main repo
        assert (repo / "kb" / "alice-entry.md").exists()

        # Status should be merged
        wt = svc.get_worktree("test-kb", user_id=1)
        assert wt.status == "merged"

    def test_reset_to_main(self, setup):
        svc = setup["svc"]
        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt_path = Path(wt.worktree_path)

        # Make a change
        (wt_path / "kb" / "temp.md").write_text("temp\n")
        subprocess.run(
            ["git", "add", "."],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            ["git", "commit", "-m", "temp"],
            cwd=str(wt_path),
            capture_output=True,
            env=_clean_git_env(),
            timeout=120,
        )

        # Reset
        result = svc.reset_to_main("test-kb", user_id=1)
        assert result.status == "active"
        assert not (wt_path / "kb" / "temp.md").exists()

    def test_delete_worktree(self, setup):
        svc = setup["svc"]
        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt_path = Path(wt.worktree_path)
        assert wt_path.exists()

        result = svc.delete_worktree("test-kb", user_id=1)
        assert result is True
        assert not wt_path.exists()
        assert svc.get_worktree("test-kb", user_id=1) is None

    def test_get_user_kb_config(self, setup):
        svc = setup["svc"]
        svc.ensure_worktree("test-kb", user_id=1, username="alice")

        user_config = svc.get_user_kb_config("test-kb", user_id=1)
        assert user_config is not None
        assert user_config.name == "test-kb"
        assert "alice" in str(user_config.path)
        assert user_config.path != setup["config"].get_kb("test-kb").path

    def test_get_user_diff_db(self, setup):
        svc = setup["svc"]
        svc.ensure_worktree("test-kb", user_id=1, username="alice")

        diff_db = svc.get_user_diff_db("test-kb", user_id=1)
        assert diff_db is not None
        assert isinstance(diff_db, PyriteDB)
        diff_db.close()

    def test_no_worktree_returns_none(self, setup):
        svc = setup["svc"]
        assert svc.get_worktree("test-kb", user_id=99) is None
        assert svc.get_user_kb_config("test-kb", user_id=99) is None
        assert svc.get_user_diff_db("test-kb", user_id=99) is None

    def test_submit_fails_and_leaves_unsubmitted_when_commit_fails(
        self, setup, monkeypatch, tmp_path
    ):
        svc = setup["svc"]
        repo = setup["repo"]
        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")
        wt_path = Path(wt.worktree_path)

        # Make commit fail by unsetting git identity and forcing config only
        empty_cfg = tmp_path / "empty_gitconfig"
        empty_cfg.write_text("")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_cfg))
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        for target in (repo, wt_path):
            subprocess.run(
                ["git", "config", "--unset-all", "user.name"], cwd=str(target), env=_clean_git_env()
            )
            subprocess.run(
                ["git", "config", "--unset-all", "user.email"],
                cwd=str(target),
                env=_clean_git_env(),
            )
            subprocess.run(
                ["git", "config", "user.useConfigOnly", "true"],
                cwd=str(target),
                env=_clean_git_env(),
                check=True,
            )

        # Make a change in the worktree
        (wt_path / "kb" / "fail.md").write_text("uncommitted edit\n")

        from pyrite.exceptions import StorageError

        with pytest.raises(StorageError):
            svc.submit("test-kb", user_id=1)

        wt_after = svc.get_worktree("test-kb", user_id=1)
        assert wt_after.status == "active"
        assert wt_after.submitted_at is None

    def test_merge_refuses_when_nothing_committed(self, setup):
        svc = setup["svc"]
        wt = svc.ensure_worktree("test-kb", user_id=1, username="alice")

        # Status set to submitted, but nothing committed on branch
        setup["db"]._raw_conn.execute(
            "UPDATE worktree SET status = 'submitted' WHERE id = ?",
            (wt.id,),
        )
        setup["db"]._raw_conn.commit()

        success, msg = svc.merge("test-kb", user_id=1)
        assert not success
        assert "nothing committed" in msg.lower()
        wt_after = svc.get_worktree("test-kb", user_id=1)
        assert wt_after.status != "merged"

    def test_worktree_rest_flow_identity_unset(self, tmp_path, monkeypatch):
        """REST flow: POST /api/worktree/submit fails with STORAGE_ERROR when git
        identity is unset and leaves worktree unsubmitted; admin merge does not report
        merged: true (#1174)."""
        from fastapi.testclient import TestClient
        from tests.auth_seed import SESSION_COOKIE, seed_and_sign_in

        from pyrite.config import AuthConfig, KBConfig, PyriteConfig, Settings
        from pyrite.server.api import create_app, get_config, get_db

        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)

        # Unset git identity so commit fails
        empty_cfg = tmp_path / "empty_gitconfig"
        empty_cfg.write_text("")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty_cfg))
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        subprocess.run(
            ["git", "config", "--unset-all", "user.name"], cwd=str(repo), env=_clean_git_env()
        )
        subprocess.run(
            ["git", "config", "--unset-all", "user.email"], cwd=str(repo), env=_clean_git_env()
        )
        subprocess.run(
            ["git", "config", "user.useConfigOnly", "true"],
            cwd=str(repo),
            env=_clean_git_env(),
            check=True,
        )

        kb_dir = repo / "kb"
        kb_dir.mkdir()
        (kb_dir / "root.md").write_text("# Root\n")
        subprocess.run(
            ["git", "-c", "user.name=Setup", "-c", "user.email=setup@example.com", "add", "."],
            cwd=str(repo),
            check=True,
            env=_clean_git_env(),
            timeout=120,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Setup",
                "-c",
                "user.email=setup@example.com",
                "commit",
                "-m",
                "Add kb",
            ],
            cwd=str(repo),
            check=True,
            env=_clean_git_env(),
            timeout=120,
        )

        db_path = tmp_path / "index.db"
        config = PyriteConfig(
            knowledge_bases=[KBConfig(name="test-kb", path=kb_dir, kb_type="generic")],
            settings=Settings(
                index_path=db_path,
                auth=AuthConfig(enabled=True, allow_registration=True),
            ),
        )

        app = create_app(config=config)
        db = PyriteDB(db_path)
        app.dependency_overrides[get_config] = lambda: config
        app.dependency_overrides[get_db] = lambda: db

        admin_client = TestClient(app)
        seed_and_sign_in(admin_client, "admin", role="admin")

        alice_client = TestClient(app)
        alice_user = seed_and_sign_in(alice_client, "alice", role="write")

        # Create alice's worktree and make an uncommitted edit
        wt_svc = WorktreeService(config, db)
        wt = wt_svc.ensure_worktree("test-kb", alice_user["id"], "alice")
        wt_path = Path(wt.worktree_path)
        (wt_path / "kb" / "alice-draft.md").write_text("# Draft\n")

        # 1. User calls POST /api/worktree/submit
        res = alice_client.post("/api/worktree/submit", json={"kb": "test-kb"})
        assert res.status_code == 500, res.text
        assert res.json()["detail"]["code"] == "STORAGE_ERROR"

        # Assert worktree is left unsubmitted
        wt_status = alice_client.get("/api/worktree/status", params={"kb": "test-kb"})
        assert wt_status.status_code == 200
        assert wt_status.json()["status"] == "active"
        assert wt_svc.get_worktree("test-kb", alice_user["id"]).status == "active"

        # 2. Admin calls POST /api/admin/merge-queue/alice/merge
        merge_res = admin_client.post("/api/admin/merge-queue/alice/merge", json={"kb": "test-kb"})
        assert merge_res.status_code == 400
        assert "not 'submitted'" in merge_res.json()["detail"]
        assert merge_res.json().get("merged") is not True

        # And direct service merge also refuses when nothing is committed
        ok, msg = wt_svc.merge("test-kb", alice_user["id"])
        assert not ok
        assert "nothing committed" in msg.lower()

        # The uncommitted change never reached main
        assert not (kb_dir / "alice-draft.md").exists()
        db.close()
