# AIMETA P=题材自适应服务_题材配置管理|R=题材Profile加载_复合题材合并_Prompt注入|NR=不含LLM调用|E=GenreProfileService|X=internal|A=题材配置|D=none|S=none|RD=./README.ai
"""
题材自适应服务 (GenreProfileService)

内置多种网文题材配置（爽文/仙侠/言情/悬疑/都市异能），每种题材有独立的：
- 钩子配置 (hook_config)
- 爽点配置 (coolpoint_config)
- 微满足配置 (micropayoff_config)
- 节奏配置 (pacing_config)
- 温度覆盖 (temperature_override)
- 护栏覆盖 (guardrail_override)

遵循奥卡姆剃刀：题材 profile 为代码内置常量，不引入数据库表。
"""
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== 题材 Profile 常量定义 ====================

GENRE_PROFILES: Dict[str, Dict[str, Any]] = {
    "爽文": {
        "name": "爽文",
        "description": "以读者爽感为核心驱动的网文类型",
        "hook_config": {
            "opening_hook_mandatory": True,
            "preferred_types": ["成就达成", "实力碾压", "身份揭示"],
            "min_hooks_per_chapter": 2,
        },
        "coolpoint_config": {
            "interval": 2,
            "types": ["碾压", "逆袭", "获宝", "升级", "打脸"],
            "density": "high",
        },
        "micropayoff_config": {
            "per_chapter_min": 2,
            "types": ["小胜", "获得认可", "意外收获", "技能领悟"],
        },
        "pacing_config": {
            "quest_ratio": 0.55,
            "fire_ratio": 0.30,
            "constellation_ratio": 0.15,
            "max_buildup_chapters": 2,
        },
        "temperature_override": {
            "coolpoint_chapter": 0.85,
            "buildup_chapter": 0.60,
        },
        "guardrail_override": {
            "omniscient_tolerance": "medium",
        },
    },
    "仙侠": {
        "name": "仙侠",
        "description": "以修仙求道为核心的东方幻想类型",
        "hook_config": {
            "opening_hook_mandatory": True,
            "preferred_types": ["境界突破", "功法领悟", "天劫来临"],
            "min_hooks_per_chapter": 1,
        },
        "coolpoint_config": {
            "interval": 3,
            "types": ["碾压", "顿悟", "获宝", "渡劫成功", "越级战斗"],
            "density": "medium",
        },
        "micropayoff_config": {
            "per_chapter_min": 1,
            "types": ["修为进步", "灵草灵矿", "前辈认可", "道法感悟"],
        },
        "pacing_config": {
            "quest_ratio": 0.60,
            "fire_ratio": 0.25,
            "constellation_ratio": 0.15,
            "max_buildup_chapters": 4,
        },
        "temperature_override": {
            "coolpoint_chapter": 0.85,
            "buildup_chapter": 0.65,
        },
        "guardrail_override": {
            "omniscient_tolerance": "medium",
        },
    },
    "言情": {
        "name": "言情",
        "description": "以情感关系为核心的恋爱类型",
        "hook_config": {
            "opening_hook_mandatory": False,
            "preferred_types": ["误会产生", "心动瞬间", "身份秘密"],
            "min_hooks_per_chapter": 1,
        },
        "coolpoint_config": {
            "interval": 4,
            "types": ["甜蜜互动", "守护时刻", "误会解除", "告白"],
            "density": "low",
        },
        "micropayoff_config": {
            "per_chapter_min": 1,
            "types": ["暧昧升级", "日常甜蜜", "相互理解", "心意传达"],
        },
        "pacing_config": {
            "quest_ratio": 0.45,
            "fire_ratio": 0.20,
            "constellation_ratio": 0.35,
            "max_buildup_chapters": 5,
        },
        "temperature_override": {
            "coolpoint_chapter": 0.80,
            "buildup_chapter": 0.70,
        },
        "guardrail_override": {
            "omniscient_tolerance": "loose",
        },
    },
    "悬疑": {
        "name": "悬疑",
        "description": "以解谜推理为核心的智力对抗类型",
        "hook_config": {
            "opening_hook_mandatory": True,
            "preferred_types": ["新线索", "反转", "死局出现"],
            "min_hooks_per_chapter": 2,
        },
        "coolpoint_config": {
            "interval": 3,
            "types": ["真相揭示", "推理突破", "反转", "悬念升级"],
            "density": "medium",
        },
        "micropayoff_config": {
            "per_chapter_min": 1,
            "types": ["线索发现", "排除嫌疑", "关键证据", "逻辑链闭合"],
        },
        "pacing_config": {
            "quest_ratio": 0.65,
            "fire_ratio": 0.20,
            "constellation_ratio": 0.15,
            "max_buildup_chapters": 3,
        },
        "temperature_override": {
            "coolpoint_chapter": 0.75,
            "buildup_chapter": 0.60,
        },
        "guardrail_override": {
            "omniscient_tolerance": "strict",
        },
    },
    "都市异能": {
        "name": "都市异能",
        "description": "以现代都市为背景、角色拥有超能力的类型",
        "hook_config": {
            "opening_hook_mandatory": True,
            "preferred_types": ["能力觉醒", "危机出现", "身份暴露危机"],
            "min_hooks_per_chapter": 1,
        },
        "coolpoint_config": {
            "interval": 3,
            "types": ["能力进化", "碾压", "逆袭", "身份揭示", "救人"],
            "density": "medium",
        },
        "micropayoff_config": {
            "per_chapter_min": 1,
            "types": ["能力小突破", "获得情报", "赢得信任", "化解危机"],
        },
        "pacing_config": {
            "quest_ratio": 0.55,
            "fire_ratio": 0.30,
            "constellation_ratio": 0.15,
            "max_buildup_chapters": 3,
        },
        "temperature_override": {
            "coolpoint_chapter": 0.85,
            "buildup_chapter": 0.65,
        },
        "guardrail_override": {
            "omniscient_tolerance": "medium",
        },
    },
}

