# AIMETA P=范文注入服务_风格锚定|R=范文库_场景匹配_注入|NR=不含API路由|E=ReferenceProseService|X=internal|A=范文注入|D=none|S=compute|RD=./README.ai
"""
ReferenceProseService: 范文注入服务

按场景类型从预置范文库中选择匹配的参考片段，注入到写作 prompt 中，
用 Few-Shot 方式锚定风格，比抽象的规则描述更有效。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..models import ReferenceNovel


@dataclass
class ProseReference:
    category: str
    label: str
    text: str
    note: str


PROSE_LIBRARY: List[ProseReference] = [
    # ---- 动作/打斗 ----
    ProseReference(
        category="action",
        label="动作场景·短句砸节奏",
        text=(
            "刀光一闪。\n"
            "他侧身，刀锋擦着耳尖过去，带起一缕碎发。\n"
            "没等对方收势，他左手已经扣住刀背——不是格挡，是借力。整个人顺着刀势旋了半圈，"
            "右肘像钉子一样砸在对方太阳穴上。\n"
            "闷响。\n"
            "那人往后踉跄了两步，眼神散了一瞬。就这一瞬够了。"
        ),
        note="注意短句制造冲击力，长句铺动态，'闷响'两字独立成段砸节奏",
    ),
    ProseReference(
        category="action",
        label="动作场景·体感代替描写",
        text=(
            "拳头还没落下来，他的胃已经开始翻涌——不是恐惧，是肾上腺素把晚饭顶了上来。\n"
            "牙齿咬住舌尖。血腥味冲进鼻腔，脑子反而清醒了几分。\n"
            "第一拳他没躲，硬吃在肋骨上。疼得整个左半边身子缩了一下，但他的手已经摸到了对方腰间的刀柄。"
        ),
        note="通过体感写战斗，读者跟着角色一起疼",
    ),
    # ---- 对话博弈 ----
    ProseReference(
        category="dialogue",
        label="对话·潜台词与停顿",
        text=(
            '"你最近还好？"她端着茶杯，没喝。\n'
            '"挺好的。"他说。\n'
            "两个人都没再开口。茶凉了，她才把杯子放下，手指在桌面上敲了两下。\n"
            '"我听说你把老宅卖了。"\n'
            '"嗯。"\n'
            '"卖了多少？"\n'
            '"够用。"\n'
            '她看了他一眼，笑了一下，那种笑不到眼睛里的笑。"够用就好。"'
        ),
        note="对话极简，潜台词全在动作和停顿里，'笑不到眼睛里'一句话刻画关系",
    ),
    ProseReference(
        category="dialogue",
        label="对话·打断与抢话",
        text=(
            '"事情是这样的，当时我——"\n'
            '"我知道当时什么情况。"老周把茶杯往桌上一顿，"你直接说，钱在哪。"\n'
            '"那不是钱的问题——"\n'
            '"那是什么问题？"老周站起来了。\n'
            "他张了张嘴，又闭上了。屋里安静了几秒。窗外有个小孩在哭，哭得断断续续的。\n"
            '"行，"他说，"你坐下，我慢慢说。"'
        ),
        note="打断制造紧张感，环境声侵入（小孩哭）打破僵局，'行'字转折自然",
    ),
    # ---- 幽默/吐槽 ----
    ProseReference(
        category="humor",
        label="幽默·内心吐槽",
        text=(
            "长老一脸慈祥地看着他，像看自家出息的孙子。\n"
            "如果忽略他手里那份三十二页的任务书的话。\n"
            '三十二页。他数了。每一页都写着"自愿"二字开头。一个有三十二页的"自愿"任务，'
            "自愿程度约等于把刀架在脖子上问你乐不乐意。"
        ),
        note="叙述者语气带态度，'三十二页'的重复制造喜感，吐槽点精准",
    ),
    ProseReference(
        category="humor",
        label="幽默·严肃中的不合时宜",
        text=(
            "千钧一发的瞬间，他脑子里闪过三个念头：第一，完了；第二，早上出门没带伞；"
            "第三，完了。\n"
            "后来他回忆起来，最让他想不通的是第二个念头。人快死的时候想的居然是伞。"
        ),
        note="生死关头想伞——反差制造笑点，且非常真实，人在极限状态思维确实会跳线",
    ),
    # ---- 情感/煽情 ----
    ProseReference(
        category="emotion",
        label="情感·克制的力度",
        text=(
            "她走了以后，他在原地站了很久。\n"
            "久到路灯亮了，又灭了。久到门口的包子铺开始支摊子了。\n"
            "他低头看了看手里的东西。一把钥匙，还带着她手心的温度。或者也可能是他自己攥出来的。\n"
            "他把钥匙放进口袋，往回走。走了两步想起来，又折回去，在包子铺买了两个菜包。\n"
            "习惯了。"
        ),
        note="最后两字'习惯了'比任何描写都重。买两个菜包——下意识还买两份——是最好的留白",
    ),
    ProseReference(
        category="emotion",
        label="情感·燃的直给",
        text=(
            "他浑身的骨头都在响，每一块都在抗议。膝盖已经跪了下去——不是他要跪，是身体扛不住了。\n"
            "台下安静了。有人已经开始摇头。\n"
            "但他的手还攥着剑。\n"
            "只要手没松，就还没输。\n"
            "他把剑往地上一插，借力站了起来。血顺着剑身往下淌，在地面上汇成一小滩。\n"
            '"继续。"他说。嗓子哑得像砂纸。'
        ),
        note="情绪直给不藏着，'只要手没松，就还没输'就是燃的本质——简单、直接、热血",
    ),
    # ---- 环境/氛围 ----
    ProseReference(
        category="atmosphere",
        label="氛围·感官浸入",
        text=(
            "酒馆里的空气是黏的，混着汗味、酒味和锅底烧糊的焦味。灯用的是最便宜的兽油，"
            "火苗发青，照得每个人脸上都像蒙了一层灰。\n"
            "靠窗那桌五个人在赌骰子，有个光头输急了，把碗往桌上一摔，汤溅了对面人一脸。"
            "对面那人抹了一把，骂了一句，继续摇。\n"
            "角落里，他正在数铜板。第三遍了，结果和前两遍一样——不够。"
        ),
        note="环境不是说明文，是角色浸泡其中的体验。赌骰子的细节不推剧情，但推真实感",
    ),
    # ---- 过渡/日常 ----
    ProseReference(
        category="transition",
        label="过渡·快速压缩",
        text=(
            "接下来三天无事可记。\n"
            "如果硬要说的话——他学会了劈柴，劈坏了两把斧头；认识了隔壁的张婶，"
            "被塞了三次红薯；以及发现了一个重要情报：这个镇上最好吃的面在北街第四家，"
            "但老板娘脾气极差，点面不能超过三秒，超了她就不做了。"
        ),
        note="三天压缩成一段，但不无聊——劈坏两把斧头、点面不超过三秒，细节有趣且塑造生活感",
    ),
]

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "action": ["打斗", "战斗", "打架", "出手", "动手", "交锋", "对决", "拼杀", "厮杀", "冲突", "追杀", "围杀"],
    "dialogue": ["对话", "谈判", "交涉", "博弈", "询问", "审问", "质问", "争论", "辩论", "密谈", "商议"],
    "humor": ["幽默", "搞笑", "吐槽", "调侃", "轻松", "日常", "欢乐"],
    "emotion": ["感动", "煽情", "离别", "重逢", "牺牲", "告白", "燃", "热血", "悲伤", "虐心"],
    "atmosphere": ["氛围", "环境", "世界观", "城镇", "场景", "阴森", "诡异", "压迫"],
    "transition": ["过渡", "衔接", "修炼", "日常", "准备", "时间跳跃"],
}


class ReferenceProseService:
    """根据场景类型从范文库中选择匹配的参考片段。"""

    @staticmethod
    def select_references(
        outline_summary: str,
        chapter_mission: Optional[dict] = None,
        project_reference_novels: Optional[List[ReferenceNovel]] = None,
        max_refs: int = 2,
    ) -> List[ProseReference]:
        combined_text = outline_summary or ""
        if chapter_mission:
            combined_text += " " + (chapter_mission.get("macro_beat_description") or "")
            scene_list = chapter_mission.get("scene_list") or []
            for scene in scene_list:
                combined_text += " " + (scene.get("goal") or "")

        scores: Dict[str, int] = {}
        for cat, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined_text)
            if score > 0:
                scores[cat] = score

        if not scores:
            top_cats = ["dialogue", "action"]
        else:
            top_cats = sorted(scores, key=scores.get, reverse=True)[:max_refs]

        selected: List[ProseReference] = []
        if project_reference_novels:
            for novel in project_reference_novels:
                text = novel.style_samples_content or ""
                if text:
                    selected.append(
                        ProseReference(
                            category="reference_library",
                            label=novel.title,
                            text=text,
                            note="来自参考小说库的风格样本",
                        )
                    )
                    if len(selected) >= max_refs:
                        return selected[:max_refs]

        if selected:
            return selected[:max_refs]

        for cat in top_cats:
            candidates = [r for r in PROSE_LIBRARY if r.category == cat]
            if candidates:
                selected.append(random.choice(candidates))

        return selected[:max_refs]

    @staticmethod
    def format_for_prompt(references: List[ProseReference]) -> str:
        if not references:
            return ""
        lines = [
            "[风格参考——不是让你抄，是让你感受这种\"味道\"和节奏。注意它如何用长短句交替、留白、体感描写来制造阅读体验]"
        ]
        for ref in references:
            lines.append(f"\n--- {ref.label} ---")
            lines.append(ref.text)
            lines.append(f"（{ref.note}）")
        return "\n".join(lines)
