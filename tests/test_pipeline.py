"""Offline tests for UI pipeline helpers (no Gemini / Streamlit server)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from affiliate_engine.config import Settings, api_key_configured
from affiliate_engine.models import ProductInput, VideoPlan
from affiliate_engine.pipeline import (
    format_optional_number,
    generate_video,
    lines_to_list,
    list_to_lines,
    load_sample_product,
    parse_optional_float,
    plan_only,
    product_from_form,
    safe_error_message,
)
from tests.test_cli_plan_only_offline import _minimal_plan


def test_lines_to_list_skips_blank():
    assert lines_to_list("  a\n\n b \n") == ["a", "b"]
    assert lines_to_list("") == []
    assert list_to_lines(["a", "b"]) == "a\nb"


def test_parse_optional_float():
    assert parse_optional_float("") is None
    assert parse_optional_float("  ") is None
    assert parse_optional_float("12") == 12.0
    assert parse_optional_float("29.90") == 29.9
    assert parse_optional_float("1,000.5") == 1000.5
    assert format_optional_number(None) == ""
    assert format_optional_number(12.0) == "12"
    assert format_optional_number(29.9) == "29.90"


def test_product_from_form_requires_name():
    with pytest.raises(ValueError, match="Product name"):
        product_from_form(
            product_name="  ",
            category="",
            price_myr=10,
            original_price_text="",
            commission_text="",
            description="",
            features_text="",
            verified_claims_text="",
            image_urls_text="",
            target_market="",
            language="",
            preferred_audience="",
            preferred_emotion="",
        )


def test_product_from_form_and_sample_roundtrip():
    sample = load_sample_product()
    product = product_from_form(
        product_name=sample.product_name,
        category=sample.category,
        price_myr=sample.price_myr,
        original_price_text=format_optional_number(sample.original_price_myr),
        commission_text=format_optional_number(sample.commission_percent),
        description=sample.product_description,
        features_text=list_to_lines(sample.features),
        verified_claims_text=list_to_lines(sample.verified_claims),
        image_urls_text=list_to_lines(sample.product_image_urls),
        target_market=sample.target_market,
        language=sample.language,
        preferred_audience=sample.preferred_audience,
        preferred_emotion=sample.preferred_emotion,
    )
    assert product.product_name == "Rotating Kitchen Organizer"
    assert product.price_myr == 18.90
    assert product.original_price_myr == 29.90
    assert product.commission_percent == 12
    assert product.features == sample.features
    assert product.verified_claims == sample.verified_claims
    assert product.target_market == "Malaysia"
    assert product.language == "casual Bahasa Melayu"
    assert product.preferred_audience == ""
    assert product.preferred_emotion == ""


def test_plan_only_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    seen: dict = {}

    def fake_generate(product, settings=None, model=None):
        seen["product"] = product
        seen["settings"] = settings
        return VideoPlan.model_validate(_minimal_plan()), "fake-model"

    monkeypatch.setattr("affiliate_engine.pipeline.generate_plan", fake_generate)
    product = load_sample_product()
    run_dir = tmp_path / "run"
    progress: list[str] = []
    plan, out_dir, model_id = plan_only(
        product, run_dir=run_dir, on_progress=progress.append
    )
    assert out_dir == run_dir
    assert model_id == "fake-model"
    assert plan.strategy.selected_angle == "convenience"
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "product.json").exists()
    assert (run_dir / "REVIEW.md").exists()
    assert (run_dir / "publishing.json").exists()
    assert progress[0] == "Planning with Gemini…"
    assert "Plan ready." in progress
    saved = json.loads((run_dir / "product.json").read_text(encoding="utf-8"))
    assert saved["product_name"] == "Rotating Kitchen Organizer"


def test_plan_only_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        plan_only(load_sample_product(), run_dir=tmp_path / "run")


def test_generate_video_calls_modules_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    plan = VideoPlan.model_validate(_minimal_plan())
    product = ProductInput(
        product_name="X",
        price_myr=1.0,
        product_image_urls=["https://example.com/p.jpg"],
    )
    order: list[str] = []

    def fake_scenes(plan_arg, run_dir, *, settings=None, product_image_urls=None, on_progress=None):
        order.append("veo")
        assert list(product_image_urls) == ["https://example.com/p.jpg"]
        if on_progress:
            on_progress("Rendering scene 1/3…")
        p = Path(run_dir) / "scene_1.mp4"
        p.write_bytes(b"fake")
        return [p]

    def fake_tts(plan_arg, run_dir, *, settings=None):
        order.append("tts")
        p = Path(run_dir) / "voice.wav"
        p.write_bytes(b"fake")
        return p

    def fake_stitch(plan_arg, run_dir, *, scene_paths=None, voice_path=None):
        order.append("stitch")
        p = Path(run_dir) / "final_video.mp4"
        p.write_bytes(b"fake-mp4")
        return p

    monkeypatch.setattr("affiliate_engine.veo.generate_scenes", fake_scenes)
    monkeypatch.setattr("affiliate_engine.tts.synthesize_voiceover", fake_tts)
    monkeypatch.setattr("affiliate_engine.pipeline.stitch_final", fake_stitch)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    progress: list[str] = []
    final = generate_video(product, plan, run_dir, on_progress=progress.append)
    assert final.name == "final_video.mp4"
    assert order == ["veo", "tts", "stitch"]
    assert "Rendering scene 1/3…" in progress
    assert "Recording voiceover…" in progress
    assert "Stitching final video…" in progress


def test_safe_error_message_redacts_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key")
    msg = safe_error_message(RuntimeError("failed super-secret-key boom"))
    assert "super-secret-key" not in msg
    assert "***" in msg


def test_api_key_configured_does_not_require_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert api_key_configured() is False
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    assert api_key_configured() is True
    settings = Settings.from_env(require_api_key=False)
    # Callers must not log settings.gemini_api_key; we only check it is present.
    assert settings.gemini_api_key == "abc"
