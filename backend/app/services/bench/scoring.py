# AIMETA P=基准评分器|R=机械评分_LLM绝对评审_LLM成对对比|NR=不做生成不落库|E=mechanical_score_judge_absolute_judge_pairwise|X=internal|A=评分工具|D=novel_bench_service_humanization_llm_service|S=none
"""基准评分器：机械评分（零 LLM）+ LLM 评审（绝对分 / 成对对比）。

- mechanical_score：复用 NovelBenchLiteService（长度/must_include/verification）
  + HumanizationService.scan 人味分 + 结尾钩子启发式 + 4-gram 重复度 + 段落统计，
  全部零 LLM 成本。
- judge_absolute：prompts/bench_judge.md 六维 1-10 绝对评分（generate_structured，
  grader 通道优先，未配置降级默认通道）。
- judge_pairwise：prompts/bench_judge_pair.md A/B 对比选优；同一对做两次调用
  （A/B 互换位置）消除位置偏差，两次一致才计胜负，不一致记 tie。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from ..context_planner_service import ContextPlan
from ..humanization_service import HumanizationService
from ..llm_service import LLMService
from ..novel_bench_service import NovelBenchCase, NovelBenchLiteService
from .fixtures import BenchScenario

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"

# 结尾钩子启发式所用信号词
_SUSPENSE_WORDS = (
    "突然", "忽然", "竟", "却", "没想到", "就在这时", "就在此刻",
    "变故", "杀机", "危险", "阴影", "不对劲", "来了",
)
_DIALOGUE_MARKS = ("“", "”", "「", "」")


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _fill(template: str, mapping: Dict[str, str]) -> str:
    """按仓库提示词模板惯例填充 {{key}} 占位符（纯替换，不用 str.format 以免正文含花括号出错）。"""
    for key, value in mapping.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in (text or "").split("\n") if p.strip()]


# ---------------------------------------------------------------------------
# 机械评分（零 LLM）
# ---------------------------------------------------------------------------
def _ending_hook_heuristic(text: str) -> Dict[str, Any]:
    """结尾钩子启发式：末段短且含对话/问句/悬念标点（或悬念信号词）。"""
    paragraphs = _split_paragraphs(text)
    last = paragraphs[-1] if paragraphs else ""
    signals: List[str] = []
    if last and len(last) <= 100:
        signals.append("short_paragraph")
    if "？" in last or "?" in last:
        signals.append("question")
    if "！" in last or "!" in last:
        signals.append("exclamation")
    if "…" in last:
        signals.append("ellipsis")
    if any(mark in last for mark in _DIALOGUE_MARKS):
        signals.append("dialogue")
    if any(word in last for word in _SUSPENSE_WORDS):
        signals.append("suspense_word")
    has_hook = "short_paragraph" in signals and len(signals) >= 2
    return {
        "has_hook": has_hook,
        "last_paragraph_chars": len(last),
        "signals": signals,
    }


def _repetition_metrics(text: str, n: int = 4, window_chars: int = 3000) -> Dict[str, Any]:
    """n-gram distinct ratio：越接近 1 重复度越低。

    定长口径：只对正文（去空白后）前 window_chars 字计算（不足取全量）——
    distinct ratio 随文本变长天然下降，定长窗口消除长度伪影，
    不同配置产出不同长度的正文才可比。
    """
    compact = re.sub(r"\s+", "", text or "")[:window_chars]
    total = max(0, len(compact) - n + 1)
    if total <= 0:
        return {
            "ngram": n, "window_chars": window_chars,
            "total_ngrams": 0, "distinct_ratio": 1.0,
        }
    grams = {compact[i : i + n] for i in range(total)}
    return {
        "ngram": n,
        "window_chars": window_chars,
        "total_ngrams": total,
        "distinct_ratio": round(len(grams) / total, 4),
    }


def _paragraph_stats(text: str) -> Dict[str, Any]:
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return {"count": 0, "avg_chars": 0.0, "dialogue_ratio": 0.0}
    dialogue = sum(1 for p in paragraphs if any(mark in p for mark in _DIALOGUE_MARKS))
    return {
        "count": len(paragraphs),
        "avg_chars": round(sum(len(p) for p in paragraphs) / len(paragraphs), 1),
        "dialogue_ratio": round(dialogue / len(paragraphs), 4),
    }


def _empty_plan() -> ContextPlan:
    """无 verification 任务的空计划：NovelBenchLiteService 仅做长度/必含词评分。"""
    return ContextPlan(
        intent={},
        chapter_phase="development",
        retrieval_tasks=[],
        skill_policies=[],
        prompt_modules=[],
        verification_tasks=[],
    )


def mechanical_score(
    chapter_text: str,
    scenario: BenchScenario,
    review_summaries: Optional[Dict[str, Any]] = None,
    *,
    target_min_chars: int = 1200,
    target_max_chars: int = 12000,
) -> Dict[str, Any]:
    """零 LLM 成本的机械评分。

    review_summaries 可选：跑批时若拿得到管线的评审摘要可传入，让
    NovelBenchLiteService 的 verification 维度有数据；单纯离线打分传 None。
    """
    text = chapter_text or ""
    case = NovelBenchCase(
        case_id=scenario.scenario_id,
        project_id="",
        chapter_number=scenario.target_chapter,
        target_min_chars=target_min_chars,
        target_max_chars=target_max_chars,
        must_include=list(scenario.must_include),
    )
    bench_lite = NovelBenchLiteService().evaluate_case(
        case=case,
        chapter_text=text,
        plan=_empty_plan(),
        evidence_summary={},
        review_summaries=review_summaries or {},
    )

    # scan() 是纯静态分析，不触碰 session/llm —— 构造参数仅为满足签名
    humanization_report = HumanizationService(session=None, llm_service=None).scan(text)

    return {
        "length": len(text),
        "bench_lite": bench_lite,
        "humanization": humanization_report.to_dict(),
        "ending_hook": _ending_hook_heuristic(text),
        "repetition": _repetition_metrics(text),
        "paragraphs": _paragraph_stats(text),
    }


# ---------------------------------------------------------------------------
# LLM 评审
# ---------------------------------------------------------------------------
class JudgeDimension(BaseModel):
    """单维评分：1-10 + 一句话理由。"""

    score: float = Field(ge=0, le=10)
    reason: str = ""


class AbsoluteJudgement(BaseModel):
    """六维绝对评分结果（与 prompts/bench_judge.md 的输出约定一致）。"""

    immersion: JudgeDimension
    pacing: JudgeDimension
    hook: JudgeDimension
    character: JudgeDimension
    prose: JudgeDimension
    outline_fit: JudgeDimension


class PairwiseJudgement(BaseModel):
    """A/B 对比结果（与 prompts/bench_judge_pair.md 的输出约定一致）。"""

    winner: Literal["A", "B", "tie"]
    reason: str = ""


def _scenario_context(scenario: BenchScenario) -> Dict[str, str]:
    blueprint = scenario.blueprint or {}
    outline = next(
        (o for o in scenario.outlines if o.chapter_number == scenario.target_chapter), None
    )
    prior = "\n".join(
        f"第{item.chapter_number}章《{item.title}》：{item.summary}"
        for item in scenario.prior_chapters
    )
    return {
        "genre": str(blueprint.get("genre") or ""),
        "style": str(blueprint.get("style") or ""),
        "one_sentence_summary": str(blueprint.get("one_sentence_summary") or ""),
        "chapter_number": str(scenario.target_chapter),
        "outline_title": outline.title if outline else "",
        "outline_summary": outline.summary if outline else "",
        "prior_summaries": prior or "（无）",
    }


def _make_judge_responder(llm_service: LLMService, temperature: float, used: Dict[str, str]):
    """评审出口：grader 通道优先；未配置（ValueError）则降级默认通道。

    get_grader_llm_response 的降级语义：llm_grader.* 完全未配置时
    _resolve_grader_llm_config 返回 None → 抛 ValueError（发生在真实调用之前），
    其余异常（网络/超时等）原样上抛。
    """

    async def _respond(prompt: str, system_prompt: str) -> str:
        try:
            reply = await llm_service.get_grader_llm_response(
                system_prompt,
                [{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=180.0,
                max_tokens=2000,
            )
            used["channel"] = "grader"
            return reply
        except ValueError:
            used["channel"] = "default"
            return await llm_service.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                response_format="json_object",
            )

    return _respond


async def judge_absolute(
    llm_service: LLMService,
    chapter_text: str,
    scenario: BenchScenario,
    *,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """六维（沉浸感/节奏/钩子/人物/文笔/大纲契合）1-10 绝对评分。"""
    template = _load_prompt("bench_judge")
    prompt = _fill(template, {**_scenario_context(scenario), "chapter_text": chapter_text or ""})
    used: Dict[str, str] = {"channel": "grader"}
    result = await llm_service.generate_structured(
        prompt=prompt,
        schema=AbsoluteJudgement,
        system_prompt="你是苛刻的资深网文主编，只输出 JSON。",
        temperature=temperature,
        responder=_make_judge_responder(llm_service, temperature, used),
    )
    data: Dict[str, Any] = result.model_dump()
    scores = [dimension["score"] for dimension in data.values()]
    data["overall"] = round(sum(scores) / len(scores), 2)
    data["judge_channel"] = used["channel"]
    return data


async def _judge_pair_once(
    llm_service: LLMService,
    first: str,
    second: str,
    scenario: BenchScenario,
    temperature: float,
    used: Dict[str, str],
) -> PairwiseJudgement:
    template = _load_prompt("bench_judge_pair")
    prompt = _fill(
        template,
        {**_scenario_context(scenario), "text_a": first or "", "text_b": second or ""},
    )
    return await llm_service.generate_structured(
        prompt=prompt,
        schema=PairwiseJudgement,
        system_prompt="你是苛刻的资深网文主编，只输出 JSON。",
        temperature=temperature,
        responder=_make_judge_responder(llm_service, temperature, used),
    )


async def judge_pairwise(
    llm_service: LLMService,
    text_a: str,
    text_b: str,
    scenario: BenchScenario,
    *,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """A/B 对比选优，消除位置偏差：同一对做两次调用（互换位置），
    两次结论一致才计胜负，不一致记 tie（consistent=False）。
    返回 winner ∈ {"a", "b", "tie"}（相对于入参 text_a/text_b）。
    """
    used: Dict[str, str] = {"channel": "grader"}
    pass_ab = await _judge_pair_once(llm_service, text_a, text_b, scenario, temperature, used)
    pass_ba = await _judge_pair_once(llm_service, text_b, text_a, scenario, temperature, used)

    verdict_ab = {"A": "a", "B": "b"}.get(pass_ab.winner, "tie")
    # 第二轮 A/B 位置互换：模型答 A 实为 text_b 胜
    verdict_ba = {"A": "b", "B": "a"}.get(pass_ba.winner, "tie")

    consistent = verdict_ab == verdict_ba
    winner = verdict_ab if consistent else "tie"
    return {
        "winner": winner,
        "consistent": consistent,
        "judge_channel": used["channel"],
        "passes": [
            {"order": "ab", "verdict": verdict_ab, "raw_winner": pass_ab.winner, "reason": pass_ab.reason},
            {"order": "ba", "verdict": verdict_ba, "raw_winner": pass_ba.winner, "reason": pass_ba.reason},
        ],
    }
