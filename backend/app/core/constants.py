"""写作流程业务常量。"""

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
