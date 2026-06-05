"""Shared UI helpers — CSS injection, sidebar filters, KPI cards, header, footer.

Aesthetic direction: dark-teal portfolio dashboard. Glass cards floating on a
deep-blue ground, lime accents, yellow CTA buttons, print-friendly layout.
Inspired by the construction-portfolio dashboard reference shared by the user.
"""

from __future__ import annotations

import base64
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import streamlit as st

from config import PALETTE
from db import date_bounds, filter_options
from i18n import t


ASSETS = Path(__file__).parent / "assets"


_MIME_BY_EXT = {
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif":  "image/gif",
}


@lru_cache(maxsize=8)
def _logo_data_uri(filename: str) -> str:
    """Read an image from /assets and return a data: URI suitable for inline <img>.

    MIME type is inferred from the file extension so SVG, PNG, JPEG etc. all work.
    Returns an empty string if the file is missing.
    """
    p = ASSETS / filename
    if not p.exists():
        return ""
    mime = _MIME_BY_EXT.get(p.suffix.lower(), "application/octet-stream")
    b64  = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ──────────────────────────────────────────────────────────────────────────────

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

:root {{
  --primary:    {PALETTE['primary']};
  --primary-dk: {PALETTE['primary_dk']};
  --success:    {PALETTE['success']};
  --warning:    {PALETTE['warning']};
  --danger:     {PALETTE['danger']};
  --neutral:    {PALETTE['neutral']};
  --bg:         {PALETTE['bg']};
  --bg-deep:    {PALETTE['bg_deep']};
  --card:       {PALETTE['card']};
  --card-solid: {PALETTE['card_solid']};
  --border:     {PALETTE['border']};
  --text:       {PALETTE['text']};
  --muted:      {PALETTE['muted']};
  --afdb-green: {PALETTE['afdb_green']};

  --display: 'Fraunces', 'Source Serif Pro', Georgia, serif;
  --sans:    'DM Sans', system-ui, sans-serif;
  --mono:    'DM Mono', ui-monospace, monospace;
}}

/* ── Clean white corporate shell ───────────────────────────────────────── */
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"] {{
  background: #FFFFFF !important;
  color: var(--text);
  font-family: var(--sans);
  font-feature-settings: "ss01", "cv11";
  min-height: 100vh;
}}
[data-testid="stMain"],
[data-testid="stHeader"],
[data-testid="stMainBlockContainer"],
.main, .block-container {{
  background: transparent !important;
}}

/* Sidebar = light grey/cream, kept legible with dark logos and inputs. */
[data-testid="stSidebar"] {{
  background: #F7F9F6 !important;
  border-right: 1px solid var(--border);
}}
[data-testid="stSidebar"] * {{ color: var(--text); font-family: var(--sans); }}
[data-testid="stSidebar"] label {{ color: var(--muted) !important; }}

