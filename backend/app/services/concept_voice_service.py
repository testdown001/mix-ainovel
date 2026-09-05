"""灵感试写：候选持久化，作者明确选中后沿用现有本书创作记忆。"""
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from ..models.creative_memory import CreativeMemoryItem
from ..schemas.concept_voice import VoiceTrialResult
from .concept_dossier_service import ConceptDossierService, _get_dossier_lock, format_dossier_for_prompt


def dossier_fingerprint(project) -> str:
    state = ConceptDossierService.get_state(project)
    return hashlib.sha256(json.dumps(
        {"dossier": state.get("dossier"), "exclusions": project.exclusions or ""},
        ensure_ascii=False, sort_keys=True,
    ).encode()).hexdigest()


def emotional_core_brief(project) -> str:
    state = getattr(project, "concept_dossier", None)
    if not isinstance(state, dict) or not isinstance(state.get("dossier"), dict):
        return ""
    core = state["dossier"].get("emotional_core") or {}
    if not isinstance(core, dict):
        return ""
    lines = []
    for key, label in (("cherished", "最舍不得"), ("exception", "会为谁破例"),
                       ("key_relationship", "核心关系"), ("hard_choice", "两难选择"),
                       ("emotional_promise", "情感承诺")):
        value = core.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f"- {label}：{value.strip()[:300]}")
    if not lines:
        return ""
    return "\n".join(["[本书情感核心] 按本章人物与事件选择相关部分，通过选择和后果呈现；立项意图不是已发生事实，不要照抄心理解释。", *lines])


class ConceptVoiceService:
    def __init__(self, session, llm_service, prompt_service):
        self.session, self.llm, self.prompts = session, llm_service, prompt_service

    async def view(self, project):
        trial = ConceptDossierService.get_state(project).get("voice_trial")
        if not isinstance(trial, dict):
            return {"trial": None}
        trial = dict(trial)
        trial["stale"] = trial.get("dossier_hash") != dossier_fingerprint(project)
        memory_id = trial.get("memory_id")
        if memory_id:
            memory = await self.session.get(CreativeMemoryItem, memory_id)
            if not memory or memory.status != "active":
                trial["selected_id"] = None
        return {"trial": trial}

    async def generate(self, project, user_id: int, scene: str):
        lock = await _get_dossier_lock(project.id)
        async with lock:
            await self.session.refresh(project)
            state = dict(ConceptDossierService.get_state(project))
            dossier = state.get("dossier")
            if not isinstance(dossier, dict) or not dossier:
                raise HTTPException(409, "请先完成故事立项书")
            fingerprint = dossier_fingerprint(project)
            prompt = await self.prompts.get_prompt("concept_voice")
            if not prompt:
                raise HTTPException(503, "试写模板尚未就绪，请稍后重试")
            result = await self.llm.generate_structured(
                prompt=format_dossier_for_prompt(dossier) + f"\n[场景要求]\n{scene or '从已有设定选一个小场景'}"
                       + f"\n[创作禁区]\n{project.exclusions or '无'}",
                schema=VoiceTrialResult, system_prompt=prompt, temperature=0.75,
                user_id=user_id, max_tokens=4500, default=None,
            )
            if result is None:
                raise HTTPException(502, "试写未完成，可以重试；原口吻设置仍保留")
            await self.session.refresh(project)
            if dossier_fingerprint(project) != fingerprint:
                raise HTTPException(409, "立项书已改变，请按新设定重新试写")
            if len({c.text.strip() for c in result.candidates}) != len(result.candidates):
                raise HTTPException(502, "试写没有产生不同口吻，请重试")
            trial = {
                "id": uuid4().hex, "scene": result.scene, "dossier_hash": fingerprint,
                "candidates": [{"id": uuid4().hex, **c.model_dump()} for c in result.candidates],
                "selected_id": None,
            }
            state = dict(ConceptDossierService.get_state(project))
            state["voice_trial"] = trial
            project.concept_dossier = state
            await self.session.commit()
            return await self.view(project)

    async def select(self, project, user_id: int, trial_id: str, candidate_id: str):
        lock = await _get_dossier_lock(project.id)
        async with lock:
            await self.session.refresh(project)
            state = dict(ConceptDossierService.get_state(project))
            trial = state.get("voice_trial") or {}
            if trial.get("id") != trial_id or trial.get("dossier_hash") != dossier_fingerprint(project):
                raise HTTPException(409, "试写与当前立项书不一致，请重新试写")
            candidate = next((c for c in trial.get("candidates", []) if c["id"] == candidate_id), None)
            if candidate is None:
                raise HTTPException(404, "试写版本不存在")
            # 一个项目一个确认口吻槽位；重复选择幂等，换口吻更新，不积累冲突规则。
            key = hashlib.sha256(f"voice-trial:{user_id}:{project.id}".encode()).hexdigest()
            memory = (await self.session.execute(select(CreativeMemoryItem).where(
                CreativeMemoryItem.dedupe_key == key,
            ))).scalars().first()
            if memory is None:
                memory = CreativeMemoryItem(
                    user_id=user_id, project_id=project.id, source_project_id=project.id,
                    scope="novel", category="style", source_type="voice_trial", dedupe_key=key,
                )
                self.session.add(memory)
            memory.title = "本书口吻：" + candidate["label"]
            memory.content = (
                "作者已选择以下口吻。只参考叙述距离、措辞、对白和停顿；服从本章功能，"
                "不复用示例剧情、人物事实或原句。\n"
                + candidate["style_notes"] + "\n[口吻样本，不是正史]\n" + candidate["text"]
            )
            memory.status, memory.pinned, memory.confidence = "active", True, 1.0
            memory.evidence = {"kind": "voice_trial", "trial_id": trial_id,
                               "candidate_id": candidate_id, "dossier_hash": trial["dossier_hash"],
                               "scene": trial["scene"]}
            await self.session.flush()
            state["voice_trial"] = {**trial, "selected_id": candidate_id, "memory_id": memory.id}
            project.concept_dossier = state
            await self.session.commit()
            return await self.view(project)
