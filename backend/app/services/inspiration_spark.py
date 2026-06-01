# AIMETA P=灵感扰动池|R=为概念对话注入随机创意激发(Oblique Strategies式)|NR=不含LLM调用|E=pick_spark,build_spark_injection|X=internal|A=工具|D=random|S=none|RD=./README.ai
"""灵感扰动池（借鉴 Brian Eno《Oblique Strategies》+ Hermes 渐进披露的技能化创意手法）。

目的：概念对话(灵感模式)历史上是"照清单填空"的问卷式收敛，建议雷同、缺意外感。
本模块提供一组精选的"创意激发卡"，每轮随机注入一条到 system prompt，
促使「文思」跳出俗套——做跨域类比、反转、受约束激发、感官/时空错位等发散。

注意：扰动只是"暗中借力"的发散燃料，不应喧宾夺主、不应强行套用；
注入文案会明确要求模型仅在自然、契合用户意图时使用，可一键关闭(disable)。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SparkCard:
    category: str  # 跨域类比 / 反转 / 约束 / 感官 / 时空 / 人物 / 结构
    prompt: str


# 精选激发卡（覆盖多种发散维度，避免同质）
SPARK_CARDS: List[SparkCard] = [
    SparkCard("跨域类比", "用一门看似无关的学科（经济学/生态学/外科/赌博/官僚制）的底层逻辑去重构这个故事的核心冲突或力量体系。"),
    SparkCard("跨域类比", "把这个题材最像的'现实行业'找出来，借它的潜规则、黑话与晋升链条来给世界观注入质感。"),
    SparkCard("反转", "把读者最可能预期的那个开局/身份/结局反过来——谁是真正的弱者？谁的胜利其实是陷阱？"),
    SparkCard("反转", "让主角的'金手指/优势'同时是他最大的诅咒，越用越接近毁灭。"),
    SparkCard("反转", "把通常的善恶/敌我关系做一次彻底倒置，但保留情感上的可信度。"),
    SparkCard("约束", "强加一条反直觉的硬规则（如：主角不能说谎/记忆每章清零/夜里才能变强），看它如何逼出新剧情。"),
    SparkCard("约束", "把故事压缩进一个极端受限的舞台（一座孤岛/一栋楼/一场永不结束的宴会/一节车厢）。"),
    SparkCard("感官", "先想象这个世界'闻起来、听起来、摸起来'是什么样，再从这种独特质感倒推设定。"),
    SparkCard("时空", "把背景挪到一个反常的时间锚点（反季节/末日后第N年/一个被重复的日子/历史拐点的前夜）。"),
    SparkCard("时空", "让两个本不该相遇的时代/文明/科技层级在故事里强行碰撞。"),
    SparkCard("人物", "给主角一个与其目标直接矛盾的隐秘身份或羁绊，让每一步前进都付出代价。"),
    SparkCard("人物", "用一个'非常规视角人物'（旁观者/反派/物件/亡者/AI/孩子）来讲这个故事，换一种灵气。"),
    SparkCard("结构", "为这本书设计一个独特的'连载节律装置'（每卷一个谜底/每十章一次世界观翻案/双线最终合流）。"),
    SparkCard("结构", "先想好这本书最高光的那一幕'封神场面'，再倒推前面所有铺垫该怎么埋。"),
    SparkCard("情绪", "锁定一种你想让读者反复体验的核心情绪（窒息感/爽快/心碎/毛骨悚然/治愈），让所有设定为它服务。"),
    SparkCard("混搭", "把两个看似冲突的类型基因强行嫁接（如：温情日常×宇宙恐怖、硬核权谋×沙雕喜剧）。"),
    SparkCard("世界观", "找一个被主流套路忽略的'设定缝隙'（这个体系的废料去哪了？神死后世界怎么运转？）深挖成卖点。"),
    SparkCard("代价", "给世界里最爽的那个能力配一个让人肉痛的、会持续累积的代价系统。"),
]


def pick_spark(rng: Optional[random.Random] = None) -> SparkCard:
    """随机抽取一张激发卡。测试可传入带种子的 Random 以保证确定性。"""
    chooser = rng or random
    return chooser.choice(SPARK_CARDS)


def build_spark_injection(card: SparkCard) -> str:
    """构造注入到 system prompt 的激发段。强调'自然借力、不喧宾夺主、可舍弃'。"""
    return (
        "\n\n## 本轮灵感激发（仅你可见，切勿直接复述给用户）\n"
        f"创意角度【{card.category}】：{card.prompt}\n"
        "用法：把它当作发散燃料——当它能让你给出更新鲜、更具画面感、更跳脱俗套的方向时，"
        "自然地融入你的提案或追问；若与用户当前意图不契合，可以忽略，绝不要为了用而用，"
        "也不要在 ai_message 里提及'灵感卡/激发角度'这类元话术。"
    )
