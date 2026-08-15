# AIMETA P=全书导出|R=已完稿章TXT与DOCX组装_AI标识头|NR=不含发布|E=export_project|X=internal|A=导出|D=sqlalchemy,zip|S=db
"""作者自用全书导出。只收已完稿章（successful + selected_version），与公开分享白名单一致。"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from typing import List, Tuple
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.novel import Chapter, ChapterOutline, ChapterVersion, NovelProject

_COMPLETED = "successful"
_DISCLOSURE_AI = "本书含 AI 辅助创作内容。定稿权属于作者。导出仅供作者自用与平台投稿。"
_DISCLOSURE_HAND = "本书章节均为作者手写。"
_DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ExportChapter = Tuple[int, str, str, bool]  # number, title, content, ai_assisted


def _safe_stem(title: str) -> str:
    stem = "".join(ch for ch in (title or "novel") if ch not in '\\/:*?"<>|').strip() or "novel"
    return stem[:80]


async def collect_export_chapters(session: AsyncSession, project: NovelProject) -> List[ExportChapter]:
    """只收 status==successful 且 selected_version_id 已设的章。"""
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
                    Chapter.status == _COMPLETED,
                    Chapter.selected_version_id.is_not(None),
                )
                .order_by(Chapter.chapter_number.asc())
            )
        ).scalars().all()
    )
    out: List[ExportChapter] = []
    for chapter in chapters:
        version = await session.get(ChapterVersion, chapter.selected_version_id)
        if not version or not (version.content or "").strip():
            continue
        title = outlines.get(chapter.chapter_number) or f"第{chapter.chapter_number}章"
        out.append(
            (
                chapter.chapter_number,
                title,
                version.content.strip(),
                bool(getattr(version, "ai_assisted", False)),
            )
        )
    return out


def _disclosure(project: NovelProject, chapters: List[ExportChapter]) -> str:
    if getattr(project, "ai_assisted", False) or any(item[3] for item in chapters):
        return _DISCLOSURE_AI
    if chapters:
        return _DISCLOSURE_HAND
    return _DISCLOSURE_HAND


def assemble_txt(project: NovelProject, chapters: List[ExportChapter]) -> str:
    lines = [
        project.title or "未命名作品",
        f"导出时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        _disclosure(project, chapters),
        "",
    ]
    project_flag = bool(getattr(project, "ai_assisted", False))
    for number, title, content, version_flag in chapters:
        flag = "（含 AI 辅助）" if version_flag or project_flag else ""
        lines.append(f"第{number}章 {title}{flag}")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _w_p(text: str, *, bold: bool = False, size: int = 24) -> str:
    props = f'<w:sz w:val="{size}"/>'
    if bold:
        props += "<w:b/>"
    return (
        "<w:p><w:r><w:rPr>"
        f"{props}"
        f'</w:rPr><w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r></w:p>'
    )


def build_docx_bytes(project: NovelProject, chapters: List[ExportChapter]) -> bytes:
    """最小 OOXML：content types + rels + document.xml，不依赖 python-docx。"""
    body: List[str] = [
        _w_p(project.title or "未命名作品", bold=True, size=36),
        _w_p(_disclosure(project, chapters), size=20),
        _w_p(""),
    ]
    project_flag = bool(getattr(project, "ai_assisted", False))
    for number, title, content, version_flag in chapters:
        flag = "（含 AI 辅助）" if version_flag or project_flag else ""
        body.append(_w_p(f"第{number}章 {title}{flag}", bold=True, size=28))
        for para in content.splitlines() or [""]:
            body.append(_w_p(para) if para.strip() else _w_p(""))
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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
    return buf.getvalue()


async def export_project_text(session: AsyncSession, project: NovelProject) -> Tuple[str, str]:
    chapters = await collect_export_chapters(session, project)
    filename = f"{_safe_stem(project.title or 'novel')}.txt"
    return filename, assemble_txt(project, chapters)


async def export_project(
    session: AsyncSession, project: NovelProject, fmt: str
) -> Tuple[str, bytes, str]:
    chapters = await collect_export_chapters(session, project)
    stem = _safe_stem(project.title or "novel")
    if fmt == "docx":
        return f"{stem}.docx", build_docx_bytes(project, chapters), _DOCX_CT
    body = assemble_txt(project, chapters).encode("utf-8")
    return f"{stem}.txt", body, "text/plain; charset=utf-8"
