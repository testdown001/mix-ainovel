# AIMETA P=写作风格预设_内置风格定义|R=预设常量_禁用词|NR=不含DB操作|E=PRESETS,UNIVERSAL_BANNED_PHRASES,build_user_style_prompt|X=internal|A=常量定义|D=none|S=none|RD=./README.ai
"""内置写作风格预设与提示词构建工具。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.user_writing_preference import UserWritingPreference

# ---------- 公共禁用词表 ----------
UNIVERSAL_BANNED_PHRASES: list[str] = [
    "充满了", "深深地", "不禁", "缓缓地",
    "仿佛在诉说着", "似乎在暗示着",
    "内心深处", "灵魂深处",
    "命运的齿轮", "历史的车轮",
    "温情与力量", "珍贵的情感联结",
    "深刻地揭示了", "令人深思的",
    "这是一段", "这一刻，他/她明白了",
    "心中涌起一股", "一股暖流",
    "不由自主地", "情不自禁地",
]

# ---------- 4 个内置预设 ----------
PRESETS: dict[str, dict] = {
    "minimal_concrete": {
        "name": "白描克制",
        "description": "海明威式。动作推动叙事，极少修饰，一个动词胜过三个形容词。",
        "rules": (
            "[白描克制风格]\n"
            "核心原则：用动作和对话推进叙事，拒绝一切不承载信息的修饰。\n"
            "1. 动词优先：一个精准动词胜过三个形容词。\"他走进房间\"优于\"他缓缓地、沉重地、带着一丝疲惫地走进了那间昏暗的房间\"。\n"
            "2. 冰山理论：只写水面上的八分之一。角色的情绪通过行为和选择体现，不需要内心独白解释。\n"
            "3. 短句为主：句子控制在20字以内。长句只在需要制造节奏变化时使用。\n"
            "4. 对话克制：人物说话像真人——不完整、有停顿、会回避。不写\"他语重心长地说道\"这类归纳式对话标签。\n"
            "5. 场景即情绪：用环境细节传递氛围，不直接描写情绪。雨、风、光线、声音比\"他感到悲伤\"更有力。\n"
            "6. 禁止总结式抒情：不在段末写\"这一刻他终于明白了\"之类的总结句。让读者自己得出结论。\n"
            "\n示例对比：\n"
            "差：他不禁深深地叹了口气，心中涌起一股难以言喻的悲伤，仿佛整个世界的重量都压在了他的肩上。\n"
            "好：他把烟掐灭在烟灰缸里，站起来走到窗边。楼下的路灯亮了。"
        ),
        "banned_phrases": [
            "不禁", "缓缓地", "深深地", "心中涌起", "仿佛整个世界",
            "难以言喻", "语重心长", "百感交集",
        ],
    },
    "cold_realism": {
        "name": "冷硬现实",
        "description": "余华/王朔式。不避粗粝，对话驱动，干净利落。",
        "rules": (
            "[冷硬现实风格]\n"
            "核心原则：直面生活的粗粝质感，用冷静的笔触写残酷与荒诞。\n"
            "1. 零修饰叙事：叙述者是冷静的旁观者。不美化、不煽情、不评判。事情发生了，就这样写。\n"
            "2. 对话即性格：人物的身份、教育、阶层全部通过对话展现。方言、口头禅、语病都是工具。\n"
            "3. 黑色幽默：荒诞感来自事实本身，不需要刻意的修辞。越严肃地写荒诞事，越有力量。\n"
            "4. 身体感：写饥饿、疼痛、疲劳的生理细节，而非抽象的\"痛苦\"。身体比心灵诚实。\n"
            "5. 节制的暴力：暴力场景用克制的语言写，像手术刀而非大锤。一句话的暴力比一段话更令人不安。\n"
            "6. 无解即结局：不需要给所有冲突安排解决方案。生活本来就不整洁。\n"
            "\n示例对比：\n"
            "差：那一巴掌打碎了他所有的尊严，他的灵魂深处涌起了无尽的屈辱，命运的齿轮无情地碾过了他最后的骄傲。\n"
            "好：一巴掌扇过来的时候他没躲。嘴角破了，他用舌头舔了舔，咸的。"
        ),
        "banned_phrases": [
            "灵魂深处", "命运的齿轮", "无尽的屈辱", "涌起", "内心深处",
            "不由自主", "情不自禁",
        ],
    },
    "classic_elegant": {
        "name": "古典意境",
        "description": "汪曾祺式。讲究韵味，细节精准但绝不堆砌。",
        "rules": (
            "[古典意境风格]\n"
            "核心原则：用最少的笔墨写出最多的意味。每个字都要有份量。\n"
            "1. 白描底色+一笔点染：大量白描中偶尔一个精妙比喻，像水墨画的留白与浓墨。比喻频率不超过每500字一个。\n"
            "2. 五感细节：视觉之外，多写声音、气味、触感、温度。\"栀子花开了\"不如\"隔着墙都闻见栀子花的香气，甜得发腻\"。\n"
            "3. 食物与节气：用食物和时令写生活质感。这是中国古典叙事的传统。\n"
            "4. 散文化节奏：段落长短错落，有呼吸感。长段写景叙事后，用一两句短句收束。\n"
            "5. 含蓄的情感：大悲大喜都不直说。\"他没有说话\"比\"他悲痛欲绝\"高级一百倍。\n"
            "6. 掌故与闲笔：允许适度离题，写一段看似无关的闲话，实则暗扣主题。但不超过全文5%。\n"
            "\n示例对比：\n"
            "差：春天来了，万物复苏，充满了生机与活力。阳光温暖地洒在大地上，仿佛在诉说着新生的喜悦。\n"
            "好：清明前后，河边的柳树抽了芽。老王头每天早上去河边遛弯，顺便掐几根嫩柳条回来，泡在玻璃瓶里搁窗台上。"
        ),
        "banned_phrases": [
            "万物复苏", "生机与活力", "仿佛在诉说", "温暖地洒",
            "充满了", "岁月静好",
        ],
    },
    "webnovel_fast": {
        "name": "网文节奏",
        "description": "快节奏、爽点密集、对话多、钩子强。",
        "rules": (
            "[网文节奏风格]\n"
            "核心原则：节奏为王，每500字至少一个信息增量或情绪转折。读者一旦想划走就是失败。\n"
            "1. 钩子前置：每个章节、每个场景开头都要有悬念或冲突。\"他推开门\"不如\"他推开门——屋里坐着三个不该出现的人\"。\n"
            "2. 对话密度：正文中对话占比不低于40%。对话要短、快、有信息量。三句话说完的事不要写五句。\n"
            "3. 爽点节奏：打脸、逆袭、升级、揭秘等爽点按 铺垫→激化→爆发 三段式安排，铺垫不超过500字。\n"
            "4. 尾钩必备：每章结尾必须留一个钩子——新危机、新线索、反转预兆。\"未完\"不是钩子。\n"
            "5. 禁止水文：心理活动不超过连续3句。景物描写不超过连续2句。回忆闪回不超过200字。\n"
            "6. 信息控制：关键情报分批释放，每次只给读者一块拼图。全知视角用于制造dramatic irony，不用于信息灌输。\n"
            "\n示例对比：\n"
            "差：经过了漫长的等待和深深的思考，他终于做出了一个艰难的决定。这个决定将会改变他的一生。\n"
            "好：\"三天。\"他竖起三根手指，\"三天之内我要看到结果，否则——\"他没说下去。在场的人都知道\"否则\"后面是什么。"
        ),
        "banned_phrases": [
            "漫长的等待", "深深的思考", "艰难的决定",
            "这个决定将会改变", "经过了",
        ],
    },
}


def get_preset_list() -> list[dict]:
    """返回供前端展示的预设列表（不含完整 rules）。"""
    result = []
    for key, preset in PRESETS.items():
        result.append({
            "key": key,
            "name": preset["name"],
            "description": preset["description"],
            "banned_phrases": preset["banned_phrases"],
        })
    return result


def build_user_style_prompt(preference: "UserWritingPreference") -> str:
    """将用户偏好合并为提示词文本。"""
    parts: list[str] = []
    if preference.style_preset and preference.style_preset in PRESETS:
        parts.append(PRESETS[preference.style_preset]["rules"])
    if preference.custom_rules:
        parts.append(f"[用户自定义规则]\n{preference.custom_rules}")
    # 合并禁用词：预设通用 + 预设专属 + 用户自定义
    all_banned: list[str] = list(UNIVERSAL_BANNED_PHRASES)
    if preference.style_preset and preference.style_preset in PRESETS:
        all_banned.extend(PRESETS[preference.style_preset]["banned_phrases"])
    if preference.banned_phrases:
        all_banned.extend(preference.banned_phrases)
    # 去重
    seen: set[str] = set()
    unique_banned: list[str] = []
    for phrase in all_banned:
        if phrase not in seen:
            seen.add(phrase)
            unique_banned.append(phrase)
    if unique_banned:
        parts.append(f"[禁用词表] 以下词汇/句式绝对禁止使用：\n{', '.join(unique_banned)}")
    return "\n\n".join(parts)
