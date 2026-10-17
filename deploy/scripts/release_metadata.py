#!/usr/bin/env python3
"""Non-secret, read-only Git/build metadata and explicit deployment events.

No repository, Docker, or network mutation is performed by this helper. The
generated dotenv file is data, never sourced as shell code.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
import uuid


KEYS = (
    "APP_GIT_COMMIT", "APP_GIT_BRANCH", "APP_GIT_COMMIT_TIME", "APP_GIT_DIRTY",
    "APP_BUILT_AT", "APP_BUILD_ID", "APP_DEPLOYED_AT", "APP_DEPLOYMENT_ID",
    "APP_DEPLOYED_BUILD_ID",
)
DEPLOYMENT_KEYS = ("APP_DEPLOYED_AT", "APP_DEPLOYMENT_ID", "APP_DEPLOYED_BUILD_ID")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def git_value(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True,
            text=True, timeout=10, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        # A successful, empty git status means clean; a failed command does not.
        return None


def collect_build(root: Path) -> dict[str, str]:
    commit = git_value(root, "rev-parse", "--verify", "HEAD") or ""
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit):
        values = {key: utc_now() if key == "APP_BUILT_AT" else "" for key in KEYS[:5]}
        values["APP_BUILD_ID"] = uuid.uuid4().hex
        return values
    raw_time = git_value(root, "show", "-s", "--format=%cI", "HEAD") or ""
    try:
        commit_time = datetime.fromisoformat(raw_time).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        commit_time = ""
    status = git_value(root, "status", "--porcelain")
    return {
        "APP_GIT_COMMIT": commit.lower(),
        "APP_GIT_BRANCH": git_value(root, "symbolic-ref", "--quiet", "--short", "HEAD") or "",
        "APP_GIT_COMMIT_TIME": commit_time,
        "APP_GIT_DIRTY": "" if status is None else "true" if status else "false",
        "APP_BUILT_AT": utc_now(),
        "APP_BUILD_ID": uuid.uuid4().hex,
    }


def read_metadata(path: Path) -> dict[str, str]:
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key in KEYS and value.startswith("'") and value.endswith("'"):
                values[key] = value[1:-1].replace("\\'", "'")
    return values


def write_metadata(path: Path, values: dict[str, str]) -> None:
    """Atomic dotenv file, with literal single quotes to disable interpolation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Generated release metadata only; contains no credentials. Do not source this file."]
    for key in KEYS:
        value = values.get(key, "")
        if "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError(f"Invalid control character in {key}")
        lines.append(key + "='" + value.replace("'", "\\'") + "'")
    fd, temporary = tempfile.mkstemp(prefix=".release-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_deployment_env(path: Path, values: dict[str, str]) -> None:
    """Update only deployment keys; retain all other bytes and file identity.

    This keeps manual Compose recreate working on older Compose versions without
    an optional env_file feature or ever copying credentials into release files.
    """
    path = path.resolve(strict=True)
    original_stat = path.stat()
    original = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    found = set()
    lines = []
    for line in original.splitlines(keepends=True):
        match = re.match(rb"^[ \t]*(?:export[ \t]+)?(APP_DEPLOYED_AT|APP_DEPLOYMENT_ID|APP_DEPLOYED_BUILD_ID)[ \t]*=", line)
        if match:
            key = match[1].decode("ascii")
            ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
            line = (key + "=" + values[key]).encode("ascii") + ending
            found.add(key)
        lines.append(line)
    content = b"".join(lines)
    for key in DEPLOYMENT_KEYS:
        if key not in found:
            if content and not content.endswith(b"\n"):
                content += newline
            content += (key + "=" + values[key]).encode("ascii") + newline
    fd, temporary = tempfile.mkstemp(prefix=".release-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            os.fchmod(output.fileno(), stat.S_IMODE(original_stat.st_mode))
            os.fchown(output.fileno(), original_stat.st_uid, original_stat.st_gid)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def image_metadata(environ: dict[str, str]) -> dict[str, object]:
    """Docker builds without arguments remain valid and contain explicit unknowns."""
    raw_dirty = environ.get("APP_GIT_DIRTY", "").lower()
    return {
        "git_commit": environ.get("APP_GIT_COMMIT") or None,
        "git_branch": environ.get("APP_GIT_BRANCH") or None,
        "git_commit_time": environ.get("APP_GIT_COMMIT_TIME") or None,
        "git_dirty": {"true": True, "false": False}.get(raw_dirty),
        "built_at": environ.get("APP_BUILT_AT") or None,
        "build_id": environ.get("APP_BUILD_ID") or None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "deploy", "load", "image"))
    # Image mode copies this helper directly into /tmp; chained .parent remains
    # safe even when the script no longer has three distinct ancestor paths.
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent.parent)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--env-file", type=Path, help="Existing Compose configuration (deploy mode only)")
    args = parser.parse_args()
    if args.mode == "image":
        if args.file is None:
            parser.error("image requires --file")
        args.file.write_text(json.dumps(image_metadata(dict(os.environ)), ensure_ascii=True) + "\n", encoding="utf-8")
        return
    path = args.file or args.root / "deploy" / ".release.env"
    values = read_metadata(path)
    if args.mode == "build":
        values.update(collect_build(args.root))
    elif args.mode == "deploy":
        # Deliberately do not inspect host Git: an old image rollback retains its
        # original artifact; only this actual deployment event is new.
        values["APP_DEPLOYED_AT"] = utc_now()
        values["APP_DEPLOYMENT_ID"] = uuid.uuid4().hex
        # Explicit build identity, not a guess based on the host checkout or a
        # previous snapshot. A mismatch makes the API withhold deployment time.
        values["APP_DEPLOYED_BUILD_ID"] = os.environ.get("APP_BUILD_ID", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{0,128}", values["APP_DEPLOYED_BUILD_ID"]):
            parser.error("APP_BUILD_ID must contain only letters, digits, underscore or hyphen")
        env_file = args.env_file or args.root / "deploy" / ".env"
        if args.env_file is None and not env_file.is_file():
            env_file = args.root / ".env"
        update_deployment_env(env_file, values)
    if args.mode != "load":
        write_metadata(path, values)
    for key in KEYS:
        if key in values:
            print(f"export {key}={shlex.quote(values[key])}")


if __name__ == "__main__":
    main()
