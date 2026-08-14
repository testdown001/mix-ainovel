# AIMETA P=提示词服务_提示模板管理|R=提示词加载_TTL缓存_CRUD_占位符护栏|NR=不含内容生成|E=PromptService|X=internal|A=服务类|D=sqlalchemy|S=db,fs|RD=./README.ai
import asyncio
import hashlib
import re
import time
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Prompt
from ..repositories.prompt_repository import PromptRepository
from ..schemas.prompt import PromptCreate, PromptRead, PromptUpdate

# 进程内缓存：name -> (PromptRead, 缓存时间)。
# 条目级 60s TTL 而非「启动 preload 后永久有效」：生产跑 3 个 app 副本，管理员在后台
# 改提示词只会写穿处理那次请求的副本，其余副本若永久缓存就一直用旧模板——后台显示
# 已保存、其实三分之二的生成还在用旧词。TTL 让任何副本的改动最迟 60 秒全集群生效，
# 零跨进程通信；每次生成读约 5-10 个模板、每模板每分钟至多回源一次 DB，开销可忽略。
_CACHE: Dict[str, Tuple[PromptRead, float]] = {}
_LOCK = asyncio.Lock()
_CACHE_TTL_SEC = 60.0

# prompts/*.md 模板目录（占位符护栏与「恢复默认」共用）
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _extract_placeholders(template: str) -> Set[str]:
    """提取模板中的 {identifier} 占位符集合（{{ }} 转义不算）。"""
    stripped = template.replace("{{", "").replace("}}", "")
    return set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", stripped))


