# 预设配置优化模块

本模块简化预设配置，提供分层预设和可视化说明
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from enum import Enum


class PresetLevel(Enum):
    """预设级别"""
    BEGINNER = "beginner"   # 初级
    INTERMEDIATE = "intermediate"  # 中级
    ADVANCED = "advanced"   # 高级


class WritingPreset:
    """
    写作预设
    
    提供分层的预设配置，满足不同用户的需求
    """
    
    # 预设定义
    PRESETS = {
        # 初级预设 - 简单易用
        "quick": {
            "level": PresetLevel.BEGINNER,
            "name": "快速生成",
            "description": "快速生成初稿，适合灵感记录",
            "features": ["生成速度快", "基础质量", "适合初稿"],
            "suitable_for": ["快速记录灵感", "大纲扩展", "初稿撰写"],
            "config": {
                "version_count": 2,
                "enable_rag": True,
                "enable_consistency": False,
                "enable_enrichment": False,
                "enable_six_dimension": False,
                "enable_humanization": False,
                "enable_foreshadowing": False,
            },
            "estimated_time": "30秒",
        },
        "quality": {
            "level": PresetLevel.BEGINNER,
            "name": "质量优先",
            "description": "注重生成质量，适合正式写作",
            "features": ["质量优先", "多维评审", "自动修订"],
            "suitable_for": ["正式写作", "重要章节", "投稿准备"],
            "config": {
                "version_count": 3,
                "enable_rag": True,
                "enable_consistency": True,
                "enable_enrichment": True,
                "enable_six_dimension": True,
                "enable_humanization": True,
                "enable_foreshadowing": True,
            },
            "estimated_time": "2-3分钟",
        },
        
        # 中级预设 - 特色功能
        "style": {
            "level": PresetLevel.INTERMEDIATE,
            "name": "文笔打磨",
            "description": "强化文笔和风格，适合进阶作者",
            "features": ["文笔优化", "风格强化", "人味增强"],
            "suitable_for": ["追求文笔", "风格化写作", "精品章节"],
            "config": {
                "version_count": 3,
                "enable_rag": True,
                "enable_consistency": True,
                "enable_prose_sculpting": True,
                "enable_golden_paragraph": True,
                "enable_humanization": True,
                "enable_narrative_variety": True,
            },
            "estimated_time": "3-4分钟",
        },
        "爽点": {
            "level": PresetLevel.INTERMEDIATE,
            "name": "爽点强化",
            "description": "强化爽点和情感共鸣",
            "features": ["爽点增强", "情感共鸣", "节奏把控"],
            "suitable_for": ["高潮章节", "打脸情节", "情感爆发"],
            "config": {
                "version_count": 3,
                "enable_rag": True,
                "enable_consistency": True,
                "enable_enrichment": True,
                "enable_six_dimension": True,
                "humanization_threshold": 50,  # 更强的人味优化
            },
            "estimated_time": "2-3分钟",
        },
        
        # 高级预设 - 完整功能
        "platinum": {
            "level": PresetLevel.ADVANCED,
            "name": "铂金模式",
            "description": "完整功能，适合高要求写作",
            "features": ["六维评审", "自动修订", "伏笔追踪", "人味优化"],
            "suitable_for": ["精品创作", "长篇连载", "出版级稿件"],
            "config": {
                "version_count": 3,
                "enable_rag": True,
                "enable_consistency": True,
                "enable_enrichment": True,
                "enable_six_dimension": True,
                "enable_self_critique": True,
                "enable_humanization": True,
                "enable_foreshadowing": True,
                "enable_faction": True,
                "enable_persona": True,
            },
            "estimated_time": "5-10分钟",
        },
        
        # 极速模式
        "fast": {
            "level": PresetLevel.BEGINNER,
            "name": "极速模式",
            "description": "最快速度生成，适合快速迭代",
            "features": ["极速生成", "轻量处理", "适合大纲"],
            "suitable_for": ["快速迭代", "大纲测试", "灵感触发"],
            "config": {
                "version_count": 1,
                "enable_rag": False,
                "enable_fast_path": True,
                "enable_consistency": False,
                "enable_humanization": False,
            },
            "estimated_time": "10秒",
        },
    }
    
    @classmethod
    def get_preset(cls, preset_name: str) -> Optional[Dict[str, Any]]:
        """获取预设配置"""
        return cls.PRESETS.get(preset_name)
    
    @classmethod
    def get_presets_by_level(cls, level: PresetLevel) -> List[Dict[str, Any]]:
        """获取指定级别的所有预设"""
        result = []
        for name, preset in cls.PRESETS.items():
            if preset["level"] == level:
                result.append({
                    "name": name,
                    **preset
                })
        return result
    
    @classmethod
    def get_all_presets(cls) -> List[Dict[str, Any]]:
        """获取所有预设（带分组）"""
        return {
            "beginner": cls.get_presets_by_level(PresetLevel.BEGINNER),
            "intermediate": cls.get_presets_by_level(PresetLevel.INTERMEDIATE),
            "advanced": cls.get_presets_by_level(PresetLevel.ADVANCED),
        }
    
    @classmethod
    def convert_to_flow_config(cls, preset_name: str) -> Dict[str, Any]:
        """
        将预设转换为 PipelineConfig 格式
        
        Args:
            preset_name: 预设名称
            
        Returns:
            可以直接传给 PipelineOrchestrator 的 flow_config
        """
        preset = cls.get_preset(preset_name)
        if not preset:
            # 默认使用 quality
            preset = cls.get_preset("quality")
        
        return preset["config"]
    
    @classmethod
    def get_preset_for_scenario(cls, scenario: str) -> str:
        """
        根据场景推荐预设
        
        Args:
            scenario: 场景描述
            
        Returns:
            推荐的预设名称
        """
        scenario_map = {
            # 场景 -> 推荐预设
            "第一次使用": "quick",
            "快速写作": "quick",
            "灵感记录": "fast",
            "大纲扩展": "fast",
            "正式写作": "quality",
            "重要章节": "quality",
            "高潮": "爽点",
            "打脸": "爽点",
            "情感": "爽点",
            "文笔": "style",
            "风格": "style",
            "精品": "platinum",
            "长篇": "platinum",
            "出版": "platinum",
        }
        
        for key, preset in scenario_map.items():
            if key in scenario:
                return preset
        
        return "quality"  # 默认


# 便捷函数
def get_preset_config(preset_name: str) -> Dict[str, Any]:
    """获取预设配置的便捷函数"""
    return WritingPreset.convert_to_flow_config(preset_name)


def recommend_preset(scenario: str) -> str:
    """根据场景推荐预设的便捷函数"""
    return WritingPreset.get_preset_for_scenario(scenario)
