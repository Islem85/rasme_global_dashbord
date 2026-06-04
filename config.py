"""
Central configuration for the Global Dashboard.

COL maps the logical fields used by the dashboard to the actual column names in
PostgreSQL `mapping.kobo_clean`. Run `\\d mapping.kobo_clean` and edit this dict
once if names differ — every SQL string in the project resolves through it.
"""

COL = {
    "country":              "country",
    "version":              "form_version",
    "uuid":                 "uuid",
    "submission_time":      "submission_time",
    "synced_at":            "synced_at",
    "project_title":        "nom_projet",
    "project_code":         "identifiant_pa",
    "sector":               "secteur_activite",
    "category":             "objectif_projet",
    "lat":                  "latitude",
    "lon":                  "longitude",
    "region_name":          "region",
    "district_name":        "province",
    "commune":              "commune",
    "site_name":            "nom_site",
    "site_description":     "description_activite",
    "status":               "statut_implementation",
    "planned_start_date":   "date_debut",
    "planned_end_date":     "date_fin_prevue",
    "completion_date":      "date_fin_reelle",
    "progress_band":        "niveau_realisation",
    "planned_activities":   "resultats_attendus",
    "realised_activities":  "resultats_obtenus",
    "funder":               "institutions_financement",
    "co_funder":            "autre_institution_financement",
    "implementing_agency":  "nom_agence_execution",
    "agency_type":          "type_agence_execution",
    "beneficiaries":                  "nb_beneficiaires_directs",
    "beneficiaries_women":            "nb_beneficiaires_femmes",
    "beneficiaries_men":              "nb_beneficiaires_hommes",
    "beneficiaries_other":            "nb_beneficiaires_autres",
    "beneficiaries_children_under_5": "nb_enfants_moins_5_ans",
    "beneficiaries_children_5_18":    "nb_enfants_5_18_ans",
    "beneficiaries_elderly":          "nb_personnes_plus_60_ans",
    "beneficiaries_disabled":         "nb_personnes_handicapees",
    "beneficiaries_refugees":         "nb_refugies",
    "beneficiaries_idps":             "nb_deplaces_internes",
    "beneficiaries_returnees":        "nb_retournes",
    "issue_type":           "type_probleme",
    "issue_description":    "detail_probleme",
    "collection_date":      "date_collecte",
    # « Today » Kobo : date saisie par l'enquêteur à l'ouverture du formulaire.
    # Utilisée par le filtre date et la timeline d'activité de collecte ; les
    # autres requêtes (last_collection_date, country_timeline, etc.) continuent
    # de s'appuyer sur "collection_date" (qui consolide plusieurs sources).
    "today":                "today",
    "validation_status":    "validation_status",
    "geom":                 "geom",
    # Photos attached to each site collection (Kobo Toolbox).
    "photo_1":              "photo_1",
    "photo_1_url":          "photo_1_url",
    "photo_2":              "photo_2",
    "photo_2_url":          "photo_2_url",
}

TABLE = "public.kobo_clean"

# ── Bounding box Afrique ─────────────────────────────────────────────────────
# Source unique (partagée par db.map_points et export_sites_sans_gps.py). Sert
# à écarter de la carte et des exports les erreurs de saisie GPS (lat/lon
# inversés, fautes de frappe) qui tombent sur des coordonnées valides au niveau
# mondial mais hors du continent. Calibrée pour contenir tous les sites
# légitimes (étendue des données : lon ≈ [-17.5, 53.7], lat ≈ [-29.3, 37.0])
# avec une marge pour les États insulaires.
AFRICA_LON_MIN, AFRICA_LON_MAX = -26.0, 64.0
AFRICA_LAT_MIN, AFRICA_LAT_MAX = -36.0, 38.0

# All date/time columns are stored as text. Most rows match 'YYYY-MM-DD HH:MM:SS',
# but a handful contain garbage (e.g. 'NaT', 'Decembre 2028', '#activity_start_date').
# dt(col) returns a SQL expression that yields NULL for any non-parsable value.
def dt(col: str) -> str:
    return (
        f"CASE WHEN {col} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' "
        f"THEN {col}::timestamp END"
    )