/* ── Bordered filter inputs ─────────────────────────────────────────────
   Visible green border around every sidebar control (date pickers,
   selects/multiselects, text inputs, radio groups). Adds a soft focus glow
   when a control is open or focused. */
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div,
[data-testid="stSidebar"] input[type="text"],
[data-testid="stSidebar"] input[type="number"],
[data-testid="stSidebar"] [data-baseweb="datepicker"] input,
[data-testid="stSidebar"] [role="combobox"] {{
  border: 1.5px solid var(--primary) !important;
  border-radius: 8px !important;
  background: #FFFFFF !important;
  transition: border-color .15s ease, box-shadow .15s ease;
}}
[data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
[data-testid="stSidebar"] [data-baseweb="input"] > div:hover,
[data-testid="stSidebar"] [data-baseweb="datepicker"] input:hover {{
  border-color: var(--primary-dk) !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
[data-testid="stSidebar"] [data-baseweb="input"] > div:focus-within,
[data-testid="stSidebar"] [data-baseweb="datepicker"] input:focus {{
  border-color: var(--primary-dk) !important;
  box-shadow: 0 0 0 3px {PALETTE['primary']}20 !important;
  outline: none !important;
}}
/* Radio group — wrap each option visually as a pill. */
[data-testid="stSidebar"] [role="radiogroup"] {{
  background: #FFFFFF;
  border: 1.5px solid var(--primary);
  border-radius: 999px;
  padding: 4px;
  display: inline-flex;
  gap: 4px;
}}

/* ── Two-tier header ────────────────────────────────────────────────────── */
.afdb-header {{
  margin: -1rem -1rem 1.6rem -1rem;
  background: var(--card);
  border-bottom: 1px solid var(--border);
}}
.afdb-ribbon {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 28px;
  background:
    radial-gradient(circle at 8% 50%, rgba(0,143,79,0.05) 0%, transparent 40%),
    radial-gradient(circle at 92% 50%, rgba(0,143,79,0.04) 0%, transparent 40%),
    #FFFFFF;
  border-bottom: 1px solid var(--border);
}}
.afdb-ribbon img {{
  display: block;
  filter: none;
}}
.afdb-ribbon .logo-afdb {{ height: 44px; width: auto; }}
.afdb-ribbon .logo-rasme {{ height: 40px; width: auto; }}

.afdb-banner {{
  position: relative;
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 28px;
  background: linear-gradient(105deg, var(--primary-dk) 0%, var(--primary) 65%, #00A85E 100%);
  color: #fff;
  overflow: hidden;
}}
.afdb-banner::before {{
  content: "";
  position: absolute; inset: 0;
  background:
    repeating-linear-gradient(135deg, rgba(255,255,255,0.04) 0 1px, transparent 1px 14px);
  pointer-events: none;
}}
.afdb-banner .titles {{ position: relative; z-index: 1; }}
.afdb-banner h1 {{
  margin: 0;
  font-family: var(--display);
  font-weight: 500;
  font-size: 26px;
  letter-spacing: -0.4px;
  line-height: 1.15;
}}
.afdb-banner .sub {{
  margin-top: 4px;
  font-size: 12px;
  font-weight: 500;
  opacity: 0.85;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}}
.afdb-banner .meta {{
  position: relative; z-index: 1;
  text-align: right;
  font-size: 11px;
  font-family: var(--mono);
  letter-spacing: 0.2px;
  line-height: 1.7;
  opacity: 0.92;
}}
.afdb-banner .meta b {{ font-weight: 500; }}

/* ── KPI cards ──────────────────────────────────────────────────────────── */
.kpi-row {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}}
.kpi-card {{
  position: relative;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 18px 20px 16px 22px;
  box-shadow: 0 1px 0 rgba(16,24,40,0.02);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
.kpi-card:hover {{
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(16,24,40,0.06);
}}
.kpi-card::before {{
  content: "";
  position: absolute; left: 0; top: 14px; bottom: 14px;
  width: 3px; border-radius: 2px;
  background: var(--primary);
}}
.kpi-card.success::before {{ background: var(--success); }}
.kpi-card.warning::before {{ background: var(--warning); }}
.kpi-card.danger::before  {{ background: var(--danger);  }}
.kpi-card .label {{
  font-size: 10.5px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.8px;
  margin-bottom: 8px;
}}
.kpi-card .value {{
  font-family: var(--display);
  font-weight: 500;
  font-size: 32px;
  color: var(--text);
  line-height: 1.05;
  letter-spacing: -0.6px;
  font-variant-numeric: tabular-nums;
}}
.kpi-card .delta {{
  font-family: var(--mono);
  font-size: 10.5px;
  margin-top: 8px;
  color: var(--muted);
  letter-spacing: 0.2px;
}}
.kpi-card .delta.up   {{ color: var(--success); }}
.kpi-card .delta.down {{ color: var(--danger);  }}

/* ── Section titles ─────────────────────────────────────────────────────── */
.section-title {{
  position: relative;
  font-size: 11px; font-weight: 700; color: var(--text);
  text-transform: uppercase; letter-spacing: 1.4px;
  margin: 26px 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 10px;
}}
.section-title::before {{
  content: "";
  display: inline-block;
  width: 8px; height: 8px;
  background: var(--primary);
  border-radius: 50%;
  flex: none;
}}
.section-title::after {{
  content: "";
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--primary) 0%, transparent 35%);
  margin-left: 4px;
}}

/* ── Insight cards ──────────────────────────────────────────────────────── */
.insight-card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--primary);
  border-radius: 4px;
  padding: 13px 16px 13px 18px;
  margin-bottom: 8px;
  font-size: 13.5px;
  line-height: 1.55;
  color: var(--text);
}}
.insight-card.warning {{ border-left-color: var(--warning); }}
.insight-card.danger  {{ border-left-color: var(--danger);  }}
.insight-card.success {{ border-left-color: var(--success); }}
.insight-card strong  {{ font-weight: 600; }}

/* ── Misc Streamlit overrides ───────────────────────────────────────────── */
[data-testid="stMetric"] {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 14px;
}}
button[kind="primary"], .stButton button[kind="primary"] {{
  background: var(--primary) !important;
  border-color: var(--primary) !important;
  font-family: var(--sans);
}}
.stDataFrame {{
  border: 1px solid var(--border);
  border-radius: 6px;
}}
.stDataFrame, .stDataFrame * {{ font-family: var(--sans) !important; }}

/* Hide Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"] {{ visibility: hidden; }}

/* ── Yellow PDF-export pill ─────────────────────────────────────────────── */
.pdf-export-btn {{
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 18px; border-radius: 999px;
  background: var(--warning); color: #1A1A1A;
  font-family: var(--sans); font-weight: 600; font-size: 13px;
  letter-spacing: .2px; cursor: pointer; border: 0;
  box-shadow: 0 6px 18px rgba(255, 214, 107, 0.28);
  transition: transform 120ms ease, box-shadow 120ms ease, filter 120ms ease;
}}
.pdf-export-btn:hover {{
  transform: translateY(-1px);
  box-shadow: 0 10px 26px rgba(255, 214, 107, 0.36);
  filter: brightness(1.04);
}}
.pdf-export-btn svg {{ width: 16px; height: 16px; }}

