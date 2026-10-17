"""Deployment is an explicit event, not GitHub HEAD, image build or process boot."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routers import admin
from app.core.dependencies import get_current_user
from app.schemas.system_info import SystemInformation
from app.schemas.user import UserInDB
from app.services import release_info_service as release


def image(tmp_path, **overrides):
    metadata = {
        "git_commit": "a" * 40, "git_branch": "main", "git_dirty": False,
        "git_commit_time": "2026-10-17T08:00:00+08:00", "built_at": "2026-10-17T01:00:00Z",
        "build_id": "build-a",
    }
    metadata.update(overrides)
    path = tmp_path / "release-info.json"
    path.write_text(json.dumps(metadata))
    return path


def test_image_identity_wins_over_environment_and_checkout(tmp_path, monkeypatch):
    path = image(tmp_path)
    monkeypatch.setattr(release, "_development_git", lambda _: pytest.fail("image must not inspect host Git"))
    result = release.get_system_information(metadata_path=path, environ={
        "APP_GIT_COMMIT": "b" * 40, "APP_DEPLOYED_BUILD_ID": "build-a",
        "APP_DEPLOYED_AT": "2026-10-17T02:00:00Z", "APP_DEPLOYMENT_ID": "release-a",
        "OPENAI_API_KEY": "secret-never-returned",
    })
    assert result.source == "image" and result.git_commit == "a" * 40
    assert result.git_short_commit == "a" * 12
    assert result.git_commit_time == datetime(2026, 10, 17, tzinfo=timezone.utc)
    assert result.deployed_at == datetime(2026, 10, 17, 2, tzinfo=timezone.utc)
    assert "secret-never-returned" not in result.model_dump_json()


@pytest.mark.parametrize("binding", [None, "build-b", ""])
def test_old_deployment_event_cannot_label_another_image(tmp_path, binding):
    env = {"APP_DEPLOYED_AT": "2026-10-17T02:00:00Z", "APP_DEPLOYMENT_ID": "old-release"}
    if binding is not None:
        env["APP_DEPLOYED_BUILD_ID"] = binding
    result = release.get_system_information(metadata_path=image(tmp_path), environ=env)
    assert result.deployed_at is None and result.deployment_id is None
    assert result.built_at is not None


def test_same_image_restart_preserves_deployment_time(tmp_path):
    path = image(tmp_path)
    env = {"APP_DEPLOYED_AT": "2026-10-17T02:00:00Z", "APP_DEPLOYMENT_ID": "release-a",
           "APP_DEPLOYED_BUILD_ID": "build-a"}
    first = release.get_system_information(metadata_path=path, environ=env)
    assert release.get_system_information(metadata_path=path, environ=env) == first
    assert first.deployed_at != first.built_at


@pytest.mark.parametrize("content", ["not json", "[]", "x" * 17000])
def test_unreadable_metadata_never_uses_host_checkout(tmp_path, monkeypatch, content):
    path = tmp_path / "release-info.json"
    path.write_text(content)
    monkeypatch.setattr(release, "_development_git", lambda _: pytest.fail("do not guess host HEAD"))
    result = release.get_system_information(metadata_path=path, environ={"APP_GIT_COMMIT": "b" * 40})
    assert result.source == "unknown" and result.git_commit is None and result.deployed_at is None


def test_artifact_without_git_arguments_is_unknown_not_the_hosts_new_commit(tmp_path):
    result = release.get_system_information(metadata_path=image(tmp_path, git_commit=None, build_id=None),
        environ={"APP_GIT_COMMIT": "b" * 40, "APP_DEPLOYED_AT": "2026-10-17T02:00:00Z"})
    assert result.source == "image" and result.git_commit is None and result.deployed_at is None


def test_explicit_non_container_environment_supports_sha256(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "_development_git", lambda _: pytest.fail("explicit metadata must win"))
    result = release.get_system_information(metadata_path=tmp_path / "missing", environ={
        "APP_GIT_COMMIT": "F" * 64, "APP_GIT_BRANCH": "feature/version-info",
        "APP_GIT_DIRTY": "false", "APP_GIT_COMMIT_TIME": "2026-10-17T00:00:00Z",
        "APP_DEPLOYED_AT": "2026-10-17T02:00:00Z",
    })
    assert result.source == "environment" and result.git_commit == "f" * 64
    assert result.git_dirty is False and result.deployed_at is not None
    assert result.built_at is None


@pytest.mark.parametrize("timestamp", ["yesterday", "2026-10-17", "2026-10-17T02:00:00", "", None])
def test_no_naive_or_fabricated_timestamp(tmp_path, timestamp):
    result = release.get_system_information(metadata_path=image(tmp_path, built_at=timestamp), environ={
        "APP_DEPLOYED_AT": timestamp, "APP_DEPLOYED_BUILD_ID": "build-a",
    })
    assert result.built_at is None and result.deployed_at is None


def test_local_checkout_is_read_only_and_distinguishes_dirty_and_detached(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()
    git("init")
    git("config", "user.name", "release-test")
    git("config", "user.email", "release@example.com")
    git("checkout", "-b", "feature/version-info")
    (repo / "file.txt").write_text("test")
    git("add", "file.txt")
    git("commit", "-m", "test release")
    result = release.get_system_information(metadata_path=tmp_path / "missing", repository_path=repo, environ={})
    assert result.source == "git" and result.git_commit == git("rev-parse", "HEAD")
    assert result.git_dirty is False and result.deployed_at is None and result.built_at is None
    (repo / "untracked.txt").write_text("not returned")
    dirty = release.get_system_information(metadata_path=tmp_path / "missing", repository_path=repo, environ={})
    assert dirty.git_dirty is True and "untracked.txt" not in dirty.model_dump_json()
    git("checkout", "--detach")
    detached = release.get_system_information(metadata_path=tmp_path / "missing", repository_path=repo, environ={})
    assert detached.git_commit == result.git_commit and detached.git_branch is None


def test_missing_git_or_git_timeout_is_a_normal_unknown_state(tmp_path, monkeypatch):
    def timeout(*args):
        raise subprocess.TimeoutExpired("git", 2)
    monkeypatch.setattr(release, "_git", timeout)
    result = release.get_system_information(metadata_path=tmp_path / "missing", environ={})
    assert result.source == "unknown" and result.git_commit is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role,expected", [(None, 401), (False, 403), (True, 200)])
async def test_endpoint_is_administrator_only_and_not_cached(monkeypatch, role, expected):
    app = FastAPI()
    app.include_router(admin.router)
    if role is not None:
        async def user():
            return UserInDB(id=1, username="user", hashed_password="x", is_admin=role)
        app.dependency_overrides[get_current_user] = user
    monkeypatch.setattr(admin, "get_system_information", lambda: SystemInformation(
        git_commit="a" * 40, git_short_commit="a" * 12, source="image"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/admin/system-info")
    assert response.status_code == expected
    if expected == 200:
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["git_commit"] == "a" * 40
        assert set(response.json()) == set(SystemInformation.model_fields)
