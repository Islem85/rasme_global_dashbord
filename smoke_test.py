"""Smoke-test every query against the live PostgreSQL DB. Bypasses Streamlit's caching."""

from __future__ import annotations

import sys
import traceback
from datetime import date, timedelta

# Stub st.cache_data / st.cache_resource so db.py can be imported without a Streamlit runtime.
class _Stub:
    def __init__(self): pass
    def __getattr__(self, name):
        def passthrough(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            def deco(fn): return fn
            return deco
        return passthrough

import streamlit  # noqa: F401  ensure path
streamlit.cache_data    = _Stub().__getattr__("x")
streamlit.cache_resource = _Stub().__getattr__("x")

import db  # noqa: E402


def run(name, fn):
    try:
        out = fn()
        if hasattr(out, "shape"):
            print(f"  ✓ {name:38s} → {out.shape}")
        elif isinstance(out, (list, tuple)):
            print(f"  ✓ {name:38s} → len={len(out)}")
        elif isinstance(out, dict):
            print(f"  ✓ {name:38s} → keys={list(out.keys())}")
        else:
            print(f"  ✓ {name:38s} → {out}")
    except Exception:
        print(f"  ✗ {name}")
        traceback.print_exc()
        sys.exit(1)


print("─── live smoke test ─────────────────────────────")
filters_empty = {"date_from": None, "date_to": None,
                 "sectors": None, "categories": None, "funders": None, "statuses": None}
filters_period = {**filters_empty,
                  "date_from": date.today() - timedelta(days=365 * 3),
                  "date_to":   date.today()}

run("filter_options",            lambda: db.filter_options())
run("date_bounds",               lambda: db.date_bounds())
run("kpi_overview (empty)",      lambda: db.kpi_overview(filters_empty))
run("kpi_overview (period)",     lambda: db.kpi_overview(filters_period))
run("kpi_by_country",            lambda: db.kpi_by_country(filters_empty))
run("country_status_breakdown",  lambda: db.country_status_breakdown(filters_empty, top_n=10))
run("sector_breakdown",          lambda: db.sector_breakdown(filters_empty))
run("funder_breakdown",          lambda: db.funder_breakdown(filters_empty))
run("temporal_trend",            lambda: db.temporal_trend(filters_empty))
run("status_distribution",       lambda: db.status_distribution(filters_empty))
run("map_points (limit 50)",     lambda: db.map_points(filters_empty, limit=50))
run("recent_submissions_count",  lambda: db.recent_submissions_count(filters_empty, days=30))

# country-specific
opts = db.filter_options()
country_pick = next((c for c in ("malawi", "burkina_faso", "nigeria") if c in opts.get("country", [])), None)
if not country_pick:
    country_pick = opts["country"][0] if opts.get("country") else None
print(f"\n  ▸ country pick: {country_pick}")

if country_pick:
    run("country_kpis_with_delta",  lambda: db.country_kpis_with_delta(country_pick, filters_empty))
    run("country_pipeline",         lambda: db.country_pipeline(country_pick, filters_empty))
    run("country_funnel",           lambda: db.country_funnel(country_pick, filters_empty))
    run("country_region_status",    lambda: db.country_region_status(country_pick, filters_empty))
    run("country_delay_distribution", lambda: db.country_delay_distribution(country_pick, filters_empty))
    run("country_issues",           lambda: db.country_issues(country_pick, filters_empty))
    run("country_projects",         lambda: db.country_projects(country_pick, filters_empty))
    run("country_regions",          lambda: db.country_regions(country_pick, filters_empty))
    run("country_beneficiaries",    lambda: db.country_beneficiaries(country_pick, filters_empty))

# Filter sanity: sectors should now include 'Multi-sector' even though some
# raw values like 'Agriculture Social' aren't canonical.
print()
print("  ▸ Bucketed sector list:")
for s in opts.get("sector", []):
    print(f"     - {s}")

# Verify Active projects KPI uses distinct project titles (not codes)
print()
kp = db.kpi_overview(filters_empty)
print(f"  ▸ active_projects (distinct project_title where status in In progress/Planned): {kp['active_projects']}")
print(f"  ▸ sites: {kp['sites']:,} · countries: {kp['countries']} · completion %: {kp['completion_rate']} · at-risk %: {kp['at_risk_rate']}")

print("\n─── all queries OK ──────────────────────────────")
