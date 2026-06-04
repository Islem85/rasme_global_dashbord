"""
KoboToolbox → PostgreSQL synchroniser.

Pour chaque pays référencé dans la table PostgreSQL ``public."List_of_forms"``
(colonnes ``Country``, ``Export _Old``, ``Export_New``), télécharge l'export
KoboToolbox correspondant et upsert les lignes dans une table
``kobo_<country>_<old|new>``. Schéma évolutif : toute nouvelle colonne
rencontrée est ajoutée via ``ALTER TABLE ... ADD COLUMN``.

Le script utilise les credentials PG + Kobo du fichier ``.env`` (mêmes
variables que celles utilisées par le dashboard Streamlit). Lancé via
``lancer_refresh_all.bat`` (étape 1) ou en standalone : ``python sync_kobo.py``.
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# ─────────────────────────────────────────────────────────────────
#  CONFIG depuis .env
# ─────────────────────────────────────────────────────────────────
HERE       = Path(__file__).resolve().parent
ASSETS_DIR = HERE / "assets"

FORMS_TABLE = 'public."List_of_forms"'

load_dotenv(HERE / ".env")

KOBO_USER     = os.getenv("KOBO_USER", "")
KOBO_PASSWORD = os.getenv("KOBO_PASSWORD", "")
PG_HOST       = os.getenv("PG_HOST", "localhost")
PG_PORT       = int(os.getenv("PG_PORT", "5432"))
PG_DB         = os.getenv("PG_DB", "mapping")
PG_USER       = os.getenv("PG_USER", "postgres")
PG_PASSWORD   = os.getenv("PG_PASSWORD", "")

# ─────────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────────
LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "kobo_sync.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
#  UTILITAIRES
# ─────────────────────────────────────────────────────────────────
def to_snake(text: str) -> str:
    """Convertit n'importe quel libellé Kobo en nom de colonne SQL."""
    s = str(text).lower()
    for src, dst in [("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
                     ("à", "a"), ("â", "a"), ("ä", "a"), ("ã", "a"),
                     ("ù", "u"), ("û", "u"), ("ü", "u"),
                     ("ô", "o"), ("ö", "o"), ("î", "i"), ("ï", "i"), ("ç", "c")]:
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:63]


def table_name(country: str, version: str) -> str:
    return f"kobo_{to_snake(country)}_{version}"


def get_pg_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )


# ─────────────────────────────────────────────────────────────────
#  CONFIGURATION DES FORMULAIRES
# ─────────────────────────────────────────────────────────────────
def _is_blank_url(value) -> bool:
    """Treat NULL / empty / '#N/A' sentinels as missing URLs."""
    if value is None:
        return True
    s = str(value).strip()
    return s == "" or s.upper() in {"#N/A", "N/A", "NA", "NONE", "NULL"}


def load_forms_config(conn) -> list[dict]:
    """Read the form catalogue from ``public."List_of_forms"``.

    The first row of the table is a BOM-prefixed header artefact left over
    from the original CSV import (``﻿Country``, ``Export _Old`` …) — we drop
    it the same way the Region loader does in ``db.py``.
    """
    sql = f'''
        SELECT
            "Country"     AS country,
            "Export _Old" AS export_old,
            "Export_New"  AS export_new
        FROM {FORMS_TABLE}
        WHERE "Country" IS NOT NULL
          AND btrim("Country") <> ''
          AND "Country" <> 'Country'
          AND "Country" <> chr(65279) || 'Country'
    '''
    forms: list[dict] = []
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    for country, url_old, url_new in rows:
        country = str(country).strip()
        if not country:
            continue
        if not _is_blank_url(url_old):
            forms.append({"country": country, "version": "old", "url": str(url_old).strip()})
        if not _is_blank_url(url_new):
            forms.append({"country": country, "version": "new", "url": str(url_new).strip()})

    log.info(
        f"Config chargée depuis {FORMS_TABLE} : "
        f"{len(forms)} formulaires à synchroniser."
    )
    return forms


