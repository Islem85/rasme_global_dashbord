"""
AfDB Field Portfolio Monitoring · Streamlit entry point.
Run:
    streamlit run app.py

Layout follows a World Bank Scorecard-inspired structure:
    - Top: white logo ribbon (AfDB + RASME)
    - Each page renders its own hero strip with eyebrow / serif headline / sub
    - Pillar-grouped indicator cards
    - Discreet footer
"""

from __future__ import annotations

import logging
from datetime import datetime

import streamlit as st

from chatbot import chat_widget
from i18n import t
from ui import (
    footer,
    header_ribbon,
    inject_css,
    language_toggle,
    set_html_lang,
    sidebar_filters,
)

_EMPTY_FILTERS: dict = {
    "date_from": None,
    "date_to": None,
    "sectors": None,
    "categories": None,
    "funders": None,
    "statuses": None,
    "countries_in": None,
}


def _config_page() -> None:
    st.set_page_config(
        page_title="AfDB · Field Portfolio Scorecard",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def main() -> None:
    _config_page()
    inject_css()

    lang = language_toggle()
    set_html_lang(lang)

    header_ribbon()

    try:
        st.session_state["filters"] = sidebar_filters(lang)
    except Exception as _e:
        logging.warning("sidebar_filters error: %s", _e)
        st.sidebar.error(
            f"Erreur chargement filtres : {type(_e).__name__}\n\n{_e}"
            if lang == "FR"
            else f"Filter loading error: {type(_e).__name__}\n\n{_e}"
        )
        st.session_state.setdefault("filters", _EMPTY_FILTERS)

    try:
        chat_widget(lang, st.session_state.get("filters", _EMPTY_FILTERS))
    except Exception as _e:
        logging.warning("chat_widget error: %s", _e)

    pages = [
        st.Page("global_view.py", title=t("nav_global", lang), icon="🌍", default=True),
        st.Page("country_view.py", title=t("nav_country", lang), icon="🇦🇫"),
    ]
    st.navigation(pages, position="sidebar").run()

    footer(lang, last_refresh=datetime.now().strftime("%Y-%m-%d %H:%M"))


main()
