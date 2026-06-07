# AIMETA P=质量审核服务_章节质量审核|R=章节质量审核|NR=调用LLM审核章节质量并保存结果|GatekeeperReviewService|X=internal|A=Service|D=business|S=async,llm|RD=./README.ai
"""章节质量审核服务"""
import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter_review import ChapterReview
from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelProject
from app.services.llm_service import LLMService
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class GatekeeperReviewService:
    """章节质量审核服务"""

    REVIEW_THRESHOLDS = {
        "overall_score": 70,         # 综合评分 >= 70
        "min_dimension_score": 50,  # 单项最低 >= 50
        "max_high_issues": 2,       # 严重问题 <= 2
    }

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)

    async def review_chapter(
        self,
        chapter_version: ChapterVersion,
        project: NovelProject,
        outline: Optional[ChapterOutline] = None,
    ) -> ChapterReview:
        """执行章节审核"""

        logger.info(f"开始审核章节: project={project.id}, chapter={chapter_version.chapter_id}")

        # 构建审核上下文
        context = await self._build_review_context(
            chapter_version, project, outline
        )

        # 调用审核 prompt
        review_result = await self._call_review_llm(context)

        # 解析结果
        review = self._parse_review_result(review_result, chapter_version, project.id)

        # 保存审核记录
        await self._save_review(review)

        logger.info(
            f"审核完成: project={project.id}, approved={review.approved}, score={review.overall_score}"
        )

        return review

    async def _build_review_context(
        self,
        chapter_version: ChapterVersion,
        project: NovelProject,
        outline: Optional[ChapterOutline],
    ) -> Dict[str, Any]:
        """构建审核上下文"""

        # 获取章节信息
        chapter = chapter_version.chapter
        if not chapter:
            from sqlalchemy import select
            stmt = select(Chapter).where(Chapter.id == chapter_version.chapter_id)
            result = await self.session.execute(stmt)
            chapter = result.scalar_one_or_none()

        # 构建上下文
        context = {
            "project_id": project.id,
            "project_title": project.title,
            "chapter_number": chapter.chapter_number if chapter else "未知",
            "chapter_title": chapter.title if chapter else "未知",
            "chapter_content": chapter_version.content[:15000],  # 限制内容长度
            "outline": "",
            "world_settings": "",
            "previous_chapter_summary": "",
        }

        # 添加大纲信息
        if outline:
            context["outline"] = f"章节大纲：{outline.content}"

        # 获取世界观设定
        try:
            from app.services.novel_service import NovelService
            novel_service = NovelService(self.session)
            blueprint = await novel_service.get_or_create_blueprint(project.id)
            if blueprint and blueprint.world_settings:
                context["world_settings"] = blueprint.world_settings[:2000]
        except Exception as e:
            logger.warning(f"获取世界观设定失败: {e}")

        # 获取前几章摘要
        try:
            from app.services.chapter_context_service import ChapterContextService
            ctx_service = ChapterContextService(self.session)
            prev_context = await ctx_service.get_context_window(
                project.id,
                chapter.chapter_number - 1 if chapter else 1,
                window=2,
            )
            if prev_context:
                context["previous_chapter_summary"] = prev_context[:2000]
        except Exception as e:
            logger.warning(f"获取前文摘要失败: {e}")

        return context

    async def _call_review_llm(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """调用 LLM 进行审核"""

        # 尝试获取审核 prompt
        prompt = await self.prompt_service.get_prompt("gatekeeper_review")

        if prompt:
            prompt_text = prompt.format(**context)
        else:
            # 使用默认审核 prompt
            prompt_text = self._get_default_prompt(context)

        logger.debug(f"审核 prompt 长度: {len(prompt_text)}")

        response = await self.llm_service.generate(
            prompt=prompt_text,
            temperature=0.3,
            max_tokens=4000,
        )

        return self._parse_llm_response(response)

    def _get_default_prompt(self, context: Dict[str, Any]) -> str:
        """获取默认审核 prompt"""
        return f"""## 角色
你是章节质量审核智能体，负责审核章节质量。你必须严格把关，不合格的内容必须封驳。

## 小说信息
- 小说标题：{context['project_title']}
- 章节号：{context['chapter_number']}
- 章节标题：{context['chapter_title']}

## 章节大纲
{context['outline']}

## 前文摘要
{context['previous_chapter_summary']}

## 世界观设定
{context['world_settings']}

## 待审核章节内容
{context['chapter_content']}

## 审核标准

### 1. 剧情一致性 (consistency)
- 与小说大纲是否冲突
- 与前文情节是否衔接
- 世界观设定是否一致

### 2. 角色立体度 (character_depth)
- 角色行为是否有合理动机
- 角色性格是否前后一致
- 角色是否有成长/变化

### 3. 节奏张力 (pacing)
- 章节是否有明确的节拍
- 是否有高潮/转折点
- 节奏是否拖沓

### 4. 伏笔呼应 (foreshadowing)
- 是否呼应了之前埋下的伏笔
- 是否有新伏笔埋下
- 伏笔是否生硬

### 5. 文笔质量 (prose_quality)
- 是否有精彩句子/段落
- 描写是否生动
- 对话是否贴合角色

### 6. 情绪曲线 (emotion_curve)
- 情绪是否有起伏
- 是否能让读者共情
- 情绪是否突兀

## 输出格式
请返回 JSON：
```json
{{
  "approved": true/false,
  "overall_score": 85,
  "scores": {{
    "consistency": 85,
    "character_depth": 70,
    "pacing": 90,
    "foreshadowing": 60,
    "prose_quality": 75,
    "emotion_curve": 80
  }},
  "issues": [
    {{
      "type": "foreshadowing",
      "severity": "high",
      "description": "...",
      "suggestion": "..."
    }}
  ],
  "review_comment": "总体评价...",
  "rewrite_required": true/false
}}
```"""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""

        # 尝试提取 JSON
        try:
            # 查找 JSON 块
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.warning(f"解析审核结果失败: {response[:200]}")

        # 返回默认结果
        return {
            "approved": False,
            "overall_score": 0,
            "scores": {},
            "issues": [{"type": "parse_error", "severity": "high", "description": "无法解析审核结果", "suggestion": "请重试"}],
            "review_comment": "审核服务异常",
            "rewrite_required": True,
        }

    def _parse_review_result(
        self,
        review_result: Dict[str, Any],
        chapter_version: ChapterVersion,
        project_id: str,
    ) -> ChapterReview:
        """解析审核结果"""

        # 根据阈值判定是否通过
        approved = review_result.get("approved", False)
        overall_score = review_result.get("overall_score", 0)
        scores = review_result.get("scores", {})
        issues = review_result.get("issues", [])

        # 应用阈值判定
        if overall_score >= self.REVIEW_THRESHOLDS["overall_score"]:
            # 检查单项最低分
            min_score = min(scores.values()) if scores else 0
            if min_score < self.REVIEW_THRESHOLDS["min_dimension_score"]:
                approved = False

            # 检查严重问题数
            high_issues = [i for i in issues if i.get("severity") == "high"]
            if len(high_issues) > self.REVIEW_THRESHOLDS["max_high_issues"]:
                approved = False

        # 检查 rewrite_required
        rewrite_required = review_result.get("rewrite_required", not approved)

        chapter = chapter_version.chapter
        chapter_number = chapter.chapter_number if chapter else 0

        review = ChapterReview(
            project_id=project_id,
            chapter_number=chapter_number,
            approved=approved,
            overall_score=overall_score,
            scores=scores,
            issues=issues,
            review_comment=review_result.get("review_comment", ""),
            rewrite_required=rewrite_required,
            chapter_version_id=chapter_version.id,
        )

        return review

    async def _save_review(self, review: ChapterReview) -> None:
        """保存审核记录"""
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)

    async def get_review_by_chapter(
        self, project_id: str, chapter_number: int
    ) -> Optional[ChapterReview]:
        """获取章节审核结果"""
        from sqlalchemy import select

        stmt = (
            select(ChapterReview)
            .where(ChapterReview.project_id == project_id)
            .where(ChapterReview.chapter_number == chapter_number)
            .order_by(ChapterReview.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_reviews_by_project(
        self, project_id: str
    ) -> list[ChapterReview]:
        """获取项目所有章节的最新审核结果（每章取最新一条）"""
        from sqlalchemy import select, func

        latest_ids_subq = (
            select(func.max(ChapterReview.id).label("max_id"))
            .where(ChapterReview.project_id == project_id)
            .group_by(ChapterReview.chapter_number)
            .subquery()
        )
        stmt = (
            select(ChapterReview)
            .where(ChapterReview.id == latest_ids_subq.c.max_id)
            .order_by(ChapterReview.chapter_number)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
