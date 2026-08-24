# AIMETA P=小说模式_小说和章节请求响应|R=小说结构_章节结构|NR=不含业务逻辑|E=NovelSchema_ChapterSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChoiceOption(BaseModel):
    """前端选择项描述，用于动态 UI 控件。"""

    id: str
    label: str
    recommended: bool = False
    recommend_reason: Optional[str] = Field(
        default=None,
        description="推荐理由（有参考小说时点明转译了哪条底层逻辑/魅力点）",
    )


class UIControl(BaseModel):
    """描述前端应渲染的组件类型与配置。"""

    type: str = Field(..., description="控件类型，如 single_choice/text_input")
    options: Optional[List[ChoiceOption]] = Field(default=None, description="可选项列表")
    placeholder: Optional[str] = Field(default=None, description="输入提示文案")


class ConverseResponse(BaseModel):
    """概念对话接口的统一返回体。"""

    ai_message: str
    ui_control: UIControl
    conversation_state: Dict[str, Any]
    is_complete: bool = False
    ready_for_blueprint: Optional[bool] = None


class ConverseRequest(BaseModel):
    """概念对话接口的请求体。"""

    user_input: Dict[str, Any]
    conversation_state: Dict[str, Any]
    reference_novels: Optional[List[str]] = Field(
        default=None,
        max_length=3,
        description="参考小说名称列表，最多 3 本",
    )
    reference_context: Optional[str] = Field(
        default=None,
        description="已检索并糅合的参考上下文（可选）",
    )
    exclusions: Optional[str] = Field(
        default=None,
        description="创作禁区：用户不希望出现的元素、方向或套路",
    )
    disable_spark: Optional[bool] = Field(
        default=False,
        description="关闭灵感扰动注入（默认开启，用于让概念对话更发散、更有灵气）",
    )
    disable_muse_search: Optional[bool] = Field(
        default=False,
        description="关闭开场的跨界素材联网发现（默认开启；未配置搜索模型时自动跳过）",
    )
    muse_persona: Optional[str] = Field(
        default=None,
        description="缪斯人格皮肤 key（default/cyberpunk/myth_epic/dark_mystery/wild_brain），需创作者档及以上",
    )


class DivergeRequest(BaseModel):
    """概念 N 路发散请求体（旗舰档特性）。"""

    seed_topic: str = Field(..., description="发散用的故事点子/方向")
    exclusions: Optional[str] = Field(default=None, description="创作禁区")
    n: int = Field(default=5, ge=2, le=8, description="发散种子数量")
    keep: int = Field(default=3, ge=1, le=8, description="评分后保留的 Top 数量")


class VolumeDivergeRequest(BaseModel):
    """卷级 N 路发散请求体（旗舰档特性）。

    与概念发散不同：不需要 seed_topic —— 发散的依据是故事**实际所处的位置**
    （上一卷复盘 + 实际摘要），由服务端自行取材。
    """

    n: int = Field(default=5, ge=2, le=8, description="发散方案数量")
    keep: int = Field(default=3, ge=1, le=8, description="评分后保留的 Top 数量")


class VolumeDivergeApplyRequest(BaseModel):
    """把选中的卷级发散卡片写入该卷 replan。"""

    title: Optional[str] = None
    arc_goal: str = Field(..., description="本卷目标")
    climax_hint: Optional[str] = None
    focus: Optional[str] = None
    avoid: Optional[str] = None


class ReferenceSearchRequest(BaseModel):
    """参考小说搜索请求体。"""

    novel_names: List[str] = Field(default_factory=list, max_length=3, description="参考小说名称，最多 3 本")


class ReferenceSearchResponse(BaseModel):
    """参考小说搜索响应体。"""

    reference_context: str = ""
    search_completed: bool = False
    skipped: bool = False
    message: Optional[str] = None
    searched_novels: List[str] = Field(default_factory=list)


class ChapterGenerationStatus(str, Enum):
    NOT_GENERATED = "not_generated"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    SELECTING = "selecting"
    FAILED = "failed"
    EVALUATION_FAILED = "evaluation_failed"
    WAITING_FOR_CONFIRM = "waiting_for_confirm"
    SUCCESSFUL = "successful"


class ChapterOutline(BaseModel):
    chapter_number: int
    title: str
    summary: str
    metadata: Optional[Dict[str, Any]] = None


class Chapter(ChapterOutline):
    real_summary: Optional[str] = None
    content: Optional[str] = None
    versions: Optional[List[str]] = None
    version_metadata: Optional[List[Dict[str, Any]]] = None
    recommended_version_index: Optional[int] = None
    evaluation: Optional[str] = None
    generation_status: ChapterGenerationStatus = ChapterGenerationStatus.NOT_GENERATED
    word_count: Optional[int] = None
    revision_id: int = 0
    content_hash: Optional[str] = None
    selected_version_id: Optional[int] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None