PALETTE = {
    # AfDB green family — primary brand colour for borders, KPI numbers, headers.
    "primary":    "#008F4F",
    "primary_dk": "#005C33",

    # Status / accent.
    "success":    "#00A651",
    "warning":    "#F2A900",
    "danger":     "#C84030",
    "neutral":    "#5C6770",

    # Surfaces — clean white shell, white cards (RASME corporate dashboard look).
    "bg":         "#FFFFFF",
    "bg_deep":    "#F4F8F2",
    "card":       "#FFFFFF",
    "card_solid": "#FFFFFF",
    "border":     "#E2E8E0",
    "card_text":  "#1A1A1A",

    # Text on the white background.
    "text":       "#1A1A1A",
    "muted":      "#5C6770",

    # Eyebrow chip — soft green tint, used by pillar header pills.
    "eyebrow_bg": "#E6F4EC",

    # Institutional AfDB green (kept identical to primary; alias for clarity).
    "afdb_green":    "#008F4F",
    "afdb_green_dk": "#005C33",
}

# Status colors keyed by raw DB value. After translation we re-key to display names.
STATUS_COLORS = {
    "Completed":           PALETTE["success"],
    "In progress":         "#0066CC",
    "Planned":             PALETTE["warning"],
    "Stalled":             "#B36A00",
    "Stalled/ suspended":  "#B36A00",
    "Suspended":           "#A6321F",
    "Abandoned":           PALETTE["danger"],
    "Canceled":            "#7A0F1A",
}

# Display labels for statuses, FR / EN. Used to translate chart legends.
STATUS_LABELS = {
    "Completed":          ("Achevé",         "Completed"),
    "In progress":        ("En cours",       "In progress"),
    "Planned":            ("Planifié",       "Planned"),
    "Stalled":            ("Au point mort",  "Stalled"),
    "Stalled/ suspended": ("Au point mort",  "Stalled"),
    "Suspended":          ("Suspendu",       "Suspended"),
    "Abandoned":          ("Abandonné",      "Abandoned"),
    "Canceled":           ("Annulé",         "Canceled"),
}


def status_label(raw: str, lang: str) -> str:
    pair = STATUS_LABELS.get(raw)
    if not pair:
        return raw
    return pair[0] if lang == "FR" else pair[1]


def status_color_map(lang: str) -> dict[str, str]:
    """Build a Plotly color_discrete_map keyed on the *displayed* status string."""
    return {status_label(k, lang): v for k, v in STATUS_COLORS.items()}


INVALID_STATUS = ("#status", "None", "")

# ── Sector grouping ──────────────────────────────────────────────────────────
# Any source value that is NOT in this list is bucketed as "Multi-sector".
# This handles concatenated values like "Agriculture Social", "Energy Social", etc.

CANONICAL_SECTORS = (
    "Water and sanitation",
    "Agriculture",
    "Energy",
    "Transport",
    "Social",
    "Environment",
    "Education",
    "Health",
    "Finance",
    "Private sector",
    "Formation Professionnelle",
    "Entrepreneuriat",
    "Multi-sector",
    "Other",
)

# Source values that should be re-tagged to a canonical bucket name (case-sensitive).
SECTOR_REMAPS = {
    "Agriculture and Rural Development": "Agriculture",
}


# Country-slug remaps: source value → target slug used everywhere downstream.
# The source data has two case-variants ("Somalia" 71 rows + "somalia" 23 rows)
# that the data owner wants treated as a single country (Somalia, incl.
# Somaliland) — we fold both onto the lowercase form.
COUNTRY_REMAPS = {
    "Somalia":    "somalia",
    "somaliland": "somalia",   # historical alias kept for older snapshots
}


def country_bucket(col: str | None = None) -> str:
    """Return a SQL CASE expression that applies `COUNTRY_REMAPS` to a country
    column. Used everywhere a country slug is read or filtered on, so the
    merge between e.g. somaliland → somalia is transparent to the rest of
    the code."""
    col = col or COL["country"]
    if not COUNTRY_REMAPS:
        return col
    branches = []
    for src, dst in COUNTRY_REMAPS.items():
        s = src.replace("'", "''")
        d = dst.replace("'", "''")
        branches.append(f"WHEN {col} = '{s}' THEN '{d}'")
    return "CASE " + " ".join(branches) + f" ELSE {col} END"


