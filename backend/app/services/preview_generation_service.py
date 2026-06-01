"""
预演-正式两阶段生成服务

先生成章节预览（500字），确认方向后再扩写成完整章节。
"""
from typing import Optional, Dict, Any, List
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from .llm_service import LLMService
from .prompt_service import PromptService
from ..core.config import settings
from ..utils.json_utils import parse_llm_json
from ..core.constants import CHAPTER_MIN_WORDS, CHAPTER_MAX_WORDS

logger = logging.getLogger(__name__)


class PreviewGenerationService:
    """预演-正式两阶段生成服务"""

    def __init__(self, db: AsyncSession, llm_service: LLMService, prompt_service: PromptService):
        self.db = db
        self.llm_service = llm_service
        self.prompt_service = prompt_service

    @staticmethod
    def _resolve_word_count_bounds() -> tuple[int, int]:
        """解析章节字数上下限，优先使用运行时配置。"""
        try:
            min_words = int(getattr(settings, "writer_chapter_word_count_min", CHAPTER_MIN_WORDS))
        except (TypeError, ValueError):
            min_words = CHAPTER_MIN_WORDS
        try:
            max_words = int(getattr(settings, "writer_chapter_word_count_max", CHAPTER_MAX_WORDS))
        except (TypeError, ValueError):
            max_words = CHAPTER_MAX_WORDS

        if min_words < 1:
            min_words = CHAPTER_MIN_WORDS
        if max_words < min_words:
            max_words = min_words
        return min_words, max_words

    def _normalize_plot_points(self, preview: Dict[str, Any]) -> List[Dict[str, Any]]:
        """标准化并按顺序排序关键情节点。"""
        raw_points = preview.get("key_plot_points", [])
        if not isinstance(raw_points, list):
            raw_points = []

        normalized: List[Dict[str, Any]] = []
        for index, point in enumerate(raw_points, start=1):
            if not isinstance(point, dict):
                continue

            description = str(point.get("description", "")).strip()
            if not description:
                continue

            try:
                order = int(point.get("order", index))
            except (TypeError, ValueError):
                order = index

            normalized.append(
                {
                    "order": order,
                    "description": description,
                    "purpose": str(point.get("purpose", "")).strip(),
                    "emotion_target": str(point.get("emotion_target", "")).strip(),
                }
            )

        normalized.sort(key=lambda item: item["order"])
        for index, item in enumerate(normalized, start=1):
            item["order"] = index

        if normalized:
            return normalized

        preview_text = str(preview.get("preview_text", "")).strip()
        if preview_text:
            return [
                {
                    "order": 1,
                    "description": preview_text[:120].replace("\n", " "),
                    "purpose": "沿预览主线推进",
                    "emotion_target": "与预览保持一致",
                }
            ]

        return []

    def _build_plot_point_checklist(self, plot_points: List[Dict[str, Any]]) -> str:
        """生成阶段 3 扩写执行清单，约束模型按顺序展开。"""
        if not plot_points:
            return "1. 以章节大纲摘要为主线推进，形成清晰的起承转合。"

        lines: List[str] = []
        for point in plot_points:
            lines.append(
                f"{point['order']}. {point['description']}（作用：{point.get('purpose') or '推进主线'}；"
                f"目标情绪：{point.get('emotion_target') or '与上下文一致'}）"
            )
        return "\n".join(lines)

    async def generate_preview(
        self,
        project_id: str,
        chapter_number: int,
        outline: Dict[str, Any],
        blueprint_context: str,
        emotion_context: str,
        memory_context: str,
        style_hint: str = "",
        user_id: int = 0
    ) -> Dict[str, Any]:
        """
        生成章节预览（500字左右）
        
        Returns:
            包含预览内容、关键情节点、预期效果的字典
        """
        prompt = f"""你是一位资深网文作者，现在需要为第 {chapter_number} 章生成一个简短的"章节预览"。

[蓝图上下文]
{blueprint_context[:3000]}

[情绪曲线指导]
{emotion_context}

[记忆层上下文]
{memory_context[:2000]}

[本章大纲]
标题：{outline.get('title', '')}
摘要：{outline.get('summary', '')}

[风格提示]
{style_hint or '无特殊要求'}

请生成一个 500 字左右的"章节预览"，包含：
1. 开场设定（时间、地点、人物状态）
2. 3-5 个关键情节点（按顺序）
3. 章节结尾的钩子设计
4. 预期的读者情绪变化

以 JSON 格式输出：
```json
{{
  "preview_text": "500字左右的章节预览正文",
  "key_plot_points": [
    {{
      "order": 1,
      "description": "情节点描述",
      "purpose": "这个情节点的作用",
      "emotion_target": "预期读者情绪"
    }}
  ],
  "opening": {{
    "time": "时间设定",
    "location": "地点",
    "character_states": ["角色1的状态", "角色2的状态"]
  }},
  "ending_hook": {{
    "type": "悬念/冲突/期待/情感",
    "description": "钩子描述"
  }},
  "expected_emotions": ["情绪1", "情绪2", "情绪3"]
}}
```"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位资深网文作者，擅长规划章节结构。请严格按照 JSON 格式输出。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.7,
                user_id=user_id,
                timeout=120.0
            )
            
            result = parse_llm_json(response, default=None)
            if isinstance(result, dict):
                result["status"] = "success"
                return result
        except Exception as e:
            logger.warning(f"生成章节预览失败: {e}")
        
        return {
            "status": "failed",
            "preview_text": "",
            "key_plot_points": [],
            "error": "生成预览失败"
        }

    async def evaluate_preview(
        self,
        preview: Dict[str, Any],
        outline: Dict[str, Any],
        emotion_context: str,
        user_id: int = 0
    ) -> Dict[str, Any]:
        """
        评估章节预览的质量
        
        Returns:
            包含评分、问题、建议的字典
        """
        prompt = f"""评估以下章节预览的质量。