# ─────────────────────────────────────────────────────────────────
#  TÉLÉCHARGEMENT EXPORT KOBOTOOLBOX
# ─────────────────────────────────────────────────────────────────
def fetch_export(url: str) -> list[dict]:
    auth = HTTPBasicAuth(KOBO_USER, KOBO_PASSWORD)
    resp = requests.get(url, auth=auth, timeout=120)

    if resp.status_code == 403:
        raise PermissionError(f"Accès refusé (403) : {url}")
    if resp.status_code == 404:
        log.warning(f"Export introuvable (404) : {url}")
        return []
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")

    if resp.text.lstrip().startswith("{") and '"FeatureCollection"' in resp.text[:200]:
        data = resp.json()
        features = data.get("features", [])
        log.info(f"    → GeoJSON : {len(features)} enregistrements")
        return features

    if "spreadsheet" in content_type or url.endswith(".xlsx"):
        try:
            df = pd.read_excel(io.BytesIO(resp.content))
            log.info(f"    → XLSX : {len(df)} lignes, {len(df.columns)} colonnes")
            return [{"geometry": None, "properties": row.to_dict()} for _, row in df.iterrows()]
        except Exception:
            pass

    if "text/csv" in content_type or url.endswith(".csv"):
        try:
            df = pd.read_csv(io.StringIO(resp.text))
            log.info(f"    → CSV : {len(df)} lignes, {len(df.columns)} colonnes")
            return [{"geometry": None, "properties": row.to_dict()} for _, row in df.iterrows()]
        except Exception:
            pass

    try:
        data = resp.json()
        if isinstance(data, list):
            return [{"geometry": None, "properties": r} for r in data]
        if "results" in data:
            return [{"geometry": None, "properties": r} for r in data["results"]]
    except Exception:
        pass

    log.warning(f"    Format non reconnu pour {url} (Content-Type: {content_type})")
    return []


# ─────────────────────────────────────────────────────────────────
#  TRANSFORMATION
# ─────────────────────────────────────────────────────────────────
def flatten_feature(feat: dict) -> dict:
    row: dict = {}
    lon, lat, alt = None, None, None
    geom = feat.get("geometry")
    if geom and geom.get("type") == "Point":
        coords = geom.get("coordinates", [])
        if len(coords) >= 2:
            lon = coords[0]
            lat = coords[1]
            alt = coords[2] if len(coords) > 2 else None
    row["longitude"] = str(lon) if lon is not None else None
    row["latitude"]  = str(lat) if lat is not None else None
    row["altitude"]  = str(alt) if alt is not None else None

    props = feat.get("properties") or {}
    for key, value in props.items():
        col = to_snake(key)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            row[col] = None
        else:
            row[col] = str(value)

    row["submission_uuid"] = (
        row.get("_uuid") or row.get("uuid") or row.get("_id")
        or str(props.get("_uuid") or props.get("_id", ""))
    )
    return row


