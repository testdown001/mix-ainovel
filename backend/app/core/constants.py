"""写作流程业务常量。"""

CHAPTER_MIN_WORDS = 2000
CHAPTER_MAX_WORDS = 4000
CHAPTER_RECOMMENDED_WORDS = 2800
CHAPTER_WORD_COUNT_RULE = (
    f"本章正文目标区间为 {CHAPTER_MIN_WORDS} 到 {CHAPTER_MAX_WORDS} 字，"
    f"推荐落点约 {CHAPTER_RECOMMENDED_WORDS} 字（允许随剧情节奏自然波动）。"
    "冲突/动作段可用短句提速，铺垫/心理段可用长句展开；长短句必须交替变化，"
    "禁止整章单一句式。不要为凑字数硬加空描写，也不要因压字数跳过关键动作与情绪递进。"
)
