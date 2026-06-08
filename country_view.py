"""Page 2 — Vue par Pays / Country View — operational view for project coordinators."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from config import PALETTE, country_label, sector_label, status_color_map, status_label
from mapper import leaflet_map
from db import (
    bad_only_active,
    bad_overview,
    country_beneficiaries,
    country_delay_distribution,
    country_funnel,
    country_issues,
    country_kpis_with_delta,
    country_output_breakdown,
    country_outputs,
    country_pipeline,
    country_projects,
    country_region_status,
    country_timeline,
    coverage_overview,
    coverage_table,
    filter_options,
    kobo_thumb_data_uri,
    last_collection_date,
    map_points,
)
import sap
from datetime import datetime

from i18n import t
from ui import (
    dark_plotly,
    fmt_delta,
    fmt_int,
    fmt_pct,
    hero,
    kpi_card,
    kpi_row,
    pdf_export_button,
    pillar_header,
    section,
)

lang = st.session_state.get("lang", "FR")
filters = st.session_state.get("filters", {})

# ── Top toolbar: PDF export ─────────────────────────────────────────────────
pdf_export_button(lang)

# ── HERO ────────────────────────────────────────────────────────────────────
hero(
    eyebrow=t("hero_country_eyebrow", lang),
    headline=t("hero_country_headline", lang),
    sub=t("hero_country_sub", lang),
    last_refresh=datetime.now().strftime("%Y-%m-%d %H:%M"),
)

# ── Country picker (top of page) ─────────────────────────────────────────────
opts = filter_options()
all_countries = opts.get("country", [])
sorted_countries = sorted(all_countries, key=lambda c: country_label(c, lang).lower())
country_options_labels = {c: country_label(c, lang) for c in sorted_countries}

c_pick, c_proj = st.columns([2, 4], gap="small")

with c_pick:
    country = st.selectbox(
        t("select_country", lang),
        options=sorted_countries,
        index=0 if sorted_countries else None,
        format_func=lambda c: country_options_labels.get(c, c),
        key="country_pick",
    )

if not country:
    st.info(t("no_data", lang))
    st.stop()

with c_proj:
    projects = country_projects(country, filters)

    # Group project titles that share the same SAP code into a single entry.
    # Titles without a code, or whose code is unique within the country,
    # remain standalone (existing behaviour).
    sap_to_titles: dict[str, list[str]] = {}
    standalone: list[str] = []
    for p in projects:
        c = sap.code_for(p)
        if c:
            sap_to_titles.setdefault(c, []).append(p)
        else:
            standalone.append(p)

    group_titles: dict[str, list[str]] = {}   # sentinel value -> list of titles
    project_options: list[str] = []
    for c, titles in sap_to_titles.items():
        if len(titles) > 1:
            sentinel = f"__SAP__{c}"
            group_titles[sentinel] = titles
            project_options.append(sentinel)
        else:
            project_options.append(titles[0])
    project_options.extend(standalone)

    def _sort_key(v: str) -> tuple[int, str]:
        if v.startswith("__SAP__"):
            return (0, v[len("__SAP__"):])
        c = sap.code_for(v)
        return (0, c) if c else (1, v.lower())
    project_options.sort(key=_sort_key)

    def _fmt_project(p: str) -> str:
        if p == "__ALL__":
            return t("all", lang)
        if p.startswith("__SAP__"):
            code = p[len("__SAP__"):]
            # Prefer the canonical title from the SAP table; fall back to the
            # shortest variant we actually found in the operational DB.
            name = sap.canonical_title_for(code) or min(group_titles[p], key=len)
            short = name if len(name) <= 80 else name[:79] + "…"
            return f"{code}   &middot;   {short}"
        # Prefix the project title with its SAP code if we have one.
        return sap.label_with_code(p, max_len=80)

    project = st.selectbox(
        t("select_project", lang),
        options=["__ALL__"] + project_options,
        format_func=_fmt_project,
        key="project_pick",
    )

# Build a country-scoped filter dict that includes the optional project filter.
# Every country_* query and the map below receives this so the entire page
# narrows to the picked project when one is chosen. Built before the chips so
# the "last collection date" pill can reuse the same project-narrowed scope.
country_filters: dict = dict(filters)
if project and project != "__ALL__":
    if project.startswith("__SAP__"):
        country_filters["projects_in"] = tuple(group_titles[project])
    else:
        country_filters["project"] = project

# Display a prominent SAP-code chip — alongside the project's most recent
# collection date — directly below the dropdown when a project is selected.
if project and project != "__ALL__":
    sap_code = project[len("__SAP__"):] if project.startswith("__SAP__") else sap.code_for(project)

    # Most recent collection date for the (project-narrowed) selection.
    last_dt = last_collection_date(country, country_filters)
    date_val = last_dt.strftime("%d %b %Y") if last_dt is not None else "—"
    date_lbl = "Dernière collecte" if lang == "FR" else "Last collection"
    date_chip = f"""
            <div style="display:inline-flex;align-items:center;gap:10px;
                        padding:8px 16px;border-radius:999px;
                        background:{PALETTE['bg_deep']};
                        border:1.5px solid {PALETTE['border']};">
              <span style="font-family:'DM Sans',system-ui,sans-serif;font-weight:600;
                           font-size:11px;letter-spacing:1.4px;text-transform:uppercase;
                           color:{PALETTE['muted']};">
                {date_lbl}
              </span>
              <span style="font-family:'DM Mono',ui-monospace,monospace;font-weight:700;
                           font-size:14px;color:{PALETTE['primary_dk']};">{date_val}</span>
            </div>
    """

    if sap_code:
        sap_chip = f"""
            <div style="display:inline-flex;align-items:center;gap:10px;
                        padding:8px 16px;border-radius:999px;
                        background:{PALETTE['primary']}15;
                        border:1.5px solid {PALETTE['primary']};">
              <span style="font-family:'DM Sans',system-ui,sans-serif;font-weight:600;
                           font-size:11px;letter-spacing:1.4px;text-transform:uppercase;
                           color:{PALETTE['muted']};">
                {('Code SAP' if lang == 'FR' else 'SAP code')}
              </span>
              <span style="font-family:'DM Mono',ui-monospace,monospace;font-weight:700;
                           font-size:14px;color:{PALETTE['primary_dk']};">{sap_code}</span>
            </div>
        """
        st.markdown(
            f"""
            <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;
                        margin:2px 0 8px 0;">
              {sap_chip}{date_chip}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.caption(
            ("Aucun code SAP référencé pour ce projet."
             if lang == "FR" else "No SAP code referenced for this project.")
        )
        st.markdown(
            f'<div style="margin:2px 0 8px 0;">{date_chip}</div>',
            unsafe_allow_html=True,
        )

    # When a grouped entry is picked, list the title variants that were
    # merged under this SAP code so the user can verify the grouping.
    if project.startswith("__SAP__"):
        variants = group_titles[project]
        if len(variants) > 1:
            with st.expander(
                (f"Variantes fusionnées sous {sap_code} ({len(variants)})"
                 if lang == "FR"
                 else f"Title variants merged under {sap_code} ({len(variants)})"),
                expanded=False,
            ):
                for v in sorted(variants):
                    st.markdown(f"- {v}")

