import asyncio
from types import SimpleNamespace

from app.agents.hybrid_executor import HybridExecutor


class _AgentSystemStub:
    async def execute_chapter_generation(self, **kwargs):
        return {
            "versions": [
                {
                    "version_id": 99,
                    "content": "agent generated text",
                    "word_count": 4,
                }
            ],
            "review_summaries": None,
            "archive_id": "archive-1",
        }


def test_agent_generation_path_returns_shared_generation_contract():
    executor = HybridExecutor(SimpleNamespace(), user_id=12)
    executor.agent_system = _AgentSystemStub()

    payload = asyncio.run(
        executor._use_agent_system(
            project_id="novel-1",
            chapter_number=2,
            writing_notes="more tension",
            flow_config={"versions": 1},
        )
    )

    assert payload["project_id"] == "novel-1"
    assert payload["chapter_number"] == 2
    assert payload["preset"] == "agent"
    assert payload["best_version_index"] == 0
    assert payload["variants"] == [
        {
            "index": 0,
            "version_id": 99,
            "content": "agent generated text",
            "metadata": {"version_id": 99, "word_count": 4},
        }
    ]
    assert payload["review_summaries"] == {}
    assert payload["archive_id"] == "archive-1"
