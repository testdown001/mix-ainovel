import asyncio
from types import SimpleNamespace

from app.agents.message import AgentResult
from app.agents.system import WritingAgentSystem


class _DummyAgent:
    def __init__(self, result: AgentResult):
        self._result = result
        self.received_contexts = []

    def set_stream_handler(self, stream_handler):
        self.stream_handler = stream_handler

    def set_archive_id(self, archive_id):
        self.archive_id = archive_id

    async def process(self, context):
        self.received_contexts.append(context)
        return self._result


def test_agent_system_passes_precollected_context_to_bingbu_flow_config():
    pre_collected_context = {
        "history_context": {"previous_summary": "上一章摘要"},
        "rag_context": {"chunks": ["片段 A"], "summaries": ["摘要 A"]},
        "rag_stats": {"mode": "simple", "chunks": 1, "summaries": 1},
    }

    taizi = _DummyAgent(
        AgentResult(
            status="completed",
            output={
                "parsed_command": {"intent": "generate"},
                "chapter_type": "普通章",
                "emotion_target": {"tone": "steady"},
                "writing_preferences": {"pace": "balanced"},
            },
        )
    )
    zhongshu = _DummyAgent(
        AgentResult(
            status="delegated",
            output={
                "writing_prompt": "prompt",
                "pre_collected_context": pre_collected_context,
            },
        )
    )
    bingbu = _DummyAgent(
        AgentResult(
            status="completed",
            output={
                "versions": [{"content": "章节正文", "version_id": "v1"}],
                "stages": {"generate": {"status": "ok"}},
            },
        )
    )

    system = WritingAgentSystem(session=SimpleNamespace(), archive_service=None)
    system._initialized = True
    system._agents = {
        "taizi": taizi,
        "zhongshu": zhongshu,
        "bingbu": bingbu,
    }

    result = asyncio.run(
        system.execute_chapter_generation(
            project_id="project-1",
            chapter_number=12,
            config={"preset": "basic", "versions": 1},
            user_id=42,
        )
    )

    assert result["version_count"] == 1
    assert zhongshu.received_contexts[0].metadata["user_id"] == 42
    assert (
        bingbu.received_contexts[0].metadata["flow_config"]["pre_collected_context"]
        == pre_collected_context
    )