# ── KPI row with deltas vs global average ─────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_compare_eyebrow", lang),
    title=t("pillar_compare_title", lang),
    description=t("pillar_compare_desc", lang),
)

kpi_df = country_kpis_with_delta(country, country_filters)
if kpi_df.empty:
    st.info(t("no_data", lang))
    st.stop()

row = kpi_df.iloc[0]
delta_completion, dir_c = fmt_delta(row.get("completion_rate"), row.get("g_completion_rate"))
delta_risk,       dir_r = fmt_delta(row.get("at_risk_rate"),    row.get("g_at_risk_rate"))
# inverse interpretation for "risk" — going down is good
dir_r_visual = "up" if dir_r == "down" else "down" if dir_r == "up" else ""

benef     = row.get("beneficiaries") or 0
g_benef   = row.get("g_beneficiaries") or 0
benef_pct = (100.0 * float(benef) / float(g_benef)) if g_benef else None

# Coverage data computed once and reused below — keeps "country_projects"
# KPI consistent with the BAD coverage section (math closes: projets actifs
# = total cartographiés + non cartographiés).
try:
    _bad_o = bad_overview()
    _cov   = coverage_overview(country)
    _cov_ok = True
except Exception:
    _bad_o, _cov, _cov_ok = {}, {}, False

# Count distinct projects in this country. Uses kobo distinct SAP codes
# (via either identifiant_pa short form or nom_projet→code_SAP) — aligned
# with the BAD coverage section. When the user has picked one specific
# project from the dropdown, the KPI resets to 0.
if project and project != "__ALL__":
    country_projects_count = 0
else:
    country_projects_count = (_cov.get("n_internal")
                              if _cov_ok else len(projects))

kpi_row([
    kpi_card(
        t("country_sites", lang),
        fmt_int(row.get("sites")),
        icon="sites",
        explainer=t("expl_country_sites", lang),
    ),
    kpi_card(
        t("country_projects", lang),
        fmt_int(country_projects_count),
        icon="project",
        explainer=("Nombre total de projets actifs dans ce pays."
                   if lang == "FR" else
                   "Total number of active projects in this country."),
    ),
    kpi_card(
        t("completion_rate", lang),
        fmt_pct(row.get("completion_rate")),
        tone="success",
        delta=f"{delta_completion} {t('vs_global_avg', lang)}" if delta_completion else None,
        delta_dir=dir_c,
        icon="completion",
        explainer=t("expl_completion", lang),
    ),
    kpi_card(
        t("in_progress", lang),
        fmt_int(row.get("in_progress")),
        icon="duration",
        explainer=t("expl_in_progress", lang),
    ),
    kpi_card(
        t("at_risk_rate", lang),
        fmt_pct(row.get("at_risk_rate")),
        tone="danger" if (row.get("at_risk_rate") or 0) > 3 else "warning",
        delta=f"{delta_risk} {t('vs_global_avg', lang)}" if delta_risk else None,
        delta_dir=dir_r_visual,
        icon="risk",
        explainer=t("expl_at_risk", lang),
    ),
    kpi_card(
        t("beneficiaries_direct", lang),
        fmt_int(benef),
        tone="success",
        delta=f"{benef_pct:.1f} % {t('of_total', lang)}" if benef_pct else None,
        icon="users",
        explainer=t("expl_benef", lang),
    ),
])

# ── Couverture Projets BAD (par pays) ───────────────────────────────────────
# Source du portefeuille : MapAfrica (table projet_BAD).
# _bad_o / _cov sont déjà calculés plus haut (utilisés par le KPI
# "country_projects") — on les réutilise pour garantir la cohérence.
_snap    = _bad_o.get("last_refresh") if _cov_ok else None
_snap_s  = _snap.strftime("%Y-%m-%d") if hasattr(_snap, "strftime") else (str(_snap) if _snap else "—")
_rate    = _cov["mapping_rate"] if _cov_ok else 0.0
_rate_tn = "success" if _rate >= 80 else "warning" if _rate >= 50 else "danger"

pillar_header(
    eyebrow=("Couverture Projets BAD" if lang == "FR" else "Projets BAD coverage"),
    title=(f"{country_label(country, lang)} &middot; couverture du portefeuille"
           if lang == "FR" else
           f"{country_label(country, lang)} &middot; portfolio coverage"),
    description=(
        f"Source : MapAfrica (snapshot du {_snap_s})."
        if lang == "FR" else
        f"Source: MapAfrica (snapshot dated {_snap_s})."
    ),
)

