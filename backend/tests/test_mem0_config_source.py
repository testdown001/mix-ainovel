"""mem0 通道配置来源回归测试。

历史 bug（2026-07-31 服务器实跑基线时从日志揪出）：`_build_mem0_config` 是全系统
唯一直读 `settings.*`（即 env）的 LLM 出口，而 env 按项目约定只是首次启动写入
SystemConfig 的**种子值**。线上后台改过 key 之后，容器 env 里仍是
`sk-PLACEHOLDER-replace-me` → mem0 每次调用 401 → premium 档长期记忆全废，
且因 best-effort except 而静默。

现改为与其余通道一致：SystemConfig 优先、env 兜底。
"""
import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.models.system_config import SystemConfig
from app.services.memory_layer_service import MemoryLayerService


async def _seed(db_session, **kv):
    for key, value in kv.items():
        db_session.add(SystemConfig(key=key.replace("__", "."), value=value))
    await db_session.commit()


@pytest.mark.asyncio
async def test_channel_config_comes_from_system_config(db_session, monkeypatch):
    """SystemConfig 里的真实 key 必须压过 env 里的占位符。"""
    monkeypatch.setenv("LLM_API_KEY", "sk-PLACEHOLDER-replace-me")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-PLACEHOLDER-replace-me")
    await _seed(
        db_session,
        llm__api_key="sk-real-llm",
        llm__base_url="https://real.example.com/v1",
        llm__model="gpt-5.5",
        embedding__api_key="jina-real",
        embedding__base_url="https://api.jina.ai/v1",
        embedding__model="jina-embeddings-v5-text-small",
    )

    cfg = await MemoryLayerService(db=db_session)._build_mem0_config()

    assert cfg["llm"]["config"]["api_key"] == "sk-real-llm"
    assert cfg["llm"]["config"]["openai_base_url"] == "https://real.example.com/v1"
    assert cfg["llm"]["config"]["model"] == "gpt-5.5"
    assert cfg["embedder"]["config"]["api_key"] == "jina-real"
    assert cfg["embedder"]["config"]["model"] == "jina-embeddings-v5-text-small"


@pytest.mark.asyncio
async def test_falls_back_to_env_when_system_config_absent(db_session, monkeypatch):
    """SystemConfig 无记录时回落 env（保持首次启动/裸部署可用）。"""
    monkeypatch.setenv("LLM_API_KEY", "sk-from-env")
    monkeypatch.setenv("LLM_BASE_URL", "https://env.example.com/v1")

    cfg = await MemoryLayerService(db=db_session)._build_mem0_config()

    assert cfg["llm"]["config"]["api_key"] == "sk-from-env"
    assert cfg["llm"]["config"]["openai_base_url"] == "https://env.example.com/v1"


@pytest.mark.asyncio
async def test_embedding_key_falls_back_to_llm_key(db_session, monkeypatch):
    """未单配 embedding key 时沿用 llm key（与 LLMService 口径一致）。"""
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    await _seed(db_session, llm__api_key="sk-shared")

    cfg = await MemoryLayerService(db=db_session)._build_mem0_config()

    assert cfg["embedder"]["config"]["api_key"] == "sk-shared"