# Display labels for sectors (FR / EN). Source values are mostly English so we
# translate to French on the fly. Keys must match the **bucketed** values
# (output of sector_bucket()), not the raw source.
SECTOR_LABELS = {
    "Water and sanitation":      ("Eau et assainissement",       "Water and sanitation"),
    "Agriculture":               ("Agriculture",                 "Agriculture"),
    "Energy":                    ("Énergie",                     "Energy"),
    "Transport":                 ("Transport",                   "Transport"),
    "Social":                    ("Social",                      "Social"),
    "Environment":               ("Environnement",               "Environment"),
    "Education":                 ("Éducation",                   "Education"),
    "Health":                    ("Santé",                       "Health"),
    "Finance":                   ("Finance",                     "Finance"),
    "Private sector":            ("Secteur privé",               "Private sector"),
    "Formation Professionnelle": ("Formation professionnelle",   "Vocational training"),
    "Entrepreneuriat":           ("Entrepreneuriat",             "Entrepreneurship"),
    "Multi-sector":              ("Multi-secteurs",              "Multi-sector"),
    "Other":                     ("Autre",                       "Other"),
    "Unknown":                   ("Inconnu",                     "Unknown"),
}


def sector_label(raw: str | None, lang: str) -> str:
    """Translate a bucketed sector value to its FR/EN display form."""
    if not raw:
        return "—"
    pair = SECTOR_LABELS.get(str(raw))
    if not pair:
        return str(raw)
    return pair[0] if lang == "FR" else pair[1]


def sector_bucket(col: str | None = None) -> str:
    """Return SQL CASE expression that buckets the sector column:

      • Values listed in `SECTOR_REMAPS` are renamed to the target bucket.
      • Values in `CANONICAL_SECTORS` are kept as-is.
      • Anything else → 'Multi-sector'.
    """
    col = col or COL["sector"]
    branches = []
    for src, dst in SECTOR_REMAPS.items():
        s = src.replace("'", "''")
        d = dst.replace("'", "''")
        branches.append(f"WHEN {col} = '{s}' THEN '{d}'")
    vals = ", ".join("'" + s.replace("'", "''") + "'" for s in CANONICAL_SECTORS)
    branches.append(f"WHEN {col} IN ({vals}) THEN {col}")
    return "CASE " + " ".join(branches) + " ELSE 'Multi-sector' END"

# Country name as it appears in the Regional Operations Dashboard (ROD)
# Excel file -> internal kobo_clean country slug. The ROD is now the
# authoritative source for the BAD portfolio (replacing MapAfrica's API).
# Countries on the ROD side that do not exist in our internal slug set
# (e.g. Algeria, Botswana, South Africa, Eritrea…) are simply left out.
ROD_COUNTRY_TO_SLUG = {
    "Angola":          "angola",
    "Benin":           "benin",
    "Burkina Faso":    "burkina_faso",
    "Burundi":         "burundi",
    "Cameroon":        "cameroun",
    "Centrafrique":    "rca",
    "Chad":            "chad",
    "Comoros":         "comoros",
    "Congo CG":        "congo",
    "Cote D'Ivoire":   "cote_d_ivoire",
    "Dem Rep Congo":   "drc",
    "Djibouti":        "djibouti",
    "Egypt":           "egypt",
    "Ethiopia":        "ethiopia",
    "Gabon":           "gabon",
    "Guinea":          "guinee",
    "Kenya":           "kenya",
    "Lesotho":         "lesotho",
    "Madagascar":      "madagascar",
    "Malawi":          "malawi",
    "Mali":            "mali",
    "Mauritania":      "mauritania",
    "Morocco":         "maroc",
    "Mozambique":      "mozambique",
    "Namibia":         "namibia",
    "Niger":           "niger",
    "Nigeria":         "nigeria",
    "Rwanda":          "rwanda",
    "Senegal":         "senegal",
    "Sierra Leone":    "sierra_leone",
    "Somalia":         "somalia",
    "South Sudan":     "south_sudan",
    "Sudan":           "sudan",
    "Tanzania":        "tanzania",
    "Togo":            "togo",
    "Tunisia":         "tunisia",
    "Uganda":          "uganda",
    "Zambia":          "zambia",
}