class Relationship(BaseModel):
    character_from: str
    character_to: str
    description: str


class BlueprintForeshadowing(BaseModel):
    name: str = ""
    description: str = ""
    planted_chapter: int = Field(..., ge=1)
    target_chapter: Optional[int] = Field(default=None, ge=1)
    tier: str = "支线"
    type: str = "hint"
    reveal_method: Optional[str] = None
    reveal_impact: Optional[str] = None
    related_characters: List[str] = []
    related_plots: List[str] = []


class BlueprintVolume(BaseModel):
    """轻量分卷规划：按总篇幅切 3-6 卷。全部字段有默认值，兼容无 volumes 的旧蓝图。"""

    name: str = ""
    start_chapter: int = 1
    end_chapter: int = 1
    arc_goal: str = ""
    climax_hint: str = ""


class Blueprint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    target_audience: str = ""
    genre: str = ""
    style: str = ""
    tone: str = ""
    one_sentence_summary: str = ""
    full_synopsis: str = ""
    world_setting: Dict[str, Any] = {}
    characters: List[Dict[str, Any]] = []
    golden_finger: Optional[Dict[str, Any]] = None
    relationships: List[Relationship] = []
    chapter_outline: List[ChapterOutline] = []
    foreshadowings: List[BlueprintForeshadowing] = []
    volumes: List[BlueprintVolume] = []
    # 蓝图审稿门产物（分数+问题清单）；None = 未审（旧蓝图/审稿降级跳过）
    review_report: Optional[Dict[str, Any]] = None


class NovelProject(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    title: str
    initial_prompt: str
    is_completed: bool = False
    cover_image: Optional[Dict[str, Any]] = None
    conversation_history: List[Dict[str, Any]] = []
    reference_novel_ids: List[int] = Field(default_factory=list)
    blueprint: Optional[Blueprint] = None
    chapters: List[Chapter] = []


class NovelProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    last_edited: str
    completed_chapters: int
    total_chapters: int
    total_words: int = 0
    next_chapter_number: Optional[int] = None
    next_chapter_title: Optional[str] = None
    is_completed: bool = False
    cover_image: Optional[Dict[str, Any]] = None


class BlueprintGenerationResponse(BaseModel):
    blueprint: Blueprint
    ai_message: str


class ChapterGenerationResponse(BaseModel):
    ai_message: str
    chapter_versions: List[Dict[str, Any]]


class NovelSectionType(str, Enum):
    OVERVIEW = "overview"
    WORLD_SETTING = "world_setting"
    CHARACTERS = "characters"
    RELATIONSHIPS = "relationships"
    CHAPTER_OUTLINE = "chapter_outline"
    CHAPTERS = "chapters"


class NovelSectionResponse(BaseModel):
    section: NovelSectionType
    data: Dict[str, Any]


class GenerateChapterRequest(BaseModel):
    chapter_number: int
    writing_notes: Optional[str] = Field(default=None, description="章节额外写作指令")


class FlowConfig(BaseModel):
    preset: str = Field(default="fast", description="fast|standard|premium（旧名 basic/enhanced/ultimate/platinum/literary 自动映射到现行三档）")
    model_code: Optional[str] = Field(default=None, description="所选模型目录 code(章鱼1.0/2.0/3.0)；决定真实大模型与积分计费，空则用默认通道")
    enable_polish: Optional[bool] = Field(default=None, description="是否启用润色(默认关)；启用额外扣积分")
    versions: Optional[int] = Field(default=None, description="生成版本数量")
    enable_preview: Optional[bool] = Field(default=None, description="是否启用预演生成")
    enable_optimizer: Optional[bool] = Field(default=None, description="是否启用优化器")
    enable_consistency: Optional[bool] = Field(default=None, description="是否启用一致性检查")
    enable_enrichment: Optional[bool] = Field(default=None, description="是否启用字数扩写")
    enable_mission_brief: Optional[bool] = Field(default=None, description="是否启用导演脚本二次转写")
    async_finalize: Optional[bool] = Field(default=None, description="是否异步定稿")
    enable_rag: Optional[bool] = Field(default=None, description="是否启用 RAG")
    rag_mode: Optional[str] = Field(default=None, description="simple|two_stage")
    rag_retrieval_mode: Optional[str] = Field(default=None, description="vector|hybrid")
    pacing_model: Optional[str] = Field(default=None, description="default|strand_weave")
    enable_scene_by_scene: Optional[bool] = Field(default=None, description="是否启用场景级分步生成")
    enable_prose_sculpting: Optional[bool] = Field(default=None, description="是否启用节奏/密度雕塑")
    enable_golden_paragraph: Optional[bool] = Field(default=None, description="是否启用黄金段落增强")
    enable_reference_prose: Optional[bool] = Field(default=None, description="是否启用范文注入")
    enable_voice_samples: Optional[bool] = Field(default=None, description="是否启用角色声纹样本")
    enable_narrative_variety: Optional[bool] = Field(default=None, description="是否启用叙事差异化约束")
    use_slim_prompt: Optional[bool] = Field(default=None, description="是否启用精简提示词")
    literary_adaptive_postprocess: Optional[bool] = Field(default=None, description="文学模式是否自适应裁剪后处理步骤")
    enable_fast_path: Optional[bool] = Field(default=None, description="是否启用 fast 单次生成路径")
    disable_guardrail_rewrite: Optional[bool] = Field(default=None, description="护栏未通过时是否跳过 LLM 重写")
    skip_history_summary_backfill: Optional[bool] = Field(default=None, description="是否跳过历史章节摘要补写")
    use_local_anti_hallucination: Optional[bool] = Field(default=None, description="是否使用本地实体规则反幻觉检查")
    batch_parallel_workers: Optional[int] = Field(default=None, ge=1, le=8, description="批量生成并行工作数")
    use_agent: Optional[bool] = Field(default=None, description="是否启用 Agent 多代理系统生成")
    use_agentic_loop: Optional[bool] = Field(default=None, description="Agent 模式下是否启用智能体循环（工具调用驱动）")
    selected_skills: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Agent 模式下的技能编排配置列表",
    )


