import asyncio

from app.services.generation_telemetry_service import GenerationTelemetryService


def test_generation_telemetry_service_emits_middle_product_payload():
    emitted = []

    async def _emit_stream(event, payload=None):
        emitted.append((event, payload))

    service = GenerationTelemetryService(_emit_stream)

    asyncio.run(service.emit_context_plan({"chapter_phase": "climax"}))
    asyncio.run(service.emit_verification_report({"summary": "验证完成"}))

    assert emitted[0][0] == "middle_product"
    assert emitted[0][1]["type"] == "context_plan"
    assert emitted[0][1]["data"]["chapter_phase"] == "climax"
    assert emitted[1][1]["type"] == "verification_report"
    assert emitted[1][1]["data"]["summary"] == "验证完成"
