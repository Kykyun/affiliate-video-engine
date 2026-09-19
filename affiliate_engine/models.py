"""Pydantic models for product input and VideoPlan structured output."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    product_name: str
    category: str = ""
    price_myr: float
    original_price_myr: Optional[float] = None
    commission_percent: Optional[float] = None
    product_description: str = ""
    features: List[str] = Field(default_factory=list)
    verified_claims: List[str] = Field(default_factory=list)
    product_image_urls: List[str] = Field(default_factory=list)
    target_market: str = "Malaysia"
    language: str = "casual Bahasa Melayu"
    preferred_audience: str = ""
    preferred_emotion: str = ""


class ShotPurpose(str, Enum):
    HOOK_PROBLEM = "HOOK_PROBLEM"
    DEMONSTRATION = "DEMONSTRATION"
    RESULT_CTA = "RESULT_CTA"


class Strategy(BaseModel):
    target_persona: str
    life_situation: str
    problem: str
    internal_thought: str
    emotional_trigger: str
    desired_after_state: str
    financial_frame: str
    selected_angle: str
    why_this_angle: str


class VideoMeta(BaseModel):
    concept_title: str
    hook: str
    duration_seconds: int = 24
    voice_direction: str
    full_voiceover: str
    cta: str


class Shot(BaseModel):
    shot_number: int
    start_second: int
    end_second: int
    purpose: ShotPurpose
    voiceover: str
    text_overlay: str
    visual_description: str
    camera: str
    emotion: str
    product_visibility: str
    veo_prompt: str


class Publishing(BaseModel):
    caption: str
    search_keywords: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)


class Compliance(BaseModel):
    passed: bool = True
    claims_used: List[str] = Field(default_factory=list)
    claims_avoided: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class VideoPlan(BaseModel):
    """Schema-constrained planner output — must match SPEC exactly."""

    strategy: Strategy
    video: VideoMeta
    shots: List[Shot]
    publishing: Publishing
    compliance: Compliance

    @field_validator("shots")
    @classmethod
    def exactly_three_shots(cls, v: List[Shot]) -> List[Shot]:
        if len(v) != 3:
            raise ValueError(f"Expected exactly 3 shots, got {len(v)}")
        return v
