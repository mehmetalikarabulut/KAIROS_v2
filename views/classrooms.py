"""Step 3 — Classrooms: KPI chips + CSV upload + inventory preview (capacity, lab)."""
import os

import streamlit as st

from timetabling.csv_import import ok_rooms, parse_classrooms, read_raw
from timetabling.ui_app import track_event
from timetabling.ui_style import (
    data_table_html, detected_columns_html, eyebrow_html, import_stats_html,
    kpi_chips_html, success_banner_html, upload_cta_html, upload_error_html,
)
from timetabling.textnorm import parse_int
from timetabling.i18n import t, ROOM_TYPE_LABELS
from timetabling.csv_import import normalize_room_type

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_classrooms.csv")


def render(lang: str) -> None:
    track_event("classrooms_viewed")
    st.markdown(eyebrow_html(None, t("step_classrooms", lang), "classrooms", sub=True),
                unsafe_allow_html=True)
    st.caption(t("cr_caption", lang))

    rooms = st.session_state["classrooms"]
    caps = [parse_int(r.get("Capacity") or r.get("Cap"), 0) for r in rooms]
    labs = sum(1 for r in rooms
               if normalize_room_type(r.get("Type", "")) in ("pc_lab", "electronics_lab"))
    st.markdown(kpi_chips_html([
        (t("kpi_rooms", lang), str(len(rooms)), ""),
        (t("kpi_labs", lang), str(labs), ""),
        (t("kpi_maxcap", lang), str(max(caps) if caps else 0), ""),
        (t("kpi_online", lang), "∞", "good"),
    ]), unsafe_allow_html=True)

    source = st.session_state.get("cr_source")

    # Upload card — same dropzone look as Step 1. Once a list is loaded (sample or
    # CSV) the card shows a green "loaded" banner with a button to load a different
    # list; until then it shows the dropzone + "Try with sample dataset" button.
    with st.container(key="cr_card"):
        if source:
            st.markdown(success_banner_html(t("cr_loaded", lang, n=len(rooms)), source),
                        unsafe_allow_html=True)
            # Center the "load a different list" button below the success banner.
            # Its keyed container (.st-key-cr_change) is a flex item that sizes to
            # its label and sits left, so it must be forced full-width + flex-center
            # while the inner stButton + button are pinned back to content width so
            # the button hugs its label.
            st.markdown(
                "<style>"
                ".st-key-cr_change{display:flex!important;justify-content:center!important;width:100%!important;}"
                ".st-key-cr_change [data-testid='stButton']{width:auto!important;flex:0 0 auto!important;}"
                ".st-key-cr_change button{width:auto!important;}"
                "</style>",
                unsafe_allow_html=True)
            if st.button(t("cr_change_btn", lang), key="cr_change",
                         icon=":material/upload_file:"):
                st.session_state.pop("cr_source", None)
                st.session_state.pop("cr_report", None)
                st.rerun()
        else:
            # Empty state: same two-button row as Step 1 — left = "Upload CSV" CTA
            # (a visual primary button with an invisible file-uploader overlaid on
            # top, so it opens the file picker and still accepts drag-drop); right =
            # the native "sample dataset" secondary button. Columns stack on mobile.
            c_up, c_sample = st.columns(2, vertical_alignment="center")
            with c_up:
                with st.container(key="cr_up_btn"):
                    st.markdown(upload_cta_html(lang), unsafe_allow_html=True)
                    up = st.file_uploader("Upload CSV", type=["csv"], key="cr_upload",
                                          label_visibility="collapsed")
            with c_sample:
                load_sample = st.button(
                    t("cr_sample", lang),
                    key="cr_sample",
                    type="secondary",
                    icon=":material/dataset:",
                )

            if up is not None:
                try:
                    report = parse_classrooms(read_raw(up))
                except Exception as exc:
                    st.markdown(upload_error_html(up.name, exc, lang), unsafe_allow_html=True)
                    report = None
                if report is not None and not ok_rooms(report):
                    st.markdown(upload_error_html(up.name, t("cr_upload_error", lang), lang),
                                unsafe_allow_html=True)
                elif report is not None:
                    st.session_state["classrooms"] = ok_rooms(report)
                    st.session_state["cr_report"] = report
                    st.session_state["cr_source"] = up.name
                    st.rerun()

            if load_sample:
                report = parse_classrooms(read_raw(_SAMPLE))
                st.session_state["classrooms"] = ok_rooms(report)
                st.session_state["cr_report"] = report
                st.session_state["cr_source"] = t("cr_sample_name", lang)
                st.rerun()

        # Format hint — always visible (mirrors upload step behaviour).
        st.markdown(f'<p style="text-align:center;font-size:.875em;color:var(--muted,#888);">{t("cr_format_label", lang)}</p>', unsafe_allow_html=True)
        _cr = [t("tbl_room", lang), t("tbl_cap", lang), t("tbl_type", lang), t("tbl_room_dept", lang)]
        st.markdown(
            data_table_html(
                _cr,
                [["A216", "25", "classroom", ""], ["A311-PC-L", "99", "pc_lab", t("sample_cr_dept", lang)]],
                max_height=160, numeric=(_cr[1],)),
            unsafe_allow_html=True)

    # Detected-column chips + valid/total badges + inventory preview — shown below
    # the card (not inside it) so the dashed border wraps only the banner + button,
    # matching the course upload module's success-state layout.
    if source:
        report = st.session_state.get("cr_report")
        if report:
            st.markdown(detected_columns_html(report["detected_columns"], lang,
                                              required=("Room", "Capacity", "Type")),
                        unsafe_allow_html=True)
            st.markdown(import_stats_html(report["stats"], lang),
                        unsafe_allow_html=True)
        _cr = [t("tbl_room", lang), t("tbl_cap", lang), t("tbl_type", lang),
               t("tbl_room_dept", lang), t("import_col_status", lang)]
        st.markdown(
            data_table_html(
                _cr,
                [[r.get("Room", ""), r.get("Capacity", r.get("Cap", "")),
                  ROOM_TYPE_LABELS[lang][normalize_room_type(r.get("Type", ""))], r.get("Dept", ""), "ok"] for r in rooms],
                max_height=300, numeric=(_cr[1],),
                pill_cols=(_cr[4],),
                pill_labels={"ok": t("import_status_ok", lang)}),
            unsafe_allow_html=True)

    _reservation_inputs(lang, rooms)


