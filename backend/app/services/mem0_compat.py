"""Small compatibility boundary for pinned mem0ai 1.0.4; never edits site-packages."""
from mem0 import AsyncMemory


class ProvenanceMemory(AsyncMemory):
    async def _create_memory(self, data, existing_embeddings, metadata=None):
        # infer=False supplies the already-created vector as a list in 1.0.4,
        # whereas _create_memory expects a text->vector mapping. Reuse it once.
        if isinstance(existing_embeddings, (list, tuple)):
            existing_embeddings = {data: existing_embeddings}
        return await super()._create_memory(data, existing_embeddings, metadata)
