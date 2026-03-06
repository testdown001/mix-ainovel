# AIMETA P=缓存服务_Redis缓存操作|R=缓存读写_失效|NR=不含业务逻辑|E=CacheService|X=internal|A=服务类|D=redis|S=cache|RD=./README.ai
import redis
import redis.asyncio as aioredis
import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

from ..core.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis 缓存服务，async 方法使用异步客户端，sync 方法使用同步客户端。"""
    
    def __init__(self, redis_url: Optional[str] = None):
        redis_dsn = (redis_url or settings.redis_url or "redis://localhost:6379/0").strip()
        self._sync_client: Optional[redis.Redis] = None
        self._async_client: Optional[aioredis.Redis] = None

        try:
            self._sync_client = redis.from_url(redis_dsn, decode_responses=True)
            self._sync_client.ping()
            self._async_client = aioredis.from_url(redis_dsn, decode_responses=True)
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败: {e}，缓存功能将被禁用")
            self._sync_client = None
            self._async_client = None
        
        self.EMOTION_CURVE_TTL = 7 * 24 * 3600  # 7 天
        self.EMOTION_META_TTL = 24 * 3600  # 1 天
        self.EMOTION_TASK_TTL = 3600  # 1 小时

    @property
    def redis_client(self) -> Optional[redis.Redis]:
        """向后兼容：返回同步客户端供外部直接使用。"""
        return self._sync_client
    
    def is_available(self) -> bool:
        """检查 Redis 是否可用"""
        return self._sync_client is not None

    async def get(self, key: str) -> Optional[Any]:
        """通用读取接口，供异步路由直接调用。"""
        if not self._async_client:
            return None

        try:
            data = await self._async_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"读取缓存失败: key={key}, error={e}")
            return None

    async def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """通用写入接口，供异步路由直接调用。"""
        if not self._async_client:
            return False

        try:
            payload = json.dumps(value, default=str, ensure_ascii=False)
            if expire and expire > 0:
                await self._async_client.setex(key, expire, payload)
            else:
                await self._async_client.set(key, payload)
            return True
        except Exception as e:
            logger.warning(f"写入缓存失败: key={key}, error={e}")
            return False

    async def delete(self, key: str) -> bool:
        """通用删除接口，供异步路由直接调用。"""
        if not self._async_client:
            return False

        try:
            await self._async_client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"删除缓存失败: key={key}, error={e}")
            return False
    
    def get_emotion_curve(self, novel_id: str) -> Optional[Dict]:
        """获取缓存的情感曲线"""
        if not self.is_available():
            return None
        
        try:
            key = f"emotion_curve:{novel_id}"
            data = self._sync_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"获取情感曲线缓存失败: {e}")
        
        return None
    
    def set_emotion_curve(self, novel_id: str, data: Dict) -> bool:
        """设置情感曲线缓存"""
        if not self.is_available():
            return False
        
        try:
            key = f"emotion_curve:{novel_id}"
            self._sync_client.setex(
                key,
                self.EMOTION_CURVE_TTL,
                json.dumps(data, default=str, ensure_ascii=False)
            )
            logger.info(f"情感曲线缓存已设置: {novel_id}")
            return True
        except Exception as e:
            logger.warning(f"设置情感曲线缓存失败: {e}")
            return False
    
    def get_emotion_meta(self, novel_id: str) -> Optional[Dict]:
        """获取情感分析元数据"""
        if not self.is_available():
            return None
        
        try:
            key = f"emotion_meta:{novel_id}"
            data = self._sync_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"获取情感元数据缓存失败: {e}")
        
        return None
    
    def set_emotion_meta(self, novel_id: str, meta: Dict) -> bool:
        """设置情感分析元数据"""
        if not self.is_available():
            return False
        
        try:
            key = f"emotion_meta:{novel_id}"
            self._sync_client.setex(
                key,
                self.EMOTION_META_TTL,
                json.dumps(meta, default=str, ensure_ascii=False)
            )
            logger.info(f"情感元数据缓存已设置: {novel_id}")
            return True
        except Exception as e:
            logger.warning(f"设置情感元数据缓存失败: {e}")
            return False
    
    def get_chapter_emotion(self, novel_id: str, chapter_id: str) -> Optional[Dict]:
        """获取单个章节的情感缓存"""
        if not self.is_available():
            return None
        
        try:
            key = f"emotion:{novel_id}:{chapter_id}"
            data = self._sync_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"获取章节情感缓存失败: {e}")
        
        return None
    
    def set_chapter_emotion(self, novel_id: str, chapter_id: str, data: Dict) -> bool:
        """设置单个章节的情感缓存"""
        if not self.is_available():
            return False
        
        try:
            key = f"emotion:{novel_id}:{chapter_id}"
            self._sync_client.setex(
                key,
                self.EMOTION_CURVE_TTL,
                json.dumps(data, default=str, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.warning(f"设置章节情感缓存失败: {e}")
            return False
    
    def invalidate_emotion_cache(self, novel_id: str) -> bool:
        """清除情感曲线缓存"""
        if not self.is_available():
            return False
        
        try:
            keys = self._sync_client.keys(f"emotion*:{novel_id}*")
            if keys:
                self._sync_client.delete(*keys)
                logger.info(f"已清除情感曲线缓存: {novel_id}")
            return True
        except Exception as e:
            logger.warning(f"清除情感曲线缓存失败: {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取异步任务状态"""
        if not self.is_available():
            return None
        
        try:
            key = f"task:{task_id}"
            data = self._sync_client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"获取任务状态失败: {e}")
        
        return None
    
    def set_task_status(self, task_id: str, status: Dict) -> bool:
        """设置异步任务状态"""
        if not self.is_available():
            return False
        
        try:
            key = f"task:{task_id}"
            self._sync_client.setex(
                key,
                self.EMOTION_TASK_TTL,
                json.dumps(status, default=str, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.warning(f"设置任务状态失败: {e}")
            return False
