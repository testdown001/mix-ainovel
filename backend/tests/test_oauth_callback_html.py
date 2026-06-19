"""OAuth 回调页 token 注入回归测试。

历史 bug：_oauth_callback_html 用 html.escape 转义 token JSON 后塞进 <script> 的
JSON.parse('...')，但 <script> 内 HTML 实体不解码，浏览器拿到 &quot; 致
"Uncaught SyntaxError: Expected property name ... at position 1"，谷歌/微信/Linux.do
登录卡在回调页。本测试锁定：注入的 token 可被 JS 直接解析，且不含 HTML 实体。
"""
import json
import re

from app.api.routers.auth import _oauth_callback_html
from app.schemas.user import Token


def _make_token() -> Token:
    return Token(access_token="eyJhbGciOiJIUzI1NiJ9.payload.sig", token_type="bearer")


def test_callback_html_has_no_html_escaped_quotes():
    html_out = _oauth_callback_html(_make_token())
    # 绝不能出现 HTML 实体形式的引号（这正是旧 bug 的症状）
    assert "&quot;" not in html_out
    assert "JSON.parse('{" not in html_out  # 不再用被实体化的字符串字面量


def test_callback_html_embeds_parseable_token_literal():
    token = _make_token()
    html_out = _oauth_callback_html(token)
    # 取出 `const token = {...};` 内联的 JS 对象字面量（即合法 JSON），应可解析回原值
    m = re.search(r"const token = (\{.*?\});", html_out)
    assert m, "未找到内联 token 字面量"
    parsed = json.loads(m.group(1))
    assert parsed["access_token"] == token.access_token
    assert parsed["token_type"] == "bearer"


def test_callback_html_escapes_angle_bracket_to_prevent_script_breakout():
    # 即便 token 含 <，也应转义为 <，避免 </script> 截断
    token = Token(access_token="a<b/script>c", token_type="bearer")
    html_out = _oauth_callback_html(token)
    assert "</script>c" not in html_out
    assert "\\u003c" in html_out
