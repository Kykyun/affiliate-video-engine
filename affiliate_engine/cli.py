"""CLI: python -m affiliate_engine run <product.json> [flags]."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from affiliate_engine.config import Settings
from affiliate_engine.models import ProductInput
from affiliate_engine.plan import generate_plan, load_plan, save_plan
from affiliate_engine.stitch import stitch_final, write_publishing_artifacts


KL = ZoneInfo("Asia/Kuala_Lumpur")


def _new_run_id() -> str:
    stamp = datetime.now(KL).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate_engine",
        description="MY Affiliate Video Engine V1 — product JSON → TikTok video plan (+ optional Veo/TTS/stitch).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the affiliate video pipeline for one product JSON.")
    run.add_argument("product_json", type=Path, help="Path to product input JSON")
    run.add_argument(
        "--plan-only",
        action="store_true",
        help="Stop after writing plan.json (no Veo/TTS/FFmpeg).",
    )
    run.add_argument("--skip-veo", action="store_true", help="Skip Veo scene generation.")
    run.add_argument("--skip-tts", action="store_true", help="Skip Gemini TTS voiceover.")
    run.add_argument(
        "--reuse-plan",
        type=Path,
        default=None,
        metavar="PLAN_JSON",
        help="Reuse an existing plan.json instead of calling the planner.",
    )
    run.add_argument(
        "--placeholder-scenes",
        action="store_true",
        help="Use ffmpeg colored placeholders instead of Veo (for stitch testing).",
    )
    run.add_argument(
        "--run-id",
        default=None,
        help="Optional run id (default: timestamp + short uuid).",
    )
    run.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output root (default: ./output or AFFILIATE_OUTPUT_DIR).",
    )
    return parser


def cmd_run(args: argparse.Namespace) -> int:
    product_path: Path = args.product_json
    if not product_path.exists():
        print(f"ERROR: product JSON not found: {product_path}", file=sys.stderr)
        return 2

    product_raw = json.loads(product_path.read_text(encoding="utf-8"))
    product = ProductInput.model_validate(product_raw)

    # Plan-only / reuse-plan don't need API key until planner is called
    need_key = args.reuse_plan is None
    settings = Settings.from_env(require_api_key=need_key)
    if args.output_dir:
        output_root = args.output_dir.resolve()
    else:
        output_root = settings.output_dir

    run_id = args.run_id or _new_run_id()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Persist product copy for audit
    (run_dir / "product.json").write_text(
        json.dumps(product.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[run] run_id={run_id}")
    print(f"[run] output={run_dir}")

    model_id: Optional[str] = None
    if args.reuse_plan:
        plan_src = Path(args.reuse_plan)
        print(f"[plan] Reusing plan from {plan_src}")
        plan = load_plan(plan_src)
        plan_path = save_plan(plan, run_dir, model_id="reused")
    else:
        # Ensure key present for live planning
        settings = Settings.from_env(require_api_key=True)
        plan, model_id = generate_plan(product, settings=settings)
        plan_path = save_plan(plan, run_dir, model_id=model_id)

    print(f"[plan] Wrote {plan_path}")
    write_publishing_artifacts(plan, run_dir)

    if args.plan_only:
        print("[run] --plan-only set; stopping after plan + publishing artifacts.")
        _print_summary(plan, plan_path, model_id)
        return 0

    # Scenes
    scene_paths = None
    if args.placeholder_scenes:
        from affiliate_engine.veo import write_placeholder_scenes

        scene_paths = write_placeholder_scenes(plan, run_dir)
    elif not args.skip_veo:
        from affiliate_engine.veo import generate_scenes

        settings = Settings.from_env(require_api_key=True)
        scene_paths = generate_scenes(
            plan,
            run_dir,
            settings=settings,
            product_image_urls=product.product_image_urls,
        )
    else:
        print("[veo] Skipped (--skip-veo).")

    # TTS
    voice_path = None
    if not args.skip_tts:
        from affiliate_engine.tts import synthesize_voiceover

        settings = Settings.from_env(require_api_key=True)
        voice_path = synthesize_voiceover(plan, run_dir, settings=settings)
    else:
        print("[tts] Skipped (--skip-tts).")

    # Stitch if we have scenes
    if scene_paths:
        stitch_final(plan, run_dir, scene_paths=scene_paths, voice_path=voice_path)
    else:
        print("[stitch] Skipped (no scene files).")

    _print_summary(plan, plan_path, model_id)
    print(f"[run] Done. Review {run_dir / 'REVIEW.md'} before posting.")
    return 0


def _print_summary(plan, plan_path: Path, model_id: Optional[str]) -> None:
    print("---")
    print(f"plan: {plan_path}")
    if model_id:
        print(f"planner_model: {model_id}")
    print(f"selected_angle: {plan.strategy.selected_angle}")
    print(f"hook: {plan.video.hook}")
    overlays = [s.text_overlay for s in plan.shots]
    print(f"text_overlays: {overlays}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            return cmd_run(args)
        except KeyboardInterrupt:
            print("Interrupted.", file=sys.stderr)
            return 130
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