/* ── @media print : tidy export, one section per page ──────────────────── */
@media print {{
  @page {{ size: A4 landscape; margin: 12mm 10mm; }}
  html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {{
    background: #FFFFFF !important;
    color: #1A1A1A !important;
  }}
  /* Hide everything that isn't part of the printed report. */
  [data-testid="stSidebar"],
  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  .pdf-export-btn,
  .pdf-export-row,
  /* The PDF-button iframe: hide every Streamlit components iframe except
     embeds that are part of the content (none on these pages). */
  iframe[title="streamlit_app"],
  iframe[title^="st.iframe"] {{ display: none !important; }}

  /* KPI / insight cards: keep readable and don't split mid-card. */
  .kpi-card, .insight-card {{
    background: #FFFFFF !important;
    border: 1.5px solid #008F4F !important;
    box-shadow: none !important;
    color: #1A1A1A !important;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .kpi-row {{
    page-break-inside: avoid;
    break-inside: avoid;
  }}

  /* Hero printed as flat green band. */
  section[style*="background:#FFFFFF"],
  section[style*="background-color:#FFFFFF"] {{
    background: #008F4F !important;
    color: #FFFFFF !important;
  }}
  section[style*="background:#FFFFFF"] *,
  section[style*="background-color:#FFFFFF"] * {{ color: #FFFFFF !important; }}

  /* Each pillar starts on a fresh page (the very first one keeps its place
     so the hero + first KPI row print on page 1). */
  .pillar-header {{
    page-break-before: always;
    break-before: page;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .pillar-header:first-of-type {{
    page-break-before: auto;
    break-before: auto;
  }}

  /* Charts and tables: never split. */
  .stPlotlyChart, .stDataFrame, [data-testid="stPlotlyChart"] {{
    page-break-inside: avoid;
    break-inside: avoid;
  }}

  /* Force chart text legibility on print (white-on-light bug guard). */
  .js-plotly-plot text {{ fill: #1A1A1A !important; }}
  .js-plotly-plot .gridlayer path {{ stroke: #D6D9DC !important; }}
}}

/* ── Animations ─────────────────────────────────────────────────────────── */
@keyframes fadeInUp {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: translateY(0);    }}
}}
@keyframes pulseDot {{
  0%   {{ transform: scale(1);   opacity: 1; }}
  50%  {{ transform: scale(1.4); opacity: .7; }}
  100% {{ transform: scale(1);   opacity: 1; }}
}}
@keyframes shimmer {{
  0%   {{ box-shadow: 0 0 0 0 rgba(200,64,48,0.0); }}
  60%  {{ box-shadow: 0 0 0 8px rgba(200,64,48,0.10); }}
  100% {{ box-shadow: 0 0 0 0 rgba(200,64,48,0.0); }}
}}
.kpi-anim {{
  animation: fadeInUp 420ms cubic-bezier(.2,.7,.2,1) both;
}}
.kpi-row .kpi-anim:nth-child(1)  {{ animation-delay: 0ms;   }}
.kpi-row .kpi-anim:nth-child(2)  {{ animation-delay: 60ms;  }}
.kpi-row .kpi-anim:nth-child(3)  {{ animation-delay: 120ms; }}
.kpi-row .kpi-anim:nth-child(4)  {{ animation-delay: 180ms; }}
.kpi-row .kpi-anim:nth-child(5)  {{ animation-delay: 240ms; }}
.kpi-anim:hover {{
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(14,40,24,0.14);
}}
.kpi-card.danger {{ animation-name: fadeInUp, shimmer; animation-duration: 420ms, 2.6s; animation-iteration-count: 1, infinite; animation-delay: 0ms, 1.2s; }}

.section-title {{
  animation: fadeInUp 380ms ease-out both;
}}
.insight-card {{
  animation: fadeInUp 380ms ease-out both;
}}
.afdb-header {{
  animation: fadeInUp 460ms cubic-bezier(.2,.7,.2,1) both;
}}

/* Section captions and subtle text */
.stCaption, [data-testid="stCaptionContainer"] {{
  font-family: var(--mono);
  letter-spacing: 0.2px;
}}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


@lru_cache(maxsize=1)
def _particles_js_source() -> str:
    """Load and cache the local particles.min.js — avoids relying on Streamlit's
    static-file serving (which is off by default) or external CDNs."""
    p = ASSETS / "particles.min.js"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


_PARTICLES_BG_CSS = """
<style id="particles-bg-style">
  /* The gradient is painted on stApp directly (NOT body), because Streamlit's
     own bootstrap CSS sets body's background to white and we don't reliably win
     that cascade fight. stApp fills the viewport so it works just as well. */
  [data-testid="stApp"] {
    background: linear-gradient(135deg, #e3f2fd 0%, #90caf9 50%, #64b5f6 100%) !important;
    background-attachment: fixed !important;
  }

  /* Inner wrappers are transparent so the stApp gradient + particles canvas
     show through. */
  [data-testid="stAppViewContainer"],
  [data-testid="stMain"],
  [data-testid="stHeader"],
  [data-testid="stMainBlockContainer"],
  .main, .block-container,
  [class*="appview-container"],
  [class*="block-container"] {
    background: transparent !important;
    background-color: transparent !important;
  }

  /* Particle canvas container. We attach into stApp via JS so it's anchored
     inside the right stacking context. */
  #particles-bg-container {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    z-index: 0; pointer-events: none;
  }
  #particles-bg-container canvas { pointer-events: auto; }

  /* Streamlit content sits above the canvas. */
  [data-testid="stAppViewContainer"] { position: relative; z-index: 1; }
</style>
"""


def particles_bg() -> None:
    """Animated particles.js background — split into two phases:

      1. CSS via `st.markdown(unsafe_allow_html=True)`  (always reliable —
         it's the same path inject_css already uses successfully)
         → paints the gradient on `[data-testid="stApp"]` and clears every
         inner Streamlit wrapper.

      2. Particles JS via `streamlit.components.v1.html` (whose iframe ships
         with `allow-same-origin` + `allow-scripts`, so reaching into
         `window.parent.document` is allowed).
         → loads particles.min.js inlined from /assets and initialises on a
         #particles-bg-container element it attaches to the parent body.

    Idempotent across reruns thanks to a `window.parent.__particlesInit` flag.
    """
    import json
    import streamlit.components.v1 as components

    # Phase 1 — CSS. Sent through the same channel inject_css uses (st.markdown
    # with unsafe_allow_html=True), which is proven to deliver styles correctly.
    st.markdown(_PARTICLES_BG_CSS, unsafe_allow_html=True)

    # Phase 2 — JS (in a near-zero-height iframe). Streamlit's components iframe
    # is same-origin by default, so `window.parent.document` access works.
    js_source = _particles_js_source()
    if not js_source:
        st.warning("assets/particles.min.js not found — background animation disabled.")
        return

    js_literal = json.dumps(js_source)

    st.iframe(
        f"""
        <script>
        (function () {{
          var p = window.parent;
          if (p.__particlesInit) return;
          p.__particlesInit = true;
          var doc = p.document;

          // Mount container into stApp (so it lives in the right stacking context).
          var stApp = doc.querySelector('[data-testid="stApp"]') || doc.body;
          if (!doc.getElementById('particles-bg-container')) {{
            var c = doc.createElement('div');
            c.id = 'particles-bg-container';
            stApp.insertBefore(c, stApp.firstChild);
          }}

          // Inline particles.js source so we don't need any external URL.
          if (typeof p.particlesJS !== 'function') {{
            var srcScript = doc.createElement('script');
            srcScript.textContent = {js_literal};
            doc.head.appendChild(srcScript);
          }}

          if (typeof p.particlesJS === 'function') {{
            p.particlesJS('particles-bg-container', {{
              particles: {{
                number: {{ value: 110, density: {{ enable: true, value_area: 900 }} }},
                color: {{ value: '#0277bd' }},
                shape: {{ type: 'circle', stroke: {{ width: 0.5, color: '#039be5' }} }},
                opacity: {{ value: 0.55, random: true,
                            anim: {{ enable: true, speed: 1, opacity_min: 0.25 }} }},
                size:    {{ value: 3, random: true,
                                 anim: {{ enable: true, speed: 2, size_min: 1 }} }},
                line_linked: {{ enable: true, distance: 160, color: '#0288d1',
                                opacity: 0.35, width: 1.1 }},
                move: {{ enable: true, speed: 1.6, random: true, out_mode: 'bounce' }}
              }},
              interactivity: {{
                detect_on: 'canvas',
                events: {{
                  onhover: {{ enable: true, mode: 'grab' }},
                  onclick: {{ enable: true, mode: 'push' }},
                  resize: true
                }},
                modes: {{
                  grab: {{ distance: 220, line_linked: {{ opacity: 0.75 }} }},
                  push: {{ particles_nb: 4 }}
                }}
              }},
              retina_detect: true
            }});
          }} else {{
            console.error('[particles_bg] particlesJS function not available after inline script');
          }}
        }})();
        </script>
        """,
                height=1,
    )


def header_ribbon() -> None:
    """Slim white ribbon at the very top of the app — AfDB + RASME logos only.

    The marketing-style banner that used to sit underneath now lives in `hero()`,
    rendered per page so each page can carry its own headline.
    """
    afdb_uri  = _logo_data_uri("AFDB.png")
    rasme_uri = _logo_data_uri("rasme_logo.svg")
    st.markdown(
        f"""
        <div style="margin:-1rem -1rem 0 -1rem;background:#FFFFFF;
                    border-bottom:1px solid #E5E9EC;
                    display:flex;align-items:center;justify-content:space-between;
                    padding:14px 28px;">
          <img src="{afdb_uri}"  alt="African Development Bank" style="height:44px;width:auto;display:block;"/>
          <img src="{rasme_uri}" alt="RASME"                    style="height:38px;width:auto;display:block;"/>
        </div>
        """,
        unsafe_allow_html=True,
    )


def header(lang: str, last_refresh: str | None = None) -> None:
    """[Legacy] Two-tier header (white logo ribbon + green banner). Kept for
    backward-compat with code that hasn't moved to header_ribbon() + hero() yet.
    Uses inline styles so rendering survives even if Streamlit strips the global <style>."""
    refresh = last_refresh or "—"
    afdb_uri  = _logo_data_uri("AFDB.png")
    rasme_uri = _logo_data_uri("rasme_logo.svg")

    primary    = PALETTE["primary"]
    primary_dk = PALETTE["primary_dk"]

    # Inline-style strings for absolute reliability.
    SHELL = (
        "margin:-1rem -1rem 1.6rem -1rem;"
        "background:#FFFFFF;"
        "border:1px solid #E5E9EC;border-radius:0;"
        "box-shadow:0 1px 0 rgba(16,24,40,.04);"
        "overflow:hidden;"
    )
    RIBBON = (
        "display:flex;align-items:center;justify-content:space-between;"
        "padding:14px 28px;background:#FFFFFF;"
        "border-bottom:1px solid #E5E9EC;"
    )
    BANNER = (
        "display:flex;align-items:center;justify-content:space-between;gap:24px;"
        "padding:20px 28px;color:#FFFFFF;"
        f"background:linear-gradient(105deg,{primary_dk} 0%,{primary} 60%,#00A85E 100%);"
    )
    H1 = (
        "margin:0;color:#FFFFFF;"
        "font-family:'Fraunces','Source Serif Pro',Georgia,serif;"
        "font-weight:500;font-size:24px;letter-spacing:-0.3px;line-height:1.15;"
    )
    SUB = (
        "margin-top:4px;color:#FFFFFF;opacity:.85;font-size:11.5px;"
        "letter-spacing:.5px;text-transform:uppercase;"
        "font-family:'DM Sans',system-ui,sans-serif;"
    )
    META = (
        "text-align:right;color:#FFFFFF;opacity:.92;"
        "font-family:'DM Mono',ui-monospace,monospace;"
        "font-size:11px;line-height:1.7;letter-spacing:.2px;"
    )
    LOGO_AFDB  = "height:44px;width:auto;display:block;"
    LOGO_RASME = "height:38px;width:auto;display:block;"

    st.markdown(
        f"""
        <div style="{SHELL}">
          <div style="{RIBBON}">
            <img src="{afdb_uri}"  alt="African Development Bank" style="{LOGO_AFDB}"/>
            <img src="{rasme_uri}" alt="RASME"                    style="{LOGO_RASME}"/>
          </div>
          <div style="{BANNER}">
            <div>
              <h1 style="{H1}">{t('app_title', lang)}</h1>
              <div style="{SUB}">{t('subtitle', lang)}</div>
            </div>
            <div style="{META}">
              {t('last_refresh', lang)} · <b style="font-weight:500">{refresh}</b>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def language_toggle() -> str:
    """Sidebar language switch. Stored in session_state so all pages stay in sync."""
    if "lang" not in st.session_state:
        st.session_state.lang = "FR"
    chosen = st.sidebar.radio(
        "Langue / Language",
        options=("FR", "EN"),
        index=0 if st.session_state.lang == "FR" else 1,
        horizontal=True,
        key="lang_radio",
    )
    st.session_state.lang = chosen
    return chosen


def set_html_lang(lang: str) -> None:
    """Force the host page's ``<html lang>`` attribute so Streamlit widgets
    (notably the date_input calendar popup) render month and weekday names in
    the chosen language. Streamlit components run in an iframe, so we reach
    the parent document via ``window.parent``. The injected iframe is 0-px
    high and visually invisible.
    """
    import streamlit.components.v1 as components
    locale = "fr-FR" if lang == "FR" else "en-US"
    st.iframe(
        f"<script>window.parent.document.documentElement.lang='{locale}';</script>",
        height=1,
    )


def sidebar_filters(lang: str) -> dict[str, Any]:
    """Render the global filter bar (period + region + sector + status). Returns a dict."""
    from config import (
        status_label, sector_label, region_label, country_to_region_lookup,
    )
    from db import region_table  # local import to avoid circular

    st.sidebar.markdown(f"### {t('filters', lang)}")

    lo, hi = date_bounds()
    today = date.today()
    default_lo = lo or (today - timedelta(days=365 * 3))
    default_hi = hi or today
    if default_hi < default_lo:
        default_hi = default_lo

    c1, c2 = st.sidebar.columns(2)
    df = c1.date_input(
        t("from", lang),
        value=default_lo, min_value=default_lo, max_value=default_hi,
        key="filter_date_from",
    )
    dt_ = c2.date_input(
        t("to",  lang),
        value=default_hi, min_value=default_lo, max_value=default_hi,
        key="filter_date_to",
    )
    # Small reset button: drop the widget state so both inputs fall back to the
    # full data range on the next rerun (equivalent to “no date filter”).
    if st.sidebar.button(t("clear_dates", lang), key="filter_date_clear",
                         width="stretch"):
        st.session_state.pop("filter_date_from", None)
        st.session_state.pop("filter_date_to", None)
        st.rerun()

    opts = filter_options()

    # ── Region filter ───────────────────────────────────────────────────────
    # Build {region_code → [country_slugs]} once. Empty if PG Region table
    # isn't reachable — fail open so the dashboard still works.
    countries_in_data = set(opts.get("country", []))
    slug_to_region = country_to_region_lookup(region_table())
    region_to_slugs: dict[str, list[str]] = {}
    for slug, code in slug_to_region.items():
        if slug in countries_in_data:
            region_to_slugs.setdefault(code, []).append(slug)
    # Display labels, ordered alphabetically by FR/EN label.
    region_display_to_code: dict[str, str] = {}
    for code in sorted(region_to_slugs.keys(),
                       key=lambda c: region_label(c, lang).lower()):
        region_display_to_code[region_label(code, lang)] = code

    selected_region_display = st.sidebar.multiselect(
        t("region", lang),
        list(region_display_to_code.keys()),
        placeholder=t("all", lang),
    )
    selected_region_codes = [region_display_to_code[d] for d in selected_region_display]
    # Convert selected regions to a flat list of country slugs for the SQL
    # filter (the `countries_in` key, handled by _where()).
    countries_in: list[str] = []
    for code in selected_region_codes:
        countries_in.extend(region_to_slugs.get(code, []))
    countries_in = sorted(set(countries_in))

    # Sector — bucketed list. Display the translated label but keep the raw
    # bucket value as the SQL filter input.
    raw_sectors = opts.get("sector", [])
    sector_display_to_raw = {sector_label(s, lang): s for s in raw_sectors}
    selected_sector_display = st.sidebar.multiselect(
        t("sector", lang),
        list(sector_display_to_raw.keys()),
        placeholder=t("all", lang),
    )
    sectors = [sector_display_to_raw[d] for d in selected_sector_display]

    # Status — show translated labels (de-duplicated) but pass *all* raw values
    # back to the SQL filter. Multiple raw statuses can share one display label
    # (e.g. 'Stalled' and 'Stalled/ suspended' both render as 'Stalled') —
    # picking one display label includes every raw status mapped to it.
    raw_statuses = opts.get("status", [])
    display_to_raws: dict[str, list[str]] = {}
    for raw in raw_statuses:
        disp = status_label(raw, lang)
        display_to_raws.setdefault(disp, []).append(raw)

    selected_display = st.sidebar.multiselect(
        t("status", lang),
        list(display_to_raws.keys()),
        placeholder=t("all", lang),
    )
    selected_raw: list[str] = []
    for disp in selected_display:
        selected_raw.extend(display_to_raws.get(disp, []))

    return {
        "date_from":    df,
        "date_to":      dt_,
        "sectors":      sectors or None,
        "categories":   None,
        "funders":      None,
        "statuses":     selected_raw or None,
        "countries_in": countries_in or None,
    }


_TONE_BAR = {
    "":        PALETTE["primary"],
    "success": PALETTE["success"],
    "warning": PALETTE["warning"],
    "danger":  PALETTE["danger"],
}
_DELTA_COLOR = {"up": PALETTE["success"], "down": PALETTE["danger"], "": "#6B7780"}


# ── Lucide-style minimal stroke icons (MIT) used inside KPI cards. ───────────
# Each value is just the inner SVG content — the wrapping <svg> is added below.
_ICON_PATHS = {
    "sites":      '<path d="M20 10c0 7-8 13-8 13s-8-6-8-13a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "country":    '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "project":    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6"/><path d="M9 17h6"/>',
    "completion": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "risk":       '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "overdue":    '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/><path d="M16 16l-4-4"/>',
    "duration":   '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
    "ontime":     '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l3 3"/>',
    "infra":      '<path d="M2 22h20"/><path d="M6 22V8a2 2 0 0 1 2-2h2"/><path d="M14 6h2a2 2 0 0 1 2 2v14"/><path d="M10 22V6"/><path d="M14 22V6"/>',
    "equipment":  '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "delivery":   '<path d="M16.5 9.4 7.5 4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.27 6.96 12 12.01l8.73-5.05"/><path d="M12 22.08V12"/>',
    "users":      '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "globe":      '<circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
}


def _icon_svg(name: str, color: str = "currentColor", size: int = 18) -> str:
    """Return a small inline SVG icon for use inside a KPI card."""
    inner = _ICON_PATHS.get(name, "")
    if not inner:
        return ""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'style="opacity:.9;">{inner}</svg>'
    )


def kpi_card(label: str, value: str, *, tone: str = "", delta: str | None = None,
             delta_dir: str = "", icon: str | None = None,
             explainer: str | None = None) -> str:
    """Indicator card — eyebrow label · big value · optional explainer line + delta chip.

    Inspired by World Bank Scorecard indicator cards: eyebrow → value → context.
    """
    bar_color   = _TONE_BAR.get(tone, PALETTE["primary"])
    delta_color = _DELTA_COLOR.get(delta_dir, "#6B7780")

    delta_html = ""
    if delta:
        arrow_bg = (
            f"{bar_color}14" if delta_dir in ("", "up") else f"{PALETTE['danger']}14"
        )
        delta_html = (
            f'<div style="display:inline-flex;align-items:center;gap:6px;margin-top:10px;'
            f'padding:3px 10px;border-radius:999px;background:{arrow_bg};'
            f'font-family:\'DM Mono\',ui-monospace,monospace;font-size:10.5px;'
            f'color:{delta_color};letter-spacing:.2px;">'
            f'{delta}</div>'
        )

    icon_html = ""
    if icon:
        icon_html = (
            f'<span style="position:absolute;top:16px;right:16px;color:{bar_color};'
            f'opacity:.85;display:inline-flex;align-items:center;justify-content:center;'
            f'width:32px;height:32px;border-radius:50%;background:{bar_color}14;">'
            f'{_icon_svg(icon, color=bar_color, size=16)}'
            f'</span>'
        )

    primary    = PALETTE["primary"]
    primary_dk = PALETTE["primary_dk"]
    muted_clr  = PALETTE["muted"]

    # Override the icon HTML position for centred-pill layout (stack at top-right corner).
    icon_html_centered = ""
    if icon:
        icon_html_centered = (
            f'<span style="position:absolute;top:14px;right:18px;color:{primary};'
            f'opacity:.85;display:inline-flex;align-items:center;justify-content:center;'
            f'width:30px;height:30px;border-radius:50%;background:{primary}14;">'
            f'{_icon_svg(icon, color=primary, size=14)}'
            f'</span>'
        )

    explainer_html = (
        f'<div style="margin-top:6px;font-size:11.5px;line-height:1.45;color:{muted_clr};'
        f"font-family:'DM Sans',system-ui,sans-serif;text-align:center;\">{explainer}</div>"
    ) if explainer else ""

    delta_centered = ""
    if delta:
        delta_centered = (
            f'<div style="display:inline-flex;align-items:center;gap:6px;margin-top:8px;'
            f'padding:3px 10px;border-radius:999px;background:{bar_color}14;'
            f'font-family:\'DM Mono\',ui-monospace,monospace;font-size:10.5px;'
            f'color:{delta_color};letter-spacing:.2px;">{delta}</div>'
        )

    return (
        f'<div class="kpi-card kpi-anim {tone}" style="'
        f'position:relative;background:#FFFFFF;'
        f'border:2px solid {bar_color};border-radius:22px;'
        f'padding:18px 22px 18px 22px;box-shadow:0 1px 2px rgba(0,143,79,0.04);'
        f'transition:transform .18s ease,box-shadow .18s ease;'
        f'display:flex;flex-direction:column;align-items:center;justify-content:center;'
        f'min-height:140px;text-align:center;'
        f'">'
        f'{icon_html_centered}'
        f'<div style="font-size:14px;font-weight:600;color:{primary};'
        f'letter-spacing:.2px;margin-bottom:8px;padding:0 28px;'
        f"font-family:'DM Sans',system-ui,sans-serif;\">{label}</div>"
        f'<div style="font-family:\'DM Sans\',system-ui,sans-serif;font-weight:700;'
        f'font-size:46px;color:{primary_dk};line-height:1;letter-spacing:-1px;'
        f'font-variant-numeric:tabular-nums;">{value}</div>'
        f'{explainer_html}'
        f'<div>{delta_centered}</div>'
        f'</div>'
    )


def kpi_row(cards_html: list[str], cols: int | None = None) -> None:
    """Render N KPI cards in a single row. By default the column count = number of cards."""
    n = cols if cols is not None else max(1, len(cards_html))
    st.markdown(
        f'<div class="kpi-row" style="display:grid;grid-template-columns:repeat({n},1fr);'
        f'gap:14px;margin-bottom:22px;">' + "".join(cards_html) + "</div>",
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    """Lightweight section divider — small uppercase title with green underline.
    pillar_header() is preferred for primary section breaks (full green band)."""
    primary = PALETTE["primary"]
    text    = PALETTE["text"]
    border  = PALETTE["border"]
    st.markdown(
        f'<div class="section-title" style="'
        f'position:relative;font-size:12px;font-weight:700;color:{primary};'
        f'text-transform:uppercase;letter-spacing:1.4px;margin:24px 0 12px 0;'
        f'padding-bottom:8px;border-bottom:2px solid {primary};'
        f"font-family:'DM Sans',system-ui,sans-serif;display:flex;align-items:center;gap:10px;\">"
        f'<span>{title}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def insight(text_html: str, tone: str = "") -> None:
    accent  = _TONE_BAR.get(tone, PALETTE["primary"])
    border  = PALETTE["border"]
    text    = PALETTE["text"]
    st.markdown(
        f'<div class="insight-card {tone}" style="'
        f'background:#FFFFFF;'
        f'border:1px solid {border};border-left:4px solid {accent};'
        f'border-radius:10px;padding:14px 18px 14px 20px;margin-bottom:10px;'
        f'font-size:13.5px;line-height:1.55;color:{text};'
        f"font-family:'DM Sans',system-ui,sans-serif;\">"
        f'{text_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def hero(eyebrow: str, headline: str, sub: str, last_refresh: str | None = None) -> None:
    """Editorial hero strip — eyebrow + serif headline + supporting paragraph.

    Inspired by the World Bank Scorecard hero: dark institutional ground, prominent
    serif headline, eyebrow tracker, last-refresh chip on the right.
    """
    primary    = PALETTE["primary"]
    primary_dk = PALETTE["primary_dk"]
    refresh_chip = ""
    if last_refresh:
        refresh_chip = (
            f'<div style="display:inline-flex;align-items:center;gap:8px;'
            f'padding:6px 14px;border:1px solid rgba(255,255,255,.30);border-radius:999px;'
            f'background:rgba(255,255,255,.14);'
            f"font-family:'DM Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.3px;"
            f'color:#FFFFFF;">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:#7CFFB0;'
            f'box-shadow:0 0 8px rgba(124,255,176,.7);animation:pulseDot 2s ease-in-out infinite;"></span>'
            f'<b style="font-weight:500;">{last_refresh}</b></div>'
        )
    refresh_chip_light = ""
    if last_refresh:
        refresh_chip_light = (
            f'<div style="display:inline-flex;align-items:center;gap:8px;'
            f'padding:6px 14px;border:1px solid {primary}40;border-radius:999px;'
            f'background:{primary}10;'
            f"font-family:'DM Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.3px;"
            f'color:{primary_dk};">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{primary};'
            f'box-shadow:0 0 8px rgba(0,143,79,0.6);animation:pulseDot 2s ease-in-out infinite;"></span>'
            f'<b style="font-weight:500;">{last_refresh}</b></div>'
        )

    st.markdown(
        f"""
        <section style="position:relative;margin:6px 0 24px 0;padding:28px 32px 26px;
                        color:#1A1A1A;border:1px solid {PALETTE['border']};border-radius:14px;
                        background:#FFFFFF;
                        box-shadow:0 1px 3px rgba(0,143,79,0.04);">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:24px;flex-wrap:wrap;">
            <div style="max-width:820px;">
              <div style="display:inline-block;padding:4px 12px;border-radius:4px;
                          background:{primary}15;color:{primary_dk};
                          font-family:'DM Sans',system-ui,sans-serif;
                          font-size:10.5px;letter-spacing:1.6px;text-transform:uppercase;font-weight:700;
                          margin-bottom:14px;">{eyebrow}</div>
              <h1 style="margin:0;color:{primary_dk};
                          font-family:'DM Sans',system-ui,sans-serif;
                          font-weight:700;font-size:30px;line-height:1.15;letter-spacing:-0.4px;">
                {headline}
              </h1>
              <p style="margin:10px 0 0 0;max-width:680px;color:{PALETTE['muted']};
                        font-family:'DM Sans',system-ui,sans-serif;
                        font-size:13.5px;line-height:1.55;">{sub}</p>
            </div>
            <div>{refresh_chip_light}</div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def pillar_header(eyebrow: str, title: str, description: str | None = None) -> None:
    """Solid AfDB-green band header. Panel-style — like the RASME corporate
    dashboard reference: green strip with white centred title, optional
    eyebrow above and description below."""
    primary = PALETTE["primary"]
    text    = PALETTE["text"]
    muted   = PALETTE["muted"]
    border  = PALETTE["border"]

    eyebrow_html = (
        f'<div style="display:inline-block;padding:3px 10px;border-radius:4px;'
        f'background:{primary}1A;color:{primary};'
        f"font-family:'DM Sans',system-ui,sans-serif;"
        f'font-size:10px;font-weight:700;letter-spacing:1.4px;'
        f'text-transform:uppercase;margin-bottom:10px;">{eyebrow}</div>'
    ) if eyebrow else ""

    desc = (
        f'<p style="margin:10px 0 0 0;color:{muted};font-size:13px;line-height:1.55;'
        f"font-family:'DM Sans',system-ui,sans-serif;max-width:880px;\">{description}</p>"
    ) if description else ""

    st.markdown(
        f"""
        <div class="pillar-header" style="margin:34px 0 14px 0;animation:fadeInUp 380ms ease-out both;">
          {eyebrow_html}
          <div style="background:{primary};color:#FFFFFF;
                      padding:12px 22px;border-radius:8px;
                      box-shadow:0 2px 6px rgba(0,143,79,0.18);
                      display:flex;align-items:center;justify-content:center;text-align:center;
                      font-family:'DM Sans',system-ui,sans-serif;font-weight:700;
                      font-size:16px;letter-spacing:.2px;">{title}</div>
          {desc}
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer(lang: str, last_refresh: str | None = None) -> None:
    """Discreet footer — copyright + last-refresh chip on the right."""
    refresh_chip = ""
    if last_refresh:
        refresh_chip = (
            f"<span style=\"font-family:'DM Mono',ui-monospace,monospace;font-size:10.5px;"
            f"letter-spacing:.4px;\">{t('last_refresh', lang)} · <b style='font-weight:500'>{last_refresh}</b></span>"
        )
    copy_text = "© " + ("Banque africaine de développement · Plateforme RASME"
                         if lang == "FR" else
                         "African Development Bank · RASME Platform")
    border = PALETTE["border"]
    muted  = PALETTE["muted"]
    st.markdown(
        f"""
        <div style="margin:48px -1rem 0 -1rem;padding:20px 32px;
                    border-top:1px solid {border};background:#FFFFFF;
                    display:flex;justify-content:space-between;align-items:center;
                    font-family:'DM Sans',system-ui,sans-serif;font-size:12px;color:{muted};
                    letter-spacing:.2px;flex-wrap:wrap;gap:8px;">
          <div>{copy_text}</div>
          <div>{refresh_chip}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def fmt_int(n: Any) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def fmt_pct(n: Any) -> str:
    try:
        return f"{float(n):.1f} %"
    except (TypeError, ValueError):
        return "—"


def fmt_delta(value: float | None, ref: float | None, *, suffix: str = "pts") -> tuple[str, str]:
    if value is None or ref is None:
        return ("", "")
    d = float(value) - float(ref)
    arrow = "▲" if d >= 0 else "▼"
    direction = "up" if d >= 0 else "down"
    return (f"{arrow} {abs(d):.1f} {suffix}", direction)


# ─── PDF export ─────────────────────────────────────────────────────────────

_PDF_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
    '<path d="M14 2v6h6"/><path d="M12 18v-6"/><path d="m9 15 3 3 3-3"/></svg>'
)


def pdf_export_button(lang: str = "FR") -> None:
    """Right-aligned PDF export button.

    Streamlit's `st.markdown(unsafe_allow_html=True)` silently strips inline
    `onclick` handlers, so the button has to live inside a `components.v1.html`
    iframe — its JS *does* execute, and `window.parent.print()` opens the
    browser print dialog on the parent dashboard (not the iframe). Combined
    with the @media print rules in inject_css, the printed output omits the
    sidebar / button / header.
    """
    import streamlit.components.v1 as components

    label = "Exporter en PDF" if lang == "FR" else "Export as PDF"
    aria  = "Imprimer ou enregistrer en PDF" if lang == "FR" else "Print or save as PDF"
    primary    = PALETTE["primary"]
    primary_dk = PALETTE["primary_dk"]

    st.iframe(
        f"""
        <style>
          html, body {{
            margin: 0; padding: 0; background: transparent;
            font-family: 'DM Sans', system-ui, sans-serif;
          }}
          .pdf-row {{
            display: flex; justify-content: flex-end;
            padding: 4px 4px 0 0;
          }}
          .pdf-btn {{
            display: inline-flex; align-items: center; gap: 8px;
            padding: 9px 18px; border-radius: 999px; cursor: pointer;
            background: #FFFFFF; color: {primary_dk};
            border: 2px solid {primary};
            font-family: inherit; font-weight: 600; font-size: 13px;
            letter-spacing: .2px;
            transition: background .15s ease, color .15s ease,
                        transform .15s ease, box-shadow .15s ease;
          }}
          .pdf-btn:hover {{
            background: {primary}; color: #FFFFFF;
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(0,143,79,0.22);
          }}
          .pdf-btn svg {{ width: 16px; height: 16px; }}
        </style>
        <div class="pdf-row">
          <button class="pdf-btn"
                  type="button"
                  aria-label="{aria}"
                  onclick="window.parent.print()">
            {_PDF_ICON}
            <span>{label}</span>
          </button>
        </div>
        """,
        height=54,
    )


# ─── Plotly dark theme ───────────────────────────────────────────────────────

def dark_plotly(fig, *, title_size: int = 14):
    """Apply the unified theme to any Plotly figure (transparent bg, deep-green text,
    subtle gridlines, serif title). The function name stays `dark_plotly` for import
    stability but the palette is now the light pastel scheme."""
    text  = PALETTE["text"]
    muted = PALETTE["muted"]
    grid  = "rgba(14,40,24,0.08)"
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, system-ui, sans-serif", color=text, size=12),
        title_font=dict(family="Fraunces, Georgia, serif", size=title_size, color=text),
        legend=dict(font=dict(color=text, size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor=grid, zerolinecolor=grid, color=muted),
        yaxis=dict(gridcolor=grid, zerolinecolor=grid, color=muted),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="rgba(14,40,24,0.15)",
                        font=dict(color=text)),
    )
    return fig