# Internal country slug -> ISO-2 alpha. Kept as a fallback for legacy
# helpers; the ROD pipeline matches on country names via ROD_COUNTRY_TO_SLUG.
COUNTRY_ISO2 = {
    "angola":"AO", "benin":"BJ", "burkina_faso":"BF", "burundi":"BI",
    "cameroun":"CM", "chad":"TD", "comoros":"KM", "congo":"CG",
    "cote_d_ivoire":"CI", "djibouti":"DJ", "drc":"CD", "egypt":"EG",
    "ethiopia":"ET", "gabon":"GA", "guinee":"GN", "kenya":"KE",
    "lesotho":"LS", "madagascar":"MG", "malawi":"MW", "mali":"ML",
    "maroc":"MA", "mauritania":"MR", "mozambique":"MZ", "namibia":"NA",
    "niger":"NE", "nigeria":"NG", "rca":"CF", "rwanda":"RW",
    "senegal":"SN", "sierra_leone":"SL", "somalia":"SO", "somaliland":"SO",
    "south_sudan":"SS", "sudan":"SD", "tanzania":"TZ", "togo":"TG",
    "tunisia":"TN", "uganda":"UG", "zambia":"ZM",
}

COUNTRY_ISO3 = {
    "angola": "AGO", "benin": "BEN", "burkina_faso": "BFA", "burundi": "BDI",
    "cameroun": "CMR", "chad": "TCD", "comoros": "COM", "congo": "COG",
    "cote_d_ivoire": "CIV", "djibouti": "DJI", "drc": "COD", "egypt": "EGY",
    "ethiopia": "ETH", "gabon": "GAB", "guinee": "GIN", "kenya": "KEN",
    "lesotho": "LSO", "madagascar": "MDG", "malawi": "MWI", "mali": "MLI",
    "maroc": "MAR", "mauritania": "MRT", "mozambique": "MOZ", "namibia": "NAM",
    "niger": "NER", "nigeria": "NGA", "rca": "CAF", "rwanda": "RWA",
    "senegal": "SEN", "sierra_leone": "SLE", "somalia": "SOM", "somaliland": "SOM",
    "south_sudan": "SSD", "sudan": "SDN", "tanzania": "TZA", "togo": "TGO",
    "tunisia": "TUN", "uganda": "UGA", "zambia": "ZMB",
}

COUNTRY_LABELS = {
    "angola":        ("Angola",                       "Angola"),
    "benin":         ("Bénin",                        "Benin"),
    "burkina_faso":  ("Burkina Faso",                 "Burkina Faso"),
    "burundi":       ("Burundi",                      "Burundi"),
    "cameroun":      ("Cameroun",                     "Cameroon"),
    "chad":          ("Tchad",                        "Chad"),
    "comoros":       ("Comores",                      "Comoros"),
    "congo":         ("Congo (Brazzaville)",          "Congo (Brazzaville)"),
    "cote_d_ivoire": ("Côte d'Ivoire",                "Côte d'Ivoire"),
    "djibouti":      ("Djibouti",                     "Djibouti"),
    "drc":           ("RD Congo",                     "DR Congo"),
    "egypt":         ("Égypte",                       "Egypt"),
    "ethiopia":      ("Éthiopie",                     "Ethiopia"),
    "gabon":         ("Gabon",                        "Gabon"),
    "guinee":        ("Guinée",                       "Guinea"),
    "kenya":         ("Kenya",                        "Kenya"),
    "lesotho":       ("Lesotho",                      "Lesotho"),
    "madagascar":    ("Madagascar",                   "Madagascar"),
    "malawi":        ("Malawi",                       "Malawi"),
    "mali":          ("Mali",                         "Mali"),
    "maroc":         ("Maroc",                        "Morocco"),
    "mauritania":    ("Mauritanie",                   "Mauritania"),
    "mozambique":    ("Mozambique",                   "Mozambique"),
    "namibia":       ("Namibie",                      "Namibia"),
    "niger":         ("Niger",                        "Niger"),
    "nigeria":       ("Nigéria",                      "Nigeria"),
    "rca":           ("République centrafricaine",    "Central African Republic"),
    "rwanda":        ("Rwanda",                       "Rwanda"),
    "senegal":       ("Sénégal",                      "Senegal"),
    "sierra_leone":  ("Sierra Leone",                 "Sierra Leone"),
    "somalia":       ("Somalie",                      "Somalia"),
    "somaliland":    ("Somaliland",                   "Somaliland"),
    "south_sudan":   ("Soudan du Sud",                "South Sudan"),
    "sudan":         ("Soudan",                       "Sudan"),
    "tanzania":      ("Tanzanie",                     "Tanzania"),
    "togo":          ("Togo",                         "Togo"),
    "tunisia":       ("Tunisie",                      "Tunisia"),
    "uganda":        ("Ouganda",                      "Uganda"),
    "zambia":        ("Zambie",                       "Zambia"),
}