# Ligne 1 (vue RASME) : Projets cartographiés = Projets actifs (n_internal),
# ventilés selon qu'ils ont OU NON une correspondance dans la base BAD.
# La math ferme : cartographiés = avec correspondance + sans correspondance.
_n_internal_c      = _cov.get("n_internal") or 0
_n_internal_only_c = _cov.get("n_internal_only") or 0
_n_with_bad_c      = _n_internal_c - _n_internal_only_c
_corr_rate_c       = (100.0 * _n_with_bad_c / _n_internal_c) if _n_internal_c else 0.0
_corr_tn_c         = "success" if _corr_rate_c >= 80 else "warning" if _corr_rate_c >= 50 else "danger"
kpi_row([
    kpi_card(
        ("Projets cartographiés" if lang == "FR" else "Mapped projects"),
        fmt_int(_n_internal_c),
        tone="success", icon="project",
        explainer=("Total des projets actifs suivis par RASME dans ce pays (= Projets actifs)."
                   if lang == "FR" else
                   "Total active projects monitored by RASME in this country (= Active projects)."),
    ),
    kpi_card(
        ("Avec correspondance BAD" if lang == "FR" else "With BAD match"),
        fmt_int(_n_with_bad_c),
        tone="success", icon="check",
        explainer=("Projets cartographiés ayant une correspondance dans la base BAD."
                   if lang == "FR" else
                   "Mapped projects matched to a record in the BAD database."),
    ),
    kpi_card(
        ("Sans correspondance BAD" if lang == "FR" else "Without BAD match"),
        fmt_int(_n_internal_only_c),
        tone="warning" if _n_internal_only_c else "success",
        icon="risk",
        explainer=("Projets cartographiés sans correspondance dans la base BAD."
                   if lang == "FR" else
                   "Mapped projects with no match in the BAD database."),
    ),
    kpi_card(
        ("Taux de correspondance" if lang == "FR" else "Match rate"),
        fmt_pct(_corr_rate_c),
        tone=_corr_tn_c, icon="duration",
        explainer=("Avec correspondance BAD / Projets cartographiés."
                   if lang == "FR" else
                   "With BAD match / Mapped projects."),
    ),
])

# Ligne 2 (vue BAD) : couverture du portefeuille BAD ACTIF (Approved + Ongoing).
kpi_row([
    kpi_card(
        ("Projets actifs (BAD)" if lang == "FR" else "Active projects (BAD)"),
        fmt_int(_cov["n_portfolio"]),
        icon="globe",
        explainer=("Projets BAD aux statuts Approved + Ongoing pour ce pays."
                   if lang == "FR" else
                   "BAD projects with status Approved + Ongoing for this country."),
    ),
    kpi_card(
        ("Actifs cartographiés" if lang == "FR" else "Mapped active"),
        fmt_int(_cov["n_mapped"]),
        tone="success", icon="completion",
        explainer=("Projets actifs avec ≥1 projet interne correspondant."
                   if lang == "FR" else
                   "Active projects with ≥1 matching internal project."),
    ),
    kpi_card(
        ("Actifs non cartographiés" if lang == "FR" else "Active unmapped"),
        fmt_int(_cov["n_unmapped"]),
        tone="warning" if _cov["n_unmapped"] else "success",
        icon="risk",
        explainer=("Projets actifs sans monitoring interne — gap de couverture."
                   if lang == "FR" else
                   "Active projects without internal monitoring — coverage gap."),
    ),
    kpi_card(
        ("Taux de couverture" if lang == "FR" else "Coverage rate"),
        fmt_pct(_rate),
        tone=_rate_tn, icon="duration",
        explainer=("Actifs cartographiés / Projets actifs (BAD)."
                   if lang == "FR" else
                   "Mapped active / Active projects (BAD)."),
    ),
])

# Ligne 3 : visibilité Completion / Cancelled — exclus du taux de couverture.
kpi_row([
    kpi_card(
        ("Clôturés (BAD)" if lang == "FR" else "Completion (BAD)"),
        fmt_int(_cov["n_completion"]),
        icon="check",
        explainer=("Projets BAD clôturés (Completion) attribués à ce pays."
                   if lang == "FR" else
                   "BAD Completion projects assigned to this country."),
    ),
    kpi_card(
        ("Clôturés cartographiés" if lang == "FR" else "Completion mapped"),
        fmt_int(_cov["n_completion_mapped"]),
        icon="completion",
        explainer=("Projets clôturés avec un suivi interne historique."
                   if lang == "FR" else
                   "Completion projects with historical internal data."),
    ),
    kpi_card(
        ("Annulés cartographiés" if lang == "FR" else "Cancelled mapped"),
        fmt_int(_cov["n_cancelled_mapped"]),
        icon="risk",
        explainer=("Projets annulés avec un suivi interne (rare)."
                   if lang == "FR" else
                   "Cancelled projects with internal data (rare)."),
    ),
], cols=3)

# ── Tableau comparatif unifié ───────────────────────────────────────────────
# Toutes les lignes = projets actifs internes, étiquetés Cartographié /
# Projet non cartographié. La méthode de match est indiquée à droite.
_cov_tbl = coverage_table(country)
if _cov_tbl.empty:
    st.caption(("Aucun projet actif interne pour ce pays."
                if lang == "FR" else
                "No internal active project for this country."))
