import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to sys.path so we can import from app
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.novel import Chapter, ChapterOutline, BlueprintCharacter

from app.core.config import settings
from app.services.chapter_ingest_service import ChapterIngestionService
from app.services.memory_layer_service import MemoryLayerService
from app.services.llm_service import LLMService
from app.services.vector_store_service import VectorStoreService
from app.services.prompt_service import PromptService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_sync():
    logger.info("开始同步已有章节到 Qdrant (RAG) 和 Mem0...")
    
    uri = settings.sqlalchemy_database_uri.replace("mysql+asyncmy", "mysql+aiomysql")
    script_engine = create_async_engine(uri, echo=False)
    
    AsyncSessionLocal = async_sessionmaker(bind=script_engine, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        llm_service = LLMService(session)
        vector_store = VectorStoreService()
        
        # Ensuring collection schemas exist
        await vector_store.ensure_schema()
        
        ingest_service = ChapterIngestionService(
            llm_service=llm_service,
            vector_store=vector_store,
        )
        
        prompt_service = PromptService(session)
        memory_service = MemoryLayerService(
            db=session,
            llm_service=llm_service,
            prompt_service=prompt_service
        )
        # Get all chapters that have text versions
        stmt = (
            select(Chapter, ChapterOutline)
            .join(
                ChapterOutline, 
                (Chapter.project_id == ChapterOutline.project_id) & (Chapter.chapter_number == ChapterOutline.chapter_number)
            )
            .options(
                selectinload(Chapter.selected_version),
                selectinload(Chapter.versions)
            )
            .order_by(Chapter.project_id, Chapter.chapter_number)
        )
        result = await session.execute(stmt)
        chapter_records = result.all()
        
        logger.info(f"找到 {len(chapter_records)} 个章节，准备进行检查和抽取...")
        
        for chapter, outline in chapter_records:
            logger.info(f"正在处理项目: {chapter.project_id}, 章节: 第{chapter.chapter_number}章")
            
            content = ""
            if chapter.selected_version:
                content = chapter.selected_version.content
            elif chapter.versions:
                content = chapter.versions[-1].content
                
            if not content or not content.strip():
                logger.warning(f"第 {chapter.chapter_number} 章没有正文内容，跳过。")
                continue

            # 1. 写入 Qdrant 块 (提供普通 RAG 用途)
            logger.info(f"-> 切分并写入片段 (Qdrant chunks)...")
            await ingest_service.ingest_chapter(
                project_id=chapter.project_id,
                chapter_number=chapter.chapter_number,
                title=outline.title or f"第{chapter.chapter_number}章",
                content=content,
                summary=outline.summary,
                user_id=1,
            )
            
            # 2. 写入 Mem0 记忆层 (供长期逻辑记忆使用)
            logger.info(f"-> 抽取核心事件库 (Mem0)...")
            try:
                # Get characters participating in this project
                stmt_chars = select(BlueprintCharacter.name).where(BlueprintCharacter.project_id == chapter.project_id)
                chars_result = await session.execute(stmt_chars)
                character_names = chars_result.scalars().all()
                
                await memory_service.update_memory_after_chapter(
                    project_id=chapter.project_id,
                    chapter_number=chapter.chapter_number,
                    chapter_content=content,
                    character_names=list(character_names),
                    user_id=1
                )
            except Exception as e:
                logger.error(f"提取 Mem0 记忆失败 (第 {chapter.chapter_number} 章): {e}")
                
    logger.info("全部同步完成！")
    await script_engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_sync())
