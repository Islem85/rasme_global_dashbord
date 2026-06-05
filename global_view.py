"""Page 1 — Vue Globale / Global View — AfDB scorecard inspired by the World Bank model.

Structure:
• Hero strip (eyebrow + serif headline + supporting paragraph + last-refresh chip)
• Pillar 1 — Coverage         : 5 indicator cards
• Pillar 2 — Delivery health  : 5 indicator cards
• Pillar 3 — Geographic       : ArcGIS embed
• Pillar 4 — Breakdowns       : top countries (stacked) + sectoral donut
• Pillar 5 — Trend            : monthly submissions + cumulative completions
• Insights cards (key takeaways)
"""

from __future__ import annotations

import logging
from datetime import datetime

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import PALETTE, country_label, sector_label, status_color_map, status_label
from mapper import leaflet_map
from db import (
    bad_overview,
    coverage_by_country,
    coverage_overview,
    delivery_kpis,
    kpi_by_country,
    kpi_overview,
    map_points,
    recent_submissions_count,
    sector_breakdown,
    status_distribution,
    country_status_breakdown,
    temporal_trend,
)
from i18n import t
from ui import (
    dark_plotly,
    fmt_int,
    fmt_pct,
    hero,
    insight,
    kpi_card,
    kpi_row,
    pdf_export_button,
    pillar_header,
)

# Maximum dots to render on the Leaflet map.
MAP_POINT_LIMIT = 30000

lang = st.session_state.get("lang", "FR")
filters = st.session_state.get("filters", {})

# ── Top toolbar: PDF export ─────────────────────────────────────────────────
pdf_export_button(lang)

# Pull all data once
try:
    kpi = kpi_overview(filters)
except Exception as _e:
    logging.warning("kpi_overview error: %s", _e)
    st.error(f"⚠ Erreur KPI global : {type(_e).__name__} — {_e}" if lang == "FR"
             else f"⚠ Global KPI error: {type(_e).__name__} — {_e}")
    kpi = {}

try:
    dlv = delivery_kpis(filters)
except Exception as _e:
    logging.warning("delivery_kpis error: %s", _e)
    dlv = {}

# ── HERO ────────────────────────────────────────────────────────────────────
hero(
    eyebrow=t("hero_eyebrow", lang),
    headline=t("hero_headline", lang),
    sub=t("hero_sub", lang, sites=fmt_int(kpi.get("sites"))),
    last_refresh=datetime.now().strftime("%Y-%m-%d %H:%M"),
)

last_col = kpi.get("last_collection")
last_col_str = last_col.strftime("%Y-%m-%d") if hasattr(last_col, "strftime") else "—"

try:
    _bad_o = bad_overview()
    _cov = coverage_overview(region_slugs=filters.get("countries_in"))
    if not isinstance(_cov, dict):
        raise ValueError(f"coverage_overview returned {type(_cov).__name__}, expected dict")
    _cov_ok = True
except Exception as _e:
    logging.warning("coverage_overview error: %s", _e)
    _bad_o, _cov, _cov_ok = {}, {}, False

# ── PILLAR 1 · COVERAGE ─────────────────────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_coverage_eyebrow", lang),
    title=t("pillar_coverage_title", lang),
    description=t("pillar_coverage_desc", lang),
)

kpi_row([
    kpi_card(
        t("sites_total", lang), fmt_int(kpi.get("sites")),
        icon="sites",
        explainer=t("expl_sites", lang),
    ),
    kpi_card(
        t("countries_covered", lang), fmt_int(kpi.get("countries")),
        icon="globe",
        explainer=t("expl_countries", lang),
    ),
    kpi_card(
        t("active_projects", lang),
        fmt_int(_cov.get("n_internal") if _cov_ok else kpi.get("active_projects")),
        icon="project",
        explainer=(
            "Nombre total de projets actifs dans les pays couverts par RASME."
            if lang == "FR" else
            "Total number of active projects in the countries covered by RASME."
        ),
    ),
    kpi_card(
        t("last_collection", lang),
        last_col_str,
        icon="duration",
        explainer=(
            f"{fmt_int(recent_submissions_count(filters, days=30))} "
            + ("nouvelles soumissions en 30 j" if lang == "FR" else "new submissions in 30 d")
        ),
    ),
], cols=4)

# ── PILLAR 2 · DELIVERY HEALTH ──────────────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_delivery_eyebrow", lang),
    title=t("pillar_delivery_title", lang),
    description=t("pillar_delivery_desc", lang),
)

