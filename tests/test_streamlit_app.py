"""Streamlit AppTest: form loads, sample fills, missing-key message is clear."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def _all_text(at: AppTest) -> str:
    chunks: list[str] = []
    for attr in ("title", "markdown", "caption", "info", "success", "warning", "error", "subheader"):
        for el in getattr(at, attr, []):
            value = getattr(el, "value", None)
            if value:
                chunks.append(str(value))
    return "\n".join(chunks)


def test_app_shows_missing_key_message(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=15)
    at.run()
    assert not at.exception
    text = _all_text(at)
    assert "AFFILIATE-OS" in text
    assert "GEMINI_API_KEY" in text
    assert ".env.example" in text
    assert "tiada auto-post" in text.lower()
    labels = [box.label for box in at.text_input]
    assert any("Product name" in label or "Nama produk" in label for label in labels)
    assert any("Buat plan" in btn.label for btn in at.button)


def test_load_sample_fills_rotating_kitchen_organizer(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=15)
    at.run()
    sample_btn = next(btn for btn in at.button if "Load sample" in btn.label)
    sample_btn.click().run()
    assert not at.exception
    values = {box.label: box.value for box in at.text_input}
    name = next(v for k, v in values.items() if "Product name" in k or "Nama produk" in k)
    assert name == "Rotating Kitchen Organizer"
    features = next(t.value for t in at.text_area if "Features" in t.label or "Ciri-ciri" in t.label)
    assert "360-degree rotation" in features
    claims = next(
        t.value for t in at.text_area if "prove" in t.label.lower() or "dibuktikan" in t.label.lower()
    )
    assert "rotates 360 degrees" in claims


def test_buat_plan_without_key_shows_env_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=15)
    at.run()
    next(btn for btn in at.button if "Load sample" in btn.label).click().run()
    submit = next(btn for btn in at.button if "Buat plan" in btn.label)
    submit.click().run()
    assert not at.exception
    text = _all_text(at)
    assert "GEMINI_API_KEY" in text
    assert ".env" in text
