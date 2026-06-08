"""
PostgreSQL access layer.

All queries:
- merge form versions (no WHERE on `version` — explicit project rule)
- exclude invalid status sentinels ('#status', 'None', '')
- accept optional filters (period, sector, category, funder, country, status)
- wrap text date columns through dt() (the source stores 'YYYY-MM-DD HH:MM:SS' as
  text with 'NaT' as the null sentinel)
- are wrapped in @st.cache_data with TTL so the dashboard auto-refreshes
"""

from __future__ import annotations

import base64
import io
import os
from datetime import date
from typing import Any, Optional
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageOps
from requests.auth import HTTPBasicAuth
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

from config import (
    AFRICA_LAT_MAX,
    AFRICA_LAT_MIN,
    AFRICA_LON_MAX,
    AFRICA_LON_MIN,
    COL,
    INVALID_STATUS,
    TABLE,
    country_bucket,
    dt,
    sector_bucket,
)

# Projets BAD reference table populated by load_rod.py from the Regional
# Operations Dashboard Excel file. Quoted because of the mixed-case
# identifier — every reference to it must use this constant.
BAD_TABLE = 'public."projet_BAD"'

load_dotenv()

# Streamlit Community Cloud (and other hosted Streamlit) expose configuration
# through st.secrets, not environment variables. Mirror any scalar secret into
# os.environ (without overriding a value already set by a real env var or .env)
# so the rest of this module can keep reading os.getenv(...). No-op locally when
# there is no secrets.toml.
try:
    for _sk, _sv in st.secrets.items():
        if isinstance(_sv, (str, int, float, bool)):
            os.environ.setdefault(_sk, str(_sv))
except Exception:
    pass

CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))

# Bounding box Afrique : AFRICA_* importées de config (source unique). Sert à
# garder la carte (map_points) propre des erreurs de saisie GPS hors continent.


@st.cache_resource(show_spinner=False)
def engine() -> Engine:
    # Priorité : DATABASE_URL (Neon/cloud) > variables PG_* individuelles
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        dsn = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        user = quote_plus(os.getenv("PG_USER", "postgres"))
        pwd  = quote_plus(os.getenv("PG_PASSWORD", ""))
        host = os.getenv("PG_HOST", "localhost")
        port = os.getenv("PG_PORT", "5432")
        db_  = os.getenv("PG_DB",   "mapping")
        ssl  = os.getenv("PG_SSLMODE", "prefer")
        dsn  = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db_}?sslmode={ssl}"
    return create_engine(dsn, pool_pre_ping=True, pool_recycle=1800)


# ──────────────────────────────────────────────────────────────────────────────
# Kobo attachment thumbnails.
#
# Photo URLs stored in the DB point at the KoboToolbox v2 attachment endpoint,
# which requires Basic Auth — so a browser <img src="…"> fetch returns 404 and
# the preview breaks. We fetch the bytes here (server-side, with credentials),
# downscale to a thumbnail, and hand the caller a base64 data URI the browser
# can render inline without any further request. Returns None on any failure so
# the caller can show a fallback (Streamlit strips inline onerror handlers, so
# the fallback must be decided server-side).
# ──────────────────────────────────────────────────────────────────────────────

THUMB_MAX_PX = int(os.getenv("TL_THUMB_MAX_PX", "360"))


@st.cache_data(ttl=86_400, show_spinner=False, max_entries=1024)
def kobo_thumb_data_uri(url: Optional[str]) -> Optional[str]:
    """Return a base64 ``data:image/jpeg`` thumbnail for a Kobo attachment URL,
    or None if it's missing / unauthorised / not an image."""
    if not url:
        return None

    user  = os.getenv("KOBO_USER", "")
    pwd   = os.getenv("KOBO_PASSWORD", "")
    token = os.getenv("KOBO_TOKEN", "")

    # Authentifier dès qu'on a des identifiants (ne pas se limiter aux URLs
    # contenant "kobotoolbox", car les instances peuvent avoir un autre domaine).
    headers = {"Authorization": f"Token {token}"} if token else {}
    auth = HTTPBasicAuth(user, pwd) if (user and pwd and not token) else None

    try:
        resp = requests.get(
            url, auth=auth, headers=headers,
            timeout=30, allow_redirects=True,
        )
        if resp.status_code != 200:
            print(f"[KOBO] HTTP {resp.status_code} pour {url}")   # visible dans les logs
            return None
        ctype = resp.headers.get("content-type", "")
        if not ctype.startswith("image/"):
            print(f"[KOBO] content-type inattendu '{ctype}' pour {url}")
            return None
        img = Image.open(io.BytesIO(resp.content))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=72, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"[KOBO] exception {type(e).__name__}: {e} pour {url}")  # au lieu d'un return muet
        return None
    user = os.getenv("KOBO_USER", "")
    pwd = os.getenv("KOBO_PASSWORD", "")
    if needs_auth and not (user and pwd):
        return None
    auth = HTTPBasicAuth(user, pwd) if (needs_auth and user and pwd) else None
    try:
        resp = requests.get(url, auth=auth, timeout=30)
        if resp.status_code != 200:
            return None
        if not resp.headers.get("Content-Type", "").startswith("image/"):
            return None
        img = Image.open(io.BytesIO(resp.content))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=72, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Filter assembly — every page uses the same filter spec.
# ──────────────────────────────────────────────────────────────────────────────