at_risk_tone = "danger" if (kpi.get("at_risk_rate") or 0) > 3 else "warning"
overdue = int(dlv.get("overdue_activities") or 0)
avg_dur = dlv.get("avg_duration_days")
overdue_tone = "danger" if overdue > 100 else "warning" if overdue > 0 else "success"

kpi_row([
    kpi_card(
        t("completion_rate", lang), fmt_pct(kpi.get("completion_rate")),
        tone="success", icon="completion",
        explainer=t("expl_completion", lang),
    ),
    kpi_card(
        t("at_risk_rate", lang), fmt_pct(kpi.get("at_risk_rate")),
        tone=at_risk_tone, icon="risk",
        explainer=t("expl_at_risk", lang),
    ),
    kpi_card(
        t("overdue_activities", lang), fmt_int(overdue),
        tone=overdue_tone, icon="overdue",
        explainer=t("expl_overdue", lang),
    ),
    kpi_card(
        t("avg_duration", lang),
        f"{avg_dur:.1f}" if avg_dur is not None else "—",
        icon="duration",
        explainer=t("expl_avg_duration", lang),
    ),
], cols=4)

# ── PILLAR 3 · COUVERTURE PROJETS BAD ───────────────────────────────────────
if _cov_ok:
    _snap = _bad_o.get("last_refresh")
    _snap_s = _snap.strftime("%Y-%m-%d") if hasattr(_snap, "strftime") else (str(_snap) if _snap else "—")
    _rate = _cov.get("mapping_rate") or 0
    if not isinstance(_rate, (int, float)):
        _rate = 0
    _rate_tn = "success" if _rate >= 80 else "warning" if _rate >= 50 else "danger"

    pillar_header(
        eyebrow=("Couverture Projets BAD" if lang == "FR" else "Projets BAD coverage"),
        title=(
            "Projets actifs vs projets cartographiés"
            if lang == "FR" else
            "Active projects vs mapped projects"
        ),
        description=(
            f"Source : MapAfrica (snapshot du {_snap_s})."
            if lang == "FR" else
            f"Source: MapAfrica (snapshot dated {_snap_s})."
        ),
    )

    # Row 1 — Vue RASME
    _n_internal = int(_cov.get("n_internal") or 0)
    _n_internal_only = int(_cov.get("n_internal_only") or 0)
    _n_with_bad = _n_internal - _n_internal_only
    _corr_rate = (100.0 * _n_with_bad / _n_internal) if _n_internal else 0.0
    _corr_tn = "success" if _corr_rate >= 80 else "warning" if _corr_rate >= 50 else "danger"
    
    kpi_row([
        kpi_card(
            ("Projets cartographiés" if lang == "FR" else "Mapped projects"),
            fmt_int(_n_internal),
            tone="success", icon="project",
            explainer=("Total des projets actifs suivis par RASME." if lang == "FR" else "Total active projects monitored by RASME."),
        ),
        kpi_card(
            ("Avec correspondance BAD" if lang == "FR" else "With BAD match"),
            fmt_int(_n_with_bad),
            tone="success", icon="check",
            explainer=("Projets cartographiés ayant une correspondance dans la base BAD." if lang == "FR" else "Mapped projects matched to a record in the BAD database."),
        ),
        kpi_card(
            ("Sans correspondance BAD" if lang == "FR" else "Without BAD match"),
            fmt_int(_n_internal_only),
            tone="warning" if _n_internal_only else "success",
            icon="risk",
            explainer=("Projets cartographiés sans correspondance dans la base BAD." if lang == "FR" else "Mapped projects with no match in the BAD database."),
        ),
        kpi_card(
            ("Taux de correspondance" if lang == "FR" else "Match rate"),
            fmt_pct(_corr_rate),
            tone=_corr_tn, icon="duration",
            explainer=("Avec correspondance BAD / Projets cartographiés." if lang == "FR" else "With BAD match / Mapped projects."),
        ),
    ], cols=4)

    # Row 2 — Couverture du portefeuille BAD ACTIF
    kpi_row([
        kpi_card(
            ("Projets actifs (BAD)" if lang == "FR" else "Active projects (BAD)"),
            fmt_int(_cov.get("n_portfolio")),
            icon="globe",
            explainer=("Projets BAD aux statuts Approved + Ongoing." if lang == "FR" else "BAD projects with status Approved + Ongoing."),
        ),
        kpi_card(
            ("Actifs cartographiés" if lang == "FR" else "Mapped active"),
            fmt_int(_cov.get("n_mapped")),
            tone="success", icon="completion",
            explainer=("Projets actifs avec au moins un projet interne correspondant." if lang == "FR" else "Active projects with at least one matching internal project."),
        ),
        kpi_card(
            ("Actifs non cartographiés" if lang == "FR" else "Active unmapped"),
            fmt_int(_cov.get("n_unmapped")),
            tone="warning" if _cov.get("n_unmapped") else "success",
            icon="risk",
            explainer=("Projets actifs sans monitoring interne." if lang == "FR" else "Active projects without internal monitoring."),
        ),
        kpi_card(
            ("Taux de couverture" if lang == "FR" else "Coverage rate"),
            fmt_pct(_rate),
            tone=_rate_tn, icon="duration",
            explainer=("Actifs cartographiés / Projets actifs (BAD)." if lang == "FR" else "Mapped active / Active projects (BAD)."),
        ),
    ], cols=4)

    # Row 3 — Visibilité Completion + Cancelled
    kpi_row([
        kpi_card(
            ("Clôturés (BAD)" if lang == "FR" else "Completion (BAD)"),
            fmt_int(_bad_o.get("completion") or 0),
            icon="check",
            explainer=("Projets BAD au statut Completion." if lang == "FR" else "BAD projects with status Completion."),
        ),
        kpi_card(
            ("Clôturés cartographiés" if lang == "FR" else "Completion mapped"),
            fmt_int(_cov.get("n_completion_mapped")),
            icon="completion",
            explainer=("Projets clôturés avec un suivi interne historique." if lang == "FR" else "Completion projects with historical internal data."),
        ),
        kpi_card(
            ("Annulés cartographiés" if lang == "FR" else "Cancelled mapped"),
            fmt_int(_cov.get("n_cancelled_mapped")),
            icon="risk",
            explainer=("Projets annulés avec un suivi interne (rare)." if lang == "FR" else "Cancelled projects with internal data (rare)."),
        ),
    ], cols=3)
