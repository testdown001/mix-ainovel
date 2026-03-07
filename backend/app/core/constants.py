"""写作流程业务常量。"""

from enum import Enum


class WritingStage(str, Enum):
    """写作进度阶段枚举 - 对应"三省六部"各职能"""
    INIT = "init"                      # 初始化
    PARSE_REQUIREMENT = "parse"        # 太子分拣 - 解析需求
    PLAN_STRATEGY = "plan"             # 中书规划 - 制定策略
    PREVIEW_GENERATION = "preview"     # 预览生成
    MAIN_WRITING = "writing"           # 兵部写作 - 核心生成
    POST_PROCESSING = "post_process"   # 后处理 - 润色优化
    REVIEW = "review"                   # 门下审核 - 质量评审
    FINALIZE = "finalize"              # 最终确认


class StageStatus(str, Enum):
    """阶段状态枚举"""
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 进行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败
    BLOCKED = "blocked"      # 阻塞
    PAUSED = "paused"        # 暂停


# 阶段显示配置
STAGE_CONFIG = {
    WritingStage.INIT: {
        "name": "初始化",
        "icon": "🚀",
        "description": "准备写作环境"
    },
    WritingStage.PARSE_REQUIREMENT: {
        "name": "需求解析",
        "icon": "📋",
        "description": "太子分拣 - 理解写作指令"
    },
    WritingStage.PLAN_STRATEGY: {
        "name": "策略规划",
        "icon": "📜",
        "description": "中书规划 - 制定写作策略"
    },
    WritingStage.PREVIEW_GENERATION: {
        "name": "预览生成",
        "icon": "🔮",
        "description": "生成预览版本"
    },
    WritingStage.MAIN_WRITING: {
        "name": "章节生成",
        "icon": "✍️",
        "description": "兵部写作 - 核心内容生成"
    },
    WritingStage.POST_PROCESSING: {
        "name": "后处理",
        "icon": "🎨",
        "description": "润色优化"
    },
    WritingStage.REVIEW: {
        "name": "质量审核",
        "icon": "🔍",
        "description": "门下审核 - 质量把关"
    },
    WritingStage.FINALIZE: {
        "name": "最终确认",
        "icon": "✅",
        "description": "完成并保存"
    },
}


CHAPTER_MIN_WORDS = 3000
CHAPTER_MAX_WORDS = 4000
CHAPTER_RECOMMENDED_WORDS = 3500
CHAPTER_WORD_COUNT_RULE = (
    f"【硬性要求】本章正文必须控制在 {CHAPTER_MIN_WORDS} 到 {CHAPTER_MAX_WORDS} 字之间，"
    f"目标约 {CHAPTER_RECOMMENDED_WORDS} 字。超过 {CHAPTER_MAX_WORDS} 字即为不合格，必须精简。"
    f"宁可少写一个场景细节，也绝对不要超过 {CHAPTER_MAX_WORDS} 字。"
    "冲突/动作段可用短句提速，铺垫/心理段可用长句展开；长短句必须交替变化，"
    "禁止整章单一句式。不要为凑字数硬加空描写，也不要因压字数跳过关键动作与情绪递进。"
)

CHAPTER_STYLE_HARD_RULE = (
    "1) 严格避免过多形容词、副词和华丽辞藻，优先使用精确名词+动词。\n"
    "2) 禁止使用以下词语：深入探讨、细致入微、至关重要、引人注目、精心、层层、宛如、犹如、深刻启示、全面、显著、"
    "meticulously、delve、intricate、tapestry、realm、pivotal。\n"
    "3) 若出现上述词语，必须改写为具体动作、事实或结果描述。\n"
    "4) 章节结尾禁止使用「环境/自然现象+拟人化暗示」来象征角色心态或命运走向。"
    "例：「风仿佛在回应……」「有什么正在苏醒/萌芽」「火焰跳了一下像是……」均属违禁。"
    "结尾应直接落在角色的动作、一句话、或一个干脆的画面上，不需要环境来「点题」。"
)

# ========== 新增：段落与节奏控制规则 ==========

PARAGRAPH_LENGTH_RULE = (
    "【段落控制硬性要求】\n"
    "1) 单个段落最长不超过150字，超过必须拆分。\n"
    "2) 避免「车轱辘话」——同一观点不要用不同措辞重复两遍以上。\n"
    "3) 心理描写连续不超过3段，超过则必须插入动作或对话打断。\n"
    "4) 景物描写每次不超过2段，必须与剧情推进结合，禁止纯写景超过200字。\n"
    "5) 回忆/闪回每次不超过200字，且必须服务于当前情节。\n"
)

