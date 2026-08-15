# AIMETA P=平台敏感词预检|R=对照起点番茄晋江词表扫描|NR=不含叙事护栏|E=precheck_text|X=internal|A=预检|D=json|S=compute
"""投稿前敏感词预检。命中只提示，不拦截——我们不是平台审核方。"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.system_config_repository import SystemConfigRepository

_DEFAULTS: Dict[str, List[str]] = {
    "qidian": ["详细血腥描写", "现实政治影射", "未成年恋爱"],
    "fanqie": ["详细血腥描写", "现实政治影射", "未成年恋爱"],
    "jjwxc": ["详细血腥描写", "现实政治影射"],
}

_KEY = {
    "qidian": "compliance.lexicon.qidian",
    "fanqie": "compliance.lexicon.fanqie",
    "jjwxc": "compliance.lexicon.jjwxc",
}


async def load_lexicon(session: AsyncSession, platform: str) -> List[str]:
    key = _KEY.get(platform, _KEY["qidian"])
    rec = await SystemConfigRepository(session).get_by_key(key)
    if rec and rec.value:
        try:
            data = json.loads(rec.value)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            return [line.strip() for line in str(rec.value).splitlines() if line.strip()]
    return list(_DEFAULTS.get(platform, _DEFAULTS["qidian"]))


def scan_text(text: str, terms: List[str]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    hay = text or ""
    for term in terms:
        start = 0
        while True:
            idx = hay.find(term, start)
            if idx < 0:
                break
            hits.append({
                "term": term,
                "index": idx,
                "snippet": hay[max(0, idx - 16): idx + len(term) + 16],
                "hint": "平台可能审核，建议改写或删除后再投稿。",
            })
            start = idx + max(1, len(term))
    return hits


async def precheck_text(session: AsyncSession, platform: str, text: str) -> Dict[str, Any]:
    plat = platform if platform in _KEY else "qidian"
    terms = await load_lexicon(session, plat)
    hits = scan_text(text, terms)
    return {"platform": plat, "hit_count": len(hits), "hits": hits[:80]}