# ─────────────────────────────────────────────────────────────────
#  SCHEMA POSTGRES
# ─────────────────────────────────────────────────────────────────
def ensure_table(conn, tbl: str, sample_cols: list) -> None:
    base_cols = ["longitude TEXT", "latitude TEXT", "altitude TEXT"]
    extra = [f'"{c}" TEXT' for c in sample_cols
             if c not in ("submission_uuid", "longitude", "latitude", "altitude", "id", "synced_at")]
    cols_ddl = ",\n    ".join(base_cols + extra)
    sql = f"""
    CREATE TABLE IF NOT EXISTS "{tbl}" (
        id              SERIAL PRIMARY KEY,
        submission_uuid TEXT UNIQUE NOT NULL,
        {cols_ddl},
        synced_at       TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS "idx_{tbl[:48]}_uuid" ON "{tbl}"(submission_uuid);
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = '_submission_time'", (tbl,)
        )
        if cur.fetchone():
            cur.execute(
                f'CREATE INDEX IF NOT EXISTS "idx_{tbl[:44]}_subtime" '
                f'ON "{tbl}"(_submission_time)'
            )
    conn.commit()


def add_missing_columns(conn, tbl: str, needed_cols: set) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (tbl,)
        )
        existing = {r[0] for r in cur.fetchall()}
    missing = needed_cols - existing - {"id", "synced_at"}
    if missing:
        with conn.cursor() as cur:
            for col in sorted(missing):
                log.info(f"    + Nouvelle colonne : \"{col}\"")
                cur.execute(f'ALTER TABLE "{tbl}" ADD COLUMN IF NOT EXISTS "{col}" TEXT')
        conn.commit()


def upsert_rows(conn, tbl: str, rows: list) -> int:
    if not rows:
        return 0
    all_cols: set = set()
    for r in rows:
        all_cols.update(r.keys())
    all_cols.discard("id")
    all_cols.discard("synced_at")
    add_missing_columns(conn, tbl, all_cols)

    cols       = sorted(all_cols)
    col_list   = ", ".join(f'"{c}"' for c in cols)
    ph         = ", ".join(["%s"] * len(cols))
    update_set = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c != "submission_uuid")
    data       = [tuple(r.get(c) for c in cols) for r in rows]

    with conn.cursor() as cur:
        psycopg2.extras.execute_batch(
            cur,
            f"""INSERT INTO "{tbl}" ({col_list}, synced_at)
                VALUES ({ph}, NOW())
                ON CONFLICT (submission_uuid) DO UPDATE SET
                    {update_set},
                    synced_at = NOW()""",
            data,
            page_size=500,
        )
    conn.commit()
    return len(rows)


def sweep_orphans(conn, tbl: str, current_uuids: list[str]) -> int:
    """Delete rows whose submission_uuid is no longer in the current export.

    Makes the per-country table a strict mirror of the live Kobo form: any
    submission deleted in KoboToolbox since the previous run is removed from
    PostgreSQL on the next sync. No-op if ``current_uuids`` is empty (we never
    wipe a table on a transient empty export — callers already skip in that
    case).
    """
    if not current_uuids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            f'DELETE FROM "{tbl}" WHERE NOT (submission_uuid = ANY(%s::text[]))',
            (list(current_uuids),),
        )
        deleted = cur.rowcount
    conn.commit()
    return deleted


# ─────────────────────────────────────────────────────────────────
#  ORCHESTRATION
# ─────────────────────────────────────────────────────────────────
def run_sync() -> bool:
    log.info("=" * 65)
    log.info(f"sync_kobo : démarrage — {datetime.now(timezone.utc).isoformat()}")

    if not (KOBO_USER and KOBO_PASSWORD):
        log.error("KOBO_USER / KOBO_PASSWORD manquants dans .env")
        return False

    conn = get_pg_connection()
    log.info(f"Connexion PostgreSQL OK ({PG_HOST}/{PG_DB})")
    forms = load_forms_config(conn)

    total, errors = 0, []
    for form in forms:
        country, version, url = form["country"], form["version"], form["url"]
        tbl = table_name(country, version)
        log.info(f"[{country}] {version.upper()} → table «{tbl}»")
        log.info(f"    URL : {url}")
        try:
            features = fetch_export(url)
            if not features:
                log.warning("    Aucune donnée — table ignorée.")
                continue
            rows = [flatten_feature(f) for f in features]
            rows = [r for r in rows if r.get("submission_uuid")]
            sample_cols = list(rows[0].keys()) if rows else []
            ensure_table(conn, tbl, sample_cols)
            n = upsert_rows(conn, tbl, rows)
            total += n
            log.info(f"    OK {n} lignes upsertées dans «{tbl}»")
            swept = sweep_orphans(conn, tbl, [r["submission_uuid"] for r in rows])
            if swept:
                log.info(f"    - {swept} ligne(s) obsolète(s) supprimée(s) de «{tbl}»")
        except PermissionError as e:
            conn.rollback()
            log.error(f"    ERR {e}")
            errors.append({"country": country, "version": version, "error": str(e)})
        except Exception as exc:
            conn.rollback()
            log.error(f"    ERR [{country}/{version}] : {exc}", exc_info=True)
            errors.append({"country": country, "version": version, "error": str(exc)})

    conn.close()
    log.info(f"sync_kobo terminé — {total} lignes traitées.")
    if errors:
        log.warning(f"{len(errors)} erreur(s) :")
        for e in errors:
            log.warning(f"  {e}")
    log.info("=" * 65)
    return len(errors) == 0


if __name__ == "__main__":
    ok = run_sync()
    sys.exit(0 if ok else 1)
