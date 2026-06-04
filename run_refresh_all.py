"""
Orchestrateur — rafraîchit toute la donnée du dashboard en un seul clic.

Pipeline :
  1. sync_kobo.py        — télécharge chaque export KoboToolbox listé dans
                            la table PostgreSQL public."List_of_forms" et
                            upsert dans les tables kobo_<country>_<old|new>.
  2. rebuild_global.py   — reconstruit kobo_all_global comme UNION ALL
                            de toutes les tables par pays (toutes colonnes
                            en TEXT, alignement automatique).
  3. cleanup_kobo.sql    — DROP/CREATE kobo_clean avec COALESCE des colonnes
                            qui changent de nom selon les versions de form
                            (inclut le fix photo_of_activity_*_url).
  4. export_sites_sans_gps.py — régénère assets/sites_sans_gps.{csv,xlsx}
                            (sites au statut valide non cartographiables).
  5. scrape_mapafrica.py — DROP/CREATE projet_BAD depuis l'API MapAfrica.
  6. export_projets_sans_bad.py — régénère assets/projets_sans_bad.{csv,xlsx}
                            (projets cartographiés sans correspondance BAD ;
                            nécessite kobo_clean ET projet_BAD).

Chaque étape est journalisée dans logs/refresh_all.log. Si une étape échoue,
le pipeline s'arrête avec un code de retour non nul.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
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

LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "refresh_all.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def run_python(script: str) -> bool:
    """Run a sibling Python script in a subprocess and stream its output."""
    log.info("─" * 65)
    log.info(f"STEP — {script}")
    log.info("─" * 65)
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, str(HERE / script)],
        cwd=str(HERE),
    )
    dt = time.time() - t0
    ok = proc.returncode == 0
    log.info(f"  -> {script} terminé en {dt:.1f}s (code {proc.returncode})")
    return ok


def run_sql_file(sql_path: Path) -> bool:
    """Execute every statement in the SQL file against the configured PG."""
    log.info("─" * 65)
    log.info(f"STEP — {sql_path.name}")
    log.info("─" * 65)
    if not sql_path.exists():
        log.error(f"  Fichier SQL introuvable : {sql_path}")
        return False
    sql_text = sql_path.read_text(encoding="utf-8")
    t0 = time.time()
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(sql_text)
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        log.error(f"  ERREUR SQL : {type(exc).__name__}: {exc}")
        return False
    dt = time.time() - t0
    log.info(f"  -> {sql_path.name} exécuté en {dt:.1f}s")
    return True


def main() -> int:
    log.info("=" * 65)
    log.info("REFRESH ALL — démarrage")
    log.info("=" * 65)

    steps = [
        ("sync_kobo.py",             lambda: run_python("sync_kobo.py")),
        ("rebuild_global.py",        lambda: run_python("rebuild_global.py")),
        ("cleanup_kobo.sql",         lambda: run_sql_file(HERE / "cleanup_kobo.sql")),
        ("export_sites_sans_gps.py", lambda: run_python("export_sites_sans_gps.py")),
        ("scrape_mapafrica.py",      lambda: run_python("scrape_mapafrica.py")),
        ("export_projets_sans_bad.py", lambda: run_python("export_projets_sans_bad.py")),
    ]

    for name, runner in steps:
        if not runner():
            log.error(f"PIPELINE STOPPED at: {name}")
            return 1

    log.info("=" * 65)
    log.info("REFRESH ALL — pipeline complet OK")
    log.info("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