class PromptService:
    """提示词服务，提供 TTL 缓存与 CRUD 能力。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PromptRepository(session)

    async def preload(self) -> None:
        """启动预热：整表载入缓存，避免首批请求逐个回源。"""
        prompts = await self.repo.list_all()
        now = time.monotonic()
        async with _LOCK:
            _CACHE.clear()
            _CACHE.update({item.name: (PromptRead.model_validate(item), now) for item in prompts})

    async def get_prompt(self, name: str) -> Optional[str]:
        now = time.monotonic()
        async with _LOCK:
            entry = _CACHE.get(name)
            if entry and now - entry[1] < _CACHE_TTL_SEC:
                return entry[0].content

        prompt = await self.repo.get_by_name(name)
        if not prompt:
            # 不缓存 miss：模板缺失是配置错误，让每次调用都有机会看到修复后的结果
            async with _LOCK:
                _CACHE.pop(name, None)
            return None

        prompt_read = PromptRead.model_validate(prompt)
        async with _LOCK:
            _CACHE[name] = (prompt_read, now)
        return prompt_read.content

    @staticmethod
    def _cache_put(prompt_read: PromptRead) -> None:
        _CACHE[prompt_read.name] = (prompt_read, time.monotonic())

    @staticmethod
    def render_prompt(template: str, /, **context: object) -> str:
        rendered: list[str] = []
        index = 0
        length = len(template)

        while index < length:
            char = template[index]
            if char == "{":
                if index + 1 < length and template[index + 1] == "{":
                    rendered.append("{")
                    index += 2
                    continue
                end = template.find("}", index + 1)
                if end != -1:
                    field_name = template[index + 1 : end]
                    if field_name.isidentifier() and field_name in context:
                        rendered.append(str(context[field_name]))
                        index = end + 1
                        continue
                rendered.append("{")
                index += 1
                continue
            if char == "}":
                if index + 1 < length and template[index + 1] == "}":
                    rendered.append("}")
                    index += 2
                    continue
                rendered.append("}")
                index += 1
                continue
            rendered.append(char)
            index += 1

        return "".join(rendered)

    async def list_prompts(self) -> list[PromptRead]:
        prompts = await self.repo.list_all()
        return [PromptRead.model_validate(item) for item in prompts]

    async def get_prompt_by_id(self, prompt_id: int) -> Optional[PromptRead]:
        instance = await self.repo.get(id=prompt_id)
        if not instance:
            return None
        return PromptRead.model_validate(instance)

    async def create_prompt(self, payload: PromptCreate) -> PromptRead:
        data = payload.model_dump()
        tags = data.get("tags")
        if tags is not None:
            data["tags"] = ",".join(tags)
        prompt = Prompt(**data)
        await self.repo.add(prompt)
        await self.session.commit()
        prompt_read = PromptRead.model_validate(prompt)
        async with _LOCK:
            self._cache_put(prompt_read)
        return prompt_read

    def _validate_placeholders(self, name: str, new_content: str) -> None:
        """占位符护栏：新内容不得缺失文件版模板的必需占位符。

        render_prompt 是宽松替换——缺了 {novel_title} 不会报错，只会带着字面量或残缺
        模板进 LLM，产出静默劣化且无人报警。以 prompts/{name}.md 的占位符集合为准；
        管理员自建的模板（无对应文件）跳过校验。
        """
        template_file = _PROMPTS_DIR / f"{name}.md"
        if not template_file.is_file():
            return
        required = _extract_placeholders(template_file.read_text(encoding="utf-8"))
        missing = required - _extract_placeholders(new_content)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"提示词缺少必需占位符：{', '.join(sorted('{' + m + '}' for m in missing))}。"
                    "这些变量会在生成时由系统填充，删除后产出会静默劣化。"
                ),
            )

    async def update_prompt(self, prompt_id: int, payload: PromptUpdate) -> Optional[PromptRead]:
        instance = await self.repo.get(id=prompt_id)
        if not instance:
            return None
        update_data = payload.model_dump(exclude_unset=True)
        if "content" in update_data and update_data["content"] is not None:
            self._validate_placeholders(instance.name, update_data["content"])
        if "tags" in update_data and update_data["tags"] is not None:
            update_data["tags"] = ",".join(update_data["tags"])
        # 注意：这里刻意不更新 prompt.checksum.{name}——checksum 语义是「上次与文件
        # 同步时的内容哈希」。管理员改动后 DB 哈希 ≠ checksum，启动同步据此判定
        # 「已被接管」而永不用 .md 覆盖（回头路走 reset_to_default）。
        await self.repo.update_fields(instance, **update_data)
        await self.session.commit()
        prompt_read = PromptRead.model_validate(instance)
        async with _LOCK:
            self._cache_put(prompt_read)
        return prompt_read

    async def delete_prompt(self, prompt_id: int) -> bool:
        instance = await self.repo.get(id=prompt_id)
        if not instance:
            return False
        await self.repo.delete(instance)
        await self.session.commit()
        async with _LOCK:
            _CACHE.pop(instance.name, None)
        return True

    async def reset_prompt_to_default(self, prompt_id: int) -> Optional[PromptRead]:
        """恢复默认：用 prompts/{name}.md 的文件内容覆盖 DB，并把 checksum 重置为
        文件哈希——此后该模板重新跟随 .md 的版本更新。

        管理员接管（后台改过）的模板永不被文件自动覆盖，这是显式的回头路。
        无对应文件（管理员自建模板）返回 None，调用方给 404。
        """
        from ..models.system_config import SystemConfig

        instance = await self.repo.get(id=prompt_id)
        if not instance:
            return None
        template_file = _PROMPTS_DIR / f"{instance.name}.md"
        if not template_file.is_file():
            return None

        content = template_file.read_text(encoding="utf-8")
        file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        await self.repo.update_fields(instance, content=content)

        checksum_key = f"prompt.checksum.{instance.name}"
        checksum = (
            await self.session.execute(select(SystemConfig).where(SystemConfig.key == checksum_key))
        ).scalars().first()
        if checksum:
            checksum.value = file_hash
        else:
            self.session.add(
                SystemConfig(
                    key=checksum_key,
                    value=file_hash,
                    description=f"Prompt checksum for auto sync: {instance.name}",
                )
            )
        await self.session.commit()

        prompt_read = PromptRead.model_validate(instance)
        async with _LOCK:
            self._cache_put(prompt_read)
        return prompt_read