def country_label(slug: str, lang: str) -> str:
    pair = COUNTRY_LABELS.get(slug)
    if not pair:
        return slug.replace("_", " ").title()
    return pair[0] if lang == "FR" else pair[1]


# Region labels — keep the AfDB technical code as-is in both languages
# (RDGN / RDGS / RDGE / RDGW / RDGC / RDNG) per the project owner's preference.
REGION_LABELS = {
    "RDGN": ("RDGN", "RDGN"),
    "RDGS": ("RDGS", "RDGS"),
    "RDGE": ("RDGE", "RDGE"),
    "RDGW": ("RDGW", "RDGW"),
    "RDGC": ("RDGC", "RDGC"),
    "RDNG": ("RDNG", "RDNG"),
}


def region_label(code: str | None, lang: str) -> str:
    """Translate a region code (RDGE/RDGW/...) to its FR/EN display form."""
    if not code:
        return "—"
    pair = REGION_LABELS.get(str(code))
    if not pair:
        return str(code)
    return pair[0] if lang == "FR" else pair[1]


# Country-name aliases used to match the "label" column of public."Region"
# (English names like 'Cape Verde', 'C\\u00f4te D\\'Ivoire', 'Congo(Brazaville)')
# back to our internal slugs in kobo_clean.country.
_REGION_NAME_ALIASES = {
    # snake_case slug : list of strings as they appear in the Region table
    "cote_d_ivoire": ["Côte D'Ivoire", "Cote D'Ivoire", "Côte d'Ivoire"],
    "drc":           ["DR Congo", "Democratic Republic of the Congo"],
    "congo":         ["Congo(Brazaville)", "Congo (Brazzaville)", "Republic of the Congo"],
    "cameroun":      ["Cameroon"],
    "rca":           ["Central African Republic"],
    "guinee":        ["Guinea"],
    "maroc":         ["Morocco"],
    "egypt":         ["Egypt"],
    "ethiopia":      ["Ethiopia"],
    "south_sudan":   ["South Sudan"],
    "sierra_leone":  ["Sierra Leone"],
    "chad":          ["Chad"],
    "comoros":       ["Comoros"],
    "somalia":       ["Somalia"],
    "somaliland":    ["Somaliland"],
    "burkina_faso":  ["Burkina Faso"],
    # All others match COUNTRY_LABELS[..][1] (the English label).
}


def country_to_region_lookup(region_df) -> dict[str, str]:
    """Build a {country_slug → region_code} map from the Region DataFrame.

    `region_df` is the cached result of `db.region_table()`. We match the
    English `label` column against our `COUNTRY_LABELS[slug][1]` plus any
    declared alias.
    """
    if region_df is None or region_df.empty:
        return {}
    label_to_region = {
        str(row["label"]).strip(): str(row["region"]).strip()
        for _, row in region_df.iterrows()
        if row.get("label") and row.get("region")
    }
    out: dict[str, str] = {}
    for slug, (_, en_label) in COUNTRY_LABELS.items():
        candidates = [en_label] + _REGION_NAME_ALIASES.get(slug, [])
        for c in candidates:
            if c in label_to_region:
                out[slug] = label_to_region[c]
                break
    return out
