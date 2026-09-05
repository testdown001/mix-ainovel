"""人味化规则表清理 + standard 先跑免费规则修复 的回归测试（审计 P2 #12-16）。

覆盖：
1. 替换表零自我抵消——任何替换产物不得命中 AI_LEXICAL_PATTERNS；
2. 删除类替换仅在安全位置生效——「一切都变了」不再被截成「变了」；
3. missing_human 独立记账（自己的字段与 20 上限，structural 不再穿透 40 上限）；
4. editor_review.md 阈值与代码对齐；
5. standard 后处理分支先跑免费 apply_rule_fixes，修复后达标则零 LLM 调用。
"""
import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

from app.services.humanization_service import (
    AI_LEXICAL_PATTERNS,
    LEXICAL_REPLACEMENTS,
    HumanizationService,
)
from app.services.standard_post_processing_service import StandardPostProcessingService


def _service() -> HumanizationService:
    """scan/apply_rule_fixes 是纯静态分析，不需要真 session/llm。"""
    service = HumanizationService.__new__(HumanizationService)
    service.session = None
    service.llm_service = None
    service.prompt_service = None
    return service


# ---------------------------------------------------------------------------
# 1. 替换表零自我抵消
# ---------------------------------------------------------------------------

def test_replacement_products_never_hit_deduction_table():
    """程序化锁定：所有替换产物（含子串）不命中任何 AI_LEXICAL_PATTERNS。"""
    for word, repl in LEXICAL_REPLACEMENTS.items():
        assert word in AI_LEXICAL_PATTERNS, f"替换表键「{word}」不在扣分词表中"
        if not repl:
            continue
        hits = [p for p in AI_LEXICAL_PATTERNS if p in repl]
        assert not hits, f"替换产物「{repl}」(来自「{word}」) 仍命中扣分词表: {hits}"


def test_apply_rule_fixes_products_rescan_clean():
    """功能验证：旧表自我抵消的两对（显而易见→显然 / 总而言之→总之）修复后再扫零词汇扣分。"""
    service = _service()
    text = "显而易见，他赢了这一局棋。总而言之，这局棋下得非常精彩，大家都看得聚精会神。"
    fixed = service.apply_rule_fixes(text)
    assert "显而易见" not in fixed
    assert "总而言之" not in fixed
    report = service.scan(fixed)
    ai_vocab_issues = [i for i in report.issues if i.category == "ai_vocabulary"]
    assert not ai_vocab_issues, f"替换后再扫仍有词汇扣分: {[i.description for i in ai_vocab_issues]}"


# ---------------------------------------------------------------------------
# 2. 删除类替换的语法安全
# ---------------------------------------------------------------------------

def test_yiqiedou_not_truncated():
    """「一切都」已移出替换表（删除会丢主语），仅保留扣分。"""
    service = _service()
    text = "他环顾四周，房间里空空荡荡。一切都变了，再也回不到从前的样子。"
    report = service.scan(text)
    assert any("一切都" in i.description for i in report.issues if i.category == "ai_vocabulary")
    fixed = service.apply_rule_fixes(text, report)
    assert "一切都变了" in fixed


def test_predicate_phrases_never_deleted():
    """「仿佛在诉说」「似乎在暗示」删除会悬空宾语，已移出替换表。"""
    service = _service()
    text = "钟声回荡，仿佛在诉说着往事。他的眼神，似乎在暗示着什么。"
    fixed = service.apply_rule_fixes(text)
    assert "仿佛在诉说着往事" in fixed
    assert "似乎在暗示着什么" in fixed


def test_deletion_only_at_safe_positions():
    """删除类替换仅在句首/标点后生效（连带尾随逗号），句中保持原样。"""
    service = _service()
    text = "总的来说，事情办成了。他说总的来说还算顺利。"
    fixed = service.apply_rule_fixes(text)
    assert fixed.startswith("事情办成了")
    assert "他说总的来说还算顺利" in fixed


def test_zhejiushi_replacement_grammatical():
    """「这就是」→「这便是」（旧表「这便」会把「这就是他」截成「这便他」）。"""
    service = _service()
    text = "他环顾四周，缓缓抬起了头。这就是他要找的答案，藏在最不起眼的角落里。"
    fixed = service.apply_rule_fixes(text)
    assert "这便是他要找的答案" in fixed
    assert "这便他" not in fixed


# ---------------------------------------------------------------------------
# 3. missing_human 独立记账
# ---------------------------------------------------------------------------

def _heavy_ai_text() -> str:
    """同时触发大量 structural 与 missing_human 扣分的构造文本。"""
    paragraphs = [
        (
            f"李明走进了第{i}间屋子，但是他却发现桌上的东西被人动过，一边收拾一边琢磨这件事情，心里盘算着接下来要做的事情。"
            "因为时间不多了，所以他很快就下定了决心，但是那个人却始终没有出现在车站门口。"
        )
        for i in range(13)
    ]
    paragraphs.append("远处的钟声仿佛在回应着他的心跳，有什么东西正在苏醒。")
    return "\n".join(paragraphs)


def test_missing_human_independent_accounting():
    service = _service()
    report = service.scan(_heavy_ai_text())

    mh_issues = [i for i in report.issues if i.layer == "missing_human"]
    structural_issues = [i for i in report.issues if i.layer == "structural"]
    assert mh_issues, "构造文本应触发 missing_human 问题"
    assert structural_issues, "构造文本应触发 structural 问题"

    # 各桶独立记账、各守各的上限
    assert report.missing_human_deduction == min(20, sum(i.severity for i in mh_issues))
    assert report.structural_deduction == min(40, sum(i.severity for i in structural_issues))
    assert report.missing_human_deduction <= 20
    assert report.structural_deduction <= 40

    # 回归锁：旧实现把 missing_human 并入 structural，可达 60 穿透 40 上限
    assert sum(i.severity for i in structural_issues) >= 40, "构造文本应打满 structural 上限"
    assert report.structural_deduction == 40

    # to_dict 分层归因正确
    d = report.to_dict()
    assert d["missing_human_deduction"] == report.missing_human_deduction
    assert d["structural_deduction"] == report.structural_deduction

    # 总分公式包含四个桶
    expected = max(0, min(100, 100
                          - report.lexical_deduction
                          - report.structural_deduction
                          - report.statistical_deduction
                          - report.missing_human_deduction))
    assert report.score == expected


