# AIMETA P=Redis缓存服务_热点数据缓存|R=缓存管理_TTL控制|E=CacheService|X=internal|A=缓存服务|D=redis|S=net
"""
Redis 缓存服务 - 热点数据缓存层

核心功能：
1. 蓝图、角色、提示词等热点数据缓存
2. 自动 TTL 管理
3. 缓存失效和更新策略
4. 序列化/反序列化支持
"""
import json
import logging
from typing import Any, Optional, Dict, List
from datetime import timedelta
import redis.asyncio as aioredis
from redis.asyncio import Redis

from ..core.config import settings

logger = logging.getLogger(__name__)

# 全部已打开的 redis 客户端（CacheService 按实例懒建、从不关闭——CLI/脚本进程退出时
# 客户端在事件循环关闭后才被 GC 析构，__del__ 触发 "Event loop is closed" 噪音）
_open_clients: "set[Redis]" = set()


async def close_all_cache_clients() -> None:
    """关闭全部缓存 redis 连接。供 CLI/脚本在事件循环关闭前调用；Web 进程无需调用。"""
    for client in list(_open_clients):
        try:
            await client.aclose()
        except Exception:
            pass
        _open_clients.discard(client)


class CacheService:
    """
    Redis 缓存服务

    缓存策略：
    - 蓝图数据: TTL 1h
    - 角色设定: TTL 1h
    - 提示词模板: TTL 24h
    - 用户 LLM 配置: TTL 30m
    - 章节摘要: TTL 2h
    """

    # 缓存键前缀
    PREFIX_BLUEPRINT = "blueprint"
    PREFIX_CHARACTERS = "characters"
    PREFIX_PROMPT = "prompt"
    PREFIX_LLM_CONFIG = "llm_config"
    PREFIX_CHAPTER_SUMMARY = "chapter_summary"
    PREFIX_PROJECT = "project"
    PREFIX_PROJECT_SCHEMA = "project_schema"
    PREFIX_CHAPTER_OUTLINE = "chapter_outline"

    # TTL 配置（秒）
    TTL_BLUEPRINT = 3600  # 1 小时
    TTL_CHARACTERS = 3600  # 1 小时
    TTL_PROMPT = 86400  # 24 小时
    TTL_LLM_CONFIG = 1800  # 30 分钟
    TTL_CHAPTER_SUMMARY = 7200  # 2 小时
    TTL_PROJECT = 1800  # 30 分钟
    TTL_PROJECT_SCHEMA = 1800  # 30 分钟
    TTL_CHAPTER_OUTLINE = 3600  # 1 小时

    def __init__(self):
        self._redis: Optional[Redis] = None

    async def _get_redis(self) -> Redis:
        """获取 Redis 连接（懒加载）"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
            _open_clients.add(self._redis)
        return self._redis

    def _make_key(self, prefix: str, *args) -> str:
        """生成缓存键"""
        parts = [prefix] + [str(arg) for arg in args]
        return ":".join(parts)

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            redis = await self._get_redis()
            value = await redis.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Redis get 失败: key={key}, error={e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """设置缓存值"""
        try:
            redis = await self._get_redis()
            serialized = json.dumps(value, ensure_ascii=False)
            if ttl:
                await redis.setex(key, ttl, serialized)
            else:
                await redis.set(key, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis set 失败: key={key}, error={e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            redis = await self._get_redis()
            await redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete 失败: key={key}, error={e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """批量删除匹配的键"""
        try:
            redis = await self._get_redis()
            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis delete_pattern 失败: pattern={pattern}, error={e}")
            return 0

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            redis = await self._get_redis()
            return await redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis exists 失败: key={key}, error={e}")
            return False

    # ==================== 业务缓存方法 ====================

    async def get_blueprint(self, project_id: str) -> Optional[Dict]:
        """获取蓝图缓存"""
        key = self._make_key(self.PREFIX_BLUEPRINT, project_id)
        return await self.get(key)

    async def set_blueprint(self, project_id: str, blueprint: Dict) -> bool:
        """设置蓝图缓存"""
        key = self._make_key(self.PREFIX_BLUEPRINT, project_id)
        return await self.set(key, blueprint, self.TTL_BLUEPRINT)

    async def invalidate_blueprint(self, project_id: str) -> bool:
        """失效蓝图缓存"""
        key = self._make_key(self.PREFIX_BLUEPRINT, project_id)
        return await self.delete(key)

    async def get_characters(self, project_id: str) -> Optional[List[Dict]]:
        """获取角色列表缓存"""
        key = self._make_key(self.PREFIX_CHARACTERS, project_id)
        return await self.get(key)

    async def set_characters(self, project_id: str, characters: List[Dict]) -> bool:
        """设置角色列表缓存"""
        key = self._make_key(self.PREFIX_CHARACTERS, project_id)
        return await self.set(key, characters, self.TTL_CHARACTERS)

    async def invalidate_characters(self, project_id: str) -> bool:
        """失效角色列表缓存"""
        key = self._make_key(self.PREFIX_CHARACTERS, project_id)
        return await self.delete(key)

    async def get_prompt(self, template_name: str) -> Optional[str]:
        """获取提示词模板缓存"""
        key = self._make_key(self.PREFIX_PROMPT, template_name)
        return await self.get(key)

    async def set_prompt(self, template_name: str, content: str) -> bool:
        """设置提示词模板缓存"""
        key = self._make_key(self.PREFIX_PROMPT, template_name)
        return await self.set(key, content, self.TTL_PROMPT)

    async def invalidate_prompt(self, template_name: str) -> bool:
        """失效提示词模板缓存"""
        key = self._make_key(self.PREFIX_PROMPT, template_name)
        return await self.delete(key)

    async def invalidate_all_prompts(self) -> int:
        """失效所有提示词缓存"""
        pattern = f"{self.PREFIX_PROMPT}:*"
        return await self.delete_pattern(pattern)

    async def get_llm_config(self, user_id: int) -> Optional[Dict]:
        """获取用户 LLM 配置缓存"""
        key = self._make_key(self.PREFIX_LLM_CONFIG, user_id)
        return await self.get(key)

    async def set_llm_config(self, user_id: int, config: Dict) -> bool:
        """设置用户 LLM 配置缓存"""
        key = self._make_key(self.PREFIX_LLM_CONFIG, user_id)
        return await self.set(key, config, self.TTL_LLM_CONFIG)

    async def invalidate_llm_config(self, user_id: int) -> bool:
        """失效用户 LLM 配置缓存"""
        key = self._make_key(self.PREFIX_LLM_CONFIG, user_id)
        return await self.delete(key)

    async def get_chapter_summary(self, chapter_id: int) -> Optional[str]:
        """获取章节摘要缓存"""
        key = self._make_key(self.PREFIX_CHAPTER_SUMMARY, chapter_id)
        return await self.get(key)

    async def set_chapter_summary(self, chapter_id: int, summary: str) -> bool:
        """设置章节摘要缓存"""
        key = self._make_key(self.PREFIX_CHAPTER_SUMMARY, chapter_id)
        return await self.set(key, summary, self.TTL_CHAPTER_SUMMARY)

    async def invalidate_chapter_summary(self, chapter_id: int) -> bool:
        """失效章节摘要缓存"""
        key = self._make_key(self.PREFIX_CHAPTER_SUMMARY, chapter_id)
        return await self.delete(key)

    async def get_project(self, project_id: str, user_id: int) -> Optional[Dict]:
        """获取项目缓存"""
        key = self._make_key(self.PREFIX_PROJECT, user_id, project_id)
        return await self.get(key)

    async def set_project(self, project_id: str, user_id: int, project: Dict) -> bool:
        """设置项目缓存"""
        key = self._make_key(self.PREFIX_PROJECT, user_id, project_id)
        return await self.set(key, project, self.TTL_PROJECT)

    async def invalidate_project(self, project_id: str, user_id: int) -> bool:
        """失效项目缓存"""
        key = self._make_key(self.PREFIX_PROJECT, user_id, project_id)
        return await self.delete(key)

    async def get_project_schema(self, project_id: str) -> Optional[Dict]:
        """获取项目详情序列化缓存"""
        key = self._make_key(self.PREFIX_PROJECT_SCHEMA, project_id)
        return await self.get(key)

    async def set_project_schema(self, project_id: str, project: Dict) -> bool:
        """设置项目详情序列化缓存"""
        key = self._make_key(self.PREFIX_PROJECT_SCHEMA, project_id)
        return await self.set(key, project, self.TTL_PROJECT_SCHEMA)

    async def invalidate_project_schema(self, project_id: str) -> bool:
        """失效项目详情序列化缓存"""
        key = self._make_key(self.PREFIX_PROJECT_SCHEMA, project_id)
        return await self.delete(key)

    async def invalidate_user_projects(self, user_id: int) -> int:
        """失效用户所有项目缓存"""
        pattern = f"{self.PREFIX_PROJECT}:{user_id}:*"
        return await self.delete_pattern(pattern)

    # ==================== 级联失效方法 ====================

    async def invalidate_project_cascade(self, project_id: str, user_id: int) -> Dict[str, int]:
        """
        级联失效项目相关的所有缓存

        当项目数据发生变化时，需要同时失效：
        - 项目缓存
        - 蓝图缓存
        - 角色列表缓存
        - 章节大纲缓存

        Returns:
            Dict[str, int]: 各类缓存失效的数量统计
        """
        import asyncio

        results = await asyncio.gather(
            self.invalidate_project(project_id, user_id),
            self.invalidate_project_schema(project_id),
            self.invalidate_blueprint(project_id),
            self.invalidate_characters(project_id),
            self.delete_pattern(f"{self.PREFIX_CHAPTER_OUTLINE}:{project_id}:*"),
            return_exceptions=True,
        )

        return {
            "project": 1 if results[0] else 0,
            "project_schema": 1 if results[1] else 0,
            "blueprint": 1 if results[2] else 0,
            "characters": 1 if results[3] else 0,
            "chapter_outlines": results[4] if isinstance(results[4], int) else 0,
        }

    async def invalidate_chapter_cascade(self, project_id: str, chapter_number: int, user_id: int) -> Dict[str, int]:
        """
        级联失效章节相关的所有缓存

        当章节数据发生变化时，需要同时失效：
        - 章节大纲缓存
        - 章节摘要缓存
        - 项目缓存（因为项目包含章节列表）

        Returns:
            Dict[str, int]: 各类缓存失效的数量统计
        """
        import asyncio

        outline_key = self._make_key(self.PREFIX_CHAPTER_OUTLINE, project_id, chapter_number)

        results = await asyncio.gather(
            self.delete(outline_key),
            self.delete_pattern(f"{self.PREFIX_CHAPTER_SUMMARY}:*"),
            self.invalidate_project(project_id, user_id),
            self.invalidate_project_schema(project_id),
            return_exceptions=True,
        )

        return {
            "chapter_outline": 1 if results[0] else 0,
            "chapter_summaries": results[1] if isinstance(results[1], int) else 0,
            "project": 1 if results[2] else 0,
            "project_schema": 1 if results[3] else 0,
        }

    async def invalidate_blueprint_cascade(self, project_id: str, user_id: int) -> Dict[str, int]:
        """
        级联失效蓝图相关的所有缓存

        当蓝图数据发生变化时，需要同时失效：
        - 蓝图缓存
        - 项目缓存（因为项目包含蓝图）

        Returns:
            Dict[str, int]: 各类缓存失效的数量统计
        """
        import asyncio

        results = await asyncio.gather(
            self.invalidate_blueprint(project_id),
            self.invalidate_project(project_id, user_id),
            self.invalidate_project_schema(project_id),
            return_exceptions=True,
        )

        return {
            "blueprint": 1 if results[0] else 0,
            "project": 1 if results[1] else 0,
            "project_schema": 1 if results[2] else 0,
        }

    async def invalidate_characters_cascade(self, project_id: str, user_id: int) -> Dict[str, int]:
        """
        级联失效角色相关的所有缓存

        当角色数据发生变化时，需要同时失效：
        - 角色列表缓存
        - 项目缓存（因为项目包含角色列表）

        Returns:
            Dict[str, int]: 各类缓存失效的数量统计
        """
        import asyncio

        results = await asyncio.gather(
            self.invalidate_characters(project_id),
            self.invalidate_project(project_id, user_id),
            self.invalidate_project_schema(project_id),
            return_exceptions=True,
        )

        return {
            "characters": 1 if results[0] else 0,
            "project": 1 if results[1] else 0,
            "project_schema": 1 if results[2] else 0,
        }

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()


# 全局缓存服务实例
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """获取全局缓存服务实例"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
