"""Gemini planner with schema-constrained structured output."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from google.genai import types

from affiliate_engine.config import Settings, get_client
from affiliate_engine.models import ProductInput, VideoPlan
from affiliate_engine.prompt import build_planner_contents

logger = logging.getLogger(__name__)

# Fallback models if the configured planner 404s / is unavailable.
PLANNER_FALLBACKS: Sequence[str] = (
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
)


class PlannerError(RuntimeError):
    """Raised when the planner cannot produce a valid VideoPlan."""


def _is_retryable_model_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "404",
            "not found",
            "not_found",
            "is not found",
            "does not exist",
            "model_not_found",
            "not supported",
            "503",
            "unavailable",
            "high demand",
            "temporarily",
            "try again",
        )
    )


def generate_plan(
    product: ProductInput | Mapping[str, Any],
    *,
    settings: Settings | None = None,
    model: str | None = None,
) -> tuple[VideoPlan, str]:
    """Call Gemini with response_schema=VideoPlan.

    Returns (plan, model_id_used).
    """
    settings = settings or Settings.from_env()
    if isinstance(product, ProductInput):
        product_dict = product.model_dump(mode="json")
    else:
        product_dict = ProductInput.model_validate(product).model_dump(mode="json")

    contents = build_planner_contents(product_dict)
    client = get_client(settings)

    primary = model or settings.planner_model
    candidates: list[str] = []
    for m in (primary, *PLANNER_FALLBACKS):
        if m and m not in candidates:
            candidates.append(m)

    last_error: Optional[BaseException] = None
    for mid in candidates:
        try:
            logger.info("Planning with model=%s", mid)
            print(f"[plan] Calling Gemini planner: {mid}")
            response = client.models.generate_content(
                model=mid,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=VideoPlan,
                    temperature=0.7,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
            plan = _parse_response(response)
            print(f"[plan] OK — model={mid}")
            return plan, mid
        except Exception as exc:  # noqa: BLE001 — surface & try next model
            last_error = exc
            if _is_retryable_model_error(exc) and mid != candidates[-1]:
                print(f"[plan] Model {mid} unavailable ({exc}); trying next…")
                continue
            raise PlannerError(f"Planner failed with model {mid}: {exc}") from exc

    raise PlannerError(f"All planner models failed. Last error: {last_error}")


def _parse_response(response: Any) -> VideoPlan:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, VideoPlan):
        return parsed
    if parsed is not None:
        return VideoPlan.model_validate(parsed)

    text = getattr(response, "text", None)
    if not text:
        raise PlannerError("Empty planner response (no parsed object and no text).")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlannerError(f"Planner returned non-JSON text: {exc}") from exc
    return VideoPlan.model_validate(data)


def save_plan(plan: VideoPlan, run_dir: Path, *, model_id: str | None = None) -> Path:
    """Write plan.json (+ optional meta) into the run directory."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "plan.json"
    path.write_text(
        plan.model_dump_json(indent=2),
        encoding="utf-8",
    )
    if model_id:
        meta = {"planner_model": model_id}
        (run_dir / "plan_meta.json").write_text(
            json.dumps(meta, indent=2),
            encoding="utf-8",
        )
    return path


def load_plan(path: Path) -> VideoPlan:
    return VideoPlan.model_validate_json(path.read_text(encoding="utf-8"))
