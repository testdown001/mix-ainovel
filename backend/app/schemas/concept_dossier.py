# AIMETA P=立项书与推演报告Schema|R=ConceptDossier_StressReport_BlueprintReviewReport结构定义|NR=不含业务逻辑|E=ConceptDossier,PremiseStressReport,BlueprintReviewReport|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
"""故事立项书（结构化前提产物）+ 压力推演报告 + 蓝图审稿报告的 Pydantic Schema。

三者都经 LLMService.generate_structured 产出（schema 校验 + 校验错误回喂重问），
字段全部给默认值：LLM 漏字段时软降级为空值而不是整单作废——立项书/推演/审稿
都是质量增益层，宁可缺一块也不能让蓝图主链路挂掉。
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 故事立项书 ConceptDossier
# ---------------------------------------------------------------------------


class ProtagonistCore(BaseModel):
    """主角三件套：欲望（要什么）/缺陷（差什么）/困境（被什么摁住）。"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="主角名（可为暂定名）")
    identity: str = Field(default="", description="开局身份与处境，一句话")
    desire: str = Field(default="", description="欲望：主角最想得到什么（具体、可追踪，不是『变强』这种空词）")
    flaw: str = Field(default="", description="缺陷：性格/能力/处境上的硬伤，会持续制造麻烦")
    predicament: str = Field(default="", description="困境：开局把主角摁在地上的具体压迫（谁/什么/为什么摆脱不掉）")
    charm_point: str = Field(default="", description="读者凭什么第一章就站他：代入点或魅力点")