else:
    _none_lbl = "—"

    # 5-bucket schema: code, canonical title, all_titles, BAD info, BAD
    # status (Approved/Ongoing/Completion/Cancelled), coverage_status.
    _disp = _cov_tbl[[
        "code", "project_title", "all_titles",
        "bad_code", "bad_title", "bad_country", "bad_status", "coverage_status",
    ]].copy()
    _disp["bad_code"]    = _disp["bad_code"].fillna(_none_lbl)
    _disp["bad_title"]   = _disp["bad_title"].fillna(_none_lbl)
    _disp["bad_country"] = _disp["bad_country"].fillna(_none_lbl)
    _disp["bad_status"]  = _disp["bad_status"].fillna(_none_lbl)
    _disp["all_titles"]  = _disp["all_titles"].fillna("")
    _disp["code"]        = _disp["code"].fillna(_none_lbl)

    if lang == "EN":
        _disp["coverage_status"] = _disp["coverage_status"].map({
            "Cartographié — Actif":       "Mapped — Active",
            "Cartographié — Clôturé":     "Mapped — Completion",
            "Cartographié — Annulé":      "Mapped — Cancelled",
            "Cartographié — Autre pays":  "Mapped — Other country",
            "Non cartographié":           "Unmapped",
        }).fillna(_disp["coverage_status"])

    _disp = _disp.rename(columns={
        "code":            ("Code SAP" if lang == "FR" else "SAP code"),
        "project_title":   ("Projet interne (titre canonique)"
                            if lang == "FR" else "Internal project (canonical title)"),
        "all_titles":      ("Autres titres trouvés" if lang == "FR" else "Other titles found"),
        "bad_code":        ("Code BAD" if lang == "FR" else "BAD code"),
        "bad_title":       ("Titre BAD" if lang == "FR" else "BAD title"),
        "bad_country":     ("Pays BAD" if lang == "FR" else "BAD country"),
        "bad_status":      ("Statut BAD" if lang == "FR" else "BAD status"),
        "coverage_status": ("Couverture" if lang == "FR" else "Coverage"),
    })

    st.dataframe(
        _disp, use_container_width=True,
        height=min(560, 80 + 28 * min(len(_disp), 18)),
        hide_index=True,
    )
    st.download_button(
        ("Exporter CSV" if lang == "FR" else "Export CSV"),
        data=_disp.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"couverture_BAD_{country}.csv",
        mime="text/csv",
    )

# Optionnel : repli des projets BAD actifs non rapprochés (informatif).
_bo_active = bad_only_active(country)
if not _bo_active.empty:
    with st.expander(
        (f"Projets BAD non cartographiés ({len(_bo_active)})"
         if lang == "FR" else
         f"Unmapped BAD projects ({len(_bo_active)})"),
        expanded=False,
    ):
        _bo_disp = _bo_active[["code", "project_title", "status_label"]].rename(columns={
            "code":          ("Code BAD" if lang == "FR" else "BAD code"),
            "project_title": ("Titre BAD" if lang == "FR" else "BAD title"),
            "status_label":  ("Statut BAD" if lang == "FR" else "BAD status"),
        })
        st.dataframe(
            _bo_disp, use_container_width=True,
            height=min(420, 80 + 28 * min(len(_bo_disp), 12)),
            hide_index=True,
        )

# ── Country map ──────────────────────────────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_geo_eyebrow", lang),
    title=t("pillar_geo_title", lang) if lang == "EN" else "Localisation des sites du pays",
    description=("Distribution géographique colorée par statut d'implémentation."
                 if lang == "FR" else
                 "Geographic distribution coloured by implementation status."),
)
pts = map_points({**country_filters, "country": country}, limit=4000)
if pts.empty:
    st.info(t("no_geo_data", lang))
else:
    # Translate the sector column so it appears in the popup in the active language.
    pts = pts.copy()
    pts["sector"] = pts["sector"].map(lambda s: sector_label(s, lang))
    center_lat = float(pts["lat"].mean())
    center_lon = float(pts["lon"].mean())
    leaflet_map(
        pts, lang,
        height=480,
        center=(center_lat, center_lon),
        zoom=5,
        point_cap=4000,
        key=f"country_leaflet_{country}",
        show_country_in_popup=False,   # country is already obvious here
    )

# ── Three-chart row : funnel &middot; region × status &middot; delay distribution ─────────
pillar_header(
    eyebrow=t("pillar_breakdown_eyebrow", lang),
    title=("Pipeline, régions et retards" if lang == "FR" else "Pipeline, regions and delays"),
    description=("Trois angles pour comprendre le portefeuille du pays : la cascade Planifié → Achevé, "
                 "la concentration régionale, et la distribution des retards."
                 if lang == "FR" else
                 "Three angles on the country portfolio: the Planned → Completed funnel, regional "
                 "concentration, and the delay distribution."),
)
col1, col2, col3 = st.columns(3, gap="medium")

# Funnel — Planned → In progress → Completed.
# Note: the 3 statuses are SNAPSHOT counts, not stages of the same flow, so
# "percent initial" can exceed 100% (a country can have more Completed than
# Planned). We use "percent total" to keep figures bounded by [0,100].
with col1:
    fnl = country_funnel(country, country_filters)
    if not fnl.empty:
        order = ["Planned", "In progress", "Completed"]
        fnl_pivot = fnl.set_index("status").reindex(order).reset_index().fillna(0)
        fig = go.Figure(go.Funnel(
            y=[t("planned", lang), t("in_progress", lang), t("completed", lang)],
            x=fnl_pivot["n"].tolist(),
            marker=dict(color=[PALETTE["warning"], "#0066CC", PALETTE["success"]]),
            textposition="inside",
            textinfo="value+percent total",
        ))
        fig.update_layout(
            title=t("chart_funnel", lang),
            margin=dict(l=0, r=0, t=40, b=0), height=340,
        )
        dark_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)

