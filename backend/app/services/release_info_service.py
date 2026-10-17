"""Read the running artifact's identity, not GitHub's latest or a restart time."""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..schemas.system_info import SystemInformation

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_METADATA_PATH = _BACKEND_ROOT / "release-info.json"
_REPOSITORY_PATH = _BACKEND_ROOT.parent
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", re.IGNORECASE)
_LABEL = re.compile(r"[\w./@+:-]{1,200}")


def _commit(value: Any) -> str | None:
    if isinstance(value, str) and _COMMIT.fullmatch(value.strip()):
        return value.strip().lower()
    return None


def _label(value: Any) -> str | None:
    if not isinstance(value, str) or not _LABEL.fullmatch(value.strip()):
        return None
    # A misplaced URL/credential must not become a displayed branch/release ID.
    return None if "://" in value else value.strip()


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return {"true": True, "false": False, "1": True, "0": False}.get(value.strip().lower())
    return None


def _git(args: list[str], repository: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args], check=True, capture_output=True,
        text=True, timeout=2, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    ).stdout.strip()


def _development_git(repository: Path) -> dict:
    """Bounded read-only fallback for source checkouts; Docker does not need Git."""
    try:
        sha = _commit(_git(["rev-parse", "HEAD"], repository))
        if not sha:
            return {}
        branch = _git(["symbolic-ref", "--short", "-q", "HEAD"], repository)
    except subprocess.CalledProcessError:
        # Detached HEAD remains a valid immutable identity.
        try:
            sha = _commit(_git(["rev-parse", "HEAD"], repository))
            branch = None
        except (OSError, subprocess.SubprocessError):
            return {}
    except (OSError, subprocess.SubprocessError):
        return {}
    try:
        return {
            "git_commit": sha, "git_branch": branch,
            "git_commit_time": _git(["show", "-s", "--format=%cI", "HEAD"], repository),
            "git_dirty": bool(_git(["status", "--porcelain", "--untracked-files=normal"], repository)),
        }
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": sha, "git_branch": branch}


def get_system_information(
    *, metadata_path: Path | None = None, repository_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> SystemInformation:
    env = os.environ if environ is None else environ
    path = _METADATA_PATH if metadata_path is None else metadata_path
    data: dict = {}
    source = "unknown"
    artifact_present = False
    try:
        if path.exists():
            artifact_present = True
            if path.stat().st_size <= 16_384:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    data, source = payload, "image"
    except (OSError, ValueError, UnicodeError):
        # Do not substitute the host checkout when artifact metadata is broken.
        artifact_present = True

    if not artifact_present:
        if _commit(env.get("APP_GIT_COMMIT")):
            data = {key: env.get(var) for key, var in {
                "git_commit": "APP_GIT_COMMIT", "git_branch": "APP_GIT_BRANCH",
                "git_commit_time": "APP_GIT_COMMIT_TIME", "git_dirty": "APP_GIT_DIRTY",
                "built_at": "APP_BUILT_AT",
            }.items()}
            source = "environment"
        else:
            data = _development_git(_REPOSITORY_PATH if repository_path is None else repository_path)
            source = "git" if data.get("git_commit") else "unknown"

    deployed_at = _timestamp(env.get("APP_DEPLOYED_AT"))
    deployment_id = _label(env.get("APP_DEPLOYMENT_ID"))
    if artifact_present:
        # A persisted event for image A must not label a newly built/rolled-back
        # image B. Restarting the same image preserves the original event.
        build_id = _label(data.get("build_id"))
        if not build_id or env.get("APP_DEPLOYED_BUILD_ID") != build_id:
            deployed_at = deployment_id = None
    sha = _commit(data.get("git_commit"))
    return SystemInformation(
        git_commit=sha, git_short_commit=sha[:12] if sha else None,
        git_branch=_label(data.get("git_branch")), git_commit_time=_timestamp(data.get("git_commit_time")),
        git_dirty=_boolean(data.get("git_dirty")), built_at=_timestamp(data.get("built_at")),
        deployed_at=deployed_at, deployment_id=deployment_id, source=source,
    )
