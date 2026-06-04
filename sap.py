"""
SAP project-code lookup — sourced from PostgreSQL ``public."code_SAP"``.

The PG table mirrors the SharePoint Excel
``RASME/RASME_DASHBORD/Data/Code SAP_data.xlsx`` and is refreshed by the
ETL pipeline. Columns:

    "Name of the project"   text
    "Country"               text
    "Code_SAP"              text   (e.g. ``P-TZ-AA0-004``)

The Python module exposes the same public API it had when it used to load the
Excel — so any caller (``country_view``) keeps working untouched.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Optional

import streamlit as st


_WS_RE = re.compile(r"\s+")


def _norm(s: str | None) -> str:
    """Aggressive title normalization for fuzzy lookups.

    - NFKC unicode normalization (folds NBSP, ligatures, full-width chars…).
    - Collapses any whitespace run (spaces, tabs, NBSP after NFKC) to one space.
    - Strips, casefolds.

    Two titles that match after this transform are treated as the same project.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = _WS_RE.sub(" ", s).strip().casefold()
    return s


@st.cache_data(ttl=300, show_spinner=False)
def _load_from_pg() -> dict[str, str]:
    """Fetch the {project_title (stripped) : code_sap (stripped)} dictionary
    from PostgreSQL. Cached for 5 minutes (Streamlit's cache_data TTL).
    """
    # Local import to avoid a circular dependency: db imports streamlit, this
    # module is imported by country_view which is loaded after db.
    from db import _q

    sql = '''
        SELECT "Name of the project" AS title,
               "Code_SAP"            AS code
        FROM public."code_SAP"
        WHERE "Name of the project" IS NOT NULL
          AND "Code_SAP" IS NOT NULL
          AND "Name of the project" <> chr(65279) || 'Name of the project'
          AND "Name of the project" <> 'Name of the project'
    '''
    try:
        df = _q(sql)
    except Exception:
        return {}

    out: dict[str, str] = {}
    for _, row in df.iterrows():
        k = str(row["title"]).strip()
        v = str(row["code"]).strip()
        if k and v and k not in out:
            out[k] = v
    return out


def _table() -> dict[str, str]:
    """Public-API alias (kept for backward compatibility with old code paths)."""
    return _load_from_pg()


@st.cache_data(ttl=300, show_spinner=False)
def _norm_index() -> dict[str, tuple[str, str]]:
    """norm(title) -> (canonical_title, code) — for whitespace-tolerant lookups."""
    out: dict[str, tuple[str, str]] = {}
    for title, code in _load_from_pg().items():
        n = _norm(title)
        if n and n not in out:
            out[n] = (title, code)
    return out


@st.cache_data(ttl=300, show_spinner=False)
def _code_to_title() -> dict[str, str]:
    """code -> first-seen canonical title from the SAP table."""
    out: dict[str, str] = {}
    for title, code in _load_from_pg().items():
        if code not in out:
            out[code] = title
    return out


def code_for(project_title: str | None) -> Optional[str]:
    """Lookup the SAP code for a project title.

    First tries an exact (stripped) match, then falls back to a normalized
    match (NFKC + whitespace collapse + casefold) so variants with NBSP,
    duplicate spaces or case differences still resolve to the same code.
    """
    if not project_title:
        return None
    s = str(project_title).strip()
    table = _load_from_pg()
    if s in table:
        return table[s]
    hit = _norm_index().get(_norm(s))
    return hit[1] if hit else None


def canonical_title_for(code: str | None) -> Optional[str]:
    """Return the canonical project title (as recorded in the SAP table)
    for a given SAP code. None if the code is unknown."""
    if not code:
        return None
    return _code_to_title().get(str(code).strip())


def label_with_code(project_title: str, max_len: int = 70) -> str:
    """Format a project title with its SAP code prefixed:
       'P-NG-K00-011  ·  Nigeria - Abia State …'  when the code is found."""
    if not project_title:
        return ""
    title = str(project_title).strip()
    short_title = title if len(title) <= max_len else title[: max_len - 1] + "…"
    code = code_for(title)
    return f"{code}  ·  {short_title}" if code else short_title


def counts() -> int:
    """Number of titles indexed (for diagnostics)."""
    return len(_load_from_pg())
