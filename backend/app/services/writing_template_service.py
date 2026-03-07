# AIMETA P=写作模板服务_模板CRUD|模板管理_应用生成|NR=|E=WritingTemplateService|X=internal|A=业务服务|D=sqlalchemy|S=db,net|RD=./README.ai
"""写作模板服务"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.writing_template import BUILTIN_TEMPLATES, WritingTemplate

logger = logging.getLogger(__name__)


class WritingTemplateService:
    """写作模板服务"""

    CATEGORIES = {
        "高潮": "⚔️",
        "情感": "💕",
        "心理": "💭",
        "悬疑": "🔮",
        "设定": "🌍",
        "人物": "👤",
        "过渡": "⏰",
        "节奏": "🎵"
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_templates(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[WritingTemplate]:
        """列出模板"""
        stmt = select(WritingTemplate).order_by(WritingTemplate.use_count.desc())

        if category:
            stmt = stmt.where(WritingTemplate.category == category)

        if search:
            stmt = stmt.where(
                WritingTemplate.name.ilike(f"%{search}%") |
                WritingTemplate.description.ilike(f"%{search}%")
            )

        result = await self.session.execute(stmt)
        templates = result.scalars().all()

        # 如果没有数据库模板，返回内置模板
        if not templates:
            return await self._get_builtin_templates(category)

        return list(templates)

    async def _get_builtin_templates(self, category: Optional[str] = None) -> List[Dict]:
        """获取内置模板"""
        templates = BUILTIN_TEMPLATES
        if category:
            templates = [t for t in templates if t["category"] == category]

        # 为内置模板添加必要字段
        for i, t in enumerate(templates):
            t["id"] = -1 - i  # 使用负数 ID 标识内置模板
            t["use_count"] = 0
            t["is_builtin"] = True

        return templates

    async def get_template(self, template_id: int) -> Optional[WritingTemplate]:
        """获取单个模板"""
        result = await self.session.execute(
            select(WritingTemplate).where(WritingTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def create_template(
        self,
        name: str,
        category: str,
        prompt_template: str,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        parameters: Optional[List[Dict]] = None
    ) -> WritingTemplate:
        """创建模板"""
        # 检查名称是否已存在
        existing = await self._check_name_exists(name)
        if existing:
            raise HTTPException(status_code=409, detail="模板名称已存在")

        template = WritingTemplate(
            name=name,
            category=category,
            description=description,
            icon=icon or self.CATEGORIES.get(category, "📝"),
            prompt_template=prompt_template,
            parameters=parameters or [],
            is_builtin=False
        )

        self.session.add(template)
        await self.session.commit()
        await self.session.refresh(template)

        logger.info(f"Created template: {name}")
        return template

    async def update_template(
        self,
        template_id: int,
        **kwargs
    ) -> WritingTemplate:
        """更新模板"""
        template = await self.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")

        if template.is_builtin:
            raise HTTPException(status_code=403, detail="内置模板不可修改")

        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)

        await self.session.commit()
        await self.session.refresh(template)

        logger.info(f"Updated template: {template_id}")
        return template

    async def delete_template(self, template_id: int) -> None:
        """删除模板"""
        template = await self.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")

        if template.is_builtin:
            raise HTTPException(status_code=403, detail="内置模板不可删除")

        await self.session.delete(template)
        await self.session.commit()

        logger.info(f"Deleted template: {template_id}")

    async def increment_use_count(self, template_id: int) -> None:
        """增加使用计数"""
        template = await self.get_template(template_id)
        if template:
            template.use_count += 1
            await self.session.commit()

    async def apply_template(
        self,
        template_id: int,
        params: Dict[str, Any]
    ) -> str:
        """应用模板，生成最终 prompt"""
        # 尝试从数据库获取
        template = await self.get_template(template_id)

        # 如果数据库没有，查找内置模板
        if not template:
            builtin = next((t for t in BUILTIN_TEMPLATES if t["name"] == str(template_id)), None)
            if builtin:
                prompt = builtin["prompt_template"]
            else:
                raise HTTPException(status_code=404, detail="模板不存在")
        else:
            prompt = template.prompt_template
            # 增加使用计数
            await self.increment_use_count(template_id)

        # 替换参数
        try:
            final_prompt = prompt.format(**params)
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"缺少必要参数: {e}")

        return final_prompt

    async def _check_name_exists(self, name: str) -> bool:
        """检查名称是否存在"""
        result = await self.session.execute(
            select(WritingTemplate).where(WritingTemplate.name == name)
        )
        return result.scalar_one_or_none() is not None

    async def init_builtin_templates(self) -> None:
        """初始化内置模板到数据库"""
        for template_data in BUILTIN_TEMPLATES:
            # 检查是否已存在
            existing = await self.session.execute(
                select(WritingTemplate).where(
                    WritingTemplate.name == template_data["name"],
                    WritingTemplate.is_builtin == True
                )
            )

            if not existing.scalar_one_or_none():
                template = WritingTemplate(
                    name=template_data["name"],
                    category=template_data["category"],
                    description=template_data.get("description"),
                    icon=template_data.get("icon", "📝"),
                    prompt_template=template_data["prompt_template"],
                    parameters=template_data.get("parameters", []),
                    is_builtin=True
                )
                self.session.add(template)

        await self.session.commit()
        logger.info("Initialized builtin templates")

    def get_categories(self) -> List[Dict[str, str]]:
        """获取所有分类"""
        return [
            {"id": cat, "name": cat, "icon": icon}
            for cat, icon in self.CATEGORIES.items()
        ]
