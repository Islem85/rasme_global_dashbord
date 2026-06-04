"""
Leaflet.js map helpers for the dashboard.

Uses Folium (the Python binding to Leaflet.js) + streamlit-folium for embedding.
Base tile: Esri World Light Gray Canvas — pale, neutral background that makes
coloured site dots pop, exactly as in the user's reference screenshot.

Public API:

    leaflet_map(points_df, lang, *, height=600, center=None, zoom=3,
                point_cap=5000, key=None)

Where `points_df` has at minimum: lat, lon, status, project_title, country,
site_name, sector. Translation to display labels is done internally.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from config import PALETTE, country_label, status_color_map, status_label


# ── Esri "Canvas Light Gray" tile URLs (no API key needed) ─────────────────
ESRI_LIGHT_GRAY_BASE = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/"
    "World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
)
ESRI_LIGHT_GRAY_REF = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/"
    "World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
)
ESRI_ATTR = "Tiles © Esri — Esri, DeLorme, NAVTEQ"


def _escape(s) -> str:
    """Minimal HTML-escape for popup content."""
    if s is None:
        return ""
    s = str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def _legend_html(status_counts: dict[str, str], color_map: dict, lang: str) -> str:
    """Build a fixed map legend listing each status, its colour and its count.

    `status_counts` is an *ordered* dict {displayed_status: count}. The legend
    is injected as a floating panel (bottom-left) over the Leaflet canvas.
    """
    title = "Statut" if lang == "FR" else "Status"
    total_lbl = "Total" if lang == "FR" else "Total"
    total = sum(status_counts.values()) if status_counts else 0

    rows = []
    for st_disp, cnt in status_counts.items():
        color = color_map.get(st_disp, PALETTE["neutral"])
        rows.append(
            "<div style='display:flex;align-items:center;gap:7px;margin:2px 0;'>"
            f"<span style='width:11px;height:11px;border-radius:50%;"
            f"background:{color};border:1px solid rgba(0,0,0,.25);"
            "display:inline-block;flex:0 0 auto;'></span>"
            f"<span style='flex:1 1 auto;color:#1A1A1A;'>{_escape(st_disp)}</span>"
            f"<span style='font-weight:700;color:#0E2818;'>{cnt:,}</span>"
            "</div>"
        )
    rows_html = "".join(rows)

    return (
        "<div style='position:absolute;bottom:22px;left:12px;z-index:9999;"
        "background:rgba(255,255,255,.95);padding:10px 12px;border-radius:10px;"
        "box-shadow:0 2px 10px rgba(0,0,0,.18);border:1px solid #E2E8E0;"
        "font-family:DM Sans,system-ui,sans-serif;font-size:12px;min-width:170px;'>"
        f"<div style='font-weight:700;color:#005C33;text-transform:uppercase;"
        f"letter-spacing:.04em;font-size:10.5px;margin-bottom:6px;'>{title}</div>"
        f"{rows_html}"
        "<div style='border-top:1px solid #E2E8E0;margin-top:6px;padding-top:5px;"
        "display:flex;justify-content:space-between;'>"
        f"<span style='color:#5C6770;'>{total_lbl}</span>"
        f"<span style='font-weight:700;color:#0E2818;'>{total:,}</span></div>"
        "</div>"
    )


def leaflet_map(
    points_df,
    lang: str,
    *,
    height: int = 600,
    center: Optional[tuple[float, float]] = None,
    zoom: int = 3,
    point_cap: int = 30000,
    key: str | None = None,
    show_country_in_popup: bool = True,
) -> None:
    """Render a Leaflet.js map (via Folium) with Esri Light Gray Canvas tiles
    and one CircleMarker per site, coloured by status.

    Markers are grouped into a `MarkerCluster` so the map stays responsive even
    with the full ~24.5 k-point dataset (clusters aggregate dots at low zoom and
    expand on zoom-in). A floating legend maps each status to its colour. The
    `point_cap` is a safety ceiling — it is set above the current data volume so
    every country, including small ones (Egypt, RCA), is shown.
    """
    import folium
    from folium.plugins import FastMarkerCluster
    from streamlit_folium import st_folium

    if points_df is None or points_df.empty:
        st.info("—")
        return

    pts = points_df.copy()

    # Cap rows (most-recent first if caller has already sorted; otherwise random
    # truncation — caller usually passes pre-sorted rows).
    if len(pts) > point_cap:
        pts = pts.head(point_cap)

    # Translate status + country and resolve marker colour — all vectorised so
    # we never touch the dataframe row-by-row (the previous iterrows + one
    # folium.CircleMarker per point made the ~24.5 k-site global map take ~3 min
    # to build and emit a 34 MB HTML blob). FastMarkerCluster ships a compact
    # coordinate array and builds the markers client-side via the JS callback
    # below, so the same map renders in ~1 s with a ~5 MB payload.
    color_map = status_color_map(lang)
    unknown = "Inconnu" if lang == "FR" else "Unknown"
    pts["_status_disp"] = pts["status"].map(lambda s: status_label(s, lang)).fillna(unknown)
    pts.loc[pts["_status_disp"] == "", "_status_disp"] = unknown
    pts["_color"] = pts["_status_disp"].map(lambda d: color_map.get(d, PALETTE["neutral"]))
    if "country_label" not in pts.columns:
        pts["country_label"] = pts.get("country", "").map(
            lambda c: country_label(c, lang) if c else ""
        )
    if not show_country_in_popup:
        pts["country_label"] = ""

    # Pre-escape every string that lands in popup HTML (the JS callback inserts
    # them verbatim) so a project/site name can never break the markup or inject.
    def _clean(col: str, fallback: str) -> None:
        if col not in pts.columns:
            pts[col] = fallback
            return
        s = pts[col].fillna("")
        s = s.where(s.astype(str).str.strip() != "", fallback)
        pts[col] = s.map(_escape)

    _clean("project_title", "—")
    _clean("site_name", "—")
    _clean("country_label", "")
    _clean("sector", "")

    # Default centre = Africa wide view if no centre given.
    if center is None:
        center = (4.0, 20.0)

    m = folium.Map(
        location=list(center),
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
        prefer_canvas=True,   # canvas renderer is faster for many markers
    )
    folium.TileLayer(
        tiles=ESRI_LIGHT_GRAY_BASE,
        attr=ESRI_ATTR,
        name="Esri Light Gray",
        max_zoom=16,
        control=False,
    ).add_to(m)
    folium.TileLayer(
        tiles=ESRI_LIGHT_GRAY_REF,
        attr=ESRI_ATTR,
        name="Esri labels",
        max_zoom=16,
        overlay=True,
        control=False,
    ).add_to(m)

    # Row layout passed to the JS callback:
    #   [0]=lat [1]=lon [2]=color [3]=status [4]=project [5]=site [6]=country [7]=sector
    data = pts[[
        "lat", "lon", "_color", "_status_disp",
        "project_title", "site_name", "country_label", "sector",
    ]].values.tolist()

    # Built client-side: one L.circleMarker per row with the same styling +
    # popup the old Python loop produced (French popup labels kept verbatim).
    callback = (
        "function(row){"
        "var html=\"<div style='font-family:DM Sans,system-ui,sans-serif;"
        "font-size:12px;line-height:1.5;max-width:260px;'>\""
        "+\"<div style='font-weight:700;color:#0E2818;font-size:12.5px;"
        "margin-bottom:4px;'>\"+row[4]+\"</div>\";"
        "if(row[6]){html+=\"<div style='color:#5C6770;font-size:11px;"
        "margin-bottom:4px;'>\"+row[6]+\"</div>\";}"
        "html+=\"<div><b>Site :</b> \"+row[5]+\"</div>\""
        "+\"<div><b>Statut :</b> <span style='color:\"+row[2]+\";font-weight:700'>\""
        "+row[3]+\"</span></div>\";"
        "if(row[7]){html+=\"<div><b>Secteur :</b> \"+row[7]+\"</div>\";}"
        "html+=\"</div>\";"
        "var marker=L.circleMarker(new L.LatLng(row[0],row[1]),"
        "{radius:4,color:row[2],weight:1,fill:true,fillColor:row[2],fillOpacity:0.78});"
        "marker.bindPopup(html);marker.bindTooltip(row[5]);"
        "return marker;}"
    )

    FastMarkerCluster(
        data=data,
        callback=callback,
        name="Sites",
        options={
            "chunkedLoading": True,
            "showCoverageOnHover": False,
            "spiderfyOnMaxZoom": True,
            "maxClusterRadius": 45,
        },
    ).add_to(m)

    # Legend counts — vectorised value_counts, sorted descending.
    counts = pts["_status_disp"].value_counts()
    status_counts = {str(k): int(v) for k, v in counts.items()}
    m.get_root().html.add_child(
        folium.Element(_legend_html(status_counts, color_map, lang))
    )

    st_folium(
        m,
        height=height,
        use_container_width=True,
        returned_objects=[],      # don't round-trip click state — avoids reruns
        key=key,
    )