else:
    st.warning(
        ("⚠ Section Projets BAD indisponible. Vérifiez que `lancer_scrape.bat` "
         "a bien chargé la table projet_BAD."
         if lang == "FR" else
         "⚠ Projets BAD section unavailable. Make sure `lancer_scrape.bat` "
         "has loaded the projet_BAD table.")
    )

# ── PILLAR 4 · GEOGRAPHIC DISTRIBUTION ──────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_geo_eyebrow", lang),
    title=t("pillar_geo_title", lang),
    description="",
)

pts = map_points(filters, limit=MAP_POINT_LIMIT)
if pts.empty:
    st.info(t("no_geo_data", lang))
else:
    leaflet_map(
        pts, lang,
        height=620,
        center=(4.0, 20.0),
        zoom=3,
        point_cap=MAP_POINT_LIMIT,
        key="global_leaflet",
    )
    _total_sites = int(kpi.get("sites") or 0)
    _no_gps = max(_total_sites - len(pts), 0)
    _gps_note_fr = f" · {_no_gps:,} site(s) sans coordonnées GPS (non affichés)" if _no_gps else ""
    _gps_note_en = f" · {_no_gps:,} site(s) without GPS coordinates (not shown)" if _no_gps else ""
    st.caption(
        (f"Carte Leaflet · fond Esri World Light Gray Canvas — {len(pts):,} sites "
         f"géolocalisés affichés{_gps_note_fr} (regroupés en clusters ; zoomer pour "
         "les détacher, cliquer un point pour les détails). Couleurs = statut (voir légende)."
         if lang == "FR" else
         f"Leaflet map · Esri World Light Gray Canvas basemap — {len(pts):,} geolocated "
         f"sites shown{_gps_note_en} (clustered; zoom in to split them, click a marker "
         "for details). Colours = status (see legend).")
    )

# ── PILLAR 5 · BREAKDOWNS ───────────────────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_breakdown_eyebrow", lang),
    title=t("pillar_breakdown_title", lang),
    description=t("pillar_breakdown_desc", lang),
)

col_a, col_b = st.columns(2, gap="medium")