class AsyncGenerateChapterRequest(BaseModel):
    """异步章节生成请求"""
    project_id: str
    chapter_number: int
    preset: str = "fast"
    use_agent_system: bool = False
    rag_mode: str = "simple"


class AsyncGenerateChapterResponse(BaseModel):
    """异步章节生成响应"""
    task_id: str
    project_id: str
    chapter_number: int
    status: str = "submitted"
    message: str = "章节生成任务已提交，请通过 task_id 查询进度"


class AdvancedGenerateRequest(BaseModel):
    project_id: str
    chapter_number: int
    writing_notes: Optional[str] = Field(default=None, description="章节额外写作指令")
    flow_config: FlowConfig = Field(default_factory=FlowConfig)


class AdvancedGenerateVariant(BaseModel):
    index: int
    version_id: int
    content: str
    metadata: Optional[Dict[str, Any]] = None


class AdvancedGenerateResponse(BaseModel):
    project_id: str
    chapter_number: int
    preset: str
    best_version_index: int
    variants: List[AdvancedGenerateVariant]
    review_summaries: Dict[str, Any] = Field(default_factory=dict)
    debug_metadata: Optional[Dict[str, Any]] = None


class BatchGenerateRequest(BaseModel):
    project_id: str
    chapter_numbers: List[int] = Field(..., description="要批量生成的章节编号列表（按顺序）")
    writing_notes: Optional[str] = Field(default=None, description="全局写作指令")
    flow_config: FlowConfig = Field(default_factory=FlowConfig)


class BatchGenerateChapterResult(BaseModel):
    chapter_number: int
    status: str  # "success" | "failed"
    error: Optional[str] = None


class BatchGenerateResponse(BaseModel):
    project_id: str
    total: int
    completed: int
    failed: int
    results: List[BatchGenerateChapterResult]


class FinalizeChapterRequest(BaseModel):
    project_id: str
    selected_version_id: int
    skip_vector_update: Optional[bool] = Field(default=False, description="是否跳过向量库更新")


class FinalizeChapterResponse(BaseModel):
    project_id: str
    chapter_number: int
    selected_version_id: int
    result: Dict[str, Any]


class SelectVersionRequest(BaseModel):
    chapter_number: int
    version_index: int


class EvaluateChapterRequest(BaseModel):
    chapter_number: int


class UpdateChapterOutlineRequest(BaseModel):
    chapter_number: int
    title: str
    summary: str
    metadata: Optional[Dict[str, Any]] = None
    planning: Optional[Dict[str, Any]] = None


class DeleteChapterRequest(BaseModel):
    chapter_numbers: List[int]


class GenerateOutlineRequest(BaseModel):
    start_chapter: int
    num_chapters: int
    estimated_total_chapters: Optional[int] = Field(default=None, description="预计总章节数，用于指导LLM控制故事进度")
    user_prompt: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="用户附加的剧情提示",
    )


