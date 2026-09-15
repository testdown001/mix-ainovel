import asyncio
import json

import httpx
import pytest

from app.utils.llm_tool import ChatMessage, OpenAIResponsesLLMClient


FORMAT = {"type": "json_schema", "json_schema": {"name": "Check", "strict": True,
          "schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}}


def _run(events, *, status=200):
    requests = []

    async def run():
        client = OpenAIResponsesLLMClient(api_key="test-key", base_url="https://provider.test/v1")
        await client._client.aclose()

        def respond(request):
            requests.append(json.loads(request.content))
            data = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
            if status != 200:
                return httpx.Response(status, json={"error": {"message": "Invalid schema"}})
            return httpx.Response(200, text=data, headers={"content-type": "text/event-stream"})

        client._client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            return [part async for part in client.stream_chat(
                messages=[ChatMessage(role="system", content="JSON"), ChatMessage(role="user", content="check")],
                model="gpt-6-astra", response_format=FORMAT, temperature=0.9, top_p=0.9,
                reasoning_effort="minimal",
            )]
        finally:
            await client.aclose()

    return asyncio.run(run()), requests


def test_responses_strict_payload_sampling_and_real_usage():
    parts, requests = _run([
        {"type": "response.output_text.delta", "delta": "{}"},
        {"type": "response.completed", "response": {"usage": {
            "input_tokens": 11, "output_tokens": 23, "total_tokens": 34}}},
    ])
    sent = requests[0]
    assert sent["text"]["format"]["strict"] is True
    assert sent["text"]["format"]["type"] == "json_schema"
    assert "temperature" not in sent and "top_p" not in sent
    assert sent["reasoning"]["effort"] == "low"
    assert parts[-1]["usage"]["total_tokens"] == 34


def test_responses_incomplete_is_length_and_reasoning_is_not_prose():
    parts, _ = _run([
        {"type": "response.reasoning_summary_text.delta", "delta": "private planning"},
        {"type": "response.incomplete", "response": {"incomplete_details": {"reason": "max_output_tokens"}}},
    ])
    assert parts[-1]["finish_reason"] == "length"
    assert not any(part.get("content") for part in parts)


def test_strict_schema_error_does_not_silently_remove_contract():
    with pytest.raises(httpx.HTTPStatusError):
        _run([], status=400)


def test_responses_eof_without_completion_is_failure():
    with pytest.raises(RuntimeError, match="未收到完成事件"):
        _run([{"type": "response.output_text.delta", "delta": "incomplete prose"}])
