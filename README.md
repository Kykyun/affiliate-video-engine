# MY Affiliate Video Engine V1

Single-product → single-TikTok-video factory for **TikTok Affiliate Malaysia**.

Gemini plans with buyer psychology first (schema-constrained JSON), then optional Veo 3.1 scenes, Gemini TTS voiceover, and FFmpeg stitch. **No TikTok auto-post** — every run writes `REVIEW.md` + `publishing.json` for a human poster.

## Pipeline

```
PRODUCT JSON → Gemini Affiliate Brain (AFFILIATE-OS-MY)
            → plan.json (3×8s shots + voiceover + Veo prompts)
            → Veo scenes (optional)
            → Gemini TTS (optional)
            → FFmpeg stitch + captions
            → final_video.mp4 + human review gate
```

## Setup

```bash
cd /workspace/affiliate-video-engine
python3 -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt
pip install -e .   # so `python -m affiliate_engine` works
cp .env.example .env   # then set GEMINI_API_KEY
```

Required: `GEMINI_API_KEY`. Optional model overrides:

| Env | Default |
|-----|---------|
| `GEMINI_PLANNER_MODEL` | `gemini-flash-latest` |
| `VEO_MODEL` | `veo-3.1-generate-preview` |
| `GEMINI_TTS_MODEL` | `gemini-2.5-flash-preview-tts` |
| `GEMINI_TTS_VOICE` | `Sulafat` |

FFmpeg is required only for full stitch / `--placeholder-scenes` (not for `--plan-only`).

## Usage

```bash
# Plan only (no Veo/TTS/FFmpeg credits beyond Gemini text)
python -m affiliate_engine run examples/rotating_kitchen_organizer.json --plan-only

# Full pipeline
python -m affiliate_engine run examples/rotating_kitchen_organizer.json

# Partial
python -m affiliate_engine run path/to/product.json --skip-veo
python -m affiliate_engine run path/to/product.json --skip-tts
python -m affiliate_engine run path/to/product.json --reuse-plan output/<run_id>/plan.json --placeholder-scenes
```

Outputs land in `output/<run_id>/`:

- `plan.json` — structured VideoPlan
- `publishing.json` — caption / hashtags for manual post
- `REVIEW.md` — human checklist
- `scene_1.mp4` … `scene_3.mp4`, `voice.wav`, `final_video.mp4` (when generated)

## Human review (before posting)

- Product look matches listing / reference images
- Hands / demos believable (no weird AI artifacts)
- Malay voiceover natural (not forced slang)
- No invented discounts, stock urgency, testimonials, or health claims
- Prices match product JSON only
- Soft CTA only (“bakul”) — no fake urgency

## Package layout

```
affiliate_engine/
  cli.py      # argparse entry
  config.py   # env settings
  models.py   # ProductInput + VideoPlan (Pydantic)
  plan.py     # Gemini structured-output planner
  prompt.py   # AFFILIATE-OS-MY master prompt
  veo.py      # Veo 3.1 scenes
  tts.py      # Gemini TTS
  stitch.py   # FFmpeg concat + mux + burn-in
```

Planner uses `google-genai` with `response_mime_type=application/json` and `response_schema=VideoPlan` (not freeform “return JSON”).