class OutlineGenerationTaskResponse(BaseModel):
    """批量章纲后台任务的用户可见状态。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    stage: str
    message: str
    start_chapter: int
    total_chapters: int
    chapter_numbers: List[int]
    completed_numbers: List[int] = Field(default_factory=list)
    failed_numbers: List[int] = Field(default_factory=list)
    current_batch_start: Optional[int] = None
    current_batch_end: Optional[int] = None
    progress_percent: int = 0
    estimated_remaining_seconds: Optional[int] = None
    cancel_requested: bool = False
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class OutlineGenerationTaskEnvelope(BaseModel):
    task: Optional[OutlineGenerationTaskResponse] = None


class RegenerateOutlinesRequest(BaseModel):
    """重新生成未完成章节大纲的请求体。"""
    chapter_numbers: Optional[List[int]] = None  # 为空时自动选取所有未完成章节
    total_chapters: Optional[int] = None  # 从零生成时的目标章节总数


class RegenerateOutlinesResponse(BaseModel):
    """重新生成大纲的响应体，包含更新的章节编号。"""
    updated_chapters: List[int]
    total_target: int
    chapter_outline: List[ChapterOutline]
    # 滚动章纲轻量审稿报告（旗舰档续排路径产出）；None = 未审/审稿降级跳过
    review_report: Optional[Dict[str, Any]] = None


class BlueprintPatch(BaseModel):
    one_sentence_summary: Optional[str] = None
    full_synopsis: Optional[str] = None
    world_setting: Optional[Dict[str, Any]] = None
    characters: Optional[List[Dict[str, Any]]] = None
    relationships: Optional[List[Relationship]] = None
    chapter_outline: Optional[List[ChapterOutline]] = None
    foreshadowings: Optional[List[BlueprintForeshadowing]] = None
    # M1：允许编辑器单独更新分卷；服务层会同步独立 Volume 实体并维护旧 JSON 投影。
    volumes: Optional[List[Dict[str, Any]]] = None


class EditChapterRequest(BaseModel):
    """旧编辑入口的兼容请求。

    M2 起服务端拒绝没有版本基线的写入；保留这个模型仅为平滑迁移旧 URL。
    新客户端应使用 ChapterSaveRequest 和 /chapters/save。
    """

    chapter_number: int
    content: str
    expected_revision_id: Optional[int] = Field(default=None, ge=0)
    expected_content_hash: Optional[str] = Field(default=None, min_length=64, max_length=64)


class ChapterSaveRequest(BaseModel):
    """M2 章节安全保存请求。"""

    chapter_number: int = Field(..., ge=1)
    content: str
    expected_revision_id: int = Field(..., ge=0)
    expected_content_hash: str = Field(..., min_length=64, max_length=64)
    # branch 不替换作者当前选中的正文，只保留冲突中的本地文本供后续历史功能处理。
    mode: Literal["save", "branch"] = "save"


class ChapterRevisionResponse(BaseModel):
    chapter_number: int
    revision_id: int
    content_hash: str
    selected_version_id: Optional[int] = None
    content: str = ""


class ChapterSaveResponse(BaseModel):
    status: Literal["saved", "branched"]
    chapter_number: int
    revision_id: int
    content_hash: str
    selected_version_id: Optional[int] = None
    saved_version_id: int
    chapter: Chapter


class ChapterVersionHistoryItem(BaseModel):
    """M3 修订历史列表项；正文只在详情端点返回。"""

    id: int
    chapter_number: int
    version_label: Optional[str] = None
    source: str
    source_label: str
    parent_version_id: Optional[int] = None
    content_hash: str
    word_count: int
    content_bytes: int
    ai_assisted: bool = False
    change_note: Optional[str] = None
    created_at: Optional[str] = None
    created_by_user_id: Optional[int] = None
    is_selected: bool = False


class ChapterVersionHistoryPage(BaseModel):
    items: List[ChapterVersionHistoryItem]
    total_count: int
    total_content_bytes: int
    has_more: bool = False
    next_before_id: Optional[int] = None


class ChapterVersionDetail(ChapterVersionHistoryItem):
    content: str


class ChapterDiffSegment(BaseModel):
    kind: Literal["equal", "insert", "delete"]
    text: str


class ChapterVersionDiffResponse(BaseModel):
    chapter_number: int
    left_version_id: int
    right_version_id: int
    left_segments: List[ChapterDiffSegment]
    right_segments: List[ChapterDiffSegment]


class RestoreChapterVersionRequest(BaseModel):
    expected_revision_id: int = Field(..., ge=0)
    expected_content_hash: str = Field(..., min_length=64, max_length=64)
    change_note: Optional[str] = Field(default=None, max_length=500)


class TransformTextRequest(BaseModel):
    chapter_number: int
    action: str = Field(..., description="expand | rewrite | de_ai")
    selected_text: str
    instruction: Optional[str] = None
    apply: bool = False
