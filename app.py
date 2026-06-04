"""
AfDB Field Portfolio Monitoring · Streamlit entry point.

Run:
    streamlit run app.py

Layout follows a World Bank Scorecard-inspired structure:
  • Top: white logo ribbon (AfDB + RASME)
  • Each page renders its own hero strip with eyebrow / serif headline / sub
  • Pillar-grouped indicator cards
  • Discreet footer
"""

from __future__ import annotations

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
    # Propagate the chosen language to the host page's <html lang> attribute
    # so date_input (and other locale-aware widgets) render month/weekday
    # names in French when FR is selected.
    set_html_lang(lang)

    # Slim white ribbon with the two logos. The hero (eyebrow + headline + sub)
    # lives on each page so it can carry page-specific copy.
    header_ribbon()

    # Sidebar filters live in session_state so each page renders the same selections.
    st.session_state["filters"] = sidebar_filters(lang)

    # Sidebar portfolio assistant — appended after the filters so it sits at the
    # bottom of the sidebar and is available on every page.
    chat_widget(lang, st.session_state["filters"])

    pages = [
        st.Page("global_view.py",  title=t("nav_global",  lang), icon="🌍", default=True),
        st.Page("country_view.py", title=t("nav_country", lang), icon="🇦🇫"),
    ]
    st.navigation(pages, position="sidebar").run()

    footer(lang, last_refresh=datetime.now().strftime("%Y-%m-%d %H:%M"))


main()
