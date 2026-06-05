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
        initial_sidebar_state="expanded",  # Indique à Streamlit de l'ouvrir au chargement
    )

    # HACK CSS : Force l'affichage de la barre latérale sur grand écran
    st.markdown(
        """
        <style>
            /* Force le conteneur de la sidebar à être visible */
            [data-testid="stSidebarCollapsedControl"] {
                display: none !important; /* Cache le petit bouton '>' pour éviter qu'on puisse la fermer */
            }
            section[data-testid="stSidebar"] {
                margin-left: 0px !important;
                transform: none !important;
                transition: none !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


def main() -> None:
    # 1. Configuration de base et styles
    _config_page()
    inject_css()

    # 2. Gestion de la langue
    lang = language_toggle()
    set_html_lang(lang)

    # 3. Affichage du bandeau d'en-tête (logos)
    header_ribbon()

    # 4. DÉCLARATION de la navigation (sans exécution immédiate)
    # Cela permet à Streamlit de préparer la structure de la barre latérale
    pages = [
        st.Page("global_view.py", title=t("nav_global", lang), icon="🌍", default=True),
        st.Page("country_view.py", title=t("nav_country", lang), icon="🇲🇦"),
    ]
    nav = st.navigation(pages, position="sidebar")

    # 5. GÉNÉRATION DES FILTRES DANS LA BARRE LATÉRALE
    # Ils viendront se positionner proprement sous le menu de navigation
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

    # 6. Widget de Chatbot
    try:
        chat_widget(lang, st.session_state.get("filters", _EMPTY_FILTERS))
    except Exception as _e:
        logging.warning("chat_widget error: %s", _e)

    # 7. EXÉCUTION DE LA PAGE SÉLECTIONNÉE
    # Le contenu du fichier (ex: global_view.py) est injecté ici au centre
    nav.run()

    # 8. Affichage du pied de page
    footer(lang, last_refresh=datetime.now().strftime("%Y-%m-%d %H:%M"))


if __name__ == "__main__":
    main()
