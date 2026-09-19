"""Gemini TTS voiceover generation."""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Optional

from google.genai import types

from affiliate_engine.config import Settings, get_client
from affiliate_engine.models import VideoPlan


class TtsError(RuntimeError):
    pass


def _write_wav(path: Path, pcm: bytes, *, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def _build_tts_prompt(plan: VideoPlan) -> str:
    direction = (plan.video.voice_direction or "").strip()
    if not direction:
        direction = (
            "Malaysian woman about 28 years old, warm, helpful, conversational, "
            "slightly fast TikTok pacing, natural Bahasa Melayu, like a useful friend sharing a discovery."
        )
    transcript = plan.video.full_voiceover.strip()
    return (
        f"{direction}\n\n"
        "Read the following TikTok affiliate voiceover naturally. "
        "Do not add extra words. Do not read stage directions.\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )


def synthesize_voiceover(
    plan: VideoPlan,
    run_dir: Path,
    *,
    settings: Settings | None = None,
) -> Path:
    """Generate voice.wav from plan.video.full_voiceover using Gemini TTS."""
    settings = settings or Settings.from_env()
    client = get_client(settings)
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "voice.wav"

    prompt = _build_tts_prompt(plan)
    print(f"[tts] Synthesizing with {settings.tts_model} voice={settings.tts_voice}…")

    # Prefer classic generate_content AUDIO modality (widely supported).
    try:
        response = client.models.generate_content(
            model=settings.tts_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=settings.tts_voice,
                        )
                    )
                ),
            ),
        )
        pcm = _extract_pcm_from_generate_content(response)
        _write_wav(out, pcm)
        print(f"[tts] Saved {out}")
        return out
    except Exception as primary_exc:
        # Fallback: interactions API (newer SDK / TTS models)
        print(f"[tts] generate_content path failed ({primary_exc}); trying interactions…")
        try:
            return _synthesize_via_interactions(client, settings, prompt, out)
        except Exception as secondary_exc:
            raise TtsError(
                f"TTS failed via generate_content ({primary_exc}) and interactions ({secondary_exc})"
            ) from secondary_exc


def _extract_pcm_from_generate_content(response) -> bytes:
    try:
        parts = response.candidates[0].content.parts
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                if isinstance(data, str):
                    import base64

                    return base64.b64decode(data)
                return data
    except Exception as exc:
        raise TtsError(f"Could not extract audio from generate_content response: {exc}") from exc
    raise TtsError("No audio inline_data in TTS response.")


def _synthesize_via_interactions(client, settings: Settings, prompt: str, out: Path) -> Path:
    import base64

    if not hasattr(client, "interactions"):
        raise TtsError("Client has no interactions API.")

    interaction = client.interactions.create(
        model=settings.tts_model,
        input=prompt,
        response_format={"type": "audio"},
        generation_config={
            "speech_config": [{"voice": settings.tts_voice}],
        },
    )
    audio = getattr(interaction, "output_audio", None)
    if audio is None:
        raise TtsError("interactions TTS returned no output_audio.")
    data = getattr(audio, "data", None)
    if data is None:
        raise TtsError("interactions TTS output_audio has no data.")
    pcm = base64.b64decode(data) if isinstance(data, str) else data
    _write_wav(out, pcm)
    print(f"[tts] Saved {out} (interactions)")
    return out


def write_silent_voice(run_dir: Path, *, duration_seconds: float = 24.0) -> Path:
    """Write a silent WAV for stitch testing without TTS credits."""
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "voice.wav"
    rate = 24000
    n_frames = int(rate * duration_seconds)
    pcm = struct.pack(f"<{n_frames}h", *([0] * n_frames))
    _write_wav(out, pcm, rate=rate)
    print(f"[tts] Silent placeholder: {out}")
    return out
