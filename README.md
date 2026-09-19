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
pip install -r requirements.txt && pip install -e .
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

## Web UI (recommended)

A simple Streamlit form — no CLI needed:

```bash
pip install -r requirements.txt && pip install -e .
streamlit run streamlit_app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

1. Fill the product form (or click **Muat contoh / Load sample**).
2. Click **Buat plan / Make plan** (uses Gemini text only).
3. Review the angle, voiceover, shots, caption, and compliance. Download `plan.json` if you want.
4. Optionally click **Generate video (Veo + TTS)** — slower and uses paid API credits. Review `final_video.mp4` + `REVIEW.md` before you post yourself.

If `GEMINI_API_KEY` is missing, the UI tells you to set it in `.env` (see [`.env.example`](.env.example)). The key is never shown.

## CLI

The command line still works the same way:

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
streamlit_app.py   # friendly web form (streamlit run streamlit_app.py)
affiliate_engine/
  cli.py      # argparse entry
  config.py   # env settings
  models.py   # ProductInput + VideoPlan (Pydantic)
  plan.py     # Gemini structured-output planner
  prompt.py   # AFFILIATE-OS-MY master prompt
  pipeline.py # plan + video helpers used by the UI
  veo.py      # Veo 3.1 scenes
  tts.py      # Gemini TTS
  stitch.py   # FFmpeg concat + mux + burn-in
```

Planner uses `google-genai` with `response_mime_type=application/json` and `response_schema=VideoPlan` (not freeform “return JSON”).