# Region × status stacked bar (translated legend)
with col2:
    rs = country_region_status(country, country_filters)
    if not rs.empty:
        rs_total = rs.groupby("region")["sites"].sum().sort_values()
        order = rs_total.index.tolist()[-15:]  # cap at 15 regions
        rs = rs[rs["region"].isin(order)].copy()
        rs["status_label"] = rs["status"].map(lambda s: status_label(s, lang))
        fig = px.bar(
            rs, y="region", x="sites", color="status_label",
            orientation="h",
            color_discrete_map=status_color_map(lang),
            title=t("chart_region_status", lang),
            labels={"region": "", "sites": t("sites_total", lang),
                    "status_label": t("status", lang)},
            category_orders={"region": order},
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=40, b=70), height=340,
            legend=dict(orientation="h", yanchor="top", y=-0.18, x=0,
                        font=dict(size=9), title_text=t("status", lang)),
            bargap=0.2,
        )
        dark_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)

# Delay distribution histogram
with col3:
    dl = country_delay_distribution(country, country_filters).dropna(subset=["delay_days"])
    if not dl.empty:
        fig = px.histogram(
            dl, x="delay_days", nbins=24,
            color_discrete_sequence=[PALETTE["warning"]],
            title=t("chart_delay_dist", lang),
            labels={"delay_days": t("delay_days", lang)},
        )
        fig.update_layout(
            margin=dict(l=0, r=0, t=40, b=0), height=340,
            showlegend=False,
        )
        fig.add_vline(x=0, line_color=PALETTE["neutral"], line_dash="dash")
        dark_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption(t("no_data", lang))

# ── Beneficiaries breakdown (gender, age, vulnerable groups) ────────────────
pillar_header(
    eyebrow=t("pillar_benef_eyebrow", lang),
    title=t("pillar_benef_title", lang),
    description=t("pillar_benef_desc", lang),
)
b = country_beneficiaries(country, country_filters)

total_benef = float(b.get("total") or 0)
if total_benef <= 0:
    st.caption(t("no_data", lang))
else:
    bcol1, bcol2, bcol3 = st.columns(3, gap="medium")

    # Gender split
    with bcol1:
        gender_df = [
            (t("beneficiaries_women", lang), float(b.get("women")  or 0)),
            (t("beneficiaries_men",   lang), float(b.get("men")    or 0)),
            (t("beneficiaries_other", lang), float(b.get("other")  or 0)),
        ]
        gender_df = [(k, v) for k, v in gender_df if v > 0]
        if gender_df:
            fig = px.pie(
                names=[k for k, _ in gender_df],
                values=[v for _, v in gender_df],
                hole=0.55,
                title=t("benef_by_gender", lang),
                color_discrete_sequence=[PALETTE["primary"], "#0066CC", PALETTE["muted"]],
            )
            fig.update_traces(textposition="inside", textinfo="percent",
                              hovertemplate="<b>%{label}</b><br>%{value:,.0f} &middot; %{percent}")
            fig.update_layout(
                margin=dict(l=0, r=0, t=40, b=0), height=300,
                legend=dict(orientation="h", yanchor="top", y=-0.05),
            )
            dark_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption(t("no_data", lang))

    # Age split
    with bcol2:
        age_df = [
            (t("beneficiaries_children_under_5", lang), float(b.get("children_under_5") or 0)),
            (t("beneficiaries_children_5_18",    lang), float(b.get("children_5_18")    or 0)),
            (t("beneficiaries_elderly",          lang), float(b.get("elderly")          or 0)),
        ]
        age_df = [(k, v) for k, v in age_df if v > 0]
        if age_df:
            fig = px.bar(
                x=[v for _, v in age_df],
                y=[k for k, _ in age_df],
                orientation="h",
                title=t("benef_by_age", lang),
                color_discrete_sequence=[PALETTE["primary"]],
                labels={"x": "", "y": ""},
            )
            fig.update_traces(text=[f"{v:,.0f}" for _, v in age_df], textposition="outside")
            fig.update_layout(
                margin=dict(l=0, r=20, t=40, b=0), height=300,
                showlegend=False,
                xaxis=dict(showgrid=False, showticklabels=False),
            )
            dark_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption(t("no_data", lang))

    # Vulnerable groups
    with bcol3:
        vuln_df = [
            (t("beneficiaries_disabled",  lang), float(b.get("disabled")  or 0)),
            (t("beneficiaries_refugees",  lang), float(b.get("refugees")  or 0)),
            (t("beneficiaries_idps",      lang), float(b.get("idps")      or 0)),
            (t("beneficiaries_returnees", lang), float(b.get("returnees") or 0)),
        ]
        vuln_df = [(k, v) for k, v in vuln_df if v > 0]
        if vuln_df:
            fig = px.bar(
                x=[v for _, v in vuln_df],
                y=[k for k, _ in vuln_df],
                orientation="h",
                title=t("benef_vulnerable", lang),
                color_discrete_sequence=[PALETTE["danger"]],
                labels={"x": "", "y": ""},
            )
            fig.update_traces(text=[f"{v:,.0f}" for _, v in vuln_df], textposition="outside")
            fig.update_layout(
                margin=dict(l=0, r=20, t=40, b=0), height=300,
                showlegend=False,
                xaxis=dict(showgrid=False, showticklabels=False),
            )
            dark_plotly(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption(t("no_data", lang))

    st.caption(f"**{t('benef_total', lang)} :** {fmt_int(total_benef)}")

# ── Outputs physiques (heuristic keyword detection) ─────────────────────────
pillar_header(
    eyebrow=t("pillar_outputs_eyebrow", lang),
    title=t("pillar_outputs_title", lang),
    description=t("pillar_outputs_desc", lang),
)
out = country_outputs(country, country_filters)
total_sites_out  = int(out.get("total_sites") or 0)
distinct_proj    = int(out.get("distinct_projects") or 0)
n_infra          = int(out.get("infra")     or 0)
n_equip          = int(out.get("equipment") or 0)
n_deliv          = int(out.get("delivery")  or 0)
n_documented     = int(out.get("documented")or 0)
detected_total   = n_infra + n_equip + n_deliv  # may overcount (a site can match multiple)
ratio_per_proj   = (detected_total / distinct_proj) if distinct_proj else None

if total_sites_out == 0:
    st.caption(t("no_data", lang))
else:
    st.caption(t("outputs_disclaimer", lang))
    kpi_row(
        [
            kpi_card(
                t("outputs_infra", lang), fmt_int(n_infra),
                icon="infra", explainer=t("expl_outputs_infra", lang),
            ),
            kpi_card(
                t("outputs_equipment", lang), fmt_int(n_equip),
                icon="equipment", explainer=t("expl_outputs_equip", lang),
            ),
            kpi_card(
                t("outputs_delivery", lang), fmt_int(n_deliv),
                icon="delivery", explainer=t("expl_outputs_deliv", lang),
            ),
            kpi_card(
                t("outputs_per_project", lang),
                f"{ratio_per_proj:.1f}" if ratio_per_proj is not None else "—",
                tone="success", icon="project",
                explainer=t("expl_outputs_per_proj", lang),
                delta=(f"{n_documented:,} / {total_sites_out:,} {t('outputs_documented', lang).lower()}"
                       .replace(",", " ")),
            ),
        ],
        cols=4,
    )

    breakdown = country_output_breakdown(country, country_filters)
    # Defensive: drop any rows where category somehow ended up null/empty —
    # those would render as "undefined" labels in Plotly.
    breakdown = breakdown.dropna(subset=["category"])
    breakdown = breakdown[breakdown["category"].astype(str).str.strip() != ""]
    if not breakdown.empty:
        section(t("outputs_breakdown", lang))
        sorted_b = breakdown.sort_values("occurrences").reset_index(drop=True)
        fig = px.bar(
            sorted_b,
            y="category", x="occurrences", orientation="h",
            color_discrete_sequence=[PALETTE["primary"]],
            labels={"category": "", "occurrences": t("issue_count", lang)},
            text="occurrences",
        )
        # texttemplate guarantees clean integer formatting (no NaN → "undefined").
        fig.update_traces(textposition="outside", texttemplate="%{x:,d}", cliponaxis=False)
        fig.update_layout(
            margin=dict(l=0, r=40, t=8, b=0), height=max(240, 30 * len(sorted_b)),
            showlegend=False,
            xaxis=dict(showgrid=False, showticklabels=False, title=""),
            yaxis=dict(title=""),
        )
        dark_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)


