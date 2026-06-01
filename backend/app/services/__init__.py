# AIMETA P=服务包标识|R=包标识|NR=不含服务实现_不再eager导出|E=-|X=internal|A=-|D=none|S=none|RD=./README.ai
"""
服务层包

历史上此处 eager 导出 ~60 个服务类（`from app.services import XxxService`），
但全仓无任何消费者，仅拖慢启动并制造耦合，故已移除。
请直接从具体子模块导入，例如：
    from app.services.llm_service import LLMService
    from app.services.finalize_service import FinalizeService
"""
