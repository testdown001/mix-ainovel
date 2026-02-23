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

CHAPTER_STYLE_HARD_RULE = (
    "1) 严格避免过多形容词、副词和华丽辞藻，优先使用精确名词+动词。\n"
    "2) 禁止使用以下词语：深入探讨、细致入微、至关重要、引人注目、精心、层层、宛如、犹如、深刻启示、全面、显著、"
    "meticulously、delve、intricate、tapestry、realm、pivotal。\n"
    "3) 若出现上述词语，必须改写为具体动作、事实或结果描述。"
)