# ── Operational pipeline table ────────────────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_ops_eyebrow", lang),
    title=t("pillar_ops_title", lang),
    description=t("pillar_ops_desc", lang),
)
pipe = country_pipeline(country, country_filters)

if pipe.empty:
    st.info(t("no_data", lang))
else:
    pipe = pipe.copy()
    pipe["status"] = pipe["status"].map(lambda s: status_label(s, lang))
    pipe["sector"] = pipe["sector"].map(lambda s: sector_label(s, lang))
    pretty_cols = {
        "project":        t("tbl_project",       lang),
        "site":           t("tbl_site",          lang),
        "region":         t("tbl_region",        lang),
        "sector":         t("tbl_sector",        lang),
        "status":         t("tbl_status",        lang),
        "progress":       t("tbl_progress",      lang),
        "planned_start":  t("tbl_planned_start", lang),
        "planned_end":    t("tbl_planned_end",   lang),
        "completion":     t("tbl_completion",    lang),
        "delay_days":     t("tbl_delay",         lang),
        "funder":         t("tbl_funder",        lang),
        "agency":         t("tbl_agency",        lang),
    }
    display = pipe[list(pretty_cols.keys())].rename(columns=pretty_cols)

    st.caption(t("n_records", lang, n=fmt_int(len(display))))
    st.dataframe(
        display,
        use_container_width=True,
        height=min(560, 80 + 28 * min(len(display), 18)),
        hide_index=True,
    )
    st.download_button(
        t("export_csv", lang),
        data=display.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"pipeline_{country}.csv",
        mime="text/csv",
    )

# ── Activity timeline (photo gallery, grouped by GPS site) ─────────────────
pillar_header(
    eyebrow=t("pillar_timeline_eyebrow", lang),
    title=t("pillar_timeline_title", lang),
    description=t("pillar_timeline_desc", lang),
)

tl_show = st.slider(
    t("tl_show_count", lang),
    min_value=24, max_value=240, value=60, step=12,
)

photos = country_timeline(country, country_filters, limit=tl_show)
if photos.empty:
    st.caption(t("tl_no_photos", lang))
