"""
Local portfolio assistant — a rule-based, bilingual (FR/EN) chat widget that
answers questions about the monitored portfolio.

It is intentionally *offline*: no external LLM, no API key, no data leaving the
system. Every answer is computed from the same cached query helpers in db.py
that feed the dashboard, so it always agrees with the charts and respects the
sidebar filters currently in effect.

The widget lives in the sidebar (rendered by app.py) so it is available on
every page.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Optional

import streamlit as st

import db
from config import (
    CANONICAL_SECTORS,
    COUNTRY_LABELS,
    PALETTE,
    SECTOR_LABELS,
    country_label,
    sector_label,
    status_label,
)
from ui import _logo_data_uri, fmt_int, fmt_pct

MAX_HISTORY = 40  # keep the session-state transcript bounded


def _L(lang: str, fr: str, en: str) -> str:
    """Pick the FR or EN variant. Keeps all assistant copy in one place."""
    return fr if lang == "FR" else en


# ──────────────────────────────────────────────────────────────────────────────
# Text normalisation + entity extraction
# ──────────────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lower-case, strip accents, collapse non-alphanumerics to single spaces."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _has(text_norm: str, *words: str) -> bool:
    """True if any whole word/phrase in `words` appears in the normalised text."""
    padded = f" {text_norm} "
    return any(f" {_norm(w)} " in padded for w in words)


# {normalised country name → slug}. Built once. Includes FR + EN labels, the
# slug itself, and a few common aliases the labels don't cover.
def _build_country_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for slug, (fr, en) in COUNTRY_LABELS.items():
        for name in (fr, en, slug.replace("_", " ")):
            key = _norm(name)
            if key:
                idx[key] = slug
    idx.update({
        _norm("rdc"): "drc",
        _norm("rd congo"): "drc",
        _norm("car"): "rca",
        _norm("centrafrique"): "rca",
        _norm("ivory coast"): "cote_d_ivoire",
        _norm("rdc congo"): "drc",
    })
    return idx


_COUNTRY_INDEX = _build_country_index()

# {normalised sector name → canonical bucket}. FR + EN labels of the canonical
# sectors only (the ones the dashboard buckets to).
def _build_sector_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for bucket in CANONICAL_SECTORS:
        pair = SECTOR_LABELS.get(bucket)
        names = [bucket]
        if pair:
            names += [pair[0], pair[1]]
        for name in names:
            key = _norm(name)
            if key:
                idx[key] = bucket
    return idx


_SECTOR_INDEX = _build_sector_index()


def _detect_country(text_norm: str) -> Optional[str]:
    """Return the country slug mentioned in the text, or None. Longest names
    first so 'south sudan' wins over 'sudan'."""
    padded = f" {text_norm} "
    for key in sorted(_COUNTRY_INDEX, key=len, reverse=True):
        if f" {key} " in padded:
            return _COUNTRY_INDEX[key]
    return None


def _detect_sector(text_norm: str) -> Optional[str]:
    padded = f" {text_norm} "
    for key in sorted(_SECTOR_INDEX, key=len, reverse=True):
        if f" {key} " in padded:
            return _SECTOR_INDEX[key]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Answer builders — each returns a Markdown string.
# ──────────────────────────────────────────────────────────────────────────────

def _help_text(lang: str) -> str:
    return _L(
        lang,
        "Je réponds à des questions sur le portefeuille suivi. Quelques exemples :\n\n"
        "- **Combien de sites** sont suivis ?\n"
        "- **Combien de pays** sont couverts ?\n"
        "- **Taux d'achèvement** (global ou *au Mali*)\n"
        "- **Sites à risque**\n"
        "- **Top pays** par nombre de sites\n"
        "- **Répartition sectorielle** / par **statut** / par **bailleur**\n"
        "- **Bénéficiaires** (global ou *au Sénégal*)\n"
        "- **Collectes récentes** (30 derniers jours)\n"
        "- *Résumé du Niger*\n\n"
        "Les réponses tiennent compte des **filtres actifs** dans la barre latérale.",
        "I answer questions about the monitored portfolio. A few examples:\n\n"
        "- **How many sites** are monitored?\n"
        "- **How many countries** are covered?\n"
        "- **Completion rate** (overall or *in Mali*)\n"
        "- **At-risk sites**\n"
        "- **Top countries** by number of sites\n"
        "- **Sector** / **status** / **funder** breakdown\n"
        "- **Beneficiaries** (overall or *in Senegal*)\n"
        "- **Recent submissions** (last 30 days)\n"
        "- *Summary of Niger*\n\n"
        "Answers respect the **active filters** in the sidebar.",
    )


def _scope_suffix(lang: str, country_slug: Optional[str]) -> str:
    if country_slug:
        return f" · {country_label(country_slug, lang)}"
    return ""


def _overview_sites(lang: str, filters: dict, country: Optional[str]) -> str:
    f = {**filters, "country": country} if country else filters
    ov = db.kpi_overview(f)
    n = fmt_int(ov.get("sites"))
    where = _scope_suffix(lang, country)
    return _L(
        lang,
        f"**{n}** sites suivis{where}.",
        f"**{n}** monitored sites{where}.",
    )


def _overview_countries(lang: str, filters: dict) -> str:
    ov = db.kpi_overview(filters)
    n = fmt_int(ov.get("countries"))
    return _L(lang, f"**{n}** pays couverts.", f"**{n}** countries covered.")


def _overview_active(lang: str, filters: dict, country: Optional[str]) -> str:
    f = {**filters, "country": country} if country else filters
    ov = db.kpi_overview(f)
    n = fmt_int(ov.get("active_projects"))
    where = _scope_suffix(lang, country)
    return _L(
        lang,
        f"**{n}** projets actifs (en cours ou planifiés){where}.",
        f"**{n}** active projects (in progress or planned){where}.",
    )


def _overview_completion(lang: str, filters: dict, country: Optional[str]) -> str:
    f = {**filters, "country": country} if country else filters
    ov = db.kpi_overview(f)
    rate = fmt_pct(ov.get("completion_rate"))
    where = _scope_suffix(lang, country)
    return _L(
        lang,
        f"Taux d'achèvement{where} : **{rate}**.",
        f"Completion rate{where}: **{rate}**.",
    )


def _overview_at_risk(lang: str, filters: dict, country: Optional[str]) -> str:
    f = {**filters, "country": country} if country else filters
    ov = db.kpi_overview(f)
    rate = fmt_pct(ov.get("at_risk_rate"))
    where = _scope_suffix(lang, country)
    return _L(
        lang,
        f"Sites à risque{where} (au point mort, suspendus, abandonnés ou annulés) : **{rate}**.",
        f"At-risk sites{where} (stalled, suspended, abandoned or canceled): **{rate}**.",
    )


def _top_countries(lang: str, filters: dict) -> str:
    df = db.kpi_by_country(filters)
    if df is None or df.empty:
        return _L(lang, "Aucune donnée pour les filtres sélectionnés.",
                  "No data for the selected filters.")
    head = df.head(5)
    lines = [
        f"{i}. **{country_label(row['country'], lang)}** — "
        f"{fmt_int(row['sites'])} {_L(lang, 'sites', 'sites')}"
        for i, (_, row) in enumerate(head.iterrows(), start=1)
    ]
    title = _L(lang, "Top pays par nombre de sites :", "Top countries by number of sites:")
    return title + "\n\n" + "\n".join(lines)


def _sector_breakdown(lang: str, filters: dict) -> str:
    df = db.sector_breakdown(filters)
    if df is None or df.empty:
        return _L(lang, "Aucune donnée pour les filtres sélectionnés.",
                  "No data for the selected filters.")
    total = df["sites"].sum()
    head = df.head(6)
    lines = []
    for _, row in head.iterrows():
        share = (100.0 * row["sites"] / total) if total else 0
        lines.append(
            f"- **{sector_label(row['sector'], lang)}** — "
            f"{fmt_int(row['sites'])} ({share:.0f} %)"
        )
    title = _L(lang, "Répartition par secteur :", "Breakdown by sector:")
    return title + "\n\n" + "\n".join(lines)


def _status_breakdown(lang: str, filters: dict) -> str:
    df = db.status_distribution(filters)
    if df is None or df.empty:
        return _L(lang, "Aucune donnée pour les filtres sélectionnés.",
                  "No data for the selected filters.")
    total = df["sites"].sum()
    lines = []
    for _, row in df.head(8).iterrows():
        share = (100.0 * row["sites"] / total) if total else 0
        lines.append(
            f"- **{status_label(row['status'], lang)}** — "
            f"{fmt_int(row['sites'])} ({share:.0f} %)"
        )
    title = _L(lang, "Répartition par statut :", "Breakdown by status:")
    return title + "\n\n" + "\n".join(lines)


def _funder_breakdown(lang: str, filters: dict) -> str:
    df = db.funder_breakdown(filters)
    if df is None or df.empty:
        return _L(lang, "Aucune donnée pour les filtres sélectionnés.",
                  "No data for the selected filters.")
    lines = [
        f"- **{row['funder']}** — {fmt_int(row['sites'])}"
        for _, row in df.head(6).iterrows()
    ]
    title = _L(lang, "Principaux bailleurs (par sites) :",
               "Top funders (by sites):")
    return title + "\n\n" + "\n".join(lines)


def _beneficiaries(lang: str, filters: dict, country: Optional[str]) -> str:
    if country:
        s = db.country_beneficiaries(country, filters)
    else:
        s = db.beneficiaries_overview(filters)
    total = fmt_int(s.get("total"))
    women = fmt_int(s.get("women"))
    men = fmt_int(s.get("men"))
    where = _scope_suffix(lang, country)
    return _L(
        lang,
        f"Bénéficiaires directs{where} : **{total}** "
        f"(femmes : {women} · hommes : {men}).",
        f"Direct beneficiaries{where}: **{total}** "
        f"(women: {women} · men: {men}).",
    )


def _recent(lang: str, filters: dict) -> str:
    n = db.recent_submissions_count(filters, days=30)
    return _L(
        lang,
        f"**{fmt_int(n)}** nouvelles collectes au cours des 30 derniers jours.",
        f"**{fmt_int(n)}** new submissions during the last 30 days.",
    )


def _country_summary(lang: str, filters: dict, country: str) -> str:
    f = {**filters, "country": country}
    ov = db.kpi_overview(f)
    name = country_label(country, lang)
    sites = fmt_int(ov.get("sites"))
    comp = fmt_pct(ov.get("completion_rate"))
    risk = fmt_pct(ov.get("at_risk_rate"))
    active = fmt_int(ov.get("active_projects"))
    return _L(
        lang,
        f"**{name}** — résumé :\n\n"
        f"- Sites suivis : **{sites}**\n"
        f"- Projets actifs : **{active}**\n"
        f"- Taux d'achèvement : **{comp}**\n"
        f"- Sites à risque : **{risk}**",
        f"**{name}** — summary:\n\n"
        f"- Monitored sites: **{sites}**\n"
        f"- Active projects: **{active}**\n"
        f"- Completion rate: **{comp}**\n"
        f"- At-risk sites: **{risk}**",
    )


def _list_countries(lang: str, filters: dict) -> str:
    df = db.kpi_by_country(filters)
    if df is None or df.empty:
        return _L(lang, "Aucun pays dans la sélection.", "No countries in the selection.")
    names = sorted(country_label(c, lang) for c in df["country"].dropna().unique())
    joined = ", ".join(names)
    return _L(
        lang,
        f"**{len(names)}** pays dans la sélection : {joined}.",
        f"**{len(names)}** countries in the selection: {joined}.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Intent routing
# ──────────────────────────────────────────────────────────────────────────────

def respond(question: str, lang: str, filters: dict[str, Any]) -> str:
    """Map a free-text question to an answer, computed from db.py helpers."""
    q = _norm(question)
    if not q:
        return _help_text(lang)

    country = _detect_country(q)
    sector = _detect_sector(q)

    # Greetings / help.
    if _has(q, "aide", "help", "bonjour", "hello", "salut", "hi", "hey",
            "que peux tu", "what can you", "comment ca marche", "how does this work"):
        return _help_text(lang)

    # If a sector is named, narrow the filters so metrics are sector-scoped.
    if sector:
        filters = {**filters, "sectors": [sector]}

    # ── Specific metrics ─────────────────────────────────────────────────────
    if _has(q, "beneficiaire", "beneficiaires", "beneficiary", "beneficiaries",
            "femmes", "women", "personnes touchees", "people reached"):
        return _beneficiaries(lang, filters, country)

    if _has(q, "a risque", "at risk", "point mort", "stalled", "abandonne",
            "abandonnes", "abandoned", "suspendu", "suspended", "risque", "risk"):
        return _overview_at_risk(lang, filters, country)

    if _has(q, "taux d achevement", "achevement", "achevee", "achevees", "acheves",
            "completion", "completed", "complete"):
        return _overview_completion(lang, filters, country)

    if _has(q, "projet actif", "projets actifs", "active project", "active projects",
            "combien de projets", "how many projects", "nombre de projets"):
        return _overview_active(lang, filters, country)

    if _has(q, "combien de pays", "how many countries", "nombre de pays",
            "pays couverts", "countries covered"):
        if _has(q, "liste", "list", "lesquels", "quels", "which"):
            return _list_countries(lang, filters)
        return _overview_countries(lang, filters)

    if _has(q, "top pays", "top countries", "classement", "ranking",
            "quels pays", "which countries", "plus de sites", "most sites"):
        return _top_countries(lang, filters)

    if _has(q, "secteur", "secteurs", "sector", "sectors", "sectoriel",
            "sectorielle", "sectoral"):
        return _sector_breakdown(lang, filters)

    if _has(q, "statut", "statuts", "status", "etat", "etats"):
        return _status_breakdown(lang, filters)

    if _has(q, "bailleur", "bailleurs", "funder", "funders", "financement",
            "funding", "donor", "donors"):
        return _funder_breakdown(lang, filters)

    if _has(q, "recent", "recents", "recente", "recentes", "30 jours",
            "last 30 days", "derniers jours", "nouvelles collectes", "new submissions"):
        return _recent(lang, filters)

    if _has(q, "combien de sites", "nombre de sites", "how many sites",
            "total sites", "sites suivis", "monitored sites", "nb sites",
            "combien de site"):
        return _overview_sites(lang, filters, country)

    if _has(q, "liste des pays", "list countries", "list of countries",
            "quels pays disponibles"):
        return _list_countries(lang, filters)

    # ── Country with no explicit metric → a compact summary. ──────────────────
    if country:
        return _country_summary(lang, filters, country)

    # ── Bare "sites" mention. ────────────────────────────────────────────────
    if _has(q, "site", "sites"):
        return _overview_sites(lang, filters, country)

    # ── Fallback. ────────────────────────────────────────────────────────────
    return _L(
        lang,
        "Je n'ai pas bien compris. ",
        "I didn't quite understand. ",
    ) + _help_text(lang)


# ──────────────────────────────────────────────────────────────────────────────
# Floating chat widget (bottom-right popup, available on every page)
# ──────────────────────────────────────────────────────────────────────────────

_STATE_KEY = "assistant_msgs"
_OPEN_KEY = "assistant_open"


def _greeting(lang: str) -> dict:
    return {
        "role": "assistant",
        "content": _L(
            lang,
            "Bonjour 👋 Je suis l'assistant du portefeuille. Posez-moi une question "
            "ou tapez « aide ».",
            "Hi 👋 I'm the portfolio assistant. Ask me a question or type \"help\".",
        ),
        "time": datetime.now().strftime("%H:%M"),
    }


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bot_logo_uri() -> str:
    """Inline data URI for the assistant logo. Prefers a raster ``assistant_bot.png``
    (drop one into /assets to override) and falls back to the vector
    ``assistant_bot.svg``. Empty string if neither exists."""
    for name in ("assistant_bot.png", "assistant_bot.svg"):
        uri = _logo_data_uri(name)
        if uri:
            return uri
    return ""


def _avatar_html(size: int) -> str:
    """The bot logo sized for an avatar circle, or the 🤖 emoji as a fallback."""
    logo = _bot_logo_uri()
    if logo:
        return (f"<img src='{logo}' alt='' "
                f"style='width:{size}px;height:{size}px;object-fit:contain;'/>")
    return "🤖"


def _md_to_html(s: str) -> str:
    """Tiny Markdown → HTML for assistant bubbles (bold, line breaks, list items).
    The text we generate is fully controlled, so this small subset is enough."""
    s = _escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    lines = []
    for ln in s.split("\n"):
        stripped = ln.strip()
        if stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
            lines.append("• " + re.sub(r"^(- |\d+\.\s)", "", stripped))
        else:
            lines.append(ln)
    return "<br>".join(lines)


def _history_html(lang: str) -> str:
    msgs = st.session_state.get(_STATE_KEY, [])
    primary = PALETTE["primary"]
    bot_bg = PALETTE["bg_deep"]
    txt = PALETTE["card_text"]
    muted = PALETTE["muted"]
    rows = []
    for m in msgs:
        ts = m.get("time", "")
        time_html = (
            f"<div style='font-size:10px;color:{muted};margin-top:2px;'>{ts}</div>"
            if ts else ""
        )
        if m["role"] == "user":
            rows.append(
                f"<div style='display:flex;justify-content:flex-end;align-items:flex-end;"
                f"gap:6px;margin:8px 0;'>"
                f"<div style='display:flex;flex-direction:column;align-items:flex-end;max-width:78%;'>"
                f"<div style='background:{primary};color:#fff;padding:8px 12px;"
                f"border-radius:14px 14px 3px 14px;font-size:13px;line-height:1.4;"
                f"word-wrap:break-word;'>{_escape(m['content'])}</div>{time_html}</div>"
                f"<div style='flex:0 0 26px;width:26px;height:26px;border-radius:50%;"
                f"background:{primary};color:#fff;display:flex;align-items:center;"
                f"justify-content:center;font-size:13px;'>🙂</div>"
                f"</div>"
            )
        else:
            rows.append(
                f"<div style='display:flex;justify-content:flex-start;align-items:flex-end;"
                f"gap:6px;margin:8px 0;'>"
                f"<div style='flex:0 0 26px;width:26px;height:26px;border-radius:50%;"
                f"background:{primary};color:#fff;display:flex;align-items:center;"
                f"justify-content:center;font-size:14px;overflow:hidden;'>{_avatar_html(22)}</div>"
                f"<div style='display:flex;flex-direction:column;align-items:flex-start;max-width:82%;'>"
                f"<div style='background:{bot_bg};color:{txt};padding:8px 12px;"
                f"border-radius:14px 14px 14px 3px;font-size:13px;line-height:1.45;"
                f"word-wrap:break-word;'>{_md_to_html(m['content'])}</div>{time_html}</div>"
                f"</div>"
            )
    inner = "".join(rows)
    return (
        "<div style='max-height:300px;min-height:120px;overflow-y:auto;"
        "padding:10px 14px;display:flex;flex-direction:column;'>"
        f"{inner}</div>"
    )


def _header_html(lang: str) -> str:
    primary = PALETTE["primary"]
    primary_dk = PALETTE["primary_dk"]
    online = _L(lang, "En ligne", "Online")
    return (
        f"<div style='background:linear-gradient(135deg,{primary},{primary_dk});"
        f"color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px;'>"
        f"<div style='flex:0 0 38px;width:38px;height:38px;border-radius:50%;"
        f"background:rgba(255,255,255,.18);display:flex;align-items:center;"
        f"justify-content:center;font-size:20px;overflow:hidden;'>{_avatar_html(32)}</div>"
        f"<div style='display:flex;flex-direction:column;line-height:1.15;'>"
        f"<span style='font-weight:700;font-size:15px;'>Assistant RASME</span>"
        f"<span style='font-size:11px;opacity:.9;'>"
        f"<span style='color:#7CFFB2;'>●</span> {online}</span>"
        f"</div></div>"
    )


def _inject_css() -> None:
    primary = PALETTE["primary"]
    primary_dk = PALETTE["primary_dk"]
    border = PALETTE["border"]
    logo = _bot_logo_uri()
    if logo:
        launcher_face = (
            f"background: url('{logo}') center 58%/64% no-repeat,"
            f" linear-gradient(135deg, {primary}, {primary_dk}) !important;"
            "color: transparent !important; font-size: 0 !important;"
        )
    else:
        launcher_face = (
            f"background: linear-gradient(135deg, {primary}, {primary_dk}) !important;"
            "color: #fff !important; font-size: 26px !important;"
        )
    css = """
    <style>
      /* Floating launcher bubble (bottom-right). */
      .st-key-asst_launcher {
        position: fixed; bottom: 24px; right: 24px;
        width: 62px; z-index: 100000;
      }
      .st-key-asst_launcher button {
        width: 62px; height: 62px; border-radius: 50%;
        __LAUNCHERFACE__
        border: none !important;
        box-shadow: 0 8px 22px rgba(0,0,0,.28) !important; padding: 0 !important;
        transition: transform .15s ease;
      }
      .st-key-asst_launcher button:hover { transform: scale(1.06); }

      /* Floating panel. */
      .st-key-asst_panel {
        position: fixed; bottom: 24px; right: 24px;
        width: 372px; max-width: calc(100vw - 32px); max-height: 86vh;
        background: #fff; border: 1px solid __BORDER__; border-radius: 16px;
        box-shadow: 0 16px 48px rgba(0,0,0,.30); overflow: hidden;
        z-index: 100000;
      }
      .st-key-asst_panel [data-testid="stVerticalBlock"] { gap: 0 !important; padding: 0 !important; }
      .st-key-asst_panel [data-testid="stElementContainer"] { margin: 0 !important; }
      .st-key-asst_panel > div { padding: 0 !important; }

      /* Minimize button, floated over the header. */
      .st-key-asst_close {
        position: absolute; top: 12px; right: 12px; width: auto !important;
        z-index: 2;
      }
      .st-key-asst_close button {
        background: rgba(255,255,255,.18) !important; color: #fff !important;
        border: none !important; border-radius: 50% !important;
        width: 30px; height: 30px; padding: 0 !important; font-size: 18px !important;
        line-height: 1 !important;
      }
      .st-key-asst_close button:hover { background: rgba(255,255,255,.32) !important; }

      /* Quick-reply chips row. */
      .st-key-asst_panel [data-testid="stHorizontalBlock"]:has(.st-key-asst_chip_0) {
        padding: 4px 12px 0; gap: 6px;
      }
      .st-key-asst_panel [class*="st-key-asst_chip_"] button {
        background: #fff !important; color: __PRIMARY__ !important;
        border: 1px solid __BORDER__ !important; border-radius: 16px !important;
        font-size: 12px !important; padding: 4px 8px !important;
        white-space: nowrap; min-height: 0 !important;
      }
      .st-key-asst_panel [class*="st-key-asst_chip_"] button:hover {
        border-color: __PRIMARY__ !important; background: #F4F8F2 !important;
      }

      /* Input row. */
      .st-key-asst_panel [data-testid="stForm"] {
        border: none !important; padding: 8px 12px 12px !important;
      }
      .st-key-asst_panel [data-testid="stForm"] [data-baseweb="input"],
      .st-key-asst_panel [data-testid="stForm"] input {
        border-radius: 22px !important;
      }
      .st-key-asst_panel [data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, __PRIMARY__, __PRIMARYDK__) !important;
        color: #fff !important; border: none !important; border-radius: 12px !important;
        font-size: 18px !important; min-height: 0 !important; height: 40px;
      }
    </style>
    """
    css = (css.replace("__LAUNCHERFACE__", launcher_face)
              .replace("__PRIMARY__", primary)
              .replace("__PRIMARYDK__", primary_dk)
              .replace("__BORDER__", border))
    st.markdown(css, unsafe_allow_html=True)


def _process(question: str, lang: str, filters: dict) -> None:
    msgs = st.session_state.setdefault(_STATE_KEY, [])
    now = datetime.now().strftime("%H:%M")
    msgs.append({"role": "user", "content": question, "time": now})
    try:
        answer = respond(question, lang, filters)
    except Exception:  # never let a query error break the page
        answer = _L(
            lang,
            "Désolé, une erreur est survenue en récupérant les données.",
            "Sorry, something went wrong while fetching the data.",
        )
    msgs.append({"role": "assistant", "content": answer,
                 "time": datetime.now().strftime("%H:%M")})
    # Trim history so the transcript can't grow without bound.
    if len(msgs) > MAX_HISTORY:
        del msgs[: len(msgs) - MAX_HISTORY]


def chat_widget(lang: str, filters: dict[str, Any]) -> None:
    """Render the assistant as a floating popup pinned to the bottom-right of
    the viewport — a launcher bubble when closed, a chat panel when open.
    Safe to call on every page; state persists in st.session_state."""
    if _STATE_KEY not in st.session_state:
        st.session_state[_STATE_KEY] = [_greeting(lang)]

    _inject_css()

    # Closed → show only the launcher bubble.
    if not st.session_state.get(_OPEN_KEY, False):
        if st.button("🤖", key="asst_launcher",
                     help=_L(lang, "Ouvrir l'assistant", "Open the assistant")):
            st.session_state[_OPEN_KEY] = True
            st.rerun()
        return

    quick = [
        (_L(lang, "Sites", "Sites"),
         _L(lang, "Combien de sites sont suivis ?", "How many sites are monitored?")),
        (_L(lang, "Top pays", "Top countries"),
         _L(lang, "Top pays par nombre de sites", "Top countries by number of sites")),
        (_L(lang, "Secteurs", "Sectors"),
         _L(lang, "Répartition sectorielle", "Sector breakdown")),
    ]

    new_q: Optional[str] = None
    panel = st.container(key="asst_panel")
    with panel:
        # Header + minimize button (the close button is floated over the header).
        st.markdown(_header_html(lang), unsafe_allow_html=True)
        if st.button("—", key="asst_close",
                     help=_L(lang, "Réduire", "Minimize")):
            st.session_state[_OPEN_KEY] = False
            st.rerun()

        # Conversation transcript.
        st.markdown(_history_html(lang), unsafe_allow_html=True)

        # Quick-reply chips.
        cols = st.columns(len(quick))
        for i, (label, qtext) in enumerate(quick):
            if cols[i].button(label, key=f"asst_chip_{i}", use_container_width=True):
                new_q = qtext

        # Free-text input (clears after each send).
        with st.form("asst_form", clear_on_submit=True):
            row = st.columns([5, 1])
            text = row[0].text_input(
                _L(lang, "Votre question", "Your question"),
                key="asst_input",
                label_visibility="collapsed",
                placeholder=_L(lang, "Écrivez votre message…", "Type your message here…"),
            )
            submitted = row[1].form_submit_button("➤", use_container_width=True)

    if submitted and text and text.strip():
        new_q = text.strip()

    if new_q:
        _process(new_q, lang, filters)
        st.rerun()
