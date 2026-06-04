"""
MapAfrica scraper — fetches AfDB's public project catalogue and upserts it
into PostgreSQL table ``public."projet_BAD"``.

API endpoint:
    https://mapafrica.afdb.org/api/v15/activities?per_page=10000

Run from a terminal (or via ``lancer_scrape.bat``):
    python scrape_mapafrica.py

Status classification (per IATI activity_status codes):
    '1' → 'Approved'         (board-approved, may or may not have started)
    '2' → 'Ongoing'          (formally under implementation)
    '3' → 'Completion'       (completed)
    '4' → 'Post-completion'
    '5' → 'Cancelled'
    '6' → 'Suspended'

Derived booleans:
    is_active     = status_code IN ('1','2')   — the active portfolio
    is_completed  = status_code = '3'          — closed projects (still useful)
    is_cancelled  = status_code = '5'
    is_suspended  = status_code = '6'

The script DROPS and RECREATES the table on each run, since this is a clean
snapshot from a public source — no manual edits are expected on the table.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config import COUNTRY_ISO2

# ── Configuration ───────────────────────────────────────────────────────────
HERE       = Path(__file__).resolve().parent
ASSETS_DIR = HERE / "assets"
CSV_PATH   = ASSETS_DIR / "projet_BAD.csv"
API_URL    = "https://mapafrica.afdb.org/api/v15/activities?per_page=10000"
TABLE      = 'public."projet_BAD"'

# IATI activity_status codes → English labels (user-facing).
STATUS_LABELS: dict[str, str] = {
    "1": "Approved",
    "2": "Ongoing",
    "3": "Completion",
    "4": "Post-completion",
    "5": "Cancelled",
    "6": "Suspended",
}

# Reverse ISO-2 → internal slug lookup so each BAD record can be tagged
# with the internal kobo_clean country slug. Somaliland (no separate code)
# falls back to Somalia.
# Reverse ISO-2 → slug map. We deliberately drop "somaliland" so the ISO
# code 'SO' resolves to the canonical "somalia" slug (otherwise Somalia
# projects end up tagged as 'somaliland' and disappear from the country
# coverage tables).
ISO2_TO_SLUG = {
    iso: slug
    for slug, iso in COUNTRY_ISO2.items()
    if iso and slug != "somaliland"
}


def _make_engine() -> Engine:
    load_dotenv(HERE / ".env")
    user = quote_plus(os.getenv("PG_USER", "postgres"))
    pwd  = quote_plus(os.getenv("PG_PASSWORD", ""))
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    db_  = os.getenv("PG_DB",   "mapping")
    ssl  = os.getenv("PG_SSLMODE", "prefer")
    dsn  = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db_}?sslmode={ssl}"
    return create_engine(dsn, pool_pre_ping=True)


def fetch_activities() -> list[dict]:
    """One HTTP call, all 5 900+ records."""
    req = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept":          "application/json",
            "Accept-Language": "fr,en;q=0.9",
            "Referer":         "https://mapafrica.afdb.org/fr",
        },
    )
    print(f"  GET {API_URL}")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        payload = json.loads(resp.read().decode("utf-8"))
    records = payload.get("results") or []
    print(f"  - {len(records):,} records in {time.time() - t0:.1f}s")
    return records


def _first_iso2(country_codes: str | None) -> str | None:
    """``country_codes`` can be 'BF' or 'Z1,BF' for multi-country rows.
    Return the first non-Z1 token; fall back to the first token; None if blank."""
    if not country_codes:
        return None
    toks = [t.strip() for t in str(country_codes).split(",") if t.strip()]
    if not toks:
        return None
    non_z1 = [t for t in toks if t.upper() != "Z1"]
    return non_z1[0] if non_z1 else toks[0]


def to_dataframe(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        code = (r.get("afdb_identifier_ref") or "").strip()
        if not code:
            continue
        status_code = str(r.get("activity_status") or "").strip()
        label = STATUS_LABELS.get(status_code, status_code or None)
        iso2 = _first_iso2(r.get("country_codes"))
        slug = ISO2_TO_SLUG.get(iso2) if iso2 else None
        rows.append({
            "project_code":             code,
            "country":                  r.get("country"),
            "country_iso2":             iso2,
            "country_slug":             slug,
            "project_name":             r.get("title"),
            "status_code":              status_code or None,
            "status_label":             label,
            "is_active":                status_code in ("1", "2"),
            "is_completed":             status_code == "3",
            "is_cancelled":             status_code == "5",
            "is_suspended":             status_code == "6",
            "iati_identifier":          r.get("iati_identifier"),
            "recipient_country":        r.get("recipient_country"),
            "region":                   r.get("region"),
            "afdb_status":              r.get("afdb_status"),
            "sector_code":              r.get("sector_code"),
            "sector_group":             r.get("sector_group"),
            "custom_sector_code":       r.get("custom_sector_code"),
            "sovereign":                bool(r.get("sovereign")) if r.get("sovereign") is not None else None,
            "non_sovereign":            bool(r.get("non_sovereign")) if r.get("non_sovereign") is not None else None,
            "total_budget":             r.get("total_budget"),
            "total_disbursements":      r.get("total_disbursements"),
            "total_commitments":        r.get("total_commitments"),
            "total_expenditure":        r.get("total_expenditure"),
            "activity_date_planned_start":  r.get("activity_date_planned_start"),
            "activity_date_planned_end":    r.get("activity_date_planned_end"),
            "activity_date_actual_start":   r.get("activity_date_actual_start"),
            "activity_date_actual_end":     r.get("activity_date_actual_end"),
            "source_id":                r.get("id"),
        })

    df = pd.DataFrame(rows)
    # Dedupe defensively — the API uses afdb_identifier_ref as natural key.
    before = len(df)
    df = df.drop_duplicates(subset=["project_code"], keep="first")
    if before != len(df):
        print(f"  - dropped {before - len(df):,} duplicate(s) on project_code")

    # Date parsing — keep as text 'YYYY-MM-DD' that PostgreSQL casts on insert.
    for c in ("activity_date_planned_start", "activity_date_planned_end",
              "activity_date_actual_start",  "activity_date_actual_end"):
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.strftime("%Y-%m-%d")

    for c in ("total_budget", "total_disbursements",
              "total_commitments", "total_expenditure"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["source_id"] = pd.to_numeric(df["source_id"], errors="coerce").astype("Int64")
    return df


def recreate_table(engine: Engine) -> None:
    ddl = f"""
    DROP TABLE IF EXISTS {TABLE} CASCADE;
    CREATE TABLE {TABLE} (
        project_code                  TEXT PRIMARY KEY,
        country                       TEXT,
        country_iso2                  TEXT,
        country_slug                  TEXT,
        project_name                  TEXT,
        status_code                   TEXT,
        status_label                  TEXT,
        is_active                     BOOLEAN,
        is_completed                  BOOLEAN,
        is_cancelled                  BOOLEAN,
        is_suspended                  BOOLEAN,
        iati_identifier               TEXT,
        recipient_country             TEXT,
        region                        TEXT,
        afdb_status                   TEXT,
        sector_code                   TEXT,
        sector_group                  TEXT,
        custom_sector_code            TEXT,
        sovereign                     BOOLEAN,
        non_sovereign                 BOOLEAN,
        total_budget                  NUMERIC,
        total_disbursements           NUMERIC,
        total_commitments             NUMERIC,
        total_expenditure             NUMERIC,
        activity_date_planned_start   DATE,
        activity_date_planned_end     DATE,
        activity_date_actual_start    DATE,
        activity_date_actual_end      DATE,
        source_id                     BIGINT,
        fetched_at                    TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX idx_projet_bad_country_slug  ON {TABLE}(country_slug);
    CREATE INDEX idx_projet_bad_status_code   ON {TABLE}(status_code);
    CREATE INDEX idx_projet_bad_is_active     ON {TABLE}(is_active);
    CREATE INDEX idx_projet_bad_is_completed  ON {TABLE}(is_completed);
    """
    with engine.begin() as conn:
        for stmt in [s for s in ddl.split(";") if s.strip()]:
            conn.execute(text(stmt))


def insert(engine: Engine, df: pd.DataFrame) -> int:
    cols = [
        "project_code", "country", "country_iso2", "country_slug", "project_name",
        "status_code", "status_label", "is_active", "is_completed",
        "is_cancelled", "is_suspended", "iati_identifier", "recipient_country",
        "region", "afdb_status", "sector_code", "sector_group", "custom_sector_code",
        "sovereign", "non_sovereign", "total_budget", "total_disbursements",
        "total_commitments", "total_expenditure",
        "activity_date_planned_start", "activity_date_planned_end",
        "activity_date_actual_start",  "activity_date_actual_end",
        "source_id",
    ]
    payload = df[cols].copy()
    # Re-cast dates from strings: pandas will write text, PG casts on insert
    # because the target columns are DATE. Empty strings become NULL via
    # the explicit NULLIF in the staging→insert step below.
    stage = "_projet_bad_stage"
    payload.to_sql(stage, engine, if_exists="replace", index=False,
                   method="multi", chunksize=500)
    date_cols = {"activity_date_planned_start", "activity_date_planned_end",
                 "activity_date_actual_start",  "activity_date_actual_end"}
    selects = []
    for c in cols:
        if c in date_cols:
            selects.append(f"NULLIF({c}::text, '')::date AS {c}")
        else:
            selects.append(c)
    sql = f"""
        INSERT INTO {TABLE} ({", ".join(cols)})
        SELECT {", ".join(selects)} FROM {stage};
    """
    with engine.begin() as conn:
        conn.execute(text(sql))
        conn.execute(text(f"DROP TABLE IF EXISTS {stage}"))
    return len(payload)


def export_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  - CSV -> {path}")


def main() -> int:
    print("MapAfrica -> projet_BAD")
    records = fetch_activities()
    df = to_dataframe(records)
    print(f"  - {len(df):,} unique projects ready")

    engine = _make_engine()
    recreate_table(engine)
    n = insert(engine, df)
    export_csv(df, CSV_PATH)

    with engine.begin() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar() or 0
        breakdown = conn.execute(text(
            f"SELECT status_code, status_label, COUNT(*) "
            f"FROM {TABLE} GROUP BY 1,2 ORDER BY 1"
        )).all()
        active = conn.execute(text(
            f"SELECT COUNT(*) FROM {TABLE} WHERE is_active"
        )).scalar() or 0
        completed = conn.execute(text(
            f"SELECT COUNT(*) FROM {TABLE} WHERE is_completed"
        )).scalar() or 0

    print()
    print(f"OK projet_BAD : {total:,} rows ({n:,} inserted)")
    print(f"  Active (Approved + Ongoing) : {active:,}")
    print(f"  Completion                  : {completed:,}")
    print("  Full status breakdown:")
    for code, label, n_ in breakdown:
        print(f"    {(code or '-'):<3} {(label or '-'):<18} {n_:>6,}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP error: {e.code} {e.reason}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