class GoldenFingerPlan(BaseModel):
    """金手指四件套 + 成长曲线。没有金手指的题材可整体为空。"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="金手指名称，无金手指题材留空")
    source: str = Field(default="", description="来源：怎么得到的，与世界观因果挂钩")
    mechanism: str = Field(default="", description="机制：它具体能做什么、怎么用")
    limitations: str = Field(default="", description="限制与代价：什么条件下失效/要付出什么（防无敌流失速的第一道闸）")
    growth_curve: str = Field(
        default="",
        description="成长曲线：分阶段解锁的里程碑（如 1-10 章只能X → 30 章解锁Y → 100 章质变Z），每阶段留有天花板",
    )


class AnticipationPromise(BaseModel):
    """期待感承诺：读者在三个时间尺度上分别在等什么。"""

    model_config = ConfigDict(extra="allow")

    ten_chapters: str = Field(default="", description="前 10 章承诺：读者立刻能看到什么（第一次爽点/第一次反杀/身份立住）")
    fifty_chapters: str = Field(default="", description="前 50 章承诺：第一阶段的大兑现（翻案/升级/版图变化）")
    long_term: str = Field(default="", description="长线承诺：贯穿全书的终极悬念与最终对决方向")


class EmotionalCore(BaseModel):
    cherished: str = Field(default="", max_length=600, description="最舍不得的人、生活或尊严，具体到场景")
    exception: str = Field(default="", max_length=600, description="嘴上的原则与会为谁破例，留出人物矛盾")
    key_relationship: str = Field(default="", max_length=600, description="最重要的关系及彼此没说破的事")
    hard_choice: str = Field(default="", max_length=600, description="外在目标与珍惜之物冲突时的有代价选择")
    emotional_promise: str = Field(default="", max_length=600, description="读者会为什么牵挂、想看到怎样的改变")


class ConceptDossier(BaseModel):
    """故事立项书：灵感对话蒸馏出的结构化前提产物，蓝图生成的最高优先级锚点。"""

    model_config = ConfigDict(extra="allow")

    core_selling_line: str = Field(default="", description="核心卖点句：主角+异常处境/金手指+对抗什么+为什么值得追，一句硬话")
    genre: str = Field(default="", description="题材（如 都市异能/仙侠/无限流）")
    audience: str = Field(default="", description="目标读者画像")
    platform_mode: str = Field(default="", description="平台模式：起点向/番茄向/Hybrid")
    protagonist: ProtagonistCore = Field(default_factory=ProtagonistCore)
    emotional_core: EmotionalCore = Field(default_factory=EmotionalCore)
    core_conflict: str = Field(default="", description="核心冲突：主角与谁/什么的对抗贯穿全书")
    conflict_engine: str = Field(
        default="",
        description="矛盾发动机：能持续再生冲突的结构性装置（利益格局/规则悖论/身份悖论），说明它为什么打不完",
    )
    golden_finger: Optional[GoldenFingerPlan] = Field(default=None, description="金手指规划，题材不适用时为 null")
    anticipation: AnticipationPromise = Field(default_factory=AnticipationPromise)
    coolpoint_chain: List[str] = Field(
        default_factory=list,
        description="爽点链：按出现顺序列出的可复用爽点类型+具体形态（如『信息差打脸：主角早知道拍卖品真伪』）",
    )
    title_candidates: List[str] = Field(default_factory=list, description="书名候选 2-4 个")
    notes: str = Field(default="", description="其余关键共识（世界观要点/重要配角/用户特殊要求）")


# ---------------------------------------------------------------------------
# 压力推演报告 PremiseStressReport
# ---------------------------------------------------------------------------


class ConflictProjection(BaseModel):
    """冲突可持续性推演：矛盾发动机在三个进度点上的形态。"""

    model_config = ConfigDict(extra="allow")

    at_50: str = Field(default="", description="第 50 章时冲突的形态：谁在打、为什么还在打")
    at_100: str = Field(default="", description="第 100 章时冲突升级后的形态")
    at_300: str = Field(default="", description="第 300 章时冲突的终局前形态；若推演不出来说明发动机供血不足")
    verdict: str = Field(default="", description="判定：充足/勉强/供血不足")
    analysis: str = Field(default="", description="判定理由与最薄弱环节")


class GoldenFingerProjection(BaseModel):
    """金手指崩坏推演：成长曲线是否会提前杀死张力。"""

    model_config = ConfigDict(extra="allow")

    stall_chapter: int = Field(default=0, description="预测的失速章号：主角从该章起碾压一切、失去阻力（0=推演不出失速点）")
    stall_reason: str = Field(default="", description="失速原因（能力天花板过早触顶/限制条款形同虚设等）")
    verdict: str = Field(default="", description="判定：健康/有隐患/必然崩坏")
    analysis: str = Field(default="", description="判定理由")


class ToxicPoint(BaseModel):
    """毒点：会让读者弃书的具体缺陷。"""

    model_config = ConfigDict(extra="allow")

    issue: str = Field(default="", description="毒点名称（如 开局信息过载/主角不讨喜/爽点太迟）")
    severity: str = Field(default="低危", description="高危/中危/低危：高危=典型弃书点")
    reason: str = Field(default="", description="为什么在这个立项里会踩中")
    fix_suggestion: str = Field(
        default="",
        description=(
            "给作者看的中文修法：点名立项书中文区块（如「主角身份处境」「金手指限制与代价」"
            "「矛盾发动机」「爽点链」「期待感承诺」「补充说明」）并写清怎么改。"
            "禁止英文变量名、下划线或带点号的路径"
        ),
    )


class PremiseStressReport(BaseModel):
    """压力推演报告：对抗性三问 + 毒点扫描。"""

    model_config = ConfigDict(extra="allow")

    conflict_sustainability: ConflictProjection = Field(default_factory=ConflictProjection)
    golden_finger_collapse: GoldenFingerProjection = Field(default_factory=GoldenFingerProjection)
    toxic_points: List[ToxicPoint] = Field(default_factory=list)
    overall_verdict: str = Field(default="", description="总体判定：可开工/建议修订/高危需重构")
    summary: str = Field(default="", description="一段话总评")

    def high_risk_points(self) -> List[ToxicPoint]:
        return [p for p in self.toxic_points if "高" in (p.severity or "")]


# ---------------------------------------------------------------------------
# 故事骨架 StoryBackbone（倒推规划：终局 → 卷高潮 → 回填前置条件）
# ---------------------------------------------------------------------------


class SetupRequirement(BaseModel):
    """让某个高潮成立的前置条件；落到蓝图时就是一条伏笔（name 对齐伏笔名）。"""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="伏笔名，短而可指认（如「师父的旧伤」）")
    what_must_be_established: str = Field(
        default="",
        description="读者在兑现前必须已经见过/知道的具体事实（如「见过师父避开左肩一次，不解释」），不是结果",
    )
    why_needed: str = Field(default="", description="不埋会怎样：高潮变成天降 / 人物动机站不住 / 规则没立过")
    plant_from: int = Field(default=1, ge=1, description="允许埋设的最早章号")
    plant_to: int = Field(default=1, ge=1, description="允许埋设的最晚章号（必须早于高潮章）")
    develop_hint: str = Field(default="", description="中途怎么浇水一次，可空")
    tier: str = Field(default="核心", description="核心 / 支线")


class ClimaxNode(BaseModel):
    """一个高潮节点：第一次兑现、各卷卷末高潮、中点翻案共用。"""

    model_config = ConfigDict(extra="allow")

    volume_index: int = Field(default=0, ge=0, description="所属卷序（从 1 起；第一次兑现/中点可为 0）")
    volume_theme: str = Field(default="", description="本卷主题或舞台，一句话")
    chapter: int = Field(default=1, ge=1, description="高潮落在哪一章")
    event: str = Field(default="", description="具体发生什么——不是「大战」，是谁对谁做了什么")
    reversal: str = Field(default="", description="翻转或揭示了什么")
    cost: str = Field(default="", description="主角付出什么")
    protagonist_state_after: str = Field(default="", description="高潮后主角的处境/境界/资源")
    setups: List[SetupRequirement] = Field(default_factory=list, description="3-6 条前置条件")


class EndgameNode(BaseModel):
    """终局：全书往哪里去。"""

    model_config = ConfigDict(extra="allow")

    final_confrontation: str = Field(default="", description="最后一战是什么、和谁、在哪")
    core_answer: str = Field(default="", description="核心冲突最终的答案")
    protagonist_becomes: str = Field(default="", description="主角最终成为什么人")
    cost: str = Field(default="", description="终局付出的代价")
    setups: List[SetupRequirement] = Field(default_factory=list, description="终局的前置条件，可跨全书埋设")


class StoryBackbone(BaseModel):
    """故事骨架：倒推规划的产物，蓝图设定段与章纲段的结构锚点。"""

    model_config = ConfigDict(extra="allow")

    total_chapters: int = Field(default=300, ge=10, description="全书预计章数（服务端预算后喂给模型，模型不得改）")
    endgame: EndgameNode = Field(default_factory=EndgameNode)
    first_promise: ClimaxNode = Field(default_factory=ClimaxNode, description="前 10 章内的第一次兑现")
    midpoint: Optional[ClimaxNode] = Field(default=None, description="全书中点翻案；短篇可为 null")
    climaxes: List[ClimaxNode] = Field(default_factory=list, description="每卷一条，按卷序")

    def all_setups(self) -> List[SetupRequirement]:
        """全部前置条件（含终局），用于回填与覆盖检查。"""
        items: List[SetupRequirement] = list(self.first_promise.setups)
        if self.midpoint is not None:
            items.extend(self.midpoint.setups)
        for node in self.climaxes:
            items.extend(node.setups)
        items.extend(self.endgame.setups)
        return items


class BackboneAlternative(BaseModel):
    """备选终局方向：只给终局与各卷高潮事件，不含前置条件（选定后再倒推回填）。"""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default="", description="服务端回填的标识")
    label: str = Field(default="", description="一句话方向标签（如「弑师证道」「归隐反杀」）")
    endgame: EndgameNode = Field(default_factory=EndgameNode)
    midpoint_event: str = Field(default="", description="中点翻案事件，可空")
    climax_events: List[str] = Field(default_factory=list, description="各卷高潮事件，按卷序，与卷数一致")
    why_different: str = Field(default="", description="与现方案的本质差异在哪（不是换个对手）")


class BackboneAlternativeSet(BaseModel):
    model_config = ConfigDict(extra="allow")

    alternatives: List[BackboneAlternative] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 蓝图审稿报告 BlueprintReviewReport
# ---------------------------------------------------------------------------


class ReviewIssue(BaseModel):
    """审稿问题条目：必须可定位（点名设定块或章号区间），否则定向修订无从下手。"""

    model_config = ConfigDict(extra="allow")

    dimension: str = Field(default="", description="所属量表维度")
    severity: str = Field(default="低", description="高/中/低")
    target: str = Field(
        default="",
        description="定位：settings:<块名>（如 settings:golden_finger）或 chapters:<起>-<止>（如 chapters:5-8）",
    )
    problem: str = Field(default="", description="问题描述，要具体到剧情内容而非空评语")
    fix_hint: str = Field(default="", description="修订方向（改成什么样才达标）")


class BlueprintReviewReport(BaseModel):
    """蓝图审稿门产物：商业量表分数 + 可定位问题清单。"""

    model_config = ConfigDict(extra="allow")

    total_score: int = Field(default=0, ge=0, le=100)
    dimension_scores: Dict[str, int] = Field(
        default_factory=dict,
        description="各维度得分（0-100）：opening_strength/character_attachment/first_coolpoint_timing/hook_chain/volume_escalation/foreshadowing_payoff/anticipation_delivery/toxic_recheck；旧报告可缺 character_attachment",
    )
    verdict: str = Field(default="", description="总评一句话")
    issues: List[ReviewIssue] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list, description="值得保留的亮点（修订时不得破坏）")
    revised: bool = Field(default=False, description="是否经过一轮定向修订（服务端回填，非 LLM 输出）")

    def issues_for_settings(self) -> List[ReviewIssue]:
        return [i for i in self.issues if (i.target or "").startswith("settings:")]

    def issues_for_chapters(self) -> List[ReviewIssue]:
        return [i for i in self.issues if (i.target or "").startswith("chapters:")]

    def needs_revision(self, min_score: int) -> bool:
        """A grounded character defect cannot be hidden by unrelated high scores.

        Missing attachment scores in legacy reviews do not create a new failure.
        The existing one-pass revision budget and author choice stay unchanged.
        """
        if not self.issues:
            return False
        if self.total_score < min_score:
            return True
        attachment = self.dimension_scores.get("character_attachment")
        return any(
            issue.dimension == "character_attachment" and issue.target
            and (issue.severity in {"高", "高危", "high"} or (attachment is not None and attachment < min_score))
            for issue in self.issues
        )


# ---------------------------------------------------------------------------
# API 响应/请求体
# ---------------------------------------------------------------------------


class DossierResponse(BaseModel):
    """GET /concept/dossier 响应：立项书 + 推演报告 + 生成状态。"""

    status: str = Field(default="ready", description="ready=立项书就绪 / absent=无对话或蒸馏失败")
    dossier: Optional[Dict[str, Any]] = None
    stress_report: Optional[Dict[str, Any]] = None
    stress_available: bool = Field(default=False, description="当前档位是否有压力推演能力（creator+）")
    deep_available: bool = Field(
        default=False,
        description="当前档位是否可选蓝图深度打磨（creator+，capability=blueprint_deep）",
    )
    deep_credit_price: int = Field(
        default=0,
        description=(
            "深度打磨积分单价（credits.price.blueprint_deep）。"
            "审稿门关闭或未配置时为 0，确认页据此展示「免费」/「N 积分」。"
        ),
    )
    generated_at: Optional[str] = None


class BlueprintGenerateRequest(BaseModel):
    """POST /blueprint/generate 可选请求体。缺省 / 旧客户端 = deep（与现网一致）。"""

    depth: str = Field(default="deep", description="fast=跳过审稿打磨 / deep=审稿门+定向修订")


class DossierPatchRequest(BaseModel):
    """PATCH /concept/dossier 请求体：分块局部更新（只合并提供的键）。"""

    dossier: Dict[str, Any] = Field(default_factory=dict)


class BackboneResponse(BaseModel):
    """GET /concept/backbone 响应。"""

    status: str = Field(default="ready", description="ready / absent（无立项书、开关关闭或生成失败）")
    backbone: Optional[Dict[str, Any]] = None
    generated_at: Optional[str] = None
    revised_by_author: bool = Field(default=False, description="作者是否改过任一块")
    stale: bool = Field(default=False, description="立项书在骨架生成后又被改过（作者改过的骨架不自动重算）")
    enabled: bool = Field(default=True, description="平台开关 blueprint.backbone_enabled")


class BackbonePatchRequest(BaseModel):
    """PATCH /concept/backbone：分块更新。

    键可为 endgame / first_promise / midpoint / climaxes；climaxes 的值是 {"<卷序>": {...}}。
    """

    backbone: Dict[str, Any] = Field(default_factory=dict)


class BackboneAlternativesResponse(BaseModel):
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: Optional[str] = None


class BackboneApplyAlternativeRequest(BaseModel):
    alternative_id: str
