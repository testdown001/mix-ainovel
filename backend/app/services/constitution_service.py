"""
小说宪法服务

提供小说宪法的 CRUD 操作和合规检查功能。
"""
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.constitution import NovelConstitution
from .llm_service import LLMService
from .prompt_service import PromptService


class ConstitutionCheckResult(BaseModel):
    """小说宪法合规检查结构化输出 schema（保留额外字段）。"""
    model_config = ConfigDict(extra="allow")
    overall_compliance: bool = True
    overall_score: int = 100
    violations: List[Any] = Field(default_factory=list)
    summary: str = ""


class ConstitutionService:
    """小说宪法服务"""

    def __init__(self, db: AsyncSession, llm_service: LLMService, prompt_service: PromptService):
        self.db = db
        self.llm_service = llm_service
        self.prompt_service = prompt_service

    async def get_constitution(self, project_id: str) -> Optional[NovelConstitution]:
        """获取项目的小说宪法"""
        result = await self.db.execute(
            select(NovelConstitution).where(NovelConstitution.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update_constitution(
        self, project_id: str, data: dict
    ) -> NovelConstitution:
        """创建或更新小说宪法"""
        constitution = await self.get_constitution(project_id)
        
        if constitution is None:
            constitution = NovelConstitution(project_id=project_id)
            self.db.add(constitution)
        
        # 更新字段
        for key, value in data.items():
            if hasattr(constitution, key):
                setattr(constitution, key, value)
        
        await self.db.commit()
        await self.db.refresh(constitution)
        return constitution

    async def check_compliance(
        self,
        project_id: str,
        chapter_number: int,
        chapter_title: str,
        chapter_content: str
    ) -> dict:
        """检查章节是否符合小说宪法"""
        constitution = await self.get_constitution(project_id)
        
        if constitution is None:
            return {
                "overall_compliance": True,
                "overall_score": 100,
                "violations": [],
                "summary": "未设置小说宪法，跳过合规检查"
            }
        
        # 获取检查提示词
        prompt_template = await self.prompt_service.get_prompt("constitution_check")
        if not prompt_template:
            return {
                "overall_compliance": True,
                "overall_score": 100,
                "violations": [],
                "summary": "未找到合规检查提示词"
            }
        
        # 构建提示词
        prompt = prompt_template.replace("{{constitution}}", constitution.to_prompt_context())
        prompt = prompt.replace("{{chapter_number}}", str(chapter_number))
        prompt = prompt.replace("{{chapter_title}}", chapter_title)
        prompt = prompt.replace("{{chapter_content}}", chapter_content)
        
        # 调用 LLM 进行检查
        # 结构化输出（schema 校验 + 失败回喂重问），替代脆弱的切大括号解析
        fallback = ConstitutionCheckResult(
            overall_compliance=True, overall_score=80,
            summary="合规检查完成，但结果解析失败",
        )
        try:
            model = await self.llm_service.generate_structured(
                prompt=prompt,
                schema=ConstitutionCheckResult,
                system_prompt=(
                    "你是一位严格的小说编辑，负责检查章节内容是否符合小说宪法。"
                    "请以 JSON 格式输出检查结果。"
                ),
                default=fallback,
            )
        except Exception:
            model = fallback
        return model.model_dump()

    def get_constitution_context(self, constitution: Optional[NovelConstitution]) -> str:
        """获取宪法上下文（用于注入到写作提示词）"""
        if constitution is None:
            return "（未设置小说宪法）"
        return constitution.to_prompt_context()
