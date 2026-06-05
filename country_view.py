"""Page 2 — Vue par Pays / Country View — operational view for project coordinators."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
    sap_to_titles: dict[str, list[str]] = {}
    standalone: list[str] = []
    for p in projects:
        c = sap.code_for(p)
        if c:
            sap_to_titles.setdefault(c, []).append(p)
        else:
            standalone.append(p)

    group_titles: dict[str, list[str]] = {}
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
            name = sap.canonical_title_for(code) or min(group_titles[p], key=len)
            short = name if len(name) <= 80 else name[:79] + "…"
            return f"{code}  ·  {short}"
        return sap.label_with_code(p, max_len=80)

    project = st.selectbox(
        t("select_project", lang),
        options=["__ALL__"] + project_options,
        format_func=_fmt_project,
        key="project_pick",
    )

country_filters: dict = dict(filters)
if project and project != "__ALL__":
    if project.startswith("__SAP__"):
        country_filters["projects_in"] = tuple(group_titles[project])
    else:
        country_filters["project"] = project

if project and project != "__ALL__":
    sap_code = project[len("__SAP__"):] if project.startswith("__SAP__") else sap.code_for(project)
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
dir_r_visual = "up" if dir_r == "down" else "down" if dir_r == "up" else ""

benef     = row.get("beneficiaries") or 0
g_benef   = row.get("g_beneficiaries") or 0
benef_pct = (100.0 * float(benef) / float(g_benef)) if g_benef else None

try:
    _bad_o = bad_overview()
    _cov   = coverage_overview(country)
    _cov_ok = True
except Exception:
    _bad_o, _cov, _cov_ok = {}, {}, False

if project and project != "__ALL__":
    country_projects_count = 0
else:
    country_projects_count = (_cov.get("n_internal") if _cov_ok else len(projects))

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
                   "Total number of active projects
breakdown = country_output_breakdown(country, country_filters)
    breakdown = breakdown.dropna(subset=["category"])
    breakdown = breakdown[breakdown["category"].astype(str).str.strip() != ""]
    
    if not breakdown.empty:
        section(t("outputs_breakdown", lang))
        sorted_b = breakdown.sort_values("occurrences").reset_index(drop=True)
        fig = px.bar(
            sorted_b,
            y="category", x="occurrences", orientation="h",
            color_discrete_sequence=[PALETTE["primary"]],
            labels={"category": "", "occurrences": t("occurrences", lang)},
        )
        fig.update_layout(
            margin=dict(l=0, r=20, t=40, b=0), height=400,
            showlegend=False,
        )
        dark_plotly(fig)
        st.plotly_chart(fig, width="stretch")

# ── RESTAURATION : Cartes de sites & chronologie de collecte ─────────────────
st.write("")
timeline_df = country_timeline(country, country_filters)
if not timeline_df.empty:
    pillar_header(
        eyebrow=t("pillar_timeline_eyebrow", lang),
        title=t("pillar_timeline_title", lang),
        description=t("pillar_timeline_desc", lang),
    )
    
    timeline_df = timeline_df.copy()
    timeline_df["status_label"] = timeline_df["status"].map(lambda s: status_label(s, lang))
    
    fig = px.bar(
        timeline_df, x="month", y="submissions", color="status_label",
        color_discrete_map=status_color_map(lang),
        title=t("chart_timeline", lang),
        labels={"month": "", "submissions": t("submissions", lang), "status_label": t("status", lang)},
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0), height=280,
        legend=dict(orientation="h", yanchor="top", y=-0.15, font=dict(size=9)),
    )
    dark_plotly(fig)
    st.plotly_chart(fig, width="stretch")

# Section finale d'affichage des alertes sur l'état d'avancement
issues_df = country_issues(country, country_filters)
if not issues_df.empty:
    pillar_header(
        eyebrow=t("pillar_issues_eyebrow", lang),
        title=t("pillar_issues_title", lang),
        description=t("pillar_issues_desc", lang),
    )
    
    for idx, g in issues_df.iterrows():
        raw_name = str(g.get("site_name") or "").strip()
        if not raw_name:
            raw_name = "Site sans nom" if lang == "FR" else "Unnamed Site"
        
        site_n = raw_name[:60] + ("…" if len(raw_name) > 62 else "")
        region = str(g.get("region_name") or "—")
        
        st.error(f"**{site_n}** ({region}) — {g.get('issue_description') or ''}")
