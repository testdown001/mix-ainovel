# AIMETA P=章节扩写服务_字数不足自动扩写|R=字数检测_扩写生成|NR=不含生成逻辑|E=EnrichmentService|X=internal|A=扩写_字数控制|D=llm_service|S=none|RD=./README.ai
"""
章节扩写服务 (EnrichmentService)

融合自 AI_NovelGenerator 的 enrich_chapter_text 设计，提供：
1. 字数检测：检查是否低于目标字数的70%
2. 智能扩写：加戏不加线（补足动作过程、对话阻力与因果步骤，不推进主线）
3. 质量控制：确保扩写后的内容与原文风格一致

这对起点风格的网文很实用，可以稳定保持每章2k~4k字。
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..utils.json_utils import is_probable_chapter_plain_text, sanitize_chapter_plain_text
from .llm_service import LLMService

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """扩写结果"""
    original_word_count: int
    enriched_word_count: int
    enriched_content: str
    enrichment_ratio: float  # 扩写比例
    enrichment_type: str  # detail/dialogue/sequel


# ==================== 提示词模板 ====================

ENRICH_CHAPTER_PROMPT = """\
以下章节文本较短，请在保持剧情连贯的前提下进行扩写，使其更充实。

## 原始内容：
{chapter_text}

## 目标字数：{target_word_count}字（当前约{current_word_count}字）

## 扩写原则（重要！）：
1. **加戏不加线**：只扩写细节，不推进主线剧情
2. **扩写优先级**（从上到下）：
   - 补全被跳过的动作过程、操作步骤、空间关系与即时结果
   - 增加会改变对话走向的追问、回避、误解或实际阻力
   - 把抽象说明改成可验证的物件、数字、痕迹或角色选择
   - 只在读者无法理解动作时补一个必要感官细节
3. **禁止内容**：
   - 不要引入新的剧情转折
   - 不要添加新的重要角色
   - 不要改变已有的人物关系
   - 不要提前揭示任何伏笔
   - 不为凑字数增加天气、光影、气味、温度或无作用的微表情
   - 不给已有句子叠加形容词、副词、排比或比喻
   - 不扩写最后两段；除非原文结尾是不完整句，否则原样保留章尾

## 扩写技巧：
- 在对话之间补会影响回答的具体动作、证据或选择，不要每句都加表情
- 在场景转换时用时间、位置或任务变化交代衔接，不写环境散文
- 在紧张时刻补清动作先后、障碍和代价，不堆身体反应
- 在情感高潮后用人物下一步选择呈现余波，不补抒情总结
- 句式长短结合：动作冲突段用更短句提速，心理/环境段可用较长句展开

## 风格要求：
- 保持原文的叙事视角
- 严格限定在当前 POV 可感知、可回忆或有证据可推断的信息内，不确认其他角色内心与幕后事实
- 保持原文的语言风格
- 保持原文的节奏感
- 不要机械平均段落长度，字数服务剧情，不要生硬凑字
- 优先精确名词和动词；一个句子只留一个主要意象，一个自然段原则上不超过一次比喻
- 简单情绪允许直陈，同一情绪节拍最多一个身体反应

请返回扩写后的完整章节内容，不要解释修改内容。
"""

ENRICH_DIALOGUE_PROMPT = """\
请扩写以下对话场景，补足会改变回应的阻力与潜台词：

## 原始对话：
{dialogue_text}

## 人物信息：
{character_info}

## 扩写要求：
1. 只补当前 POV 的必要判断，其他人的想法只能通过台词和可观察行为推断
2. 每2-4句对话最多设置一个动作锚点，不要逐句添加微表情和肢体语言
3. 增加对话的言外之意和潜台词
4. 保持对话的原有含义不变
5. 不增加比喻、环境抒情或身体反应套装

请返回扩写后的对话内容。
"""

ENRICH_SCENE_PROMPT = """\
请扩写以下场景描写，补足人物行动所需的空间与物理信息：

## 原始场景：
{scene_text}

