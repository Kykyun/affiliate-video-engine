"""Offline CLI smoke: --reuse-plan + --plan-only needs no API key / ffmpeg."""

from __future__ import annotations

import json
from pathlib import Path

from affiliate_engine.cli import main
from affiliate_engine.models import VideoPlan


def _minimal_plan() -> dict:
    shot = {
        "shot_number": 1,
        "start_second": 0,
        "end_second": 8,
        "purpose": "HOOK_PROBLEM",
        "voiceover": "vo1",
        "text_overlay": "Overlay 1",
        "visual_description": "vis",
        "camera": "cam",
        "emotion": "emo",
        "product_visibility": "hidden",
        "veo_prompt": "veo1",
    }
    return {
        "strategy": {
            "target_persona": "persona",
            "life_situation": "situation",
            "problem": "problem",
            "internal_thought": "thought",
            "emotional_trigger": "trigger",
            "desired_after_state": "after",
            "financial_frame": "frame",
            "selected_angle": "convenience",
            "why_this_angle": "why",
        },
        "video": {
            "concept_title": "title",
            "hook": "hook line",
            "duration_seconds": 24,
            "voice_direction": "warm",
            "full_voiceover": "full vo",
            "cta": "check bakul",
        },
        "shots": [
            shot,
            {**shot, "shot_number": 2, "start_second": 8, "end_second": 16, "purpose": "DEMONSTRATION", "text_overlay": "Overlay 2"},
            {**shot, "shot_number": 3, "start_second": 16, "end_second": 24, "purpose": "RESULT_CTA", "text_overlay": "Overlay 3"},
        ],
        "publishing": {"caption": "cap", "search_keywords": ["a"], "hashtags": ["#b"]},
        "compliance": {"passed": True, "claims_used": [], "claims_avoided": [], "warnings": []},
    }


def test_reuse_plan_plan_only(tmp_path: Path):
    product = {
        "product_name": "Test Product",
        "category": "Home",
        "price_myr": 10.0,
        "product_description": "desc",
        "features": [],
        "verified_claims": [],
    }
    product_path = tmp_path / "product.json"
    product_path.write_text(json.dumps(product), encoding="utf-8")
    plan_path = tmp_path / "existing_plan.json"
    plan_path.write_text(json.dumps(_minimal_plan()), encoding="utf-8")
    out = tmp_path / "out"

    code = main(
        [
            "run",
            str(product_path),
            "--plan-only",
            "--reuse-plan",
            str(plan_path),
            "--output-dir",
            str(out),
            "--run-id",
            "test_run",
        ]
    )
    assert code == 0
    written = out / "test_run" / "plan.json"
    assert written.exists()
    plan = VideoPlan.model_validate_json(written.read_text(encoding="utf-8"))
    assert plan.strategy.selected_angle == "convenience"
    assert (out / "test_run" / "REVIEW.md").exists()
    assert (out / "test_run" / "publishing.json").exists()