with col_a:
    cs = country_status_breakdown(filters, top_n=10)
    cs = cs.dropna(subset=["country", "status"]).copy()
    if not cs.empty:
        cs["country_label"] = cs["country"].map(lambda c: country_label(c, lang))
        cs["status_label"] = cs["status"].map(lambda s: status_label(s, lang))
        order = cs.groupby("country_label")["sites"].sum().sort_values().index.tolist()
        fig = px.bar(
            cs, y="country_label", x="sites", color="status_label",
            orientation="h",
            color_discrete_map=status_color_map(lang),
            title=t("chart_top_countries", lang),
            labels={"country_label": "", "sites": t("sites_total", lang), "status_label": t("status", lang)},
            category_orders={"country_label": order},
        )
        fig.update_layout(
            margin=dict(l=0, r=10, t=44, b=80), height=460,
            legend=dict(
                orientation="h", yanchor="top", y=-0.15,
                xanchor="left", x=0, font=dict(size=10),
                title_text=t("status", lang),
            ),
            bargap=0.25,
        )
        dark_plotly(fig, title_size=16)
        st.plotly_chart(fig, width="stretch")

with col_b:
    sec = sector_breakdown(filters)
    sec = sec.dropna(subset=["sector"]).copy()
    sec = sec[sec["sector"].astype(str).str.strip() != ""]
    if not sec.empty:
        sec["sector"] = sec["sector"].map(lambda s: sector_label(s, lang))
        fig = px.pie(
            sec, names="sector", values="sites", hole=0.6,
            title=t("chart_sector_split", lang),
            color_discrete_sequence=[
                PALETTE["primary"], "#7CFFB0", "#FFD66B", "#7A4DBA",
                "#56B6FF", "#FF6B6B", "#94A3B8", "#FFA94D",
                "#FF8FA3", "#A8E865", "#9D7CFF", "#5BD0C9",
            ],
        )
        fig.update_traces(
            textposition="inside", textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value:,} sites · %{percent}",
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=44, b=0), height=460,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=10)),
        )
        dark_plotly(fig, title_size=16)
        st.plotly_chart(fig, width="stretch")

# ── PILLAR 6 · TREND ────────────────────────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_trend_eyebrow", lang),
    title=t("pillar_trend_title", lang),
    description=t("pillar_trend_desc", lang),
)

trend = temporal_trend(filters)

if trend.empty:
    st.info(t("no_data", lang))
else:
    trend = trend.dropna(subset=["month"]).copy()
    trend["submissions"] = trend["submissions"].fillna(0).astype(int)
    trend["cumulative_completed"] = trend["cumulative_completed"].fillna(0).astype(int)
    fig = go.Figure()
    fig.add_bar(
        x=trend["month"], y=trend["submissions"],
        name=t("submissions", lang),
        marker_color=PALETTE["primary"], opacity=0.55,
        hovertemplate="%{x|%b %Y}<br>%{y:,d}<extra></extra>",
    )
    fig.add_scatter(
        x=trend["month"], y=trend["cumulative_completed"],
        name=t("cumulative_completed", lang), mode="lines+markers",
        line=dict(color=PALETTE["success"], width=2.5), yaxis="y2",
        hovertemplate="%{x|%b %Y}<br>%{y:,d}<extra></extra>",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=60), height=400,
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(title=t("submissions", lang)),
        yaxis2=dict(title=t("cumulative_completed", lang), overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0),
    )
    dark_plotly(fig)
    st.plotly_chart(fig, width="stretch")

