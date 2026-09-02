import asyncio

from app.services.text_compression_service import TextCompressionService


def test_text_compression_service_strips_preamble_and_tail():
    raw = (
        "可以，下面是精简后的版本（控制在4000字以内）：\n\n"
        "正文第一句。正文第二句。\n\n"
        "您需要我帮您继续精简下一章吗？"
    )

    cleaned = TextCompressionService.strip_compression_preamble(raw)

    assert cleaned == "正文第一句。正文第二句。"


def test_text_compression_service_hard_trim_to_limit():
    text = "第一段。\n\n第二段很长很长很长。\n\n第三段。"
    trimmed = TextCompressionService.hard_trim_to_limit(text, 10)

    assert len(trimmed) <= 10


def test_text_compression_only_calls_llm_once_then_trims():
    class _StillTooLongLLM:
        def __init__(self):
            self.calls = []

        async def get_llm_response(self, **kwargs):
            self.calls.append(kwargs)
            return "压缩后正文。" * 100

    llm = _StillTooLongLLM()
    service = TextCompressionService(llm)
    result = asyncio.run(
        service.compress_overlength("原始正文。" * 200, target_max=120, user_id=1)
    )

    assert len(llm.calls) == 1
    assert llm.calls[0]["timeout"] == 60.0
    assert llm.calls[0]["max_retries"] == 0
    assert llm.calls[0]["reasoning_effort"] == "low"
    assert len(result) <= 120
