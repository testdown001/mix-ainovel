"""Deterministic model-boundary responses for scene orchestration tests."""
import json

from app.services.generation_quality_gate import NarrativeCheck
from app.services.scene_generation_service import SceneContract, SceneContracts


async def scene_structured_response(**kwargs):
    if kwargs["schema"] is NarrativeCheck:
        return NarrativeCheck(issues=[], state_delta=["场景内的人物已完成当前行动"])
    payload = json.loads(kwargs["prompt"].split("\n", 1)[1])
    return SceneContracts(scenes=[SceneContract(
        goal=scene.get("goal") or "推进剧情", obstacle=scene.get("conflict") or "雨中道路受阻",
        choice="继续前行", turn=scene.get("turn") or "发现新的通路",
        consequence=scene.get("end_state") or "抵达门前", emotion_before="犹豫", emotion_after="决心",
    ) for scene in payload["scenes"]])
