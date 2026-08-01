"""两遍制草稿-改写（路线三件套 ③，2026-08-01）。

针对「约束堆叠上限」与「防错非求好」：prompt_assembly 会把 26 个段落一次性堆进
同一个生成提示，其中约一半是「不许犯什么错」。模型在单次生成里既要把故事写好、
又要满足一张长清单，注意力被后者吃掉——写出来没毛病但也没劲。

两遍制把两件事拆开：第一遍只给事实与方向（求好），第二遍拿着草稿施加全部规则（防错）。

本文件锁住三件最容易出错的事：
1. 切分口径（规则进第二遍、事实留第一遍，未知标签默认进草稿=退化回现状而非饿死草稿）；
2. 第二遍是「改写」不是「重写」——缩水过多/校验不过/调用失败一律**退回草稿**，
   两遍制绝不能比一遍更差；
3. 第二遍不重灌全量上下文，否则只是把堆叠搬到了第二遍。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.services.two_pass_draft_service import TwoPassDraftService

_SECTIONS = [
    ("[当前章节目标]", "标题：破阵\n摘要：主角闯入丹阁"),
    ("[创作任务书](本章写作的核心执行指南，必须严格遵循)", "任务书正文"),
    ("[角色当前状态](数据库实时查询，零幻觉)", "沈青崖：警觉"),
    ("[检索到的剧情上下文](Markdown)", "前文片段"),
    ("[力量体系约束](角色能力上限，严禁超阶)", "不得超过筑基期"),
    ("[写作硬性约束](必须严格遵守)", "禁止使用「不由得」"),
    ("[禁止角色](本章不允许提及)", '["长老"]'),
    ("[作者风格指纹]", "短句为主"),
    ("[白金写作准则](硬约束)", "每章一个爽点"),
]


def _prompts(text="改写系统提示"):
    return SimpleNamespace(get_prompt=AsyncMock(return_value=text))


def _llm(response):
    return SimpleNamespace(get_llm_response=AsyncMock(return_value=response))


# --------------------------------------------------------------------------
# 1. 切分口径
# --------------------------------------------------------------------------

def test_partition_splits_facts_from_rules():
    draft, constraints = TwoPassDraftService.partition_sections(_SECTIONS)
    draft_labels = " ".join(l for l, _ in draft)
    constraint_labels = " ".join(l for l, _ in constraints)

    # 事实与方向留在第一遍
    assert "当前章节目标" in draft_labels
    assert "创作任务书" in draft_labels
    assert "角色当前状态" in draft_labels
    assert "检索到的剧情上下文" in draft_labels

    # 规则挪到第二遍
    for marker in ("力量体系约束", "写作硬性约束", "禁止角色", "作者风格指纹", "白金写作准则"):
        assert marker in constraint_labels, marker
        assert marker not in draft_labels, marker


def test_unknown_labels_default_to_draft():
    """未知标签默认进草稿：行为退化回「一次性堆叠」这个已知状态，
    而不是悄悄饿掉草稿的关键事实（前者可控，后者难查）。"""
    draft, constraints = TwoPassDraftService.partition_sections(
        [("[某个将来新增的段落]", "内容")]
    )
    assert len(draft) == 1 and not constraints


def test_empty_sections_are_dropped():
    draft, constraints = TwoPassDraftService.partition_sections(
        [("[当前章节目标]", ""), ("[写作硬性约束](必须严格遵守)", "")]
    )
    assert draft == [] and constraints == []


def test_draft_input_excludes_all_rules():
    draft, _ = TwoPassDraftService.partition_sections(_SECTIONS)
    text = TwoPassDraftService.build_draft_input(draft)
    assert "主角闯入丹阁" in text
    assert "不得超过筑基期" not in text     # 力量上限属规则
    assert "不由得" not in text             # 硬性约束属规则


# --------------------------------------------------------------------------
# 2. 第二遍输入形状：规则 + 少量锚点 + 草稿，不重灌全量上下文
# --------------------------------------------------------------------------

def test_rewrite_input_carries_rules_draft_and_minimal_anchors():
    _, constraints = TwoPassDraftService.partition_sections(_SECTIONS)
    text = TwoPassDraftService.build_rewrite_input(
        draft_text="草稿正文内容", constraint_sections=constraints, all_sections=_SECTIONS,
    )
    assert "草稿正文内容" in text
    assert "不得超过筑基期" in text          # 规则在
    assert "主角闯入丹阁" in text            # 章节目标作为锚点在
    assert "沈青崖：警觉" in text            # 角色状态作为锚点在
    # 但不该把检索上下文等全量事实再灌一遍——否则只是把堆叠搬到第二遍
    assert "前文片段" not in text
    assert "任务书正文" not in text


# --------------------------------------------------------------------------
# 3. 改写：任何异常都退回草稿，绝不能比一遍更差
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rewrite_applies_when_healthy():
    draft = "草稿" * 500
    revised = "改写后的正文" * 400
    text, report = await TwoPassDraftService().rewrite(
        draft_text=draft, sections=_SECTIONS,
        llm_service=_llm(revised), prompt_service=_prompts(), user_id=1,
    )
    assert text == revised
    assert report["applied"] is True
    assert report["constraint_sections"] == 5


@pytest.mark.asyncio
async def test_rewrite_falls_back_when_output_shrinks():
    """缩水过多说明模型把「改写」做成了「摘要」，宁可要原草稿。"""
    draft = "草稿内容" * 500
    text, report = await TwoPassDraftService().rewrite(
        draft_text=draft, sections=_SECTIONS,
        llm_service=_llm("太短了"), prompt_service=_prompts(), user_id=1,
    )
    assert text == draft
    assert report["applied"] is False
    assert report["reason"] == "shrunk_too_much"


@pytest.mark.asyncio
async def test_rewrite_falls_back_on_llm_error():
    draft = "草稿" * 500
    llm = SimpleNamespace(get_llm_response=AsyncMock(side_effect=RuntimeError("挂了")))
    text, report = await TwoPassDraftService().rewrite(
        draft_text=draft, sections=_SECTIONS,
        llm_service=llm, prompt_service=_prompts(), user_id=1,
    )
    assert text == draft
    assert report["applied"] is False
    assert report["reason"].startswith("error:")


@pytest.mark.asyncio
async def test_rewrite_falls_back_when_validation_fails():
    """产出不像正文（例如模型回了分析/清单）时退回草稿，与 optimizer/polish 同口径。"""
    draft = "草稿" * 500
    text, report = await TwoPassDraftService().rewrite(
        draft_text=draft, sections=_SECTIONS,
        llm_service=_llm("以下是我的修改说明：" * 200), prompt_service=_prompts(), user_id=1,
        validator=lambda _t: False,
    )
    assert text == draft
    assert report["reason"] == "validation_failed"


@pytest.mark.asyncio
async def test_rewrite_skipped_without_prompt_or_constraints():
    draft = "草稿" * 500

    # 缺提示词
    text, report = await TwoPassDraftService().rewrite(
        draft_text=draft, sections=_SECTIONS,
        llm_service=_llm("x"), prompt_service=_prompts(text=None), user_id=1,
    )
    assert text == draft and report["reason"] == "prompt_missing"

    # 没有任何规则要施加 → 第二遍纯属浪费一次调用
    llm = _llm("x")
    text, report = await TwoPassDraftService().rewrite(
        draft_text=draft, sections=[("[当前章节目标]", "目标")],
        llm_service=llm, prompt_service=_prompts(), user_id=1,
    )
    assert text == draft and report["reason"] == "no_constraints"
    llm.get_llm_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_rewrite_handles_empty_draft():
    text, report = await TwoPassDraftService().rewrite(
        draft_text="", sections=_SECTIONS,
        llm_service=_llm("x"), prompt_service=_prompts(), user_id=1,
    )
    assert text == "" and report["reason"] == "empty_draft"


# --------------------------------------------------------------------------
# 4. 门控
# --------------------------------------------------------------------------

def test_switch_defaults_off_and_is_flagship_only():
    from app.services.pipeline_config_service import PipelineConfig

    assert PipelineConfig().enable_two_pass_draft is False
