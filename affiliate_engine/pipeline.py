"""High-level pipeline helpers for the Streamlit UI.

CLI continues to live in ``affiliate_engine.cli`` and is unchanged.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from affiliate_engine.config import Settings
from affiliate_engine.models import ProductInput, VideoPlan
from affiliate_engine.plan import generate_plan, save_plan
from affiliate_engine.stitch import stitch_final, write_publishing_artifacts

KL = ZoneInfo("Asia/Kuala_Lumpur")
ProgressFn = Callable[[str], None]
ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PRODUCT_PATH = ROOT / "examples" / "rotating_kitchen_organizer.json"
ENV_EXAMPLE_PATH = ROOT / ".env.example"


def new_run_id() -> str:
    stamp = datetime.now(KL).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def lines_to_list(text: str) -> list[str]:
    """Split textarea input into a clean list (one item per non-empty line)."""
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def list_to_lines(items: list[str] | None) -> str:
    return "\n".join(items or [])


def parse_optional_float(text: str) -> Optional[float]:
    raw = (text or "").strip().replace(",", "")
    if not raw:
        return None
    return float(raw)


def format_optional_number(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def load_sample_product() -> ProductInput:
    return ProductInput.model_validate_json(
        SAMPLE_PRODUCT_PATH.read_text(encoding="utf-8")
    )


def product_from_form(
    *,
    product_name: str,
    category: str,
    price_myr: float,
    original_price_text: str,
    commission_text: str,
    description: str,
    features_text: str,
    verified_claims_text: str,
    image_urls_text: str,
    target_market: str,
    language: str,
    preferred_audience: str,
    preferred_emotion: str,
) -> ProductInput:
    name = (product_name or "").strip()
    if not name:
        raise ValueError("Nama produk diperlukan / Product name is required.")
    try:
        original = parse_optional_float(original_price_text)
    except ValueError as exc:
        raise ValueError(
            "Harga asal mesti nombor (contoh 29.90) / Original price must be a number."
        ) from exc
    try:
        commission = parse_optional_float(commission_text)
    except ValueError as exc:
        raise ValueError(
            "Komisen % mesti nombor (contoh 12) / Commission must be a number."
        ) from exc
    return ProductInput(
        product_name=name,
        category=(category or "").strip(),
        price_myr=float(price_myr),
        original_price_myr=original,
        commission_percent=commission,
        product_description=(description or "").strip(),
        features=lines_to_list(features_text),
        verified_claims=lines_to_list(verified_claims_text),
        product_image_urls=lines_to_list(image_urls_text),
        target_market=(target_market or "").strip() or "Malaysia",
        language=(language or "").strip() or "casual Bahasa Melayu",
        preferred_audience=(preferred_audience or "").strip(),
        preferred_emotion=(preferred_emotion or "").strip(),
    )


def create_run_dir(output_dir: Path | None = None, run_id: str | None = None) -> Path:
    settings = Settings.from_env(require_api_key=False)
    root = Path(output_dir) if output_dir else settings.output_dir
    run_dir = root / (run_id or new_run_id())
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def plan_only(
    product: ProductInput,
    *,
    run_dir: Path | None = None,
    on_progress: ProgressFn | None = None,
) -> tuple[VideoPlan, Path, str]:
    """Run the Gemini planner and write plan.json + publishing artifacts."""
    if on_progress:
        on_progress("Planning with Gemini…")
    settings = Settings.from_env(require_api_key=True)
    run_dir = Path(run_dir) if run_dir else create_run_dir()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "product.json").write_text(
        json.dumps(product.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    plan, model_id = generate_plan(product, settings=settings)
    save_plan(plan, run_dir, model_id=model_id)
    write_publishing_artifacts(plan, run_dir)
    if on_progress:
        on_progress("Plan ready.")
    return plan, run_dir, model_id


def generate_video(
    product: ProductInput,
    plan: VideoPlan,
    run_dir: Path,
    *,
    on_progress: ProgressFn | None = None,
) -> Path:
    """Run Veo + TTS + FFmpeg stitch into ``final_video.mp4``."""
    from affiliate_engine.tts import synthesize_voiceover
    from affiliate_engine.veo import generate_scenes

    settings = Settings.from_env(require_api_key=True)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if on_progress:
        on_progress("Starting Veo + TTS (this can take several minutes)…")
    scene_paths = generate_scenes(
        plan,
        run_dir,
        settings=settings,
        product_image_urls=product.product_image_urls,
        on_progress=on_progress,
    )
    if on_progress:
        on_progress("Recording voiceover…")
    voice_path = synthesize_voiceover(plan, run_dir, settings=settings)
    if on_progress:
        on_progress("Stitching final video…")
    final = stitch_final(plan, run_dir, scene_paths=scene_paths, voice_path=voice_path)
    write_publishing_artifacts(plan, run_dir)
    if on_progress:
        on_progress("Video ready. Please review before posting.")
    return final


def safe_error_message(exc: BaseException) -> str:
    """Human-readable error with any API key stripped out."""
    text = str(exc)
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if key:
        text = text.replace(key, "***")
    return text