# ── Tableau pays-par-pays (couverture Projets BAD) ──────────────────────────
try:
    with st.spinner(("Compilation du tableau pays-par-pays…" if lang == "FR" else "Compiling country-by-country table…")):
        _by_country = coverage_by_country()
        _region_slugs = filters.get("countries_in")
        
    if _region_slugs and not _by_country.empty:
        _by_country = _by_country[_by_country["country_slug"].isin(_region_slugs)]
        
    if not _by_country.empty:
        pillar_header(
            eyebrow=("Couverture Projets BAD · détail" if lang == "FR" else "Projets BAD coverage · detail"),
            title=("Couverture par pays" if lang == "FR" else "Coverage by country"),
            description=("Détail pays-par-pays : nombre de soumissions kobo, portefeuille BAD, projets cartographiés et taux." if lang == "FR" else "Per-country detail: kobo submissions, BAD portfolio, mapped projects and rate."),
        )
        _disp = _by_country.copy()
        _disp["country"] = _disp["country_slug"].map(lambda s: country_label(s, lang))
        _disp["n_total_mapped"] = (
            _disp["n_mapped"].fillna(0)
            + _disp["n_completion_mapped"].fillna(0)
            + _disp["n_cancelled_mapped"].fillna(0)
        ).astype(int)
        
        _disp = _disp[[
            "country", "n_submissions", "n_total_mapped",
            "n_mapped", "n_portfolio", "mapping_rate",
            "n_completion_mapped", "n_completion",
            "n_cancelled_mapped", "n_cancelled",
        ]]
        _disp = _disp.rename(columns={
            "country": ("Pays" if lang == "FR" else "Country"),
            "n_submissions": ("Soumissions kobo" if lang == "FR" else "Kobo submissions"),
            "n_total_mapped": ("Projets cartographiés" if lang == "FR" else "Mapped projects"),
            "n_mapped": ("Actifs cartographiés" if lang == "FR" else "Active mapped"),
            "n_portfolio": ("Actifs (BAD)" if lang == "FR" else "Active (BAD)"),
            "mapping_rate": ("% actifs cartographiés" if lang == "FR" else "% Active mapped"),
            "n_completion_mapped": ("Clôturés cartographiés" if lang == "FR" else "Completion mapped"),
            "n_completion": ("Clôturés (BAD)" if lang == "FR" else "Completion (BAD)"),
            "n_cancelled_mapped": ("Annulés cartographiés" if lang == "FR" else "Cancelled mapped"),
            "n_cancelled": ("Annulés (BAD)" if lang == "FR" else "Cancelled (BAD)"),
        })

        _rate_col = "% actifs cartographiés" if lang == "FR" else "% Active mapped"

        def _rate_color(v):
            try:
                x = float(v)
                if x >= 80:
                    bg, fg = "#D6F5E3", "#005C33"
                elif x >= 50:
                    bg, fg = "#FFF4D6", "#8A5A00"
                elif x > 0:
                    bg, fg = "#FDE0DC", "#8B1A0E"
                else:
                    bg, fg = "#EEEEEE", "#5C6770"
                return f"background-color:{bg};color:{fg};font-weight:600;"
            except (TypeError, ValueError):
                return ""

        _styler = (
            _disp.style
            .format({_rate_col: "{:.2f}%"})
            .map(_rate_color, subset=[_rate_col])
        )
        st.dataframe(
            _styler,
            width="stretch",
            height=min(640, 80 + 28 * min(len(_disp), 20)),
            hide_index=True,
        )
        st.download_button(
            ("Exporter CSV" if lang == "FR" else "Export CSV"),
            data=_disp.to_csv(index=False).encode("utf-8-sig"),
            file_name="couverture_projets_BAD_par_pays.csv",
            mime="text/csv",
            key="dl_coverage_by_country",
        )
except Exception as _e:
    st.warning(
        (f"⚠ Tableau pays-par-pays indisponible : {type(_e).__name__}."
         if lang == "FR" else
         f"⚠ Country-by-country table unavailable: {type(_e).__name__}.")
    )

# ── INSIGHTS ────────────────────────────────────────────────────────────────
pillar_header(
    eyebrow=t("section_insights", lang),
    title=t("section_insights", lang) if lang == "EN" else "Points clés à retenir",
    description=("Les 4 lectures à retenir de la période sélectionnée." if lang == "FR" else "Four take-aways from the selected period."),
)

sec_top = sector_breakdown(filters)
status_d = status_distribution(filters)
by_count = kpi_by_country(filters)
recent_n = recent_submissions_count(filters, days=30)

if not sec_top.empty:
    top = sec_top.iloc[0]
    insight(
        t("insight_top_sector", lang,
          sector=sector_label(top["sector"], lang),
          pct=fmt_pct(100 * top["sites"] / max(int(kpi.get("sites") or 1), 1)).replace(" %", ""),
          rate=fmt_pct(top["completion_rate"]).replace(" %", "")),
        tone="success",
    )

if not status_d.empty:
    risky = status_d[status_d["status"].isin(["Stalled", "Stalled/ suspended", "Abandoned", "Suspended", "Canceled"])]["sites"].sum()
    total = int(status_d["sites"].sum() or 0)
    if risky:
        insight(
            t("insight_at_risk", lang, n=fmt_int(risky), pct=f"{(100 * risky / max(total, 1)):.1f}"),
            tone="danger",
        )

if not by_count.empty:
    lead = by_count.iloc[0]
    insight(
        t("insight_top_country", lang,
          country=country_label(lead["country"], lang),
          n=fmt_int(lead["sites"]),
          pct=fmt_pct(lead["completion_rate"]).replace(" %", "")),
        tone="",
    )

if recent_n:
    insight(t("insight_recent", lang, n=fmt_int(recent_n)), tone="warning")
