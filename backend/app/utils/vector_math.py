# AIMETA P=向量数学工具_纯Python余弦相似度|R=cosine_similarity|E=cosine_similarity|X=internal|A=纯函数|D=|S=
"""小规模向量运算工具。

适用场景：几十条以内的候选打分（如参考桥段按情境选取），不值得为此建 Qdrant
collection——一次 batch embedding + 内存排序就够。大规模检索走 VectorStoreService。
"""
from __future__ import annotations

import math
from typing import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """余弦相似度；维度不匹配或零向量返回 0（调用方不必再防御）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
