"""FFmpeg stitching: concat scenes, mux voiceover, burn-in text overlays."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import List, Optional, Sequence

from affiliate_engine.models import VideoPlan


class StitchError(RuntimeError):
    pass


def _require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise StitchError("ffmpeg not found on PATH. Install ffmpeg to stitch videos.")
    return path


def _escape_drawtext(s: str) -> str:
    # Escape characters special to ffmpeg drawtext
    return (
        s.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def stitch_final(
    plan: VideoPlan,
    run_dir: Path,
    *,
    scene_paths: Sequence[Path] | None = None,
    voice_path: Path | None = None,
    burn_captions: bool = True,
) -> Path:
    """Concatenate scenes, mux TTS, burn text overlays → final_video.mp4."""
    ffmpeg = _require_ffmpeg()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    if scene_paths is None:
        scene_paths = [run_dir / f"scene_{s.shot_number}.mp4" for s in plan.shots]
    scene_paths = [Path(p) for p in scene_paths]
    for p in scene_paths:
        if not p.exists():
            raise StitchError(f"Missing scene file: {p}")

    voice_path = Path(voice_path) if voice_path else run_dir / "voice.wav"
    concat_list = run_dir / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in scene_paths),
        encoding="utf-8",
    )

    concat_out = run_dir / "concat_raw.mp4"
    print("[stitch] Concatenating scenes…")
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(concat_out),
        ],
        check=True,
        capture_output=True,
    )

    # Build drawtext filter chain timed per shot
    vf_parts: List[str] = []
    if burn_captions:
        for shot in plan.shots:
            text = (shot.text_overlay or "").strip()
            if not text:
                continue
            # Keep overlays short; wrap if needed
            text = " ".join(text.split())
            if len(text) > 48:
                text = text[:45] + "…"
            esc = _escape_drawtext(text)
            start = float(shot.start_second)
            end = float(shot.end_second)
            vf_parts.append(
                f"drawtext=text='{esc}':fontsize=42:fontcolor=white:borderw=3:"
                f"bordercolor=black@0.8:x=(w-text_w)/2:y=h*0.12:"
                f"enable='between(t\\,{start}\\,{end})'"
            )

    vf = ",".join(vf_parts) if vf_parts else None
    final = run_dir / "final_video.mp4"

    cmd = [ffmpeg, "-y", "-i", str(concat_out)]
    has_voice = voice_path.exists()
    if has_voice:
        cmd += ["-i", str(voice_path)]

    if vf and has_voice:
        cmd += [
            "-vf", vf,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            "-movflags", "+faststart",
            str(final),
        ]
    elif vf:
        cmd += [
            "-vf", vf,
            "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(final),
        ]
    elif has_voice:
        cmd += [
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-shortest",
            "-movflags", "+faststart",
            str(final),
        ]
    else:
        cmd += ["-c", "copy", str(final)]

    print("[stitch] Muxing / burning captions → final_video.mp4…")
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace")[-2000:]
        raise StitchError(f"ffmpeg failed:\n{stderr}") from exc

    print(f"[stitch] Saved {final}")
    return final


def write_publishing_artifacts(plan: VideoPlan, run_dir: Path) -> tuple[Path, Path]:
    """Write publishing.json and REVIEW.md for human poster (NO auto-post)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    pub = {
        "caption": plan.publishing.caption,
        "search_keywords": plan.publishing.search_keywords,
        "hashtags": plan.publishing.hashtags,
        "cta": plan.video.cta,
        "note": "Human review required — do NOT auto-post to TikTok.",
    }
    pub_path = run_dir / "publishing.json"
    pub_path.write_text(json.dumps(pub, ensure_ascii=False, indent=2), encoding="utf-8")

    review = textwrap.dedent(
        f"""\
        # Human review checklist (NO auto-post)

        Run folder: `{run_dir}`

        ## Strategy
        - Selected angle: {plan.strategy.selected_angle}
        - Persona: {plan.strategy.target_persona}
        - Problem: {plan.strategy.problem}

        ## Video
        - Hook: {plan.video.hook}
        - CTA: {plan.video.cta}

        ## Compliance
        - Passed: {plan.compliance.passed}
        - Claims used: {', '.join(plan.compliance.claims_used) or '(none)'}
        - Claims avoided: {', '.join(plan.compliance.claims_avoided) or '(none)'}
        - Warnings: {', '.join(plan.compliance.warnings) or '(none)'}

        ## Before posting to TikTok Affiliate MY
        - [ ] Product appearance matches listing / reference images
        - [ ] Hands / demos look believable (no weird AI artifacts)
        - [ ] Bahasa Melayu voiceover sounds natural (not forced slang)
        - [ ] No invented discounts, stock urgency, testimonials, or health claims
        - [ ] Prices match PRODUCT_DATA only
        - [ ] Text overlays readable on phone
        - [ ] Soft CTA only (bakul) — no fake urgency

        Publishing copy is in `publishing.json`. Post manually after review.
        """
    )
    review_path = run_dir / "REVIEW.md"
    review_path.write_text(review, encoding="utf-8")
    print(f"[publish] Wrote {pub_path} and {review_path}")
    return pub_path, review_path
