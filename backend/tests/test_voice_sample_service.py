from app.services.voice_sample_service import VoiceSampleService


def test_voice_sample_service_returns_empty_for_single_character():
    service = VoiceSampleService()
    result = __import__("asyncio").run(
        service.generate_voice_samples(
            characters=[{"name": "林玄", "role": "主角", "personality": "冷静"}],
            outline_summary="测试",
            chapter_mission=None,
            user_id=1,
        )
    )

    assert result == ""
