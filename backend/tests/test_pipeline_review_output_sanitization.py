import asyncio
import json

from app.services.pipeline_review import PipelineReviewMixin


META_ONLY_OUTPUT = """1.  分析任务：
角色：擅长小说润色的文学编辑。
目标：在保持原有情节、人物关系、对话内容完全不变的前提下，提升文字的文学性和画面感，强化感官描写，润色对话个性，打磨叙事节奏。
限制：总字数不超过4000字，不增删情节，直接输出润色后的完整章节，不输出其他内容。

2.  原文本分析：
情节：直播恋综中，唐亦薇和林摆观点碰撞。
人物：
林摆：男主，看似摆烂实则被压迫。
唐亦薇：前妻，精英做派，控制狂。
氛围：从综艺的荒诞搞笑，到儿子出场后的窒息、心酸。
需要提升的地方：
画面感：场景细节可以更细腻。
感官描写：声音、触觉、视觉。
文学性：遣词造句更凝练。
"""

CHAPTER_BODY = (
    "雨声砸在青瓦上，沈砚推开窗，冷风卷着潮气扑进屋内。"
    "街口的灯笼被风吹得一晃一晃，红光落在他的指节上，像一层迟迟不肯退去的血色。"
    "他听见楼下有人压低声音争吵，茶盏碰在桌沿，发出短促的一声响。"
    "那声音让他想起昨夜未写完的信，也想起信尾被墨水洇开的名字。"
)


class _DummyLLMService:
    def __init__(self, response: str):
        self.response = response

    async def get_optimize_llm_response(self, **_kwargs):
        return self.response

    async def get_llm_response(self, **_kwargs):
        return self.response


class _ReviewHarness(PipelineReviewMixin):
    def __init__(self, response: str):
        self.llm_service = _DummyLLMService(response)


def test_run_polish_falls_back_when_response_contains_only_task_analysis():
    original = CHAPTER_BODY
    harness = _ReviewHarness(META_ONLY_OUTPUT)

    content, report = asyncio.run(harness._run_polish(original, user_id=1, max_word_count=4000))

    assert content == original
    assert report["applied"] is False
    assert report["reason"] == "invalid_chapter_response"


def test_run_optimizer_sanitizes_optimized_content_before_returning():
    response = json.dumps(
        {
            "optimized_content": META_ONLY_OUTPUT
            + "\n润色后内容：\n"
            + CHAPTER_BODY,
            "optimization_notes": "综合优化完成",
        },
        ensure_ascii=False,
    )
    harness = _ReviewHarness(response)

    content, report = asyncio.run(harness._run_optimizer("原文", user_id=1))

    assert content == CHAPTER_BODY
    assert report["steps"][0]["notes"] == "综合优化完成"
