# AIMETA P=写作模板服务_模板CRUD|模板管理_应用生成|NR=|E=WritingTemplateService|X=internal|A=业务服务|D=sqlalchemy|S=db,net|RD=./README.ai
"""写作模板服务"""
from __future__ import annotations

import json
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

    @staticmethod
    def _choose_option_fallback(parameter: Dict[str, Any]) -> Any:
        options = parameter.get("options") or []
        default = parameter.get("default")
        if not options:
            return default
        if default in options:
            return default
        if default is not None:
            try:
                default_num = float(default)
                numeric_options = []
                for option in options:
                    try:
                        numeric_options.append((abs(float(option) - default_num), option))
                    except (TypeError, ValueError):
                        numeric_options = []
                        break
                if numeric_options:
                    numeric_options.sort(key=lambda item: item[0])
                    return numeric_options[0][1]
            except (TypeError, ValueError):
                pass
        return options[0]

    @classmethod
    def _infer_fallback_value(
        cls,
        parameter: Dict[str, Any],
        *,
        chapter_number: int,
        chapter_title: str,
        chapter_summary: str,
        character_names: List[str],
    ) -> Any:
        parameter_type = str(parameter.get("type") or "text")
        fallback_option = cls._choose_option_fallback(parameter)
        if parameter_type == "select":
            return fallback_option

        descriptor = " ".join(
            str(part or "")
            for part in (
                parameter.get("name"),
                parameter.get("label"),
                parameter.get("description"),
            )
        ).lower()

        if parameter_type == "number":
            if "chapter" in descriptor or "章节" in descriptor:
                return max(1, chapter_number - 1)
            default = parameter.get("default")
            try:
                return int(default)
            except (TypeError, ValueError):
                return 1

        if any(token in descriptor for token in ("antagonist", "对手", "反派", "被动方", "character_b")):
            if len(character_names) >= 2:
                return character_names[1]
            if character_names:
                return character_names[0]
            return "对手"

        if any(token in descriptor for token in ("protagonist", "主角", "主动方", "character_a", "character", "角色")):
            if character_names:
                return character_names[0]
            return "主角"

        if any(token in descriptor for token in ("location", "地点", "场景")):
            return chapter_title

        if any(
            token in descriptor
            for token in (
                "background",
                "背景",
                "current_plot",
                "当前情节",
                "trigger_event",
                "触发事件",
                "event",
                "事件",
                "twist_content",
                "转折内容",
                "foreshadowing_content",
                "伏笔内容",
                "reveal",
                "揭示",
                "summary",
                "摘要",
            )
        ):
            return chapter_summary

        if any(token in descriptor for token in ("word_count", "字数")) and fallback_option is not None:
            return fallback_option

        if parameter_type == "textarea":
            return chapter_summary
        if parameter.get("default") not in (None, ""):
            return parameter.get("default")
        return chapter_title

    @classmethod
    def _build_fallback_params(
        cls,
        parameters: List[Dict[str, Any]],
        *,
        chapter_number: int,
        chapter_title: str,
        chapter_summary: str,
        character_names: List[str],
    ) -> Dict[str, Any]:
        return {
            parameter["name"]: cls._infer_fallback_value(
                parameter,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_summary=chapter_summary,
                character_names=character_names,
            )
            for parameter in parameters
            if parameter.get("name")
        }

    @classmethod
    def _normalize_param_values(
        cls,
        parameters: List[Dict[str, Any]],
        values: Dict[str, Any],
        *,
        fallback_values: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for parameter in parameters:
            name = parameter.get("name")
            if not name:
                continue
            value = values.get(name, fallback_values.get(name))
            parameter_type = str(parameter.get("type") or "text")
            options = parameter.get("options") or []

            if options and value not in options:
                value = cls._choose_option_fallback(parameter)

            if value in (None, ""):
                value = fallback_values.get(name)

            if parameter_type == "number":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    fallback_number = fallback_values.get(name, 1)
                    try:
                        value = int(fallback_number)
                    except (TypeError, ValueError):
                        value = 1

            normalized[name] = value
        return normalized

    async def infer_params(
        self,
        template_id: int,
        project_id: str,
        chapter_number: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """使用 LLM 根据章节上下文推演模板参数值。"""
        from ..models.novel import BlueprintCharacter, ChapterOutline
        from ..services.llm_service import LLMService
        from ..services.prompt_service import PromptService

        # 1. 获取模板参数定义
        template = await self.get_template(template_id)
        if template:
            parameters = template.parameters or []
            template_name = template.name
        else:
            # 内置模板 id 为负数
            builtin_list = await self._get_builtin_templates()
            builtin = next((t for t in builtin_list if t.get("id") == template_id), None)
            if not builtin:
                raise HTTPException(status_code=404, detail="模板不存在")
            parameters = builtin.get("parameters", [])
            template_name = builtin["name"]

        if not parameters:
            return {}

        # 2. 获取章节大纲
        result = await self.session.execute(
            select(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
        )
        outline = result.scalar_one_or_none()
        chapter_title = outline.title if outline else f"第{chapter_number}章"
        chapter_summary = (outline.summary if outline and outline.summary else "暂无摘要")

        # 3. 获取项目角色
        result = await self.session.execute(
            select(BlueprintCharacter).where(
                BlueprintCharacter.project_id == project_id
            ).order_by(BlueprintCharacter.position)
        )
        characters = result.scalars().all()
        characters_text = "\n".join(
            f"- {c.name}（{c.identity or '未知身份'}）"
            for c in characters
        ) or "暂无角色信息"
        character_names = [c.name for c in characters if getattr(c, "name", None)]
        fallback_params = self._build_fallback_params(
            parameters,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            character_names=character_names,
        )

        # 4. 构建参数描述
        param_desc = []
        for p in parameters:
            desc: Dict[str, Any] = {"name": p["name"], "label": p["label"], "type": p["type"]}
            if p.get("description"):
                desc["description"] = p["description"]
            if p.get("options"):
                desc["options"] = p["options"]
            param_desc.append(desc)
        parameters_json = json.dumps(param_desc, ensure_ascii=False, indent=2)

        # 5. 渲染 prompt 并调用 LLM
        prompt_service = PromptService(self.session)
        system_prompt = await prompt_service.get_prompt("template_param_infer")
        if not system_prompt:
            logger.warning(
                "模板参数推演缺少提示词，使用回退值: template=%s project=%s chapter=%s",
                template_name,
                project_id,
                chapter_number,
            )
            return fallback_params

        rendered = PromptService.render_prompt(
            system_prompt,
            chapter_title=chapter_title,
            chapter_summary=chapter_summary,
            characters_text=characters_text,
            template_name=template_name,
            parameters_json=parameters_json,
        )

        llm_service = LLMService(self.session)
        try:
            raw = await llm_service.generate(
                prompt="请根据上述信息推演模板参数值，输出 JSON。",
                system_prompt=rendered,
                temperature=0.3,
                response_format="json_object",
                user_id=user_id,
            )
            inferred = json.loads(raw)
            if not isinstance(inferred, dict):
                raise ValueError("LLM 返回的参数推演结果不是对象")
        except HTTPException as exc:
            logger.warning(
                "模板参数推演降级为回退值: template=%s project=%s chapter=%s status=%s detail=%s",
                template_name,
                project_id,
                chapter_number,
                exc.status_code,
                exc.detail,
            )
            return fallback_params
        except Exception as exc:
            logger.warning(
                "模板参数推演解析失败，使用回退值: template=%s project=%s chapter=%s error=%s",
                template_name,
                project_id,
                chapter_number,
                exc,
            )
            return fallback_params

        return self._normalize_param_values(
            parameters,
            inferred,
            fallback_values=fallback_params,
        )
