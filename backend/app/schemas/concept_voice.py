"""可选的同场景口吻试写；只在作者选中后成为本书偏好。"""
from typing import List
from pydantic import BaseModel, Field


class VoiceTrialRequest(BaseModel):
    scene: str = Field(default="", max_length=600)


class VoiceSelectionRequest(BaseModel):
    trial_id: str = Field(min_length=1, max_length=64)
    candidate_id: str = Field(min_length=1, max_length=64)


class VoiceCandidate(BaseModel):
    label: str = Field(min_length=2, max_length=40)
    style_notes: str = Field(min_length=4, max_length=200)
    text: str = Field(min_length=80, max_length=1000)


class VoiceTrialResult(BaseModel):
    scene: str = Field(min_length=4, max_length=600)
    candidates: List[VoiceCandidate] = Field(min_length=2, max_length=3)