## 场景信息：
- 地点：{location}
- 时间：{time}
- 氛围：{atmosphere}

## 扩写要求：
1. 只增加会影响移动、判断、冲突或操作结果的物件与空间细节
2. 感官只选当前动作真正需要的一种，不做视觉/听觉/触觉清单式补齐
3. 优先精确名词和动词，不给原句叠加形容词、副词和比喻
4. 环境只承担阻力或信息，不替人物暗示情绪，不做象征
5. 严格保持当前 POV，不写角色无法感知的画面或他人内心

请返回扩写后的场景描写。
"""


class EnrichmentService:
    """
    章节扩写服务
    
    负责检测字数不足并进行智能扩写。
    """
    
    def __init__(
        self,
        db: Session,
        llm_service: LLMService
    ):
        self.db = db
        self.llm_service = llm_service
    
    async def check_and_enrich(
        self,
        chapter_text: str,
        target_word_count: int,
        user_id: int,
        threshold: float = 0.8
    ) -> Optional[EnrichmentResult]:
        """
        检查字数并在需要时进行扩写
        
        Args:
            chapter_text: 章节内容
            target_word_count: 目标字数
            user_id: 用户ID
            threshold: 触发扩写的阈值（默认70%）
            
        Returns:
            如果进行了扩写返回EnrichmentResult，否则返回None
        """
        current_count = self._count_words(chapter_text)
        
        # 检查是否需要扩写
        if current_count >= target_word_count * threshold:
            logger.info(f"字数充足 ({current_count}/{target_word_count})，无需扩写")
            return None
        
        logger.info(f"字数不足 ({current_count}/{target_word_count})，开始扩写")
        
        # 执行扩写
        enriched = await self._enrich_chapter(
            chapter_text=chapter_text,
            target_word_count=target_word_count,
            current_word_count=current_count,
            user_id=user_id
        )
        
        if not enriched:
            return None
        
        enriched_count = self._count_words(enriched)
        
        return EnrichmentResult(
            original_word_count=current_count,
            enriched_word_count=enriched_count,
            enriched_content=enriched,
            enrichment_ratio=enriched_count / current_count if current_count > 0 else 1.0,
            enrichment_type="detail"
        )
    
    async def enrich_to_target(
        self,
        chapter_text: str,
        target_word_count: int,
        user_id: int,
        max_iterations: int = 3
    ) -> str:
        """
        迭代扩写直到达到目标字数
        
        Args:
            chapter_text: 章节内容
            target_word_count: 目标字数
            user_id: 用户ID
            max_iterations: 最大迭代次数
            
        Returns:
            扩写后的内容
        """
        current_text = chapter_text
        
        for i in range(max_iterations):
            current_count = self._count_words(current_text)
            
            if current_count >= target_word_count * 0.9:  # 达到90%即可
                break
            
            logger.info(f"扩写迭代 {i+1}: {current_count}/{target_word_count}")
            
            result = await self.check_and_enrich(
                chapter_text=current_text,
                target_word_count=target_word_count,
                user_id=user_id,
                threshold=0.9  # 使用更高的阈值进行迭代
            )
            
            if result:
                current_text = result.enriched_content
            else:
                break
        
        return current_text
    
    async def enrich_dialogue(
        self,
        dialogue_text: str,
        character_info: str,
        user_id: int
    ) -> Optional[str]:
        """
        扩写对话场景
        
        专门针对对话进行扩写，增加潜台词和内心活动。
        """
        prompt = ENRICH_DIALOGUE_PROMPT.format(
            dialogue_text=dialogue_text,
            character_info=character_info
        )
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                user_id=user_id,
                max_tokens=4000,
                temperature=0.6
            )
            return response.strip() if response else None
        except Exception as e:
            logger.error(f"对话扩写失败: {e}")
            return None
    
    async def enrich_scene(
        self,
        scene_text: str,
        location: str,
        time: str,
        atmosphere: str,
        user_id: int
    ) -> Optional[str]:
        """
        扩写场景描写
        
        专门针对场景补足会影响行动的空间、物件与物理信息。
        """
        prompt = ENRICH_SCENE_PROMPT.format(
            scene_text=scene_text,
            location=location,
            time=time,
            atmosphere=atmosphere
        )
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                user_id=user_id,
                max_tokens=3000,
                temperature=0.6
            )
            return response.strip() if response else None
        except Exception as e:
            logger.error(f"场景扩写失败: {e}")
            return None
    
    async def _enrich_chapter(
        self,
        chapter_text: str,
        target_word_count: int,
        current_word_count: int,
        user_id: int,
        max_word_count: int = 0,
    ) -> Optional[str]:
        """执行章节扩写"""
        prompt = ENRICH_CHAPTER_PROMPT.format(
            chapter_text=chapter_text,
            target_word_count=target_word_count,
            current_word_count=current_word_count
        )

        # 动态计算 max_tokens：优先使用 max_word_count 限制，否则使用默认值 8000
        _enrich_max_tokens = int(max_word_count * 1.5) if max_word_count else 8000

        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                user_id=user_id,
                max_tokens=_enrich_max_tokens,
                temperature=0.6,
                timeout=180.0,
                fail_on_truncation=True,
            )
            if not response or not response.strip():
                return None
            enriched = sanitize_chapter_plain_text(response.strip())
            if not enriched or not is_probable_chapter_plain_text(enriched):
                logger.warning("扩写结果不是有效章节正文，放弃应用")
                return None
            if len(enriched) < len(chapter_text) * 0.5:
                logger.warning("扩写后字数过少 (原%d, 现%d)，放弃应用", len(chapter_text), len(enriched))
                return None
            return enriched
        except Exception as e:
            logger.error(f"章节扩写失败: {e}")
            return None
    
    def _count_words(self, text: str) -> int:
        """计算中文字数"""
        import re
        # 移除空白字符
        text = re.sub(r'\s+', '', text)
        # 计算字符数（中文一个字符算一个字）
        return len(text)
    
    def get_enrichment_suggestions(
        self,
        chapter_text: str,
        target_word_count: int
    ) -> Dict[str, Any]:
        """
        获取扩写建议
        
        分析章节内容，给出具体的扩写建议。
        """
        current_count = self._count_words(chapter_text)
        needed = target_word_count - current_count
        
        suggestions = {
            "current_word_count": current_count,
            "target_word_count": target_word_count,
            "needed": max(0, needed),
            "ratio": current_count / target_word_count if target_word_count > 0 else 1.0,
            "recommendations": []
        }
        
        if needed <= 0:
            suggestions["status"] = "sufficient"
            return suggestions
        
        suggestions["status"] = "needs_enrichment"
        
        # 分析内容，给出建议
        if "说" in chapter_text or "道" in chapter_text or '"' in chapter_text:
            suggestions["recommendations"].append({
                "type": "dialogue",
                "description": "检测到对话场景，建议增加人物内心活动和潜台词",
                "estimated_words": min(needed // 2, 500)
            })
        
        # 检测场景描写
        scene_keywords = ["走进", "来到", "站在", "坐在", "看着"]
        if any(kw in chapter_text for kw in scene_keywords):
            suggestions["recommendations"].append({
                "type": "scene",
                "description": "检测到场景转换，建议增加环境细节描写",
                "estimated_words": min(needed // 3, 300)
            })
        
        # 检测动作场景
        action_keywords = ["打", "踢", "跑", "跳", "攻击", "防御"]
        if any(kw in chapter_text for kw in action_keywords):
            suggestions["recommendations"].append({
                "type": "action",
                "description": "检测到动作场景，建议增加动作细节和感官描写",
                "estimated_words": min(needed // 3, 400)
            })
        
        # 通用建议
        suggestions["recommendations"].append({
            "type": "general",
            "description": "建议在情节转折处增加人物的情绪反应和思考",
            "estimated_words": min(needed // 4, 300)
        })
        
        return suggestions
