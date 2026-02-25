import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Assume standard local testing setup for arboris-novel
from app.core.config import settings
from app.services.power_system_service import PowerSystemService
from app.schemas.power_system import PowerSystemCreate, PowerLevelCreate
from app.models.novel import NovelProject
from sqlalchemy import select

async def main():
    # Database connection setup
    engine = create_async_engine(settings.sqlalchemy_database_uri, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Get any existing project
        result = await session.execute(select(NovelProject).limit(1))
        project = result.scalar_one_or_none()
        
        if not project:
            print("No projects found in the database. Please create a novel project first in the UI.")
            return

        print(f"Adding test power system to project: {project.title} (ID: {project.id})")
        
        service = PowerSystemService(session)
        
        # Create mock power system
        sys_data = PowerSystemCreate(
            name="星海修真",
            description="吸收宇宙星辰之力进行的修真体系。",
            levels=[
                PowerLevelCreate(level_order=1, name="炼气期", abilities="可以感知四周灵源", limitations="无法离地飞行，寿元不过百年", breakthrough_conditions="气沉丹田，积累百日"),
                PowerLevelCreate(level_order=2, name="筑基期", abilities="灵气外放，可御剑飞行", limitations="真元储备有限", breakthrough_conditions="需要筑基丹或者庞大灵力冲关"),
                PowerLevelCreate(level_order=3, name="金丹期", abilities="结成金丹，寿元五百", limitations="金丹碎则修为尽毁", breakthrough_conditions="渡过三九天劫")
            ]
        )
        
        new_sys = await service.create_power_system(project.id, sys_data)
        print(f"Successfully created power system '{new_sys.name}' with {len(new_sys.levels)} levels.")

if __name__ == "__main__":
    asyncio.run(main())
