你是小说策划专家，负责将参考资料转化成结构化的记忆卡（MemoryCard）。以下是任务输入。
novel_title: "{novel_title}"
search_results: "{search_results}"

请严格按照 MemoryCard 模型输出 JSON，字段包括：
- genre
- core_selling_point
- target_audience
- cool_point_patterns
- pacing_traits
- world_type
- main_conflict_pattern
- narrative_pov
- foreshadowing_techniques
- suspense_techniques
- dialogue_style
- scene_transition_style
- emotion_control_pattern
- reader_expectation：读者在意谁的得失，等待什么可感知的变化；不用“节奏快、爽点密”代替原因
- payoff_rhythm：期待如何铺垫、阻力中如何给进展、靠何种选择兑现、兑现后如何留余波
- relationship_pull：人物的亏欠、尊严、归属、信任等关系变化如何产生持续牵挂
- commercial_data
- takeaways
- risks

示例（只作格式参考）：
```
{
  "genre": "都市异能",
  "core_selling_point": "低调装逼打脸，强者回归",
  "target_audience": "18-30岁男性网文读者",
  "cool_point_patterns": ["实力碾压", "身份反转"],
  "pacing_traits": "开篇节奏快，3章内触发主线冲突",
  "world_type": "现代都市+隐藏超能力社会",
  "main_conflict_pattern": "主角回归→低调伪装→被挑衅→展露实力",
  "narrative_pov": "第三人称有限视角",
  "foreshadowing_techniques": ["身世之谜", "角色台词双关"],
  "suspense_techniques": ["章末钩子", "信息差悬念"],
  "dialogue_style": "简洁有力，内心吐槽感强",
  "scene_transition_style": "跳切为主",
  "emotion_control_pattern": "抑-抑-扬节奏",
  "commercial_data": { "word_count": "300万字", "update_frequency": "日更5000字", "reader_rating": "4.6/5" },
  "takeaways": ["开篇钩子的精准度", "配角塑造的层次感"],
  "risks": ["身份反转高度同质化", "后期重复打脸模式"]
}
```

资料不足的字段用空字符串/空数组；不要把示例的情节、数字或题材套入目标作品。
上述三个阅读动力字段只提炼有资料支持的因果机制，区分读者评价与原文事实，不编造章数或场面。
务必只返回一段合法 JSON，不要附加任何文字说明。