[章节大纲]
标题：{outline.get('title', '')}
摘要：{outline.get('summary', '')}

[情绪曲线要求]
{emotion_context}

[章节预览]
{preview.get('preview_text', '')}

[关键情节点]
{json.dumps(preview.get('key_plot_points', []), ensure_ascii=False, indent=2)}

请评估以下方面：
1. 是否符合大纲要求
2. 情节点安排是否合理
3. 情绪节奏是否符合曲线要求
4. 钩子设计是否有效
5. 是否存在明显问题

以 JSON 格式输出：
```json
{{
  "overall_score": 1-100,
  "scores": {{
    "outline_compliance": 1-100,
    "plot_arrangement": 1-100,
    "emotion_rhythm": 1-100,
    "hook_effectiveness": 1-100
  }},
  "issues": [
    {{
      "severity": "critical/warning/minor",
      "description": "问题描述",
      "suggestion": "修改建议"
    }}
  ],
  "approved": true/false,
  "revision_needed": true/false,
  "revision_suggestions": ["修改建议1", "修改建议2"]
}}
```"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位资深网文编辑，擅长评估章节结构。请严格按照 JSON 格式输出。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.3,
                user_id=user_id,
                timeout=90.0
            )
            
            result = parse_llm_json(response, default=None)
            if isinstance(result, dict):
                return result
        except Exception as e:
            logger.warning(f"评估章节预览失败: {e}")
        
        return {
            "overall_score": 70,
            "approved": True,
            "revision_needed": False,
            "issues": []
        }

    async def expand_preview_to_full_chapter(
        self,
        preview: Dict[str, Any],
        outline: Dict[str, Any],
        blueprint_context: str,
        memory_context: str,
        target_word_count: int = 3000,
        style_hint: str = "",
        user_id: int = 0
    ) -> str:
        """
        将预览扩写成完整章节
        
        Args:
            preview: 章节预览
            outline: 章节大纲
            blueprint_context: 蓝图上下文
            memory_context: 记忆层上下文
            target_word_count: 目标字数
            style_hint: 风格提示
        
        Returns:
            完整的章节正文
        """
        min_words, max_words = self._resolve_word_count_bounds()
        target_word_count = max(min_words, min(max_words, target_word_count))
        normalized_plot_points = self._normalize_plot_points(preview)
        plot_point_checklist = self._build_plot_point_checklist(normalized_plot_points)
        preview_text = str(preview.get("preview_text", "")).strip()
        if not preview_text:
            preview_text = f"根据大纲扩写：{outline.get('summary', '')}".strip()

        expected_emotions = preview.get("expected_emotions", [])
        if not isinstance(expected_emotions, list):
            expected_emotions = []

        prompt = f"""你是一位资深网文作者，现在需要将章节预览扩写成完整的章节正文。

[蓝图上下文]
{blueprint_context[:3000]}

[记忆层上下文]
{memory_context[:2000]}

[章节大纲]
标题：{outline.get('title', '')}
摘要：{outline.get('summary', '')}

[章节预览]
{preview_text}

[关键情节点（已标准化顺序）]
{json.dumps(normalized_plot_points, ensure_ascii=False, indent=2)}

[情节点执行清单]
{plot_point_checklist}

[开场设定]
{json.dumps(preview.get('opening', {}), ensure_ascii=False, indent=2)}

[结尾钩子]
{json.dumps(preview.get('ending_hook', {}), ensure_ascii=False, indent=2)}

[预期读者情绪]
{json.dumps(expected_emotions, ensure_ascii=False, indent=2)}

[风格提示]
{style_hint or '无特殊要求'}

[字数硬约束]
- 正文字数目标区间：{min_words} 到 {max_words} 字
- 建议目标字数：{target_word_count} 字左右（可随剧情节奏上下浮动）
- 冲突场景可多用短句提速，铺垫/心理段可用长句展开，长短句需交替，不要整章同一节奏

请严格按照预览中的情节点顺序，扩写成完整的章节正文。

写作要求：
1. 必须按“情节点执行清单”顺序推进，不得跳序、逆序或遗漏
2. 必须覆盖预览中的所有关键情节点（可扩展细节，不可删除主干事件）
3. 开场必须符合设定的时间、地点、人物状态
4. 结尾必须实现设计的钩子
5. 使用镜头语言，多写动作、对话、感官描写
6. 禁止总结性结尾，禁止"他知道..."、"他明白..."等全知视角
7. 禁止使用"值得注意的是"、"总而言之"等 AI 典型词汇

直接输出章节正文，不要输出 JSON 或其他格式。"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一位资深网文作者，文笔流畅，擅长写出让读者欲罢不能的章节。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.8,
                user_id=user_id,
                timeout=180.0
            )
            
            return response.strip()
        except Exception as e:
            logger.error(f"扩写章节失败: {e}")
            return ""

    async def generate_with_preview(
        self,
        project_id: str,
        chapter_number: int,
        outline: Dict[str, Any],
        blueprint_context: str,
        emotion_context: str,
        memory_context: str,
        target_word_count: int = 3000,
        style_hint: str = "",
        auto_approve: bool = True,
        max_preview_retries: int = 2,
        user_id: int = 0
    ) -> Dict[str, Any]:
        """
        完整的三阶段生成流程（预览生成 -> 预览评估 -> 扩写正文）
        
        Args:
            auto_approve: 是否自动批准预览（True 则不需要人工确认）
            max_preview_retries: 预览不通过时的最大重试次数
        
        Returns:
            包含预览、评估、正文的完整结果
        """
        result = {
            "preview": None,
            "evaluation": None,
            "full_chapter": "",
            "retries": 0,
            "status": "pending"
        }
        min_words, max_words = self._resolve_word_count_bounds()
        target_word_count = max(min_words, min(max_words, target_word_count))
        
        # 阶段 1：生成预览
        for retry in range(max_preview_retries + 1):
            result["retries"] = retry
            
            # 生成预览
            preview = await self.generate_preview(
                project_id=project_id,
                chapter_number=chapter_number,
                outline=outline,
                blueprint_context=blueprint_context,
                emotion_context=emotion_context,
                memory_context=memory_context,
                style_hint=style_hint,
                user_id=user_id
            )
            
            if preview.get("status") != "success":
                continue
            
            result["preview"] = preview
            
            # 评估预览
            evaluation = await self.evaluate_preview(
                preview=preview,
                outline=outline,
                emotion_context=emotion_context,
                user_id=user_id
            )
            
            result["evaluation"] = evaluation
            
            # 检查是否通过
            if auto_approve or evaluation.get("approved", False):
                break
            
            # 如果有严重问题且还有重试机会，重新生成
            critical_issues = [
                issue for issue in evaluation.get("issues", [])
                if issue.get("severity") == "critical"
            ]
            
            if not critical_issues or retry >= max_preview_retries:
                break
            
            # 将修改建议加入风格提示
            suggestions = evaluation.get("revision_suggestions", [])
            if suggestions:
                style_hint = style_hint + "\n注意：" + "；".join(suggestions)
        
        # 阶段 3：扩写正文
        if result["preview"]:
            full_chapter = await self.expand_preview_to_full_chapter(
                preview=result["preview"],
                outline=outline,
                blueprint_context=blueprint_context,
                memory_context=memory_context,
                target_word_count=target_word_count,
                style_hint=style_hint,
                user_id=user_id
            )
            
            result["full_chapter"] = full_chapter
            result["status"] = "success" if full_chapter else "failed"
        else:
            result["status"] = "preview_failed"
        
        return result

    async def generate_multiple_previews(
        self,
        project_id: str,
        chapter_number: int,
        outline: Dict[str, Any],
        blueprint_context: str,
        emotion_context: str,
        memory_context: str,
        count: int = 3,
        user_id: int = 0
    ) -> List[Dict[str, Any]]:
        """
        生成多个不同风格的预览供选择
        
        Args:
            count: 生成预览的数量
        
        Returns:
            预览列表
        """
        style_hints = [
            "情绪更细腻，节奏更慢，多写内心戏和感官描写",
            "冲突更强，节奏更快，多写动作和对话",
            "悬念更重，多埋伏笔，结尾钩子更强",
            "幽默轻松，多写有趣的对话和互动",
            "紧张刺激，多写危机和转折",
        ]
        
        previews = []
        for i in range(min(count, len(style_hints))):
            preview = await self.generate_preview(
                project_id=project_id,
                chapter_number=chapter_number,
                outline=outline,
                blueprint_context=blueprint_context,
                emotion_context=emotion_context,
                memory_context=memory_context,
                style_hint=style_hints[i],
                user_id=user_id
            )
            
            if preview.get("status") == "success":
                preview["style_hint"] = style_hints[i]
                preview["index"] = i
                
                # 评估预览
                evaluation = await self.evaluate_preview(
                    preview=preview,
                    outline=outline,
                    emotion_context=emotion_context,
                    user_id=user_id
                )
                preview["evaluation"] = evaluation
                
                previews.append(preview)
        
        # 按评分排序
        previews.sort(
            key=lambda x: x.get("evaluation", {}).get("overall_score", 0),
            reverse=True
        )
        
        return previews