DIALOGUE_RATIO_RULE = (
    "【对话密度硬性要求】\n"
    "1) 对话占正文比例不低于35%（即每1000字至少350字是对话）。\n"
    "2) 对话必须短、快、有信息量——三句话能说完的事不要写五句。\n"
    "3) 对话必须推动情节或揭示人物，禁止「水文式寒暄」（如「你吃了吗」「吃了」之类无关紧要的对话）。\n"
    "4) 每段对话必须附带说话时的动作/表情/心理，至少2选1。\n"
    "5) 禁止大段独白——单次内心独白超过150字必须删减。\n"
)

CHAPTER_STRUCTURE_RULE = (
    "【章节结构硬性要求】\n"
    "1) 开篇150字内必须出现第一个戏剧冲突或悬念（主角面临问题/困境/选择）。\n"
    "2) 章中必须包含至少一个「反转点」或「升级点」——情节朝着意想不到或更加严峻的方向发展。\n"
    "3) 每800-1000字必须有一个「节奏变化点」——通过以下方式之一：\n"
    "   - 新人物出现\n"
    "   - 新信息揭示\n"
    "   - 意外事件发生\n"
    "   - 冲突升级/转移\n"
    "   - 场景切换\n"
    "4) 章节结尾必须留「钩子」——新危机、新线索、反转预兆、或悬念问题。「未完待续」不是钩子。\n"
    "5) 结尾最后一段必须落在角色动作/台词/具体画面上，禁止以议论、抒情、环境描写收尾。\n"
)

SENTENCE_VARIETY_RULE = (
    "【句式变化硬性要求】\n"
    "1) 禁止连续3句以上使用相同句式（主谓宾/主谓/主谓补）。\n"
    "2) 至少30%的句子使用「先果后因」「先结果后细节」的倒装/变化句式。\n"
    "3) 动作场面使用短句+断句（逗号/句号频繁），每10-15字一顿。\n"
    "4) 心理/情感场面使用长句+从句，让阅读节奏慢下来感受情绪。\n"
    "5) 禁止「和」字连续出现超过3次，超过必须拆分或换词。\n"
    "6) 禁止「的」字连续出现超过4次，超过必须简化结构。\n"
)

PROTAGONIST_VOICE_RULE = (
    "【主角人设硬性要求】\n"
    "1) 主角必须有鲜明且统一的行为逻辑——面对同类问题必须做出符合人设的选择。\n"
    "2) 主角必须有「标志性动作」或「口头禅」，每章至少出现2次强化记忆点。\n"
    "3) 主角面临的困境/选择必须与其「核心恐惧」或「核心渴望」直接关联。\n"
    "4) 主角必须主动行动推动情节，不能只是被动回应（每章至少1次主动选择/行动）。\n"
    "5) 主角的成长/转变必须有迹可循，不能性格突变——通过具体事件和心理变化展现。\n"
)

SCENE_TRANSITION_RULE = (
    "【场景切换硬性要求】\n"
    "1) 场景切换必须使用「硬切」或「过渡句」，禁止模糊叙事导致时空混乱。\n"
    "2) 切换场景后必须在50字内明确时间/地点/人物，否则读者会困惑。\n"
    "3) 避免同一场景内频繁切换视角——如需切换，用段落分隔并标注。\n"
    "4) 时间跨度超过3个月必须标注明确的时间线或使用时间戳。\n"
    "5) 多线叙事时，每条线每章至少推进一次，避免「消失」的线索。\n"
)

# 规则汇总：所有硬性规则打包
ALL_HARD_RULES = (
    f"{CHAPTER_WORD_COUNT_RULE}\n\n"
    f"{CHAPTER_STYLE_HARD_RULE}\n\n"
    f"{PARAGRAPH_LENGTH_RULE}\n\n"
    f"{DIALOGUE_RATIO_RULE}\n\n"
    f"{CHAPTER_STRUCTURE_RULE}\n\n"
    f"{SENTENCE_VARIETY_RULE}\n\n"
    f"{PROTAGONIST_VOICE_RULE}\n\n"
    f"{SCENE_TRANSITION_RULE}"
)
