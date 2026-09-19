"""Basic unit tests for schema + prompt injection (no API calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from affiliate_engine.models import ProductInput, VideoPlan
from affiliate_engine.prompt import AFFILIATE_OS_MY, inject_product_data


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "rotating_kitchen_organizer.json"


def test_example_product_loads():
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    product = ProductInput.model_validate(data)
    assert product.product_name == "Rotating Kitchen Organizer"
    assert product.price_myr == 18.90
    assert "360-degree rotation" in product.features


def test_video_plan_requires_three_shots():
    base = {
        "strategy": {
            "target_persona": "p",
            "life_situation": "s",
            "problem": "pr",
            "internal_thought": "t",
            "emotional_trigger": "e",
            "desired_after_state": "a",
            "financial_frame": "f",
            "selected_angle": "angle",
            "why_this_angle": "why",
        },
        "video": {
            "concept_title": "c",
            "hook": "h",
            "duration_seconds": 24,
            "voice_direction": "v",
            "full_voiceover": "vo",
            "cta": "cta",
        },
        "shots": [],
        "publishing": {"caption": "cap", "search_keywords": [], "hashtags": []},
        "compliance": {
            "passed": True,
            "claims_used": [],
            "claims_avoided": [],
            "warnings": [],
        },
    }
    with pytest.raises(Exception):
        VideoPlan.model_validate(base)

    shot = {
        "shot_number": 1,
        "start_second": 0,
        "end_second": 8,
        "purpose": "HOOK_PROBLEM",
        "voiceover": "a",
        "text_overlay": "t",
        "visual_description": "v",
        "camera": "c",
        "emotion": "e",
        "product_visibility": "hidden",
        "veo_prompt": "prompt",
    }
    base["shots"] = [
        shot,
        {**shot, "shot_number": 2, "start_second": 8, "end_second": 16, "purpose": "DEMONSTRATION"},
        {**shot, "shot_number": 3, "start_second": 16, "end_second": 24, "purpose": "RESULT_CTA"},
    ]
    plan = VideoPlan.model_validate(base)
    assert len(plan.shots) == 3
    assert plan.strategy.selected_angle == "angle"


def test_master_prompt_contains_affiliate_os_and_injects_json():
    assert "AFFILIATE-OS-MY" in AFFILIATE_OS_MY
    assert "{{PRODUCT_DATA}}" in AFFILIATE_OS_MY
    product = ProductInput.model_validate(json.loads(EXAMPLE.read_text(encoding="utf-8")))
    filled = inject_product_data(product.model_dump(mode="json"))
    assert "{{PRODUCT_DATA}}" not in filled
    assert "Rotating Kitchen Organizer" in filled
    assert "18.9" in filled or "18.90" in filled
