# AIMETA P=小说封面文件存储|R=路径约束_原子写入_项目删除清理|NR=不含图片生成_鉴权_计费|E=cover_path,write_cover_atomically,delete_cover_file|X=internal|A=文件存储|D=config|S=fs|RD=./README.ai
"""小说封面文件存储工具。

封面文件和作品记录是两种存储介质：生成时先原子替换文件再更新数据库；删除作品
则先提交数据库事务，再尽力清理文件，避免数据库回滚后封面已经不可恢复。
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from ..core.config import settings


def cover_path(project_id: str) -> Path:
    safe_id = "".join(ch for ch in project_id if ch.isalnum() or ch in {"-", "_"})
    if not safe_id or safe_id != project_id:
        raise ValueError("作品 ID 不合法")
    return Path(settings.cover_storage_dir) / f"{safe_id}.image"


def write_cover_atomically(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def delete_cover_file(project_id: str) -> bool:
    target = cover_path(project_id)
    if not target.exists():
        return False
    target.unlink()
    return True
