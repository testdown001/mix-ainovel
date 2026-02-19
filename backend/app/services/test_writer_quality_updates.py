# AIMETA P=写作质量更新回归测试|R=采样评审_护栏本地修补_推荐版本序列化|NR=不含生产代码|E=pytest|X=internal|A=测试函数|D=pytest|S=none|RD=./README.ai
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.ai_review_service import AIReviewService
from app.services.chapter_guardrails import GuardrailResult, Violation, ChapterGuardrails
from app.services.novel_service import NovelService


def test_ai_review_uses_head_middle_tail_sampling_for_long_text():
    long_text = "A" * 1400 + "B" * 1400 + "C" * 1400
    sampled, is_sampled = AIReviewService._sample_content_for_review(long_text)

    assert is_sampled is True
    assert "[开头片段]" in sampled
    assert "[中段片段]" in sampled
    assert "[结尾片段]" in sampled
    assert "A" * 200 in sampled
    assert "B" * 200 in sampled
    assert "C" * 200 in sampled


def test_ai_review_keeps_short_text_without_sampling():
    short_text = "这是一个短文本"
    sampled, is_sampled = AIReviewService._sample_content_for_review(short_text)
    assert is_sampled is False
    assert sampled == short_text


def test_guardrail_local_patch_fixes_forbidden_name_and_omniscient_cue():
    guardrails = ChapterGuardrails()
    text = "与此同时，张三走进门内。"
    result = GuardrailResult(
        passed=False,
        violations=[
            Violation(
                type="omniscient_cue",
                severity="medium",
                description="出现全知视角 cue 词「与此同时」",
            ),
            Violation(
                type="forbidden_name",
                severity="high",
                description="出现了禁止角色「张三」的名字",
            ),
        ],
    )

    patched = guardrails.apply_local_patches(text, result)
    assert "与此同时" not in patched
    assert "张三" not in patched
    assert "那人" in patched


def test_guardrail_local_patch_strips_markdown_and_trims_trailing_camera():
    guardrails = ChapterGuardrails()
    text = "**小标题**\n他转身离开。身后传来脚步。"
    trailing_pos = text.find("身后")
    result = GuardrailResult(
        passed=False,
        violations=[
            Violation(
                type="markdown_marker",
                severity="medium",
                description="正文包含 Markdown 标签「**小标题**」",
            ),
            Violation(
                type="trailing_camera",
                severity="high",
                description="章末滞后镜头",
                position=trailing_pos,
            ),
        ],
    )

    patched = guardrails.apply_local_patches(text, result)
    assert "**" not in patched
    assert "身后传来脚步" not in patched


def test_chapter_schema_includes_recommended_version_from_ai_review():
    service = NovelService(session=None)  # _build_chapter_schema 不依赖 session

    now = datetime.utcnow()
    version1 = SimpleNamespace(
        id=11,
        content="版本一",
        created_at=now,
        metadata={"ai_review": {"is_best": False}, "foo": "bar"},
        version_label="v1",
    )
    version2 = SimpleNamespace(
        id=12,
        content="版本二",
        created_at=now + timedelta(seconds=1),
        metadata={"ai_review": {"is_best": True}},
        version_label="v2",
    )
    selected_version = version1

    chapter = SimpleNamespace(
        chapter_number=1,
        real_summary="真实摘要",
        selected_version=selected_version,
        selected_version_id=selected_version.id,
        versions=[version2, version1],  # 故意打乱顺序，验证按 created_at 排序
        evaluations=[],
        status="waiting_for_confirm",
        word_count=1234,
    )
    outline = SimpleNamespace(chapter_number=1, title="第一章", summary="摘要")
    project = SimpleNamespace(outlines=[outline], chapters=[chapter])

    schema = service._build_chapter_schema(project, 1, include_content=True)

    assert schema.versions == ["版本一", "版本二"]
    assert schema.version_metadata is not None
    assert schema.version_metadata[0]["version_id"] == 11
    assert schema.version_metadata[1]["version_id"] == 12
    assert schema.recommended_version_index == 1
    assert schema.word_count == 1234

