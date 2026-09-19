"""Veo 3.1 scene generation (one 8s clip per shot)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional, Sequence
from urllib.request import urlopen

from google.genai import types

from affiliate_engine.config import Settings, get_client
from affiliate_engine.models import VideoPlan


class VeoError(RuntimeError):
    pass


def _load_reference_images(
    urls: Sequence[str],
    *,
    max_images: int = 3,
) -> List[types.Image]:
    images: List[types.Image] = []
    for url in list(urls)[:max_images]:
        url = (url or "").strip()
        if not url:
            continue
        try:
            if url.startswith(("http://", "https://")):
                with urlopen(url, timeout=30) as resp:  # noqa: S310 — user-supplied product URLs
                    data = resp.read()
                    mime = resp.headers.get_content_type() or "image/jpeg"
            else:
                p = Path(url)
                data = p.read_bytes()
                suffix = p.suffix.lower()
                mime = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                }.get(suffix, "image/jpeg")
            images.append(types.Image(image_bytes=data, mime_type=mime))
        except Exception as exc:  # noqa: BLE001
            print(f"[veo] Warning: could not load reference image {url!r}: {exc}")
    return images


def generate_scenes(
    plan: VideoPlan,
    run_dir: Path,
    *,
    settings: Settings | None = None,
    product_image_urls: Sequence[str] | None = None,
    poll_seconds: float = 15.0,
    max_wait_seconds: float = 600.0,
) -> List[Path]:
    """Generate scene_1.mp4 … scene_N.mp4 via Veo. Returns paths."""
    settings = settings or Settings.from_env()
    client = get_client(settings)
    run_dir.mkdir(parents=True, exist_ok=True)

    refs = _load_reference_images(product_image_urls or [])
    paths: List[Path] = []

    for shot in plan.shots:
        out = run_dir / f"scene_{shot.shot_number}.mp4"
        print(f"[veo] Generating scene {shot.shot_number} ({settings.veo_model})…")
        config_kwargs: dict = {
            "aspect_ratio": "9:16",
            "duration_seconds": 8,
        }
        # Reference images when available (Veo product consistency)
        if refs:
            try:
                config_kwargs["reference_images"] = [
                    types.VideoGenerationReferenceImage(
                        image=img,
                        reference_type="asset",
                    )
                    for img in refs
                ]
            except Exception:
                # Older SDK variants may not expose this type — continue without.
                print("[veo] Reference images not applied (SDK/config unsupported).")

        try:
            operation = client.models.generate_videos(
                model=settings.veo_model,
                prompt=shot.veo_prompt,
                config=types.GenerateVideosConfig(**config_kwargs),
            )
        except TypeError:
            # Retry without reference_images / duration if rejected
            operation = client.models.generate_videos(
                model=settings.veo_model,
                prompt=shot.veo_prompt,
                config=types.GenerateVideosConfig(aspect_ratio="9:16"),
            )

        waited = 0.0
        while not getattr(operation, "done", False):
            if waited >= max_wait_seconds:
                raise VeoError(
                    f"Veo operation timed out after {max_wait_seconds}s for scene {shot.shot_number}"
                )
            time.sleep(poll_seconds)
            waited += poll_seconds
            operation = client.operations.get(operation)
            print(f"[veo] scene {shot.shot_number}: polling… ({int(waited)}s)")

        _download_generated_video(client, operation, out)
        print(f"[veo] Saved {out}")
        paths.append(out)

    return paths


def _download_generated_video(client, operation, out: Path) -> None:
    response = getattr(operation, "response", None) or getattr(operation, "result", None)
    if response is None:
        raise VeoError(f"Veo operation finished without response: {operation}")

    generated = getattr(response, "generated_videos", None) or []
    if not generated:
        raise VeoError("Veo returned no generated_videos.")

    video = generated[0].video
    # Prefer SDK download helpers when present
    try:
        client.files.download(file=video)
        video.save(str(out))
        return
    except Exception:
        pass

    # Fallback: write raw bytes if available
    data = getattr(video, "video_bytes", None) or getattr(video, "data", None)
    if data:
        out.write_bytes(data)
        return

    uri = getattr(video, "uri", None)
    if uri:
        with urlopen(uri, timeout=120) as resp:  # noqa: S310
            out.write_bytes(resp.read())
        return

    raise VeoError("Could not download Veo video (no save/bytes/uri).")


def write_placeholder_scenes(plan: VideoPlan, run_dir: Path) -> List[Path]:
    """Create silent colored placeholder MP4s (needs ffmpeg) for pipeline testing."""
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        raise VeoError("ffmpeg not found — cannot create placeholder scenes.")

    run_dir.mkdir(parents=True, exist_ok=True)
    colors = ["#1a1a2e", "#16213e", "#0f3460"]
    paths: List[Path] = []
    for i, shot in enumerate(plan.shots):
        out = run_dir / f"scene_{shot.shot_number}.mp4"
        color = colors[i % len(colors)]
        # Escape overlay text lightly
        label = (shot.text_overlay or f"Scene {shot.shot_number}")[:40].replace(":", "\\:")
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s=1080x1920:d=8",
            "-vf", f"drawtext=text='{label}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "8",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        paths.append(out)
        print(f"[veo] Placeholder written: {out}")
    return paths