else:
    primary    = PALETTE["primary"]
    primary_dk = PALETTE["primary_dk"]
    border     = PALETTE["border"]
    muted      = PALETTE["muted"]

    # Build a site identity from rounded GPS — 5 decimal places ≈ 1.1 m.
    p = photos.copy()
    p["lat_r"] = p["lat"].round(5)
    p["lon_r"] = p["lon"].round(5)
    p["_site_key"] = list(zip(p["lat_r"], p["lon_r"]))

    # Build site groups: list of dicts, each with its visits sorted oldest-first.
    site_groups = []
    for key, df_s in p.groupby("_site_key"):
        df_sorted = df_s.sort_values("collection_date")
        most_recent = df_sorted["collection_date"].max()
        site_groups.append({
            "key": key,
            "site_name":     next((s for s in df_sorted["site_name"]     if s), None) or "—",
            "project_title": next((s for s in df_sorted["project_title"] if s), None) or "—",
            "region_name":   next((s for s in df_sorted["region_name"]   if s), None) or "",
            "most_recent": most_recent,
            "visits": df_sorted,
        })

    # Sites with the most recent visit show first.
    site_groups.sort(
        key=lambda g: (g["most_recent"] is not None, g["most_recent"]),
        reverse=True,
    )

    # ── Group sites by project ────────────────────────────────────────────
    # The timeline is now a 2-level hierarchy: project → sites → visits.
    # Sites without a project_title fall into a placeholder "—" bucket.
    project_groups: dict[str, list[dict]] = {}
    for _g in site_groups:
        project_groups.setdefault(_g["project_title"] or "—", []).append(_g)

    def _proj_recency(kv):
        recents = [s["most_recent"] for s in kv[1] if s["most_recent"] is not None]
        return (bool(recents), max(recents) if recents else 0)

    projects_sorted = sorted(project_groups.items(), key=_proj_recency, reverse=True)

    # Hint above the strip + counter (projects &middot; sites)
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
                    margin:4px 0 14px 0;font-family:'DM Sans',system-ui,sans-serif;
                    font-size:12.5px;color:{muted};">
          <span>{t('tl_evolution_hint', lang)}</span>
          <span style="font-family:'DM Mono',ui-monospace,monospace;font-size:11px;
                       letter-spacing:.4px;">
            {t('tl_projects_sites_shown', lang, p=len(projects_sorted), s=len(site_groups))}
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Inject the strip styles once (a single style tag — CSS, not script —
    # which Streamlit's markdown allows reliably).
    st.markdown(
        f"""
        <style>
        .tl-project {{
          background:#F7F9F6;border:1px solid {primary}33;border-left:4px solid {primary};
          border-radius:14px;padding:16px 18px 6px;margin:0 0 22px 0;
          box-shadow:0 2px 8px rgba(0,143,79,.06);
        }}
        .tl-project-header {{
          display:flex;align-items:baseline;justify-content:space-between;gap:12px;
          margin-bottom:14px;flex-wrap:wrap;
        }}
        .tl-project-name {{
          font-family:'DM Sans',system-ui,sans-serif;font-weight:700;font-size:15.5px;
          color:{primary_dk};line-height:1.3;
        }}
        .tl-project-badge {{
          font-family:'DM Mono',ui-monospace,monospace;font-size:10.5px;
          color:#FFFFFF;background:{primary};
          padding:4px 12px;border-radius:999px;letter-spacing:.3px;flex:none;
        }}
        .tl-project .tl-site {{
          margin:0 0 10px 0;
          box-shadow:none;border-color:{border};
        }}
        .tl-site {{
          background:#FFFFFF;border:1px solid {border};border-radius:14px;
          padding:14px 16px 16px;margin:0 0 14px 0;
          box-shadow:0 1px 4px rgba(0,143,79,0.05);
        }}
        .tl-site-header {{
          display:flex;align-items:baseline;justify-content:space-between;gap:10px;
          margin-bottom:10px;flex-wrap:wrap;
        }}
        .tl-site-name {{
          font-family:'DM Sans',system-ui,sans-serif;font-weight:600;font-size:14px;
          color:{primary_dk};line-height:1.3;
        }}
        .tl-site-meta {{
          font-family:'DM Sans',system-ui,sans-serif;font-size:11.5px;color:{muted};
        }}
        .tl-site-badge {{
          font-family:'DM Mono',ui-monospace,monospace;font-size:10.5px;
          color:{primary_dk};background:{primary}1A;
          padding:3px 10px;border-radius:999px;letter-spacing:.3px;
          border:1px solid {primary}33;flex:none;
        }}
        .tl-strip {{
          display:flex;gap:10px;overflow-x:auto;padding:6px 2px 8px 2px;
          scroll-snap-type:x mandatory;
        }}
        .tl-strip::-webkit-scrollbar      {{ height:8px; }}
        .tl-strip::-webkit-scrollbar-thumb{{ background:{primary}55;border-radius:4px; }}
        .tl-visit {{
          flex:0 0 200px;scroll-snap-align:start;
          background:#FFFFFF;border:1px solid {border};border-radius:10px;overflow:hidden;
          display:flex;flex-direction:column;
        }}
        .tl-visit .tl-img-wrap {{
          display:block;background:#F0F4F2;height:140px;overflow:hidden;
        }}
        .tl-visit img {{ width:100%;height:140px;object-fit:cover;display:block; }}
        .tl-visit .tl-img-fallback {{
          display:flex;align-items:center;justify-content:center;height:140px;
          color:#94A3B8;font-family:'DM Sans',system-ui,sans-serif;font-size:11px;
          background:repeating-linear-gradient(45deg,#F7F9F6 0 8px,#EAF0EA 8px 16px);
        }}
        .tl-visit-body {{
          padding:10px 12px 12px;display:flex;flex-direction:column;gap:4px;
        }}
        .tl-visit-date {{
          font-family:'DM Mono',ui-monospace,monospace;font-size:10.5px;
          color:{muted};letter-spacing:.4px;
        }}
        .tl-visit-status {{
          align-self:flex-start;font-family:'DM Sans',system-ui,sans-serif;
          font-size:10px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;
          padding:2px 8px;border-radius:999px;
        }}
        .tl-visit-latest {{
          position:absolute;top:8px;right:8px;background:{primary};color:#FFFFFF;
          font-family:'DM Sans',system-ui,sans-serif;font-size:9.5px;font-weight:700;
          letter-spacing:.5px;text-transform:uppercase;
          padding:3px 8px;border-radius:999px;
          box-shadow:0 2px 6px rgba(0,143,79,.3);
        }}
        .tl-visit-wrapper {{ position:relative; }}
        .tl-arrow {{
          align-self:center;color:{primary};font-size:18px;flex:none;opacity:.6;
          font-family:'DM Mono',ui-monospace,monospace;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    color_map = status_color_map(lang)

    # Warm the thumbnail cache in one pass under a single spinner, so the strip
    # renders fully on first paint instead of fetching image-by-image.
    with st.spinner("Chargement des photos…" if lang == "FR" else "Loading photos…"):
        for _g in site_groups:
            for _, _r in _g["visits"].iterrows():
                kobo_thumb_data_uri(_r.get("photo_1_url") or _r.get("photo_2_url") or "")

    def _img_html(url: str) -> str:
        """Miniature récupérée côté serveur ; sinon, le navigateur charge l'image
        directement, avec le repli rayé en arrière-plan."""
        if not url:
            return ('<div class="tl-img-wrap"><div class="tl-img-fallback">'
                    '📷 image indisponible</div></div>')
        data_uri = kobo_thumb_data_uri(url)
        src = data_uri or url
        return (
            f'<a class="tl-img-wrap" href="{url}" target="_blank" rel="noopener" '
            f'title="{t("tl_open_full", lang)}">'
            f'<div class="tl-img-fallback">📷 image indisponible</div>'
            f'<img src="{src}" loading="lazy" style="position:relative;z-index:1"/>'
            f'</a>'
        )

    def _site_card_html(g: dict) -> str:
        """Build the HTML for a single site card (header + visits strip).

        Project name is omitted from the meta line because the parent
        ``.tl-project`` wrapper already shows it — only region is kept.
                """
        visits     = g["visits"]
        n_visits   = len(visits)
        _sn        = g["site_name"]
        _name      = str(_sn) if _sn is not None and _sn == _sn else ""
        site_n     = _name[:60] + ("…" if len(_name) > 62 else "")
        region     = g["region_name"]
        latest_idx = len(visits) - 1   # last visit (sorted ascending)

        cards_html = []
        for i, (_, row) in enumerate(visits.iterrows()):
            # ── URL image (KoboToolbox _attachments) ──────────────────────
            _atts = row.get("_attachments") or []
            if isinstance(_atts, str):
                import json
                try:    _atts = json.loads(_atts)
                except: _atts = []
            if _atts and isinstance(_atts, list) and len(_atts) > 0:
                _first = _atts[0]
                url = (
                    _first.get("download_medium_url") or
                    _first.get("download_url") or
                    _first.get("download_large_url") or ""
                )
            else:
                url = ""
            # ──────────────────────────────────────────────────────────────
            _dt        = row.get("collection_date")
            date_str   = _dt.strftime("%d %b %Y") if (_dt is not None and _dt == _dt) else "—"
            status_v   = row.get("status") or ""
            status_lbl = status_label(status_v, lang) if status_v else "—"
            scol       = color_map.get(status_lbl, PALETTE["neutral"])

            badge = f'<span class="tl-visit-latest">{t("tl_latest", lang)}</span>' \
                    if i == latest_idx and n_visits > 1 else ""
            cards_html.append(
                f'<div class="tl-visit tl-visit-wrapper">'
                f'  {badge}'
                f'  {_img_html(url)}'
                f'  <div class="tl-visit-body">'
                f'    <div class="tl-visit-date">{date_str}</div>'
                f'    <div class="tl-visit-status" '
                f'         style="background:{scol}22;color:{scol};">{status_lbl}</div>'
                f'  </div>'
                f'</div>'
            )
            if i < latest_idx:
                cards_html.append('<div class="tl-arrow">→</div>')

        strip_html = '<div class="tl-strip">' + "".join(cards_html) + '</div>'

        return (
            f'<div class="tl-site">'
            f'  <div class="tl-site-header">'
            f'    <div>'
            f'      <div class="tl-site-name">{site_n}</div>'
            f'      <div class="tl-site-meta">{region}</div>'
            f'    </div>'
            f'    <span class="tl-site-badge">{n_visits} {t("tl_visits", lang)}</span>'
            f'  </div>'
            f'  {strip_html}'
            f'</div>'
        )

    for proj_title, sites in projects_sorted:
        # Sort sites in this project: most recently visited first.
        sites_sorted = sorted(
            sites,
            key=lambda s: (s["most_recent"] is not None, s["most_recent"]),
            reverse=True,
        )

        proj_n = proj_title[:120] + ("…" if len(str(proj_title)) > 122 else "")
        n_sites_p  = len(sites_sorted)
        n_visits_p = sum(len(s["visits"]) for s in sites_sorted)

        sites_html = "".join(_site_card_html(g) for g in sites_sorted)

        st.markdown(
            f"""
        <div class="tl-project">
              <div class="tl-project-header">
                <div class="tl-project-name">{proj_n}</div>
                <span class="tl-project-badge">
                  {n_sites_p} {t('tl_project_sites', lang)} &middot; {n_visits_p} {t('tl_visits', lang)}
                </span>
              </div>
              {sites_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── Issues panel ─────────────────────────────────────────────────────────────
pillar_header(
    eyebrow=t("pillar_issues_eyebrow", lang),
    title=t("pillar_issues_title", lang),
    description=t("pillar_issues_desc", lang),
)
issues = country_issues(country, country_filters, top_n=10)
if issues.empty:
    st.caption(t("no_data", lang))
else:
    issues = issues.dropna(subset=["issue_type"])
    issues = issues[issues["issue_type"].astype(str).str.strip() != ""]
    if not issues.empty:
        fig = px.bar(
            issues.sort_values("occurrences"),
            y="issue_type", x="occurrences", orientation="h",
            color_discrete_sequence=[PALETTE["danger"]],
            labels={"issue_type": "", "occurrences": t("issue_count", lang)},
            text="occurrences",
        )
        fig.update_traces(textposition="outside", texttemplate="%{x:,d}", cliponaxis=False)
        fig.update_layout(
            margin=dict(l=0, r=40, t=8, b=0), height=320,
            showlegend=False,
            xaxis=dict(title=""),
            yaxis=dict(title=""),
        )
        dark_plotly(fig)
        st.plotly_chart(fig, use_container_width=True)
