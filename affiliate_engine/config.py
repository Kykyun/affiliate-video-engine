"""Environment-driven configuration for the affiliate video engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Defaults prefer working current models (env-overridable).
DEFAULT_PLANNER_MODEL = "gemini-flash-latest"
DEFAULT_VEO_MODEL = "veo-3.1-generate-preview"
DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_TTS_VOICE = "Sulafat"  # Warm — good for Malaysian conversational narration
DEFAULT_OUTPUT_DIR = "output"


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    planner_model: str
    veo_model: str
    tts_model: str
    tts_voice: str
    output_dir: Path

    @classmethod
    def from_env(cls, *, require_api_key: bool = True) -> "Settings":
        key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if require_api_key and not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Export it before running the planner/Veo/TTS. "
                "See .env.example."
            )
        return cls(
            gemini_api_key=key,
            planner_model=os.environ.get("GEMINI_PLANNER_MODEL", DEFAULT_PLANNER_MODEL).strip(),
            veo_model=os.environ.get("VEO_MODEL", DEFAULT_VEO_MODEL).strip(),
            tts_model=os.environ.get("GEMINI_TTS_MODEL", DEFAULT_TTS_MODEL).strip(),
            tts_voice=os.environ.get("GEMINI_TTS_VOICE", DEFAULT_TTS_VOICE).strip(),
            output_dir=Path(os.environ.get("AFFILIATE_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)).resolve(),
        )


def get_client(settings: Settings | None = None):
    """Return a google.genai Client configured with GEMINI_API_KEY."""
    from google import genai

    s = settings or Settings.from_env()
    return genai.Client(api_key=s.gemini_api_key)
