import asyncio
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.memory_layer_service import MemoryLayerService
from app.services.llm_service import LLMService
from app.services.prompt_service import PromptService
from app.core.config import settings

async def test_init():
    print("Testing mem0 initialization...")
    print(f"Environment: {settings.environment}")
    # We are not going to pass real DB or LLM services just to test mem0 init
    try:
        service = MemoryLayerService(db=None, llm_service=None, prompt_service=None)
        print("MemoryLayerService initialized successfully.")
        print("mem0 config loaded.")
        print(service.memory)
    except Exception as e:
        print(f"Initialization failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_init())
