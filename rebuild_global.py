"""
Reconstruit la table consolidée ``public.kobo_all_global`` à partir des
tables par pays ``kobo_<country>_<old|new>`` produites par sync_kobo.py.

Stratégie :
  1. Lister toutes les tables matchant ``kobo_*_(old|new)`` (sauf
     kobo_all_* et kobo_clean).
  2. Découvrir l'union de toutes leurs colonnes.
  3. DROP + CREATE TABLE kobo_all_global avec ces colonnes (+ origin_table,
     country, form_version) toutes en TEXT — alignées avec ce que le
     script de nettoyage cleanup_kobo.sql attend en entrée.
  4. INSERT … SELECT (UNION ALL) chaque table dans la table consolidée,
     avec NULL::TEXT pour les colonnes absentes d'une table donnée. Certaines
     tables sources sont filtrées à l'insertion (cf. SOURCE_FILTERS) : pour le
     Malawi, seules les activités financées par la Banque africaine de
     développement (AfDB seule ou co-financement WB+AfDB) sont consolidées.

Note : on garde tout en TEXT côté kobo_all_global ; les conversions
::DOUBLE PRECISION / ::DATE sont gérées par cleanup_kobo.sql au moment
de produire kobo_clean.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

PG_HOST     = os.getenv("PG_HOST", "localhost")
PG_PORT     = int(os.getenv("PG_PORT", "5432"))
PG_DB       = os.getenv("PG_DB", "mapping")
PG_USER     = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

# Colonnes méta toujours présentes dans kobo_all_global, dans l'ordre où
# cleanup_kobo.sql les attend.
META_COLS = ["origin_table", "country", "form_version"]

# Filtres source appliqués au SELECT d'insertion (sans le mot-clé WHERE).
# Pour le Malawi, on ne consolide que les activités financées — même
# partiellement — par la Banque africaine de développement.
SOURCE_FILTERS = {
    "kobo_malawi_old":
        "\"institution_s_financing_the_visited_activity\" IN "
        "('African Development Bank (AfDB)', 'Both WB and AfDB')",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(HERE / "logs" / "rebuild_global.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
(HERE / "logs").mkdir(exist_ok=True)
log = logging.getLogger(__name__)


def get_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )


def list_country_tables(conn) -> list[tuple[str, str, str]]:
    """Return [(table_name, country, version), …] for every per-country source."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name ~ '^kobo_.+_(old|new)$'
              AND table_name NOT LIKE 'kobo_all_%'
              AND table_name <> 'kobo_clean'
            ORDER BY table_name
        """)
        out = []
        for (tbl,) in cur.fetchall():
            # kobo_<slug>_<version>
            assert tbl.startswith("kobo_") and (tbl.endswith("_old") or tbl.endswith("_new"))
            version = "new" if tbl.endswith("_new") else "old"
            country_slug = tbl[len("kobo_"):-(len(version) + 1)]
            out.append((tbl, country_slug, version))
        return out


def columns_of(conn, tbl: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (tbl,))
        return [r[0] for r in cur.fetchall()]


def rebuild() -> bool:
    log.info("rebuild_global : démarrage")
    conn = get_conn()
    try:
        tables = list_country_tables(conn)
        if not tables:
            log.warning("Aucune table kobo_<country>_<old|new> trouvée.")
            return False
        log.info(f"{len(tables)} tables sources détectées.")

        # Union de toutes les colonnes vues à travers les tables sources.
        all_cols_set: set[str] = set()
        per_table_cols: dict[str, set[str]] = {}
        for tbl, _, _ in tables:
            cols = set(columns_of(conn, tbl))
            # Filtre les colonnes purement techniques qu'on ne veut pas
            # propager dans kobo_all_global.
            cols.discard("id")
            per_table_cols[tbl] = cols
            all_cols_set.update(cols)

        # Order: META_COLS first, then everything else sorted alphabetically.
        all_cols = META_COLS + sorted(c for c in all_cols_set if c not in META_COLS)
        log.info(f"Union des colonnes : {len(all_cols)} (dont {len(META_COLS)} métadonnées).")

        # DROP + CREATE TABLE
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS public.kobo_all_global CASCADE")
            cols_ddl = ",\n    ".join(f'"{c}" TEXT' for c in all_cols)
            cur.execute(f'CREATE TABLE public.kobo_all_global (\n    {cols_ddl}\n)')
            log.info(f"Table kobo_all_global recréée avec {len(all_cols)} colonnes.")

            # INSERT FROM each source table, padding missing columns with NULL.
            inserted_total = 0
            for tbl, country, version in tables:
                src_cols = per_table_cols[tbl]
                select_parts = []
                for c in all_cols:
                    if c == "origin_table":
                        select_parts.append(f"'{tbl}' AS \"origin_table\"")
                    elif c == "country":
                        select_parts.append(f"'{country}' AS \"country\"")
                    elif c == "form_version":
                        select_parts.append(f"'{version}' AS \"form_version\"")
                    elif c in src_cols:
                        select_parts.append(f'"{c}"::TEXT AS "{c}"')
                    else:
                        select_parts.append(f'NULL::TEXT AS "{c}"')
                col_list = ", ".join(f'"{c}"' for c in all_cols)
                where_sql = SOURCE_FILTERS.get(tbl)
                insert_sql = (
                    f'INSERT INTO public.kobo_all_global ({col_list})\n'
                    f'SELECT {", ".join(select_parts)} FROM public."{tbl}"'
                )
                if where_sql:
                    insert_sql += f"\nWHERE {where_sql}"
                cur.execute(insert_sql)
                inserted_total += cur.rowcount
                flag = "  [filtre AfDB]" if where_sql else ""
                log.info(f'  + {tbl:<40}  {cur.rowcount:>6} lignes{flag}')
            conn.commit()
            log.info(f"Total inséré : {inserted_total} lignes dans kobo_all_global.")

            cur.execute("CREATE INDEX idx_all_global_country ON public.kobo_all_global(country)")
            cur.execute("CREATE INDEX idx_all_global_version ON public.kobo_all_global(form_version)")
            conn.commit()
            log.info("Index attribués (country, form_version).")
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    ok = rebuild()
    sys.exit(0 if ok else 1)
