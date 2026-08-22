# AIMETA P=M3专业全书导出|R=结构化Markdown_TXT_DOCX内存组装|NR=不落盘_不含发布|E=export_project|X=internal|A=作者下载|D=sqlalchemy,zip|S=db|RD=./README.ai
"""作者自用的全书导出（M3）。

导出内容只在本次 HTTP 响应的内存中组装，不写入项目目录、数据库或对象存储；响应
结束后 Python 引用即释放。DOCX 为最小 OOXML 包，避免引入额外的运行时依赖。
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Tuple
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import Chapter, ChapterOutline, ChapterVersion, NovelProject, Volume

_DISCLOSURE_AI = "本书含 AI 辅助创作内容。定稿权属于作者。导出仅供作者自用与平台投稿。"
_DISCLOSURE_HAND = "本书章节均为作者手写。"
_DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MARKDOWN_CT = "text/markdown; charset=utf-8"
_TXT_CT = "text/plain; charset=utf-8"

ExportChapter = Tuple[int, str, str, bool]  # number, title, content, ai_assisted


@dataclass(frozen=True)
class ExportVolume:
    position: int
    name: str
    chapters: tuple[ExportChapter, ...]


def _safe_stem(title: str) -> str:
    stem = "".join(ch for ch in (title or "novel") if ch not in '\\/:*?\"<>|').strip() or "novel"
    return stem[:80]


def _display_volume_title(position: int, name: str) -> str:
    return f"第{position}卷 {name.strip() or '未命名分卷'}"


def _indented_paragraphs(content: str) -> Iterable[str]:
    """按原有空行分段，正文统一使用全角首行缩进。"""
    blocks = (content or "").strip().split("\n\n")
    for block in blocks:
        normalized = "\n".join(line.strip() for line in block.splitlines()).strip()
        if normalized:
            yield f"　　{normalized}"


async def collect_export_chapters(session: AsyncSession, project: NovelProject) -> List[ExportChapter]:
    """只收当前已确认正文；历史版本不会被重复导出。"""
    outlines = {
        row.chapter_number: row.title
        for row in (
            await session.execute(
                select(ChapterOutline).where(ChapterOutline.project_id == project.id)
            )
        ).scalars().all()
    }
    chapters: List[Chapter] = list(
        (
            await session.execute(
                select(Chapter)
                .where(
                    Chapter.project_id == project.id,
                    Chapter.selected_version_id.is_not(None),
                )
                .order_by(Chapter.sort_key.asc(), Chapter.chapter_number.asc())
            )
        ).scalars().all()
    )
    out: List[ExportChapter] = []
    for chapter in chapters:
        version = await session.get(ChapterVersion, chapter.selected_version_id)
        if not version or not (version.content or "").strip():
            continue
        title = outlines.get(chapter.chapter_number) or f"第{chapter.chapter_number}章"
        out.append((chapter.chapter_number, title, version.content.strip(), bool(version.ai_assisted)))
    return out


async def collect_export_volumes(
    session: AsyncSession,
    project: NovelProject,
    chapters: List[ExportChapter],
) -> list[ExportVolume]:
    """按 M1 分卷实体组织导出；无分卷时维持连续章节的简洁结构。"""
    volume_records = (
        await session.execute(
            select(Volume).where(Volume.project_id == project.id).order_by(Volume.position.asc())
        )
    ).scalars().all()
    if not volume_records:
        return []

    grouped: dict[int, list[ExportChapter]] = {volume.id: [] for volume in volume_records}
    ungrouped: list[ExportChapter] = []
    for chapter in chapters:
        number = chapter[0]
        volume = next(
            (item for item in volume_records if item.start_chapter <= number <= item.end_chapter),
            None,
        )
        if volume is None:
            ungrouped.append(chapter)
        else:
            grouped[volume.id].append(chapter)

    groups = [
        ExportVolume(volume.position, volume.name, tuple(grouped[volume.id]))
        for volume in volume_records
        if grouped[volume.id]
    ]
    if ungrouped:
        groups.append(ExportVolume(len(groups) + 1, "未归卷章节", tuple(ungrouped)))
    return groups


def _disclosure(project: NovelProject, chapters: List[ExportChapter]) -> str:
    if getattr(project, "ai_assisted", False) or any(item[3] for item in chapters):
        return _DISCLOSURE_AI
    return _DISCLOSURE_HAND


def _chapter_title(number: int, title: str, version_flag: bool, project_ai: bool) -> str:
    flag = "（含 AI 辅助）" if version_flag or project_ai else ""
    return f"第{number}章 {title}{flag}"


def _export_groups(
    chapters: List[ExportChapter], volumes: list[ExportVolume] | None
) -> list[tuple[int, str, list[ExportChapter]]]:
    if volumes:
        return [(group.position, group.name, list(group.chapters)) for group in volumes]
    return [(0, "", chapters)]


def assemble_txt(
    project: NovelProject,
    chapters: List[ExportChapter],
    volumes: list[ExportVolume] | None = None,
) -> str:
    lines = [
        project.title or "未命名作品",
        f"导出时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        _disclosure(project, chapters),
        "",
    ]
    project_ai = bool(getattr(project, "ai_assisted", False))
    for position, name, group_chapters in _export_groups(chapters, volumes):
        if position:
            lines.extend([_display_volume_title(position, name), "", "=" * 24, ""])
        for number, title, content, version_flag in group_chapters:
            lines.extend([_chapter_title(number, title, version_flag, project_ai), ""])
            lines.extend(_indented_paragraphs(content))
            lines.extend(["", "---", ""])
    return "\n".join(lines).strip() + "\n"


def assemble_markdown(
    project: NovelProject,
    chapters: List[ExportChapter],
    volumes: list[ExportVolume] | None = None,
) -> str:
    lines = [
        f"# {project.title or '未命名作品'}",
        "",
        f"> 导出时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> {_disclosure(project, chapters)}",
        "",
    ]
    project_ai = bool(getattr(project, "ai_assisted", False))
    for position, name, group_chapters in _export_groups(chapters, volumes):
        if position:
            lines.extend([f"## {_display_volume_title(position, name)}", ""])
        for number, title, content, version_flag in group_chapters:
            lines.extend([f"### {_chapter_title(number, title, version_flag, project_ai)}", ""])
            lines.extend(_indented_paragraphs(content))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def _w_p(text: str, *, bold: bool = False, size: int = 24, indent: bool = False) -> str:
    props = f'<w:sz w:val="{size}"/>'
    if bold:
        props += "<w:b/>"
    paragraph_props = '<w:pPr><w:ind w:firstLine="420"/></w:pPr>' if indent and text else ""
    return (
        f"<w:p>{paragraph_props}<w:r><w:rPr>{props}</w:rPr>"
        f'<w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r></w:p>'
    )


def build_docx_bytes(
    project: NovelProject,
    chapters: List[ExportChapter],
    volumes: list[ExportVolume] | None = None,
) -> bytes:
    """按书名 / 卷 / 章 / 正文的层级组装 DOCX，数据仅存在当前内存缓冲。"""
    body: List[str] = [
        _w_p(project.title or "未命名作品", bold=True, size=36),
        _w_p(_disclosure(project, chapters), size=20),
        _w_p(""),
    ]
    project_ai = bool(getattr(project, "ai_assisted", False))
    for position, name, group_chapters in _export_groups(chapters, volumes):
        if position:
            body.extend([_w_p(_display_volume_title(position, name), bold=True, size=32), _w_p("")])
        for number, title, content, version_flag in group_chapters:
            body.append(_w_p(_chapter_title(number, title, version_flag, project_ai), bold=True, size=28))
            for paragraph in _indented_paragraphs(content):
                body.append(_w_p(paragraph, indent=True))
            body.append(_w_p(""))

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(body)}<w:sectPr/></w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
    return buffer.getvalue()


async def export_project_text(session: AsyncSession, project: NovelProject) -> Tuple[str, str]:
    chapters = await collect_export_chapters(session, project)
    volumes = await collect_export_volumes(session, project, chapters)
    filename = f"{_safe_stem(project.title or 'novel')}.txt"
    return filename, assemble_txt(project, chapters, volumes)


async def export_project(
    session: AsyncSession, project: NovelProject, fmt: str
) -> Tuple[str, bytes, str]:
    chapters = await collect_export_chapters(session, project)
    volumes = await collect_export_volumes(session, project, chapters)
    stem = _safe_stem(project.title or "novel")
    if fmt == "docx":
        return f"{stem}.docx", build_docx_bytes(project, chapters, volumes), _DOCX_CT
    if fmt == "markdown":
        return f"{stem}.md", assemble_markdown(project, chapters, volumes).encode("utf-8"), _MARKDOWN_CT
    return f"{stem}.txt", assemble_txt(project, chapters, volumes).encode("utf-8"), _TXT_CT