def _where(filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return ('WHERE …', params). Always excludes invalid statuses; never filters version."""
    clauses = [
        f"{COL['status']} IS NOT NULL",
        f"{COL['status']} NOT IN :_invalid_status",
    ]
    params: dict[str, Any] = {"_invalid_status": tuple(INVALID_STATUS)}

    if filters.get("date_from"):
        # Filtre date appuyé sur la colonne « today » Kobo (date d'ouverture
        # du formulaire par l'enquêteur), cohérent avec date_bounds() et la
        # timeline d'activité de collecte.
        clauses.append(f"{dt(COL['today'])} >= :date_from")
        params["date_from"] = filters["date_from"]
    if filters.get("date_to"):
        clauses.append(f"{dt(COL['today'])} <= :date_to")
        params["date_to"] = filters["date_to"]
    if filters.get("sectors"):
        # Filter on bucketed sector so 'Multi-sector' selection catches all concatenated values.
        clauses.append(f"{sector_bucket()} IN :sectors")
        params["sectors"] = tuple(filters["sectors"])
    if filters.get("statuses"):
        clauses.append(f"{COL['status']} IN :statuses")
        params["statuses"] = tuple(filters["statuses"])
    if filters.get("country"):
        # country_bucket() folds somaliland into somalia so picking 'somalia'
        # catches both raw values.
        clauses.append(f"{country_bucket()} = :country")
        params["country"] = filters["country"]
    if filters.get("countries_in"):
        # Used by the region filter: a list of country slugs (bucketed).
        clauses.append(f"{country_bucket()} IN :countries_in")
        params["countries_in"] = tuple(filters["countries_in"])
    if filters.get("project"):
        clauses.append(f"{COL['project_title']} = :project")
        params["project"] = filters["project"]
    if filters.get("projects_in"):
        # Used when several project titles share the same SAP code and the
        # country view dropdown narrows the page to that grouped entry.
        clauses.append(f"{COL['project_title']} IN :projects_in")
        params["projects_in"] = tuple(filters["projects_in"])

    return "WHERE " + " AND ".join(clauses), params


def _q(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Run SQL with named params. Tuple/list params auto-bound as expanding for IN clauses."""
    params = params or {}
    stmt = text(sql)
    expanding = [k for k, v in params.items() if isinstance(v, (tuple, list, set))]
    if expanding:
        stmt = stmt.bindparams(*[bindparam(k, expanding=True) for k in expanding])
        params = {k: list(v) if isinstance(v, (tuple, set)) else v for k, v in params.items()}
    with engine().connect() as conn:
        return pd.read_sql(stmt, conn, params=params)


# ──────────────────────────────────────────────────────────────────────────────
# Cached query helpers. `filters` is a hashable dict of primitives.
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def region_table() -> pd.DataFrame:
    """Return the public.\"Region\" table as a clean DataFrame.

    The table has 2 columns (label = English country name, region = code).
    The first import row is a BOM-prefixed header ('﻿label') which we
    drop. Duplicate rows (Burundi appears twice in the source) are deduped
    on (label, region).
    """
    sql = '''
        SELECT DISTINCT label, region
        FROM public."Region"
        WHERE label IS NOT NULL
          AND label <> chr(65279) || 'label'
          AND label <> 'label'
    '''
    return _q(sql)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def filter_options() -> dict[str, list[str]]:
    sql = f"""
        SELECT 'sector'   AS k, {sector_bucket()}::text AS v FROM {TABLE}
            WHERE {COL['sector']} IS NOT NULL
        UNION ALL
        SELECT 'status'   AS k, {COL['status']}::text   AS v FROM {TABLE}
            WHERE {COL['status']} IS NOT NULL AND {COL['status']} NOT IN :_invalid_status
        UNION ALL
        SELECT 'country'  AS k, {country_bucket()}::text AS v FROM {TABLE} WHERE {COL['country']} IS NOT NULL
    """
    df = _q(sql, {"_invalid_status": tuple(INVALID_STATUS)})
    out: dict[str, list[str]] = {}
    for k, group in df.groupby("k"):
        vals = sorted(v for v in group["v"].unique() if v)
        out[k] = vals
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def date_bounds() -> tuple[Optional[date], Optional[date]]:
    # Bornes du filtre date calculées sur la colonne « today » Kobo (date
    # d'ouverture du formulaire), pour rester cohérent avec _where() et la
    # timeline d'activité de collecte.
    df = _q(f"""
        SELECT MIN({dt(COL['today'])}) AS lo,
               MAX({dt(COL['today'])}) AS hi
        FROM {TABLE}
    """)
    lo = df.at[0, "lo"]
    hi = df.at[0, "hi"]
    return (
        lo.date() if hasattr(lo, "date") else lo,
        hi.date() if hasattr(hi, "date") else hi,
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def last_collection_date(country: str, filters: dict[str, Any]) -> Optional[date]:
    """Most recent data-collection date within the country-scoped (and, when a
    project is picked, project-filtered) selection. None when no dated
    submission exists."""
    f = {**filters, "country": country}
    where, params = _where(f)
    df = _q(
        f"""
        SELECT MAX({dt(COL['collection_date'])}) AS hi
        FROM {TABLE}
        {where}
        """,
        params,
    )
    hi = df.at[0, "hi"] if not df.empty else None
    if hi is None or pd.isna(hi):
        return None
    return hi.date() if hasattr(hi, "date") else hi


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def kpi_overview(filters: dict[str, Any]) -> pd.Series:
    where, params = _where(filters)
    sql = f"""
        SELECT
          COUNT(*) AS sites,
          COUNT(DISTINCT {country_bucket()}) AS countries,
          COUNT(DISTINCT {COL['project_title']}) FILTER (
            WHERE {COL['status']} IN ('In progress','Planned')
              AND {COL['project_title']} IS NOT NULL
          ) AS active_projects,
          ROUND(100.0 * COUNT(*) FILTER (WHERE {COL['status']}='Completed')
                / NULLIF(COUNT(*),0), 1) AS completion_rate,
          ROUND(100.0 * COUNT(*) FILTER (
              WHERE {COL['status']} IN ('Stalled','Stalled/ suspended','Abandoned','Suspended','Canceled')
          ) / NULLIF(COUNT(*),0), 1) AS at_risk_rate,
          MAX({dt(COL['collection_date'])}) AS last_collection
        FROM {TABLE}
        {where};
    """
    df = _q(sql, params)
    return df.iloc[0]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def kpi_by_country(filters: dict[str, Any]) -> pd.DataFrame:
    where, params = _where(filters)
    sql = f"""
        SELECT {country_bucket()} AS country,
               COUNT(*) AS sites,
               ROUND(100.0 * COUNT(*) FILTER (WHERE {COL['status']}='Completed')
                     / NULLIF(COUNT(*),0), 1) AS completion_rate,
               ROUND(100.0 * COUNT(*) FILTER (
                   WHERE {COL['status']} IN ('Stalled','Stalled/ suspended','Abandoned','Suspended','Canceled')
               ) / NULLIF(COUNT(*),0), 1) AS at_risk_rate
        FROM {TABLE}
        {where}
        GROUP BY {country_bucket()}
        ORDER BY sites DESC;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_status_breakdown(filters: dict[str, Any], top_n: int = 12) -> pd.DataFrame:
    """Sites grouped by country × status, restricted to top_n countries by total sites."""
    where, params = _where(filters)
    sql = f"""
        SELECT {country_bucket()} AS country,
               {COL['status']}    AS status,
               COUNT(*)           AS sites
        FROM {TABLE}
        {where}
        GROUP BY 1, 2;
    """
    df = _q(sql, params)
    if df.empty:
        return df
    top = df.groupby("country")["sites"].sum().nlargest(top_n).index
    return df[df["country"].isin(top)].sort_values(["country", "status"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def sector_breakdown(filters: dict[str, Any]) -> pd.DataFrame:
    where, params = _where(filters)
    sql = f"""
        SELECT COALESCE({sector_bucket()}, 'Unknown') AS sector,
               COUNT(*) AS sites,
               ROUND(100.0 * COUNT(*) FILTER (WHERE {COL['status']}='Completed')
                     / NULLIF(COUNT(*),0), 1) AS completion_rate
        FROM {TABLE}
        {where}
        GROUP BY 1
        ORDER BY sites DESC
        LIMIT 15;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def funder_breakdown(filters: dict[str, Any]) -> pd.DataFrame:
    where, params = _where(filters)
    sql = f"""
        SELECT COALESCE({COL['funder']}, 'Unknown') AS funder,
               COUNT(*) AS sites
        FROM {TABLE}
        {where}
        GROUP BY 1
        ORDER BY sites DESC
        LIMIT 10;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def temporal_trend(filters: dict[str, Any]) -> pd.DataFrame:
    # « Activité de collecte au fil du temps » s'appuie sur la colonne « today »
    # Kobo (date d'ouverture du formulaire) — l'indicateur reflète quand les
    # enquêteurs sont passés saisir, pas la date de l'activité elle-même.
    where, params = _where(filters)
    sql = f"""
        SELECT date_trunc('month', {dt(COL['today'])})::date AS month,
               COUNT(*) AS submissions,
               COUNT(*) FILTER (WHERE {COL['status']}='Completed') AS completions
        FROM {TABLE}
        {where}
          AND {dt(COL['today'])} IS NOT NULL
        GROUP BY 1
        ORDER BY 1;
    """
    df = _q(sql, params)
    if not df.empty:
        df["cumulative_completed"] = df["completions"].cumsum()
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def status_distribution(filters: dict[str, Any]) -> pd.DataFrame:
    where, params = _where(filters)
    sql = f"""
        SELECT {COL['status']} AS status, COUNT(*) AS sites
        FROM {TABLE}
        {where}
        GROUP BY 1
        ORDER BY sites DESC;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def map_points(filters: dict[str, Any], limit: int = 30000) -> pd.DataFrame:
    """Return every mappable site (valid lat/lon inside Africa, valid status).

    The default ``limit`` is set above the current mappable volume (~24.5 k)
    so the global map shows ALL countries — including small ones like Egypt
    or RCA. The explicit ``ORDER BY`` is essential: without it, a LIMIT under
    the total row count returns an *arbitrary* slice in physical scan order,
    which used to silently drop whole countries from the map.

    Coordinates are constrained to the Africa bounding box (AFRICA_* consts):
    global ``-180/180 × -90/90`` bounds let through GPS data-entry errors that
    are valid worldwide but plot outside the continent (e.g. lon=76 → India,
    lat=46 → Europe). The tighter box keeps every legitimate site (data extent
    lon ≈ [-17.5, 53.7], lat ≈ [-29.3, 37.0]) while dropping those outliers.
    """
    where, params = _where(filters)
    params["lim"] = limit
    sql = f"""
        SELECT {COL['lat']} AS lat,
               {COL['lon']} AS lon,
               {country_bucket()}                AS country,
               {COL['sector']}                   AS sector,
               {COL['status']}                   AS status,
               {COL['project_title']}            AS project_title,
               {COL['site_name']}                AS site_name,
               {dt(COL['collection_date'])}      AS collection_date
        FROM {TABLE}
        {where}
          AND {COL['lat']} IS NOT NULL
          AND {COL['lon']} IS NOT NULL
          AND {COL['lat']} BETWEEN {AFRICA_LAT_MIN} AND {AFRICA_LAT_MAX}
          AND {COL['lon']} BETWEEN {AFRICA_LON_MIN} AND {AFRICA_LON_MAX}
        ORDER BY {dt(COL['collection_date'])} DESC NULLS LAST
        LIMIT :lim;
    """
    return _q(sql, params)


# ──────────────────────────────────────────────────────────────────────────────
# Country-page specific queries.
# ──────────────────────────────────────────────────────────────────────────────

def _rename_params(where: str, params: dict[str, Any], prefix: str) -> tuple[str, dict[str, Any]]:
    """Prefix every named param in a WHERE clause + its dict (avoid collisions in unions)."""
    new_params = {f"{prefix}{k}": v for k, v in params.items()}
    new_where = where
    # iterate from longest to shortest to avoid prefix collisions (e.g. :date_from vs :date)
    for k in sorted(params, key=len, reverse=True):
        new_where = new_where.replace(f":{k}", f":{prefix}{k}")
    return new_where, new_params


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_kpis_with_delta(country: str, filters: dict[str, Any]) -> pd.DataFrame:
    """Country KPIs alongside global averages computed on the same filtered window.

    The country aggregate honours every filter (including `project`).
    The global aggregate drops the `project` filter — comparing one project
    across countries that don't have it would otherwise yield trivial deltas.
    """
    f_country = {**filters, "country": country}
    f_global  = {k: v for k, v in filters.items() if k not in ("project", "country")}

    w_country, p_country = _where(f_country)
    w_global,  p_global  = _where({**f_global, "country": None})

    w_country, p_country = _rename_params(w_country, p_country, "c_")
    w_global,  p_global  = _rename_params(w_global,  p_global,  "g_")

    sql = f"""
        WITH country_rows AS (
          SELECT {COL['status']}               AS status,
                 COUNT(*)                      AS n,
                 SUM({COL['beneficiaries']})   AS beneficiaries
          FROM {TABLE}
          {w_country}
          GROUP BY 1
        ),
        country_agg AS (
          SELECT
            SUM(n)                                                                  AS sites,
            100.0 * SUM(n) FILTER (WHERE status='Completed')
                  / NULLIF(SUM(n),0)                                                AS completion_rate,
            100.0 * SUM(n) FILTER (WHERE status IN ('Stalled','Stalled/ suspended','Abandoned','Suspended','Canceled'))
                  / NULLIF(SUM(n),0)                                                AS at_risk_rate,
            SUM(n) FILTER (WHERE status='In progress')                              AS in_progress,
            SUM(beneficiaries)                                                      AS beneficiaries
          FROM country_rows
        ),
        per_country_global AS (
          SELECT {country_bucket()} AS country,
                 {COL['status']}    AS status,
                 COUNT(*)           AS n,
                 SUM({COL['beneficiaries']}) AS beneficiaries
          FROM {TABLE}
          {w_global}
          GROUP BY 1, 2
        ),
        country_rates AS (
          SELECT country,
                 100.0 * SUM(n) FILTER (WHERE status='Completed')
                       / NULLIF(SUM(n),0)                                           AS completion_rate,
                 100.0 * SUM(n) FILTER (WHERE status IN ('Stalled','Stalled/ suspended','Abandoned','Suspended','Canceled'))
                       / NULLIF(SUM(n),0)                                           AS at_risk_rate,
                 SUM(beneficiaries) AS beneficiaries
          FROM per_country_global
          GROUP BY 1
        ),
        global_agg AS (
          SELECT AVG(completion_rate) AS g_completion_rate,
                 AVG(at_risk_rate)    AS g_at_risk_rate,
                 SUM(beneficiaries)   AS g_beneficiaries
          FROM country_rates
        )
        SELECT
          :country_pick                       AS country,
          ca.sites, ca.completion_rate, ca.at_risk_rate, ca.in_progress, ca.beneficiaries,
          g.g_completion_rate, g.g_at_risk_rate, g.g_beneficiaries
        FROM country_agg ca CROSS JOIN global_agg g;
    """
    params = {**p_country, **p_global, "country_pick": country}
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_pipeline(country: str, filters: dict[str, Any]) -> pd.DataFrame:
    f = {**filters, "country": country}
    where, params = _where(f)
    sql = f"""
        SELECT
          {COL['project_code']}                AS project_code,
          {COL['project_title']}               AS project,
          {COL['site_name']}                   AS site,
          {COL['region_name']}                 AS region,
          {COL['sector']}                      AS sector,
          {COL['status']}                      AS status,
          {COL['progress_band']}               AS progress,
          {dt(COL['planned_start_date'])}::date AS planned_start,
          {dt(COL['planned_end_date'])}::date   AS planned_end,
          {dt(COL['completion_date'])}::date    AS completion,
          CASE
            WHEN {COL['status']}='Completed'
                 AND {dt(COL['completion_date'])} IS NOT NULL
                 AND {dt(COL['planned_end_date'])} IS NOT NULL
              THEN ({dt(COL['completion_date'])}::date - {dt(COL['planned_end_date'])}::date)
            WHEN {COL['status']} <> 'Completed'
                 AND {dt(COL['planned_end_date'])} IS NOT NULL
                 AND {dt(COL['planned_end_date'])}::date < CURRENT_DATE
              THEN (CURRENT_DATE - {dt(COL['planned_end_date'])}::date)
            ELSE NULL
          END                                  AS delay_days,
          {COL['funder']}                      AS funder,
          {COL['implementing_agency']}         AS agency
        FROM {TABLE}
        {where}
        ORDER BY delay_days DESC NULLS LAST, status
        LIMIT 5000;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_funnel(country: str, filters: dict[str, Any]) -> pd.DataFrame:
    f = {**filters, "country": country}
    where, params = _where(f)
    sql = f"""
        SELECT {COL['status']} AS status, COUNT(*) AS n
        FROM {TABLE}
        {where}
        GROUP BY 1;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_region_status(country: str, filters: dict[str, Any]) -> pd.DataFrame:
    f = {**filters, "country": country}
    where, params = _where(f)
    sql = f"""
        SELECT COALESCE({COL['region_name']}, '—') AS region,
               {COL['status']} AS status,
               COUNT(*) AS sites
        FROM {TABLE}
        {where}
        GROUP BY 1, 2
        ORDER BY 1, 2;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_delay_distribution(country: str, filters: dict[str, Any]) -> pd.DataFrame:
    f = {**filters, "country": country}
    where, params = _where(f)
    sql = f"""
        SELECT
          CASE
            WHEN {COL['status']}='Completed'
                 AND {dt(COL['completion_date'])} IS NOT NULL
                 AND {dt(COL['planned_end_date'])} IS NOT NULL
              THEN ({dt(COL['completion_date'])}::date - {dt(COL['planned_end_date'])}::date)
            WHEN {COL['status']} <> 'Completed'
                 AND {dt(COL['planned_end_date'])} IS NOT NULL
                 AND {dt(COL['planned_end_date'])}::date < CURRENT_DATE
              THEN (CURRENT_DATE - {dt(COL['planned_end_date'])}::date)
          END AS delay_days
        FROM {TABLE}
        {where};
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_issues(country: str, filters: dict[str, Any], top_n: int = 10) -> pd.DataFrame:
    f = {**filters, "country": country}
    where, params = _where(f)
    params["top_n"] = top_n
    sql = f"""
        SELECT COALESCE({COL['issue_type']}, 'Other') AS issue_type,
               COUNT(*) AS occurrences
        FROM {TABLE}
        {where}
          AND {COL['issue_type']} IS NOT NULL
        GROUP BY 1
        ORDER BY occurrences DESC
        LIMIT :top_n;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_projects(country: str, filters: dict[str, Any]) -> list[str]:
    f = {**filters, "country": country}
    where, params = _where(f)
    sql = f"""
        SELECT DISTINCT {COL['project_title']} AS p
        FROM {TABLE}
        {where}
          AND {COL['project_title']} IS NOT NULL
        ORDER BY 1;
    """
    return _q(sql, params)["p"].tolist()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_regions(country: str, filters: dict[str, Any]) -> list[str]:
    f = {**filters, "country": country}
    where, params = _where(f)
    sql = f"""
        SELECT DISTINCT {COL['region_name']} AS r
        FROM {TABLE}
        {where}
          AND {COL['region_name']} IS NOT NULL
        ORDER BY 1;
    """
    return _q(sql, params)["r"].tolist()


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def delivery_kpis(filters: dict[str, Any]) -> pd.Series:
    """Three delivery-health metrics shown on the Global view second KPI row.

      • overdue_activities : sites whose planned end date is past but status ≠ Completed
      • avg_duration_days  : among Completed sites, mean (completion_date − planned_start_date)
      • on_time_rate       : among Completed sites, % completed on or before planned end
    """
    where, params = _where(filters)
    sql = f"""
        WITH d AS (
          SELECT
            {COL['status']}                       AS status,
            {dt(COL['planned_start_date'])}::date AS p_start,
            {dt(COL['planned_end_date'])}::date   AS p_end,
            {dt(COL['completion_date'])}::date    AS c_end
          FROM {TABLE}
          {where}
        )
        SELECT
          COUNT(*) FILTER (WHERE status <> 'Completed'
                             AND p_end IS NOT NULL
                             AND p_end < CURRENT_DATE)                                  AS overdue_activities,
          ROUND(AVG(c_end - p_start) FILTER (
              WHERE status='Completed' AND c_end IS NOT NULL AND p_start IS NOT NULL
          )::numeric, 1)                                                                AS avg_duration_days,
          ROUND(100.0 * COUNT(*) FILTER (
              WHERE status='Completed' AND c_end IS NOT NULL AND p_end IS NOT NULL
                AND c_end <= p_end
          ) / NULLIF(COUNT(*) FILTER (
              WHERE status='Completed' AND c_end IS NOT NULL AND p_end IS NOT NULL
          ), 0), 1)                                                                     AS on_time_rate
        FROM d;
    """
    return _q(sql, params).iloc[0]


# ── Heuristic output detection — keyword categories matched against site_name + description.
# Order matters: the FIRST matching pattern wins. Patterns are PostgreSQL regex (case-insensitive).
_OUTPUT_BUCKETS = [
    ("Latrines",                 r"latrine"),
    ("Puits / forages",          r"puits|forage|piezo|piézo"),
    ("Routes / pistes / ponts",  r"route|piste|pont|voirie"),
    ("Écoles / classes",         r"école|ecole|classe|lyc[eé]e|coll[eé]ge"),
    ("Centres de santé",         r"centre.de.sant|dispensaire|h[oô]pital|clinique"),
    ("Marchés / hangars",        r"march[eé]|hangar|halle"),
    ("Barrages / retenues",      r"barrage|retenue|digue|seuil"),
    ("Bas-fonds / périmètres",   r"bas[ -]fond|p[eé]rim[eè]tre|am[eé]nagement.hydro"),
    ("Magasins / stockage",      r"magasin|entrep[oô]t|silo|stockage"),
    ("Équipements / matériels",  r"kit|outil|tracteur|motopompe|cage|ruche|équipement|materiel|matériel"),
    ("Semences / plants",        r"semence|plant\b|p[eé]pini[eè]re|engrais"),
    ("Volailles / aliments",     r"poussin|alevin|volaille|aliment.b[eé]tail|b[eé]tail"),
    ("Pompes / hydraulique",     r"pompe|chateau.d.eau|adduction|robinet"),
]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_outputs(country: str, filters: dict[str, Any]) -> pd.Series:
    """Aggregate output counts per country: total / infra / equipment / delivery."""
    f = {**filters, "country": country}
    where, params = _where(f)
    INFRA  = (r"latrine|puits|forage|route|piste|pont|école|ecole|classe|centre.de.sant|"
              r"march[eé]|hangar|barrage|retenue|p[eé]rim[eè]tre|bas[ -]fond|magasin|entrep|silo")
    EQUIP  = (r"kit|outil|tracteur|motopompe|cage|ruche|équipement|materiel|matériel|"
              r"pompe|chateau.d.eau|adduction|robinet")
    DELIV  = (r"semence|plant\b|p[eé]pini|engrais|poussin|alevin|volaille|b[eé]tail|aliment")
    site   = COL["site_name"]
    descr  = COL["site_description"]
    haystack = f"COALESCE({site}, '') || ' ' || COALESCE({descr}, '')"
    sql = f"""
        SELECT
          COUNT(*)                                                            AS total_sites,
          COUNT(DISTINCT {COL['project_title']})
              FILTER (WHERE {COL['project_title']} IS NOT NULL)                AS distinct_projects,
          COUNT(*) FILTER (WHERE {haystack} ~* :infra)                         AS infra,
          COUNT(*) FILTER (WHERE {haystack} ~* :equip)                         AS equipment,
          COUNT(*) FILTER (WHERE {haystack} ~* :deliv)                         AS delivery,
          COUNT(*) FILTER (WHERE COALESCE({COL['realised_activities']}, '') <> '') AS documented
        FROM {TABLE}
        {where};
    """
    params.update({"infra": INFRA, "equip": EQUIP, "deliv": DELIV})
    return _q(sql, params).iloc[0]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_output_breakdown(country: str, filters: dict[str, Any]) -> pd.DataFrame:
    """Top output categories detected via keyword regex. Each site contributes to ONE category."""
    f = {**filters, "country": country}
    where, params = _where(f)
    site   = COL["site_name"]
    descr  = COL["site_description"]
    haystack = f"COALESCE({site}, '') || ' ' || COALESCE({descr}, '')"
    cases = []
    for label, pattern in _OUTPUT_BUCKETS:
        # Use $$..$$ literals to avoid quoting issues
        esc = pattern.replace("'", "''")
        elbl = label.replace("'", "''")
        cases.append(f"WHEN {haystack} ~* '{esc}' THEN '{elbl}'")
    case_expr = "CASE " + " ".join(cases) + " ELSE NULL END"
    sql = f"""
        SELECT category, COUNT(*) AS occurrences
        FROM (
          SELECT {case_expr} AS category
          FROM {TABLE}
          {where}
        ) x
        WHERE category IS NOT NULL
        GROUP BY 1
        ORDER BY occurrences DESC;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_timeline(country: str, filters: dict[str, Any], limit: int = 200) -> pd.DataFrame:
    """Recent site visits with photos, plus *every* historical visit of those
    sites — so a multi-visit timeline can be drawn for each one.

    Strategy:
      1. Take the top-`limit` most-recent rows that have a photo + GPS.
      2. Find the distinct GPS sites (rounded to 5 decimals ≈ 1.1 m) among them.
      3. Return ALL rows from those sites (regardless of date), so older visits
         hidden beyond the top-N still appear in the strip when the site is
         shown.

    Includes lat/lon (used for site identity), plus the usual photo, status,
    project metadata. Sorted by collection date descending so the UI can pick
    the first row per site as the "latest" one.
    """
    f = {**filters, "country": country}
    where, params = _where(f)
    params["lim"] = limit

    lat = COL["lat"]
    lon = COL["lon"]
    dtc = dt(COL["collection_date"])
    p1u = COL["photo_1_url"]
    p2u = COL["photo_2_url"]

    sql = f"""
        WITH base AS (
          SELECT
            {dtc}::date                       AS collection_date,
            {COL['project_title']}            AS project_title,
            {COL['site_name']}                AS site_name,
            {COL['region_name']}              AS region_name,
            {COL['status']}                   AS status,
            {COL['progress_band']}            AS progress_band,
            {COL['site_description']}         AS site_description,
            {p1u}                             AS photo_1_url,
            {p2u}                             AS photo_2_url,
            {COL['photo_1']}                  AS photo_1_name,
            {COL['photo_2']}                  AS photo_2_name,
            {lat}                             AS lat,
            {lon}                             AS lon,
            {COL['sector']}                   AS sector,
            ROUND({lat}::numeric, 5)          AS lat_r,
            ROUND({lon}::numeric, 5)          AS lon_r
          FROM {TABLE}
          {where}
            AND ({p1u} IS NOT NULL OR {p2u} IS NOT NULL)
            AND {dtc} IS NOT NULL
            AND {lat} IS NOT NULL
            AND {lon} IS NOT NULL
        ),
        top_sites AS (
          SELECT DISTINCT lat_r, lon_r
          FROM (
            SELECT lat_r, lon_r,
                   ROW_NUMBER() OVER (ORDER BY collection_date DESC NULLS LAST) AS rn
            FROM base
          ) ranked
          WHERE rn <= :lim
        )
        SELECT b.collection_date, b.project_title, b.site_name, b.region_name,
               b.status, b.progress_band, b.site_description,
               b.photo_1_url, b.photo_2_url, b.photo_1_name, b.photo_2_name,
               b.lat, b.lon, b.sector
        FROM base b
        JOIN top_sites s ON s.lat_r = b.lat_r AND s.lon_r = b.lon_r
        ORDER BY b.collection_date DESC NULLS LAST;
    """
    return _q(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def country_beneficiaries(country: str, filters: dict[str, Any]) -> pd.Series:
    """Detailed beneficiary breakdown for one country (gender, age, vulnerable groups)."""
    f = {**filters, "country": country}
    where, params = _where(f)
    cols = [
        ("total",            COL["beneficiaries"]),
        ("women",            COL["beneficiaries_women"]),
        ("men",              COL["beneficiaries_men"]),
        ("other",            COL["beneficiaries_other"]),
        ("children_under_5", COL["beneficiaries_children_under_5"]),
        ("children_5_18",    COL["beneficiaries_children_5_18"]),
        ("elderly",          COL["beneficiaries_elderly"]),
        ("disabled",         COL["beneficiaries_disabled"]),
        ("refugees",         COL["beneficiaries_refugees"]),
        ("idps",             COL["beneficiaries_idps"]),
        ("returnees",        COL["beneficiaries_returnees"]),
    ]
    select = ",\n          ".join(f"COALESCE(SUM({c}), 0) AS {alias}" for alias, c in cols)
    sql = f"""
        SELECT
          {select}
        FROM {TABLE}
        {where};
    """
    return _q(sql, params).iloc[0]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def beneficiaries_overview(filters: dict[str, Any]) -> pd.Series:
    """Beneficiary totals across the current selection (no country injected).

    Same columns as :func:`country_beneficiaries`, but scoped only by the
    active sidebar filters — used by the assistant for portfolio-wide answers.
    """
    where, params = _where(filters)
    cols = [
        ("total",            COL["beneficiaries"]),
        ("women",            COL["beneficiaries_women"]),
        ("men",              COL["beneficiaries_men"]),
        ("children_under_5", COL["beneficiaries_children_under_5"]),
        ("children_5_18",    COL["beneficiaries_children_5_18"]),
        ("elderly",          COL["beneficiaries_elderly"]),
        ("disabled",         COL["beneficiaries_disabled"]),
        ("refugees",         COL["beneficiaries_refugees"]),
        ("idps",             COL["beneficiaries_idps"]),
        ("returnees",        COL["beneficiaries_returnees"]),
    ]
    select = ",\n          ".join(f"COALESCE(SUM({c}), 0) AS {alias}" for alias, c in cols)
    sql = f"""
        SELECT
          {select}
        FROM {TABLE}
        {where};
    """
    return _q(sql, params).iloc[0]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def recent_submissions_count(filters: dict[str, Any], days: int = 30) -> int:
    where, params = _where(filters)
    sql = f"""
        SELECT COUNT(*) AS n
        FROM {TABLE}
        {where}
          AND {dt(COL['collection_date'])} >= (CURRENT_DATE - INTERVAL '{int(days)} days');
    """
    return int(_q(sql, params).at[0, "n"])


def random_sites_with_photos(filters: dict[str, Any], n: int = 3) -> pd.DataFrame:
    """Up to ``n`` randomly-picked site visits **that have a photo**, within the
    current filter window (dates + scope). Used by the newsletter to illustrate
    a given period.

    Deliberately NOT cached: each call re-runs ``ORDER BY random()`` so the
    caller can reshuffle. Returns columns: site_name, site_description,
    project_title, country, collection_date, photo_url (photo_1 with photo_2
    fallback).
    """
    where, params = _where(filters)
    params["nphotos"] = int(n)
    p1u = COL["photo_1_url"]
    p2u = COL["photo_2_url"]
    dtc = dt(COL["collection_date"])
    sql = f"""
        SELECT
          {COL['site_name']}        AS site_name,
          {COL['site_description']} AS site_description,
          {COL['project_title']}    AS project_title,
          {country_bucket()}        AS country,
          {dtc}::date               AS collection_date,
          COALESCE(NULLIF(btrim({p1u}), ''), NULLIF(btrim({p2u}), '')) AS photo_url
        FROM {TABLE}
        {where}
          AND COALESCE(NULLIF(btrim({p1u}), ''), NULLIF(btrim({p2u}), '')) IS NOT NULL
        ORDER BY random()
        LIMIT :nphotos;
    """
    return _q(sql, params)


# ──────────────────────────────────────────────────────────────────────────────
# Projets BAD coverage helpers — Regional Operations Dashboard (ROD) source.
#
# Headline metric (per user spec, see reference table):
#   % Projects mapped = Ongoing Project mapped / Portfolio
#
# Where:
#   • Portfolio  = projet_BAD records for the country (country_slug = X)
#                  with is_active = TRUE, i.e. ROD status IN ('OnGo','APVD'):
#                  "En cours" + "Approuvé".
#   • Ongoing Project mapped = portfolio records that have at least one
#                  internal project (kobo_clean) matching them.
#   • # Submissions = count of kobo_clean rows for the country.
#
# Internal "active" universe for the country-view comparison TABLE is each
# distinct kobo_clean.nom_projet in the country (any status). Matching tries:
#   1. SAP code (exact strip via public."code_SAP")
#   2. SAP code (NFKC + casefold + ws-collapse via _normalized_code_sap_index)
#   3. fuzzy title against the BAD ACTIVE titles (full ROD universe)
#
# Design choices reconciled:
#   • The internal-anchored TABLE matches against the FULL ROD-active universe
#     so multinational projects (Multi-Countries) appear as Cartographié in
#     their country's table even though they're not in that country's
#     strict portfolio.
#   • The headline KPI uses the strict country_slug portfolio as denominator,
#     and the matched-count is computed against the SAME strict portfolio
#     (so it stays ≤ portfolio and the % stays in [0,100]).
# ──────────────────────────────────────────────────────────────────────────────

# Fuzzy match acceptance threshold (0-1). 0.85 catches "Mali - Highway" vs
# "Mali - Highway (Phase 2)" while rejecting different projects.
FUZZY_THRESHOLD = 0.85


def _norm_title(s: Any) -> str:
    """Aggressive title normalization shared by the matchers."""
    import re
    import unicodedata
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = re.sub(r"\s+", " ", s).strip().casefold()
    # Strip punctuation that often differs between sources (em-dash vs hyphen,
    # parentheses, slashes…). Keep word chars + spaces only.
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def rasme_countries() -> list[str]:
    """Return the set of internal slugs where RASME is deployed.

    A country is considered RASME-deployed iff it has at least one valid
    kobo_clean row (i.e. it appears in the bucketed country column with a
    non-null status that passes the INVALID_STATUS filter). All BAD-side
    aggregates are scoped to this set so totals reflect ONLY the countries
    where RASME monitoring is active.
    """
    where, params = _where({})
    df = _q(f"""
        SELECT DISTINCT {country_bucket()} AS slug
        FROM {TABLE}
        {where}
          AND {COL['country']} IS NOT NULL
    """, params)
    return sorted(s for s in df["slug"].dropna().tolist() if s)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def bad_overview() -> pd.Series:
    """Top-level counters for the Projets BAD snapshot — **scoped to
    RASME-deployed countries only** (see :func:`rasme_countries`).

    Returns a Series with::

        total          int    — BAD records in RASME countries
        active         int    — Approved + Ongoing in RASME countries
        approved       int    — status_code '1'
        ongoing        int    — status_code '2'
        completion     int    — status_code '3'
        cancelled      int    — status_code '5'
        suspended      int    — status_code '6'
        last_refresh   date   — MAX(fetched_at)
    """
    slugs = tuple(rasme_countries())
    sql = f"""
        SELECT
          COUNT(*)                                            AS total,
          COUNT(*) FILTER (WHERE is_active IS TRUE)           AS active,
          COUNT(*) FILTER (WHERE status_code = '1')           AS approved,
          COUNT(*) FILTER (WHERE status_code = '2')           AS ongoing,
          COUNT(*) FILTER (WHERE status_code = '3')           AS completion,
          COUNT(*) FILTER (WHERE status_code = '5')           AS cancelled,
          COUNT(*) FILTER (WHERE status_code = '6')           AS suspended,
          MAX(fetched_at)::date                               AS last_refresh
        FROM {BAD_TABLE}
        WHERE country_slug IN :slugs;
    """
    return _q(sql, {"slugs": slugs or ("__none__",)}).iloc[0]


def _internal_active_titles_sql(country_slug: Optional[str] = None) -> tuple[str, dict[str, Any]]:
    """SQL returning every distinct internal project (title, country slug,
    SAP code if any) that has at least one site collected in the country
    scope. No statut_implementation filter — see header docstring for the
    definition of "actif" used here. The LEFT JOIN keeps projects even
    when they are absent from the public."code_SAP" reference.

    Goes through ``_where()`` so the invalid-status sentinels ('#status',
    'None', '') are filtered out — same baseline as country_projects().
    """
    f: dict[str, Any] = {}
    if country_slug:
        f["country"] = country_slug
    where, params = _where(f)
    sql = f"""
        SELECT DISTINCT
            k.{COL['project_title']}   AS project_title,
            {country_bucket()}         AS country_slug,
            s."Code_SAP"               AS code
        FROM {TABLE} k
        LEFT JOIN public."code_SAP" s
          ON btrim(k.{COL['project_title']}) = btrim(s."Name of the project")
        {where}
          AND k.{COL['project_title']} IS NOT NULL
          AND btrim(k.{COL['project_title']}) <> '';
    """
    return sql, params


def _internal_codes_with_titles_sql(country_slug: Optional[str] = None) -> tuple[str, dict[str, Any]]:
    """SQL returning every (code, title) pair seen in kobo_clean for the
    country scope. Each submission resolves to a SINGLE code, name first:
      (b) ``nom_projet`` matched to public."code_SAP".Code_SAP — if found,
      (a) else ``identifiant_pa`` truncated to first 4 dash segments.

    Name resolution wins because ``code_SAP`` is a curated catalogue, whereas
    ``identifiant_pa`` is free-form field entry that often carries a local site
    code (e.g. ``other-NG005-…``) instead of the SAP code. Emitting only one
    code per submission stops such local codes from surfacing as spurious
    "Non cartographié" projects when the title already maps to a BAD record.

    A single SAP code can have multiple titles in the data — the caller
    picks a canonical title via :func:`_pick_canonical_title`.
    """
    f: dict[str, Any] = {}
    if country_slug:
        f["country"] = country_slug
    where, params = _where(f)
    sql = f"""
        WITH base AS (
            SELECT
                array_to_string(
                    (string_to_array(k.identifiant_pa, '-'))[1:4], '-'
                )                                  AS code_a,
                NULLIF(btrim(s."Code_SAP"), '')    AS code_b,
                k.{COL['project_title']}           AS title,
                {country_bucket()}                 AS country_slug
            FROM {TABLE} k
            LEFT JOIN public."code_SAP" s
              ON btrim(k.{COL['project_title']}) = btrim(s."Name of the project")
            {where}
              AND k.{COL['project_title']} IS NOT NULL
              AND btrim(k.{COL['project_title']}) <> ''
        )
        SELECT DISTINCT
            COALESCE(code_b, NULLIF(btrim(code_a), '')) AS code,
            title, country_slug
        FROM base
        WHERE COALESCE(code_b, NULLIF(btrim(code_a), '')) IS NOT NULL
          AND COALESCE(code_b, NULLIF(btrim(code_a), '')) <> '';
    """
    return sql, params


def _pick_canonical_title(titles: list[str], country_name: str) -> str:
    """Pick the most canonical title for a SAP code.

    Preference order:
      1. Titles that start with the country name (case-insensitive)
         — e.g. "Burundi - Projet d'appui …" wins over "PADCAE-B: …".
      2. Among those, the LONGEST title (more descriptive).
      3. If none start with the country name, the longest title overall.
      4. Fallback: the first title (alphabetical).
    """
    if not titles:
        return ""
    cn = (country_name or "").strip().casefold()
    starts_with = [t for t in titles if t and t.strip().casefold().startswith(cn)] if cn else []
    pool = starts_with if starts_with else titles
    # Longest among the preferred pool — descriptive titles tend to be longer.
    return max(pool, key=lambda t: (len(t or ""), t or ""))


def _bad_sql(
    country_slug: Optional[str] = None,
    status_filter: str = "active",
) -> tuple[str, dict[str, Any]]:
    """SQL returning (code, country, title, status_code, status_label) for
    projet_BAD records. The ``status_filter`` selects which subset:

      • "active"     — is_active IS TRUE  (Approved + Ongoing)
      • "completed"  — is_completed IS TRUE  (Completion)
      • "cancelled"  — is_cancelled IS TRUE  (Cancelled)
      • "any"        — all records (any status, including Post-completion / Suspended)

    Scoping:
      • If ``country_slug`` is provided, results are limited to that one slug.
      • Otherwise, results are limited to the set of RASME-deployed countries
        (:func:`rasme_countries`) — i.e. countries with ≥1 kobo submission.
    """
    where_status = {
        "active":    "is_active     IS TRUE",
        "completed": "is_completed  IS TRUE",
        "cancelled": "is_cancelled  IS TRUE",
        "any":       "1 = 1",
    }[status_filter]

    params: dict[str, Any] = {}
    if country_slug:
        scope_clause = "country_slug = :slug"
        params["slug"] = country_slug
    else:
        slugs = tuple(rasme_countries())
        scope_clause = "country_slug IN :slugs"
        params["slugs"] = slugs or ("__none__",)
    sql = f"""
        SELECT
            project_code   AS code,
            country        AS country,
            project_name   AS project_title,
            status_code    AS status_code,
            status_label   AS status_label
        FROM {BAD_TABLE}
        WHERE {where_status}
          AND {scope_clause};
    """
    return sql, params


def _bad_active_sql(country_slug: Optional[str] = None) -> tuple[str, dict[str, Any]]:
    """Backward-compatible alias kept for callers expecting the old name.
    Equivalent to :func:`_bad_sql` with ``status_filter='active'``."""
    return _bad_sql(country_slug, status_filter="active")


def _normalized_code_sap_index() -> dict[str, str]:
    """norm(title) -> SAP code from public."code_SAP". Cached for the session."""
    df = _q('''
        SELECT "Name of the project" AS title, "Code_SAP" AS code
        FROM public."code_SAP"
        WHERE "Name of the project" IS NOT NULL
          AND "Code_SAP"            IS NOT NULL
          AND "Name of the project" <> chr(65279) || 'Name of the project'
          AND "Name of the project" <> 'Name of the project'
    ''')
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        n = _norm_title(row["title"])
        if n and n not in out:
            out[n] = str(row["code"]).strip()
    return out


def _resolve_coverage(int_df: pd.DataFrame, bad_df: pd.DataFrame) -> pd.DataFrame:
    """Augment ``int_df`` (internal active projects) with coverage data: which
    BAD active project matches, via which strategy.

    Returns ``int_df`` plus columns:
      bad_code, bad_title, bad_status_label, match_source.
    ``match_source`` is one of {'code', 'code_normalized', 'name_fuzzy', None}.
    Rows where match_source is None are "Projet non cartographié".
    """
    import difflib

    bad_codes = set(bad_df["code"].dropna().astype(str).str.strip())
    bad_by_code = bad_df.set_index(
        bad_df["code"].astype(str).str.strip()
    )[["project_title", "status_label"]].to_dict("index")

    # Pre-built lookups for steps 2 and 3.
    code_sap_norm_idx = _normalized_code_sap_index()
    bad_norm_idx: dict[str, str] = {}        # norm(title) -> code
    for _, r in bad_df.iterrows():
        n = _norm_title(r["project_title"])
        if n and n not in bad_norm_idx:
            bad_norm_idx[n] = str(r["code"]).strip()
    bad_norm_titles = list(bad_norm_idx.keys())  # for SequenceMatcher

    bad_codes_set = bad_codes  # alias for readability

    bad_codes_arr = []
    bad_titles_arr = []
    bad_statuses_arr = []
    sources_arr = []

    for _, row in int_df.iterrows():
        title = row.get("project_title")
        raw_code = (row.get("code") or "")
        raw_code = str(raw_code).strip() if raw_code else ""

        matched_code: Optional[str] = None
        source: Optional[str] = None

        # Step 1 — direct SAP code match (already produced by the LEFT JOIN).
        if raw_code and raw_code in bad_codes_set:
            matched_code, source = raw_code, "code"

        # Step 2 — normalized title -> code_SAP -> BAD.
        if matched_code is None:
            n = _norm_title(title)
            if n:
                cand = code_sap_norm_idx.get(n)
                if cand and cand in bad_codes_set:
                    matched_code, source = cand, "code_normalized"

        # Step 3 — fuzzy match of the internal title against BAD active titles.
        if matched_code is None:
            n = _norm_title(title)
            if n and bad_norm_titles:
                if n in bad_norm_idx:
                    matched_code, source = bad_norm_idx[n], "name_fuzzy"
                else:
                    best = difflib.get_close_matches(
                        n, bad_norm_titles, n=1, cutoff=FUZZY_THRESHOLD,
                    )
                    if best:
                        matched_code, source = bad_norm_idx[best[0]], "name_fuzzy"

        if matched_code:
            info = bad_by_code.get(matched_code, {})
            bad_codes_arr.append(matched_code)
            bad_titles_arr.append(info.get("project_title"))
            bad_statuses_arr.append(info.get("status_label"))
            sources_arr.append(source)
        else:
            bad_codes_arr.append(None)
            bad_titles_arr.append(None)
            bad_statuses_arr.append(None)
            sources_arr.append(None)

    out = int_df.copy()
    out["bad_code"]         = bad_codes_arr
    out["bad_title"]        = bad_titles_arr
    out["bad_status_label"] = bad_statuses_arr
    out["match_source"]     = sources_arr
    return out


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def coverage_overview(
    country_slug: Optional[str] = None,
    region_slugs: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Headline coverage figures, counted by **distinct SAP code** (never by
    title — so PADCAE-B and "Burundi - Projet d'appui…" count as ONE).

    Coverage = mapped / portfolio   where portfolio = **active** (Approved +
    Ongoing) only. Completion and Cancelled BAD projects are reported as
    SEPARATE counters (visible but excluded from the headline rate).

    Returns a dict::

        {
          'n_submissions':       int,
          'n_internal':          int,   # DISTINCT SAP codes in kobo for country
          'n_portfolio':         int,   # ACTIVE BAD projects (codes 1+2)
          'n_mapped':            int,   # active codes also in kobo
          'n_unmapped':          int,   # portfolio - mapped (active gap)
          'mapping_rate':        float, # 100 * mapped / portfolio
          # ── Visibility on closed / cancelled portfolios ─────────────────
          'n_completion':        int,   # BAD Completion projects for country
          'n_completion_mapped': int,   # Completion codes also in kobo
          'n_cancelled':         int,   # BAD Cancelled projects for country
          'n_cancelled_mapped':  int,   # Cancelled codes also in kobo
          'n_internal_only':     int,   # kobo codes not in BAD at all
        }
    """
    # Single round trip. The earlier implementation issued 6 separate queries
    # (submissions + internal codes + 4 BAD status buckets); against the LAN
    # Postgres each round trip costs ~0.9 s, so the section took ~6 s to load.
    # Folding everything into one query keeps the exact counting semantics —
    # codes btrim-stripped on both sides; the "any" bucket (n_internal_only)
    # = every BAD record in scope, all statuses combined.
    sub_f: dict[str, Any] = {}
    if country_slug:
        sub_f["country"] = country_slug
    elif region_slugs:
        sub_f["countries_in"] = list(region_slugs)
    sub_where, params = _where(sub_f)

    if country_slug:
        country_clause_kobo = " AND k.country = :slug"
        bad_scope = "country_slug = :slug"
        # n_internal_only universe = same scope as the portfolio for a country.
        bad_all_scope = "country_slug = :slug"
        params["slug"] = country_slug
    elif region_slugs:
        # Region filter: scope kobo (bucketed, like _where's countries_in) and
        # the BAD portfolio to the selected country slugs so "Projets actifs"
        # and the Pillar 3 coverage row reflect the chosen region.
        country_clause_kobo = (
            f" AND {country_bucket('k.' + COL['country'])} IN :region_slugs"
        )
        bad_scope = "country_slug IN :region_slugs"
        bad_all_scope = "country_slug IN :region_slugs"
        params["region_slugs"] = tuple(region_slugs)
    else:
        country_clause_kobo = ""
        slugs = tuple(rasme_countries())
        bad_scope = "country_slug IN :slugs"
        # GLOBAL view: "Non cartographié" = a kobo code absent from the WHOLE
        # projet_BAD table — including multinational records (country_slug NULL)
        # that the RASME-scoped portfolio excludes. Keeps n_portfolio/n_mapped
        # (and the headline rate) on the RASME scope; only n_internal_only uses
        # this full universe, matching coverage_table(None).
        bad_all_scope = "1 = 1"
        params["slugs"] = slugs or ("__none__",)

    sql = f"""
        WITH ic AS (
            SELECT DISTINCT btrim(code) AS code FROM (
                -- One code per submission, name (code_SAP) first then the
                -- identifiant_pa short code — see _internal_codes_with_titles_sql.
                SELECT COALESCE(
                           NULLIF(btrim(s."Code_SAP"), ''),
                           NULLIF(btrim(array_to_string(
                               (string_to_array(k.identifiant_pa, '-'))[1:4], '-'
                           )), '')
                       ) AS code
                FROM {TABLE} k
                LEFT JOIN public."code_SAP" s
                  ON btrim(k.{COL['project_title']}) = btrim(s."Name of the project")
                WHERE (k.identifiant_pa IS NOT NULL OR s."Code_SAP" IS NOT NULL)
                  {country_clause_kobo}
            ) u
            WHERE code IS NOT NULL AND btrim(code) <> ''
        ),
        bc AS (
            SELECT btrim(project_code)   AS code,
                   bool_or(is_active)    AS is_active,
                   bool_or(is_completed) AS is_completed,
                   bool_or(is_cancelled) AS is_cancelled
            FROM {BAD_TABLE}
            WHERE {bad_scope}
              AND project_code IS NOT NULL
            GROUP BY btrim(project_code)
        ),
        bc_all AS (
            -- Universe for "absent from BAD": full table in the global view
            -- (catches multinational country_slug-NULL records), scoped exactly
            -- like bc for a country/region.
            SELECT DISTINCT btrim(project_code) AS code
            FROM {BAD_TABLE}
            WHERE {bad_all_scope}
              AND project_code IS NOT NULL
        )
        SELECT
          (SELECT COUNT(*) FROM {TABLE} {sub_where})                                   AS n_submissions,
          (SELECT COUNT(*) FROM ic)                                                    AS n_internal,
          (SELECT COUNT(*) FROM bc WHERE is_active)                                    AS n_portfolio,
          (SELECT COUNT(*) FROM bc WHERE is_completed)                                 AS n_completion,
          (SELECT COUNT(*) FROM bc WHERE is_cancelled)                                 AS n_cancelled,
          (SELECT COUNT(*) FROM ic JOIN bc ON bc.code = ic.code WHERE bc.is_active)    AS n_mapped,
          (SELECT COUNT(*) FROM ic JOIN bc ON bc.code = ic.code WHERE bc.is_completed) AS n_completion_mapped,
          (SELECT COUNT(*) FROM ic JOIN bc ON bc.code = ic.code WHERE bc.is_cancelled) AS n_cancelled_mapped,
          (SELECT COUNT(*) FROM ic
             WHERE NOT EXISTS (SELECT 1 FROM bc_all WHERE bc_all.code = ic.code))      AS n_internal_only
    """
    r = _q(sql, params).iloc[0]
    n_portfolio = int(r["n_portfolio"])
    n_mapped    = int(r["n_mapped"])
    return {
        "n_submissions":       int(r["n_submissions"]),
        "n_internal":          int(r["n_internal"]),
        "n_portfolio":         n_portfolio,
        "n_mapped":            n_mapped,
        "n_unmapped":          n_portfolio - n_mapped,
        "mapping_rate":        (100.0 * n_mapped / n_portfolio) if n_portfolio else 0.0,
        "n_completion":        int(r["n_completion"]),
        "n_completion_mapped": int(r["n_completion_mapped"]),
        "n_cancelled":         int(r["n_cancelled"]),
        "n_cancelled_mapped":  int(r["n_cancelled_mapped"]),
        "n_internal_only":     int(r["n_internal_only"]),
    }


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def coverage_by_country() -> pd.DataFrame:
    """Country-by-country breakdown for the Global view summary table.

    Single SQL query — one code per kobo submission, name first:
      (b) nom_projet → public."code_SAP".Code_SAP — if found,
      (a) else identifiant_pa truncated to first 4 dash segments.

    Returns DataFrame columns:
        country_slug, n_submissions,
        n_mapped, n_portfolio, mapping_rate,        — ACTIVE portfolio (Approved+Ongoing)
        n_completion_mapped, n_completion,          — Completion bucket (visibility)
        n_cancelled_mapped,  n_cancelled            — Cancelled bucket (visibility)
    """
    sql = f"""
        WITH submissions AS (
            SELECT {country_bucket()} AS slug, COUNT(*) AS n_submissions
            FROM {TABLE}
            WHERE {COL['country']} IS NOT NULL
            GROUP BY 1
        ),
        portfolio AS (
            SELECT country_slug AS slug,
                   COUNT(*) FILTER (WHERE is_active IS TRUE)    AS n_portfolio,
                   COUNT(*) FILTER (WHERE is_completed IS TRUE) AS n_completion,
                   COUNT(*) FILTER (WHERE is_cancelled IS TRUE) AS n_cancelled
            FROM {BAD_TABLE}
            WHERE country_slug IS NOT NULL
            GROUP BY 1
        ),
        kobo_codes AS (
            -- One code per submission, name (code_SAP) first then the
            -- identifiant_pa short code — see _internal_codes_with_titles_sql.
            SELECT DISTINCT
                {country_bucket()} AS slug,
                COALESCE(
                    NULLIF(btrim(s."Code_SAP"), ''),
                    NULLIF(btrim(array_to_string(
                        (string_to_array(k.identifiant_pa, '-'))[1:4], '-'
                    )), '')
                ) AS code
            FROM {TABLE} k
            LEFT JOIN public."code_SAP" s
              ON btrim(k.{COL['project_title']}) = btrim(s."Name of the project")
            WHERE k.{COL['country']} IS NOT NULL
        ),
        mapped AS (
            SELECT b.country_slug AS slug,
                   COUNT(DISTINCT b.project_code) FILTER (WHERE b.is_active    IS TRUE) AS n_mapped,
                   COUNT(DISTINCT b.project_code) FILTER (WHERE b.is_completed IS TRUE) AS n_completion_mapped,
                   COUNT(DISTINCT b.project_code) FILTER (WHERE b.is_cancelled IS TRUE) AS n_cancelled_mapped
            FROM {BAD_TABLE} b
            JOIN kobo_codes k
              ON k.slug = b.country_slug AND k.code = b.project_code
            WHERE b.country_slug IS NOT NULL
            GROUP BY 1
        ),
        all_slugs AS (
            -- RASME-deployed countries only = slugs with ≥1 kobo submission.
            SELECT slug FROM submissions
        )
        SELECT
            a.slug                                                 AS country_slug,
            COALESCE(s.n_submissions, 0)                           AS n_submissions,
            COALESCE(m.n_mapped, 0)                                AS n_mapped,
            COALESCE(p.n_portfolio, 0)                             AS n_portfolio,
            CASE WHEN COALESCE(p.n_portfolio, 0) > 0
                 THEN 100.0 * COALESCE(m.n_mapped, 0) / p.n_portfolio
                 ELSE 0
            END                                                    AS mapping_rate,
            COALESCE(m.n_completion_mapped, 0)                     AS n_completion_mapped,
            COALESCE(p.n_completion, 0)                            AS n_completion,
            COALESCE(m.n_cancelled_mapped, 0)                      AS n_cancelled_mapped,
            COALESCE(p.n_cancelled, 0)                             AS n_cancelled
        FROM all_slugs a
        LEFT JOIN submissions s ON s.slug = a.slug
        LEFT JOIN portfolio   p ON p.slug = a.slug
        LEFT JOIN mapped      m ON m.slug = a.slug
        WHERE a.slug IS NOT NULL
        ORDER BY a.slug;
    """
    return _q(sql)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def coverage_table(country_slug: Optional[str] = None) -> pd.DataFrame:
    """Comparison table — **one row per distinct internal SAP code** for the
    country scope. Multi-named projects are collapsed (PADCAE-B vs the
    full title → single row, canonical title chosen via
    :func:`_pick_canonical_title`).

    Granular coverage status (5 buckets):
      • "Cartographié — Actif"      — code in BAD active for THIS country
                                       (Approved or Ongoing).
      • "Cartographié — Clôturé"    — code in BAD Completion for this country.
      • "Cartographié — Annulé"     — code in BAD Cancelled for this country.
      • "Cartographié — Autre pays" — code in BAD (any status) but attributed
                                       to another country (multinational).
      • "Non cartographié"          — code not in BAD at all.

    Returned columns:
        code, project_title, all_titles, bad_code, bad_title, bad_country,
        bad_status, coverage_status, is_active_in_bad
    """
    from config import country_label as _country_label

    int_sql, int_params = _internal_codes_with_titles_sql(country_slug)
    int_df = _q(int_sql, int_params)

    if int_df.empty:
        return pd.DataFrame(columns=[
            "code", "project_title", "all_titles", "bad_code", "bad_title",
            "bad_country", "bad_status", "coverage_status", "is_active_in_bad",
        ])

    country_name = _country_label(country_slug, "FR") if country_slug else ""

    code_groups: dict[str, dict[str, Any]] = {}
    for _, row in int_df.iterrows():
        code = (str(row["code"]).strip() if row["code"] else "")
        if not code:
            continue
        title = (row["title"] or "").strip()
        entry = code_groups.setdefault(code, {"code": code, "titles": []})
        if title and title not in entry["titles"]:
            entry["titles"].append(title)

    # BAD lookups in a SINGLE round trip, then derive the country-strict status
    # buckets in pandas. The old code issued 4 separate queries (~0.9 s each on
    # the LAN Postgres) for the same data.
    #
    # Scope: a specific country pulls every RASME-country record (so the
    # "Autre pays" fallback works); the GLOBAL view (country_slug is None) pulls
    # the WHOLE table — including multinational records whose country_slug is
    # NULL — so those projects are recognised instead of flagged "Non
    # cartographié". Per-country views keep the RASME scope unchanged.
    if country_slug:
        _bad_where, _bad_params = "WHERE country_slug IN :slugs", \
            {"slugs": tuple(rasme_countries()) or ("__none__",)}
    else:
        _bad_where, _bad_params = "", {}
    bad_all_df = _q(f"""
        SELECT
            project_code   AS code,
            country        AS country,
            country_slug   AS country_slug,
            project_name   AS project_title,
            status_code    AS status_code,
            status_label   AS status_label,
            is_active      AS is_active,
            is_completed   AS is_completed,
            is_cancelled   AS is_cancelled
        FROM {BAD_TABLE}
        {_bad_where};
    """, _bad_params)

    def _by_code(df: pd.DataFrame) -> dict[str, dict]:
        return {
            str(r["code"]).strip(): {
                "code": r["code"], "project_title": r["project_title"],
                "country": r["country"], "status_label": r["status_label"],
            }
            for _, r in df.iterrows()
        }

    if country_slug:
        _country_rows = bad_all_df[bad_all_df["country_slug"] == country_slug]
    else:
        _country_rows = bad_all_df
    bad_active    = _by_code(_country_rows[_country_rows["is_active"]    == True])  # noqa: E712
    bad_completed = _by_code(_country_rows[_country_rows["is_completed"] == True])  # noqa: E712
    bad_cancelled = _by_code(_country_rows[_country_rows["is_cancelled"] == True])  # noqa: E712
    bad_any       = _by_code(bad_all_df)

    rows = []
    for code, info in code_groups.items():
        canonical  = _pick_canonical_title(info["titles"], country_name)
        all_titles = " | ".join(info["titles"]) if len(info["titles"]) > 1 else ""

        # Match priority: active country → completed country → cancelled
        # country → any country → none.
        if code in bad_active:
            br, status, is_active = bad_active[code], "Cartographié — Actif", True
        elif code in bad_completed:
            br, status, is_active = bad_completed[code], "Cartographié — Clôturé", False
        elif code in bad_cancelled:
            br, status, is_active = bad_cancelled[code], "Cartographié — Annulé", False
        elif code in bad_any:
            br, status, is_active = bad_any[code], "Cartographié — Autre pays", None
        else:
            br, status, is_active = None, "Non cartographié", None

        rows.append({
            "code":              code,
            "project_title":     canonical,
            "all_titles":        all_titles,
            "bad_code":          br["code"]          if br else None,
            "bad_title":         br["project_title"] if br else None,
            "bad_country":       br["country"]       if br else None,
            "bad_status":        br["status_label"]  if br else None,
            "coverage_status":   status,
            "is_active_in_bad":  is_active,
        })

    # Sort: non-cartographiés first, then closed (Clôturé / Annulé),
    # then other-country, then active. The user wants gaps surfaced.
    status_rank = {
        "Non cartographié":            0,
        "Cartographié — Clôturé":      1,
        "Cartographié — Annulé":       2,
        "Cartographié — Autre pays":   3,
        "Cartographié — Actif":        4,
    }
    out = pd.DataFrame(rows)
    out["_rank"] = out["coverage_status"].map(status_rank).fillna(99)
    return out.sort_values(["_rank", "code"]).drop(columns="_rank").reset_index(drop=True)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def bad_only_active(country_slug: Optional[str] = None) -> pd.DataFrame:
    """BAD active projects that none of the internal active projects map onto.
    Useful for spotting AfDB-tracked active projects that the field-monitoring
    pipeline hasn't picked up yet."""
    int_sql, int_params = _internal_active_titles_sql(country_slug)
    bad_sql, bad_params = _bad_active_sql(country_slug)
    int_df = _q(int_sql, int_params)
    bad_df = _q(bad_sql, bad_params)

    if int_df.empty:
        return bad_df.reset_index(drop=True)

    resolved = _resolve_coverage(int_df, bad_df)
    used_codes = set(resolved.loc[resolved["match_source"].notna(), "bad_code"].dropna())
    return (
        bad_df[~bad_df["code"].astype(str).str.strip().isin(used_codes)]
        .reset_index(drop=True)
    )
