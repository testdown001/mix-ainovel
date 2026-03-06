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

务必只返回一段合法 JSON，不要附加任何文字说明。