def _reservation_inputs(lang, rooms):
    from timetabling.room_reservations import parse_room_reservations, apply_room_reservations
    from timetabling.ui_input import build_rooms_from_ui
    from timetabling.config import Config

    def label(en, tr):
        return tr if lang == "tr" else en

    st.subheader(label("Room reservations", "Derslik rezervasyonları"))
    st.caption(label(
        "Weekly reservations block a physical room for every department. Sessions may end at Start or begin at End. Blank Room rows are ignored. Dept is optional information.",
        "Haftalık rezervasyonlar dersliği tüm bölümler için kapatır. Dersler Start saatinde bitebilir veya End saatinde başlayabilir. Room boşsa satır yok sayılır. Dept isteğe bağlı bilgidir."))
    from pathlib import Path
    asset_dir = Path(__file__).resolve().parent.parent / "assets"
    template = (asset_dir / "example_room_reservations.csv").read_text(encoding="utf-8")
    st.download_button(label("Download reservation CSV example", "Rezervasyon CSV örneğini indir"),
                       template, "room_reservations.csv", "text/csv", key="reservation_download")
    st.download_button(label("Download Excel input template", "Excel giriş şablonunu indir"),
                       (asset_dir / "kairos_input_template.xlsx").read_bytes(), "kairos_input_template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="reservation_excel")
    with st.form("room_reservation_form"):
        up = st.file_uploader(label("Reservation CSV", "Rezervasyon CSV"), type=["csv"], key="reservation_upload")
        load = st.form_submit_button(label("Load reservations (replace current list)", "Rezervasyonları yükle (listeyi değiştir)"))
    if load:
        try:
            if up is None:
                raise ValueError(label("Choose a reservation CSV first.", "Önce rezervasyon CSV dosyasını seçin."))
            up.seek(0)
            parsed = parse_room_reservations(read_raw(up))
            apply_room_reservations(build_rooms_from_ui(rooms, Config()), parsed)
            st.session_state["room_reservations"] = parsed
            st.session_state.pop("room_reservation_error", None)
            st.success(label(f"Loaded {len(parsed)} reservations.", f"{len(parsed)} rezervasyon yüklendi."))
        except ValueError as exc:
            st.session_state["room_reservation_error"] = str(exc)
    if st.button(label("Clear reservations", "Rezervasyonları temizle"), key="reservation_clear"):
        st.session_state["room_reservations"] = []
        st.session_state.pop("room_reservation_error", None)
        st.rerun()
    if st.session_state.get("room_reservation_error"):
        st.error(st.session_state["room_reservation_error"])
    reservations = st.session_state.get("room_reservations", [])
    if reservations:
        columns = ["Room", "Dept", "Day", "Start", "End"]
        st.markdown(data_table_html(columns, [[r.get(c, "") for c in columns] for r in reservations],
                                    max_height=300), unsafe_allow_html=True)
