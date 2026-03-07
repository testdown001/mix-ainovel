from app.services.prompt_service import PromptService


def test_render_prompt_replaces_named_fields_and_preserves_json_braces():
    template = """novel_title: {novel_title}
search_results: {search_results}
```json
{
  "genre": "都市异能",
  "commercial_data": { "word_count": "300万字" }
}
```
{{already_escaped}}
"""

    rendered = PromptService.render_prompt(
        template,
        novel_title="测试小说",
        search_results="一段搜索结果",
    )

    assert "测试小说" in rendered
    assert "一段搜索结果" in rendered
    assert '"genre": "都市异能"' in rendered
    assert '{ "word_count": "300万字" }' in rendered
    assert '{already_escaped}' in rendered
