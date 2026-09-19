"""Simple Streamlit form for MY Affiliate Video Engine (AFFILIATE-OS).

Run from the repo root:

    streamlit run streamlit_app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from affiliate_engine.config import api_key_configured
from affiliate_engine.models import ProductInput, VideoPlan
from affiliate_engine.pipeline import (
    ENV_EXAMPLE_PATH,
    format_optional_number,
    generate_video,
    list_to_lines,
    load_sample_product,
    plan_only,
    product_from_form,
    safe_error_message,
)

REPO_ROOT = Path(__file__).resolve().parent
ENV_EXAMPLE_URL = (
    "https://github.com/Kykyun/affiliate-video-engine/blob/main/.env.example"
)

FORM_DEFAULTS = {
    "f_product_name": "",
    "f_category": "",
    "f_price_myr": 0.00,
    "f_original_price": "",
    "f_commission": "",
    "f_description": "",
    "f_features": "",
    "f_verified_claims": "",
    "f_image_urls": "",
    "f_target_market": "Malaysia",
    "f_language": "casual Bahasa Melayu",
    "f_preferred_audience": "",
    "f_preferred_emotion": "",
}


def _init_state() -> None:
    for key, value in FORM_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value
    st.session_state.setdefault("plan_dict", None)
    st.session_state.setdefault("product_dict", None)
    st.session_state.setdefault("run_dir", None)
    st.session_state.setdefault("model_id", None)
    st.session_state.setdefault("final_video", None)
    st.session_state.setdefault("video_confirm", False)


def _clear_results() -> None:
    st.session_state.plan_dict = None
    st.session_state.product_dict = None
    st.session_state.run_dir = None
    st.session_state.model_id = None
    st.session_state.final_video = None
    st.session_state.video_confirm = False


def _apply_sample() -> None:
    product = load_sample_product()
    st.session_state.f_product_name = product.product_name
    st.session_state.f_category = product.category
    st.session_state.f_price_myr = float(product.price_myr)
    st.session_state.f_original_price = format_optional_number(product.original_price_myr)
    st.session_state.f_commission = format_optional_number(product.commission_percent)
    st.session_state.f_description = product.product_description
    st.session_state.f_features = list_to_lines(product.features)
    st.session_state.f_verified_claims = list_to_lines(product.verified_claims)
    st.session_state.f_image_urls = list_to_lines(product.product_image_urls)
    st.session_state.f_target_market = product.target_market or "Malaysia"
    st.session_state.f_language = product.language or "casual Bahasa Melayu"
    st.session_state.f_preferred_audience = product.preferred_audience
    st.session_state.f_preferred_emotion = product.preferred_emotion
    _clear_results()


def _current_product() -> ProductInput:
    return product_from_form(
        product_name=st.session_state.f_product_name,
        category=st.session_state.f_category,
        price_myr=st.session_state.f_price_myr,
        original_price_text=st.session_state.f_original_price,
        commission_text=st.session_state.f_commission,
        description=st.session_state.f_description,
        features_text=st.session_state.f_features,
        verified_claims_text=st.session_state.f_verified_claims,
        image_urls_text=st.session_state.f_image_urls,
        target_market=st.session_state.f_target_market,
        language=st.session_state.f_language,
        preferred_audience=st.session_state.f_preferred_audience,
        preferred_emotion=st.session_state.f_preferred_emotion,
    )


def _render_key_banner() -> bool:
    if api_key_configured():
        st.success("Gemini siap digunakan. Key dibaca dari `.env` (tidak dipaparkan).")
        return True
    st.error(
        "Set **GEMINI_API_KEY** in `.env` before planning or generating video. "
        "Salin fail contoh, letak key, kemudian restart app ini."
    )
    st.markdown(
        f"Template: [`.env.example`]({ENV_EXAMPLE_URL}) "
        f"(local path `{ENV_EXAMPLE_PATH}`)."
    )
    if ENV_EXAMPLE_PATH.exists():
        with st.expander("Tengok isi `.env.example`"):
            st.code(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), language="bash")
    return False


def _render_form() -> None:
    st.subheader("1. Maklumat produk")
    st.caption("Isi macam borang biasa. Satu baris = satu item untuk senarai.")

    st.button(
        "Muat contoh / Load sample",
        on_click=_apply_sample,
        help="Isi borang dengan contoh Rotating Kitchen Organizer.",
        use_container_width=True,
    )

    with st.form("product_form", clear_on_submit=False):
        st.text_input(
            "Nama produk / Product name *",
            key="f_product_name",
            placeholder="contoh: Rotating Kitchen Organizer",
        )
        st.text_input(
            "Kategori / Category",
            key="f_category",
            placeholder="contoh: Home & Living",
        )
        st.number_input(
            "Harga (MYR) / Price *",
            min_value=0.0,
            step=0.10,
            format="%.2f",
            key="f_price_myr",
        )
        st.text_input(
            "Harga asal (MYR) / Original price — optional",
            key="f_original_price",
            placeholder="contoh: 29.90  (kosong jika tiada)",
        )
        st.text_input(
            "Komisen % / Commission — optional",
            key="f_commission",
            placeholder="contoh: 12",
        )
        st.text_area(
            "Penerangan / Description",
            key="f_description",
            height=100,
            placeholder="Apa produk ni buat, dalam 1–3 ayat.",
        )
        st.text_area(
            "Ciri-ciri / Features (satu per baris)",
            key="f_features",
            height=110,
            placeholder="360-degree rotation\ncompact\neasy access",
        )
        st.text_area(
            "Claim yang boleh dibuktikan / Only say things we can prove (satu per baris)",
            key="f_verified_claims",
            height=110,
            placeholder="rotates 360 degrees\ncan hold bottles and containers",
            help="Jangan letak claim yang kita tak boleh buktikan. Planner hanya guna list ini.",
        )
        st.text_area(
            "URL gambar produk / Product image URLs — optional (satu per baris)",
            key="f_image_urls",
            height=80,
            placeholder="https://…",
        )
        st.text_input("Pasaran / Target market", key="f_target_market")
        st.text_input("Bahasa / Language", key="f_language")
        st.text_input(
            "Audience pilihan / Preferred audience — optional",
            key="f_preferred_audience",
            placeholder="Kosong = Gemini pilih",
        )
        st.text_input(
            "Emosi pilihan / Preferred emotion — optional",
            key="f_preferred_emotion",
            placeholder="Kosong = Gemini pilih  (contoh: relief, convenience)",
        )
        submitted = st.form_submit_button(
            "Buat plan / Make plan",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        _run_plan()


def _run_plan() -> None:
    _clear_results()
    try:
        product = _current_product()
    except ValueError as exc:
        st.error(safe_error_message(exc))
        return
    if not api_key_configured():
        st.error(
            "Set GEMINI_API_KEY in `.env` dulu. "
            f"See [`.env.example`]({ENV_EXAMPLE_URL})."
        )
        return

    status = st.status("Planning with Gemini…", expanded=True)
    try:
        def on_progress(msg: str) -> None:
            status.write(msg)

        plan, run_dir, model_id = plan_only(product, on_progress=on_progress)
        st.session_state.plan_dict = plan.model_dump(mode="json")
        st.session_state.product_dict = product.model_dump(mode="json")
        st.session_state.run_dir = str(run_dir)
        st.session_state.model_id = model_id
        status.update(label="Plan ready", state="complete")
    except Exception as exc:  # noqa: BLE001 — show a friendly UI error
        status.update(label="Planning failed", state="error")
        status.write(safe_error_message(exc))
        st.error(safe_error_message(exc))


def _render_plan(plan: VideoPlan) -> None:
    st.subheader("2. Hasil plan")
    st.caption("Semak sudut, voiceover dan compliance sebelum generate video.")

    strategy = plan.strategy
    st.markdown(f"**Sudut / Angle:** {strategy.selected_angle}")
    st.markdown(f"**Kenapa:** {strategy.why_this_angle}")
    st.markdown(f"**Persona:** {strategy.target_persona}")
    st.markdown(f"**Situasi:** {strategy.life_situation}")
    st.markdown(f"**Masalah / Problem:** {strategy.problem}")

    st.markdown("---")
    st.markdown(f"**Tajuk konsep:** {plan.video.concept_title}")
    st.markdown(f"**Hook:** {plan.video.hook}")
    st.markdown("**Voiceover penuh**")
    st.write(plan.video.full_voiceover)
    st.markdown(f"**Arah suara:** {plan.video.voice_direction}")
    st.markdown(f"**CTA (soft):** {plan.video.cta}")

    st.markdown("---")
    st.markdown("**3 shots**")
    for shot in plan.shots:
        with st.expander(
            f"Shot {shot.shot_number} · {shot.purpose.value} · {shot.start_second}–{shot.end_second}s",
            expanded=True,
        ):
            st.markdown(f"**Overlay:** {shot.text_overlay}")
            st.markdown(f"**Nota visual:** {shot.visual_description}")
            st.caption(f"Kamera: {shot.camera} · Emosi: {shot.emotion}")
            st.caption(f"Voiceover shot: {shot.voiceover}")

    st.markdown("---")
    st.markdown("**Caption / hashtags** (untuk anda paste sendiri)")
    st.write(plan.publishing.caption)
    if plan.publishing.hashtags:
        st.write(" ".join(plan.publishing.hashtags))
    if plan.publishing.search_keywords:
        st.caption("Keywords: " + ", ".join(plan.publishing.search_keywords))

    st.markdown("---")
    compliance = plan.compliance
    if compliance.passed and not compliance.warnings:
        st.success("Compliance: pass.")
    elif compliance.passed:
        st.warning("Compliance: pass, with warnings. Semak sebelum post.")
    else:
        st.error("Compliance: tidak pass. Jangan post sehingga dibetulkan.")
    if compliance.claims_used:
        st.caption("Claims used: " + "; ".join(compliance.claims_used))
    if compliance.claims_avoided:
        st.caption("Claims avoided: " + "; ".join(compliance.claims_avoided))
    if compliance.warnings:
        for warning in compliance.warnings:
            st.warning(warning)

    plan_json = plan.model_dump_json(indent=2)
    st.download_button(
        "Download plan.json",
        data=plan_json.encode("utf-8"),
        file_name="plan.json",
        mime="application/json",
        use_container_width=True,
    )
    run_dir = st.session_state.get("run_dir")
    if run_dir:
        st.caption(f"Disimpan di `{run_dir}`")
        if st.session_state.get("model_id"):
            st.caption(f"Planner model: {st.session_state.model_id}")


def _render_video_section(plan: VideoPlan) -> None:
    st.subheader("3. Generate video (Veo + TTS)")
    st.warning(
        "Langkah ni guna **Veo** (video) dan **TTS** (suara). "
        "Boleh ambil beberapa minit dan ada **kos API**. "
        "Semak plan dulu. Anda masih perlu review + post sendiri ke TikTok — "
        "app ni tidak auto-post."
    )
    confirm = st.checkbox(
        "Faham, teruskan / I understand the time and API cost",
        key="video_confirm",
    )
    can_run = bool(confirm and api_key_configured() and st.session_state.get("run_dir"))
    clicked = st.button(
        "Generate video (Veo + TTS)",
        type="secondary",
        disabled=not can_run,
        use_container_width=True,
        help="Aktif lepas ada plan dan anda tick kotak amaran kos.",
    )
    if clicked:
        _run_video(plan)

    video_path = st.session_state.get("final_video")
    if video_path:
        path = Path(video_path)
        st.success("Video siap. Semak REVIEW checklist sebelum post.")
        st.markdown(f"**Fail:** `{path}`")
        if path.exists():
            st.video(str(path))
            st.download_button(
                "Download final_video.mp4",
                data=path.read_bytes(),
                file_name="final_video.mp4",
                mime="video/mp4",
                use_container_width=True,
            )
        review = Path(st.session_state.run_dir) / "REVIEW.md"
        if review.exists():
            st.markdown("**REVIEW checklist**")
            st.markdown(review.read_text(encoding="utf-8"))
            st.download_button(
                "Download REVIEW.md",
                data=review.read_text(encoding="utf-8"),
                file_name="REVIEW.md",
                mime="text/markdown",
                use_container_width=True,
            )


def _run_video(plan: VideoPlan) -> None:
    if not api_key_configured():
        st.error(
            "Set GEMINI_API_KEY in `.env` dulu. "
            f"See [`.env.example`]({ENV_EXAMPLE_URL})."
        )
        return
    product = ProductInput.model_validate(st.session_state.product_dict)
    run_dir = Path(st.session_state.run_dir)
    status = st.status("Generating video…", expanded=True)
    try:
        def on_progress(msg: str) -> None:
            status.write(msg)

        final = generate_video(product, plan, run_dir, on_progress=on_progress)
        st.session_state.final_video = str(final)
        status.update(label="Video ready", state="complete")
    except Exception as exc:  # noqa: BLE001
        status.update(label="Video generation failed", state="error")
        status.write(safe_error_message(exc))
        st.error(safe_error_message(exc))


def main() -> None:
    st.set_page_config(
        page_title="AFFILIATE-OS · MY Affiliate Video Engine",
        page_icon="🎬",
        layout="centered",
    )
    st.markdown(
        """
        <style>
        .stTextInput input, .stTextArea textarea, .stNumberInput input {
            font-size: 1.05rem;
        }
        div[data-testid="stForm"] {
            border: none;
            padding-left: 0;
            padding-right: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _init_state()

    st.title("AFFILIATE-OS")
    st.markdown("**MY Affiliate Video Engine** — borang mudah untuk rancangan video TikTok Affiliate.")
    st.caption(
        "Isi produk → buat plan → semak → generate video jika perlu. "
        "Anda review dan post sendiri. Tiada auto-post ke TikTok."
    )
    _render_key_banner()
    st.markdown("---")
    _render_form()

    plan_dict = st.session_state.get("plan_dict")
    if plan_dict:
        plan = VideoPlan.model_validate(plan_dict)
        st.markdown("---")
        _render_plan(plan)
        st.markdown("---")
        _render_video_section(plan)
    else:
        st.info(
            "Generate video (Veo + TTS) akan aktif selepas ada plan. "
            "Buat plan dulu — ia lebih murah dan cepat untuk disemak."
        )


main()