# ---------------------------------------------------------------------------
# 4. editor_review.md 阈值与代码对齐
# ---------------------------------------------------------------------------

def test_editor_review_prompt_thresholds_match_code():
    md = (Path(__file__).resolve().parents[1] / "prompts" / "editor_review.md").read_text(encoding="utf-8")
    assert "标准差 ≥ 5 为合格" in md          # 代码 _scan_statistical: std < 5 扣分
    assert "标准差 < 3 = 严重" in md          # 代码: std < 3 重扣
    assert "CV ≥ 0.25 为合格" in md          # 代码 _scan_structural: cv < 0.25 扣分
    assert "CV < 0.15 = 严重" in md          # 代码: cv < 0.15 重扣
    assert "每 500 字 ≤ 3 个为合格" in md     # 代码: per_500 > 3 扣分


# ---------------------------------------------------------------------------
# 5. standard 后处理：先免费规则修复，达标则零 LLM
# ---------------------------------------------------------------------------

class _DummyGuardrails:
    def check(self, **kwargs):
        return SimpleNamespace(passed=True)

    def apply_local_patches(self, text, result):
        return text

    def format_violations_for_rewrite(self, result):
        return ""


class _DummyOrchestrator:
    def __init__(self):
        self.session = SimpleNamespace()
        self.llm_service = SimpleNamespace()
        self.prompt_service = SimpleNamespace()
        self.guardrails = _DummyGuardrails()

    async def _run_consistency_check(self, **kwargs):
        return kwargs["chapter_text"], {"status": "ok"}


def _run_standard_humanization(monkeypatch, scores, *, consistency=False):
    """跑 standard 后处理的 humanization 分支，返回 (调用顺序, run 结果)。"""
    calls: list[str] = []
    score_iter = iter(scores)

    class _Report:
        def __init__(self, score):
            self.score = score
            self.issues = []

        def to_dict(self):
            return {"score": self.score}

    class _StubHumanizationService:
        def __init__(self, session, llm_service):
            pass

        def scan(self, text):
            calls.append("scan")
            return _Report(next(score_iter))

        def apply_rule_fixes(self, text, report=None):
            calls.append("rule_fix")
            return text

        async def humanize(self, text, report, *, user_id):
            calls.append("llm_humanize")
            return text + "，留下一处具体动作。"

    import app.services.humanization_service as hmod
    monkeypatch.setattr(hmod, "HumanizationService", _StubHumanizationService)

    config = SimpleNamespace(
        enable_self_critique=False,
        enable_consistency=consistency,
        enable_humanization=True,
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=False,
        enable_optimizer=False,
        enable_enrichment=False,
        enable_polish=False,
        enable_density_compression=False,
        enable_six_dimension=False,
        humanization_threshold=70,
    )
    service = StandardPostProcessingService(_DummyOrchestrator())
    result = asyncio.run(
        service.run(
            best_content="正文内容",
            best_version={"metadata": {}},
            ai_review_result=None,
            review_summaries={},
            config=config,
            project_id="proj-1",
            chapter_number=5,
            chapter_mission={"pov": "林玄"},
            writer_blueprint={"characters": []},
            history_context={"previous_summary": "上章摘要", "completed_chapters": []},
            user_id=1,
            chapter_word_count_min=2000,
            chapter_word_count_max=4000,
            chapter_target_word_count=3000,
            enhanced_flow=None,
            outline_title="第五章",
            forbidden_characters=[],
            allowed_new_characters=[],
        )
    )
    return calls, result


def test_standard_rule_fix_first_no_llm_when_passing(monkeypatch):
    """扫描低分 → 免费规则修复 → 重扫达标 → 零 LLM 调用。"""
    calls, result = _run_standard_humanization(monkeypatch, scores=[50, 90])
    assert calls == ["scan", "rule_fix", "scan"]
    assert "llm_humanize" not in calls
    assert result["review_summaries"]["humanization"]["humanized"] is False
    assert result["review_summaries"]["humanization"]["score"] == 90


def test_standard_llm_only_after_rule_fix_still_low(monkeypatch):
    """规则修复后仍低于阈值才 LLM，且 LLM 一定发生在规则修复之后。"""
    calls, result = _run_standard_humanization(monkeypatch, scores=[50, 60])
    assert calls == ["scan", "rule_fix", "scan", "llm_humanize"]
    assert calls.index("rule_fix") < calls.index("llm_humanize")
    assert result["review_summaries"]["humanization"]["humanized"] is True
    assert result["best_content"].endswith("留下一处具体动作。")


def test_standard_parallel_branch_rule_fix_first(monkeypatch):
    """consistency+humanization 并行分支同样先规则修复，达标零 LLM。"""
    calls, result = _run_standard_humanization(monkeypatch, scores=[50, 90], consistency=True)
    assert "llm_humanize" not in calls
    assert "rule_fix" in calls
    # 规则修复后有重扫，且最终分数来自重扫
    assert calls[-1] == "scan"
    assert result["review_summaries"]["humanization"]["humanized"] is False
    assert result["review_summaries"]["consistency"] == {"status": "ok"}