# 题材别名映射
GENRE_ALIASES: Dict[str, str] = {
    "shuangwen": "爽文",
    "xianxia": "仙侠",
    "romance": "言情",
    "mystery": "悬疑",
    "urban_fantasy": "都市异能",
    "都市": "都市异能",
    "修仙": "仙侠",
    "修真": "仙侠",
    "恋爱": "言情",
    "推理": "悬疑",
    "异能": "都市异能",
}


class GenreProfileService:
    """题材配置服务：加载、合并和注入题材约束。"""

    @staticmethod
    def get_profile(genre: str) -> Optional[Dict[str, Any]]:
        """获取题材配置。支持别名查找。"""
        normalized = genre.strip().lower() if genre else ""
        key = GENRE_ALIASES.get(normalized, genre.strip() if genre else "")
        profile = GENRE_PROFILES.get(key)
        if profile:
            return deepcopy(profile)
        for pkey, pval in GENRE_PROFILES.items():
            if pkey.lower() == normalized or normalized in pkey.lower():
                return deepcopy(pval)
        return None

    @staticmethod
    def merge_profiles(genres: List[str], weights: Optional[List[float]] = None) -> Dict[str, Any]:
        """合并多个题材配置（复合题材），按权重加权。"""
        profiles = []
        for g in genres:
            p = GenreProfileService.get_profile(g)
            if p:
                profiles.append(p)

        if not profiles:
            return {}
        if len(profiles) == 1:
            return profiles[0]

        if weights is None:
            weights = [1.0 / len(profiles)] * len(profiles)
        else:
            total = sum(weights)
            weights = [w / total for w in weights] if total > 0 else [1.0 / len(profiles)] * len(profiles)

        merged = deepcopy(profiles[0])
        merged["name"] = "+".join(p["name"] for p in profiles)
        merged["description"] = "复合题材：" + "、".join(p["name"] for p in profiles)

        # 加权合并 pacing_config
        for ratio_key in ("quest_ratio", "fire_ratio", "constellation_ratio"):
            merged["pacing_config"][ratio_key] = sum(
                p["pacing_config"].get(ratio_key, 0) * w
                for p, w in zip(profiles, weights)
            )

        # 合并 coolpoint types
        all_types = []
        for p in profiles:
            all_types.extend(p.get("coolpoint_config", {}).get("types", []))
        merged["coolpoint_config"]["types"] = list(dict.fromkeys(all_types))

        # 取最严格的护栏
        tolerance_order = {"strict": 0, "medium": 1, "loose": 2}
        strictest = min(
            (p.get("guardrail_override", {}).get("omniscient_tolerance", "medium") for p in profiles),
            key=lambda t: tolerance_order.get(t, 1),
        )
        merged["guardrail_override"]["omniscient_tolerance"] = strictest

        return merged

    @staticmethod
    def build_genre_prompt_injection(profile: Dict[str, Any]) -> str:
        """将题材配置转化为可注入 prompt 的文本。"""
        if not profile:
            return ""

        name = profile.get("name", "未知题材")
        lines = [f"[题材约束：{name}]"]

        hook_cfg = profile.get("hook_config", {})
        if hook_cfg.get("opening_hook_mandatory"):
            lines.append(f"- 开头钩子必须存在，推荐类型：{'、'.join(hook_cfg.get('preferred_types', []))}")
        lines.append(f"- 每章至少 {hook_cfg.get('min_hooks_per_chapter', 1)} 个钩子")

        cool_cfg = profile.get("coolpoint_config", {})
        lines.append(f"- 爽点密度：{cool_cfg.get('density', 'medium')}，每 {cool_cfg.get('interval', 3)} 章至少 1 个爽点")
        lines.append(f"- 推荐爽点类型：{'、'.join(cool_cfg.get('types', [])[:5])}")

        micro_cfg = profile.get("micropayoff_config", {})
        lines.append(f"- 每章至少 {micro_cfg.get('per_chapter_min', 1)} 个微满足（如：{'、'.join(micro_cfg.get('types', [])[:4])}）")

        pacing_cfg = profile.get("pacing_config", {})
        lines.append(f"- 节奏配比：Quest={pacing_cfg.get('quest_ratio', 0.6):.0%} / Fire={pacing_cfg.get('fire_ratio', 0.25):.0%} / Constellation={pacing_cfg.get('constellation_ratio', 0.15):.0%}")
        lines.append(f"- 最大蓄力章节数：{pacing_cfg.get('max_buildup_chapters', 3)}")

        return "\n".join(lines)

    @staticmethod
    def resolve_temperature(
        profile: Optional[Dict[str, Any]],
        chapter_mission: Optional[dict],
        default_temperature: float = 0.75,
    ) -> float:
        """根据题材和章节类型决定生成温度。"""
        if not profile:
            return default_temperature

        temp_override = profile.get("temperature_override", {})
        if not chapter_mission or not temp_override:
            return default_temperature

        macro_beat = (chapter_mission.get("macro_beat") or "").lower()
        sat_type = (chapter_mission.get("satisfaction_design") or {}).get("type", "")

        if sat_type and sat_type != "无（蓄力中）":
            return temp_override.get("coolpoint_chapter", default_temperature)
        for kw in ("高潮", "爆发", "反转", "碾压", "决战", "爽"):
            if kw in macro_beat:
                return temp_override.get("coolpoint_chapter", default_temperature)
        for kw in ("蓄力", "铺垫", "布局", "过渡", "日常"):
            if kw in macro_beat:
                return temp_override.get("buildup_chapter", default_temperature)

        return default_temperature

    @staticmethod
    def get_omniscient_tolerance(profile: Optional[Dict[str, Any]]) -> str:
        """获取题材的全知视角容忍度。"""
        if not profile:
            return "medium"
        return profile.get("guardrail_override", {}).get("omniscient_tolerance", "medium")

    @staticmethod
    def list_available_genres() -> List[str]:
        """列出所有可用题材。"""
        return list(GENRE_PROFILES.keys())
