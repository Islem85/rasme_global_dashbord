"""Bilingual labels — every visible string in the dashboard resolves through `t(key, lang)`."""

I18N = {
    "app_title":             ("AfDB · Suivi du portefeuille terrain",  "AfDB · Field Portfolio Monitoring"),
    "subtitle":              ("Plateforme de visualisation Kobo · BAD","Kobo Visualisation Platform · AfDB"),
    "language":              ("Langue",                         "Language"),
    "last_refresh":          ("Dernière mise à jour",           "Last refresh"),
    "data_source":           ("Source : PostgreSQL · public.kobo_clean", "Source: PostgreSQL · public.kobo_clean"),

    # nav
    "nav_global":            ("Vue Globale",                    "Global View"),
    "nav_country":           ("Vue par Pays",                   "Country View"),

    # filters
    "filters":               ("Filtres",                        "Filters"),
    "period":                ("Période",                        "Period"),
    "from":                  ("Du",                             "From"),
    "to":                    ("Au",                             "To"),
    "region":                ("Région",                         "Region"),
    "sector":                ("Secteur",                        "Sector"),
    "category":              ("Catégorie",                      "Category"),
    "funder":                ("Bailleur",                       "Funder"),
    "status":                ("Statut",                         "Status"),
    "all":                   ("Tous",                           "All"),
    "select_country":        ("Sélectionner un pays",           "Select a country"),
    "select_project":        ("Projet (optionnel)",             "Project (optional)"),
    "select_region":         ("Région (optionnel)",             "Region (optional)"),
    "reset_filters":         ("Réinitialiser",                  "Reset"),
    "clear_dates":           ("Effacer les dates",              "Clear dates"),

    # KPIs
    "sites_total":           ("Sites suivis",                   "Sites monitored"),
    "countries_covered":     ("Pays couverts",                  "Countries covered"),
    "active_projects":       ("Projets actifs",                 "Active projects"),
    "completion_rate":       ("Taux d'achèvement",              "Completion rate"),
    "at_risk_rate":          ("Sites à risque",                 "At-risk sites"),
    "in_progress":           ("En cours",                       "In progress"),
    "planned":               ("Planifié",                       "Planned"),
    "completed":             ("Achevé",                         "Completed"),
    "stalled":               ("Au point mort",                  "Stalled"),
    "suspended":             ("Suspendu",                       "Suspended"),
    "abandoned":             ("Abandonné",                      "Abandoned"),
    "canceled":              ("Annulé",                         "Canceled"),
    "delay_days":            ("Retard (jours)",                 "Delay (days)"),
    "beneficiaries_direct":  ("Bénéficiaires directs",          "Direct beneficiaries"),
    "beneficiaries_women":   ("Femmes",                         "Women"),
    "beneficiaries_men":     ("Hommes",                         "Men"),
    "beneficiaries_other":   ("Autres",                         "Other"),
    "beneficiaries_children_under_5": ("Enfants < 5 ans",       "Children < 5"),
    "beneficiaries_children_5_18":    ("Enfants 5–18 ans",      "Children 5–18"),
    "beneficiaries_elderly": ("Plus de 60 ans",                 "Over 60"),
    "beneficiaries_disabled":("Personnes handicapées",          "Persons with disabilities"),
    "beneficiaries_refugees":("Réfugiés",                       "Refugees"),
    "beneficiaries_idps":    ("Déplacés internes",              "Internally displaced"),
    "beneficiaries_returnees":("Retournés",                     "Returnees"),
    "section_beneficiaries": ("Bénéficiaires",                  "Beneficiaries"),
    "benef_by_gender":       ("Répartition par genre",          "Breakdown by gender"),
    "benef_by_age":          ("Répartition par âge",            "Breakdown by age"),
    "benef_vulnerable":      ("Groupes vulnérables",            "Vulnerable groups"),
    "benef_total":           ("Total bénéficiaires directs",    "Total direct beneficiaries"),
    "of_total":              ("du total",                       "of total"),
    "vs_global_avg":         ("vs moyenne globale",             "vs global average"),
    "data_completeness":     ("Complétude des données",         "Data completeness"),
    "last_collection":       ("Dernière collecte",              "Last data collection"),
    "country_sites":         ("Sites du pays",                  "Country sites"),
    "country_projects":      ("Projets du pays",                "Country projects"),
    "expl_country_projects": ("Projets distincts (titre) ayant au moins un site collecté dans le pays.",
                              "Distinct projects (title) with at least one collected site in the country."),

    # sections / chart titles
    "section_overview":      ("Vue d'ensemble",                 "Overview"),
    "section_geo":           ("Cartographie",                   "Geographic distribution"),
    "section_breakdown":     ("Répartitions",                   "Breakdowns"),
    "section_temporal":      ("Évolution temporelle",           "Temporal trend"),
    "section_insights":      ("Points clés",                    "Key insights"),
    "section_pipeline":      ("Pipeline opérationnel",          "Operational pipeline"),
    "section_issues":        ("Problèmes signalés",             "Reported issues"),
    "section_compare":       ("Comparaison avec le global",     "Comparison with global"),
    "section_arcgis":        ("Carte interactive ArcGIS",       "Interactive ArcGIS map"),
    "section_delivery":      ("Performance d'exécution",        "Delivery performance"),
    "section_outputs":       ("Outputs physiques",              "Physical outputs"),

    # Delivery KPIs
    "overdue_activities":    ("Activités en retard",            "Overdue activities"),
    "avg_duration":          ("Durée moyenne (j)",              "Average duration (d)"),
    "on_time_rate":          ("Respect des délais",             "On-time completion"),

    # Outputs
    "outputs_total":         ("Sites avec output détecté",      "Sites with detected output"),
    "outputs_infra":         ("Infrastructures construites",    "Infrastructure built"),
    "outputs_equipment":     ("Équipements / matériels",        "Equipment delivered"),
    "outputs_delivery":      ("Livraisons (semences, intrants)","Inputs delivered"),
    "outputs_per_project":   ("Outputs / projet",               "Outputs per project"),
    "outputs_documented":    ("Sites avec résultats renseignés","Sites with documented results"),
    "outputs_breakdown":     ("Détail par catégorie",           "Breakdown by category"),
    "outputs_disclaimer":    ("Détection automatique par mots-clés sur les noms et descriptions de site",
                              "Automatic keyword detection on site names and descriptions"),

    # Hero
    "hero_eyebrow":          ("AfDB · Scorecard du portefeuille terrain",
                              "AfDB · Field Portfolio Scorecard"),
    "hero_headline":         ("Mesurer l'impact",
                              "Measuring impact"),
    "hero_sub":              ("Visibilité en temps quasi réel sur 38 pays africains et {sites} sites monitorés. "
                              "Suivez l'avancement, les retards, les outputs réalisés et les bénéficiaires touchés.",
                              "Near-real-time visibility across 38 African countries and {sites} monitored sites. "
                              "Track progress, delays, delivered outputs and beneficiaries reached."),
    "hero_country_eyebrow":  ("AfDB · Vue détaillée par pays",
                              "AfDB · Country deep-dive"),
    "hero_country_headline": ("Performance opérationnelle",
                              "Operational performance"),
    "hero_country_sub":      ("Analyse pays par pays — KPIs comparés à la moyenne globale, retards, "
                              "outputs sur le terrain et bénéficiaires touchés.",
                              "Country-by-country analysis — KPIs benchmarked against the global mean, "
                              "delays, on-the-ground outputs and beneficiaries reached."),

    # Pillars
    "pillar_coverage_eyebrow": ("Pilier 1 · Couverture",        "Pillar 1 · Coverage"),
    "pillar_coverage_title":   ("Périmètre du portefeuille suivi",
                                "Scope of the monitored portfolio"),
    "pillar_coverage_desc":    ("Nombre de sites et de projets actifs collectés via RASME.",
                                "Number of sites and active projects collected via RASME."),

    "pillar_delivery_eyebrow": ("Pilier 2 · Performance d'exécution",
                                "Pillar 2 · Delivery performance"),
    "pillar_delivery_title":   ("Niveau de performance",
                                "Performance level"),
    "pillar_delivery_desc":    ("Achèvement, sites à risque, retards et durée moyenne — vision globale "
                                "de la trajectoire d'exécution.",
                                "Completion, at-risk sites, overdue activities and average duration — "
                                "the overall execution trajectory."),

    "pillar_geo_eyebrow":      ("Pilier 3 · Cartographie",      "Pillar 3 · Geographic distribution"),
    "pillar_geo_title":        ("Localisation des sites monitorés",
                                "Where monitored sites are located"),
    "pillar_geo_desc":         ("Carte interactive ArcGIS — zoom, filtres et cartes thématiques par pays.",
                                "Interactive ArcGIS map — zoom, filters and thematic country views."),

    "pillar_breakdown_eyebrow":("Pilier 4 · Répartitions",      "Pillar 4 · Breakdowns"),
    "pillar_breakdown_title":  ("Concentration par pays et secteur",
                                "Country and sector concentration"),
    "pillar_breakdown_desc":   ("Où sont concentrés les sites suivis, dans quels secteurs et avec quel statut.",
                                "Where monitored sites cluster, in which sectors and at which status."),

    "pillar_trend_eyebrow":    ("Pilier 5 · Évolution",         "Pillar 5 · Trend"),
    "pillar_trend_title":      ("Activité de collecte au fil du temps",
                                "Data collection activity over time"),
    "pillar_trend_desc":       ("Volume mensuel de soumissions et achèvements cumulés — pour suivre "
                                "le rythme du terrain.",
                                "Monthly submissions and cumulative completions — to track field cadence."),

    "pillar_outputs_eyebrow":  ("Pilier · Outputs",             "Pillar · Outputs"),
    "pillar_outputs_title":    ("Outputs physiques détectés",
                                "Detected physical outputs"),
    "pillar_outputs_desc":     ("Infrastructures construites, équipements livrés et intrants distribués — "
                                "extraits par mots-clés sur les noms de site.",
                                "Infrastructure built, equipment delivered and inputs distributed — "
                                "extracted via keywords on site names."),

    "pillar_benef_eyebrow":    ("Pilier · Bénéficiaires",       "Pillar · Beneficiaries"),
    "pillar_benef_title":      ("Personnes touchées",
                                "People reached"),
    "pillar_benef_desc":       ("Total des bénéficiaires directs avec ventilation par genre, âge et "
                                "groupes vulnérables.",
                                "Total direct beneficiaries with gender, age and vulnerable-group breakdowns."),

    "pillar_compare_eyebrow":  ("Pilier · Benchmark",           "Pillar · Benchmark"),
    "pillar_compare_title":    ("Le pays comparé à la moyenne globale",
                                "Country versus global average"),
    "pillar_compare_desc":     ("KPI clés du pays sélectionné, avec écart en points par rapport à la "
                                "moyenne des autres pays sur la même période.",
                                "Key KPIs for the selected country, with the gap in points versus the "
                                "average across other countries for the same period."),

    "pillar_ops_eyebrow":      ("Pilier · Pipeline opérationnel","Pillar · Operational pipeline"),
    "pillar_ops_title":        ("Sites en cours et retards",
                                "Live sites and overdue items"),
    "pillar_ops_desc":         ("Liste exhaustive des sites du pays avec statut, avancement, "
                                "retard calculé et bailleur — exportable en CSV.",
                                "Full list of country sites with status, progress, computed delay and "
                                "funder — exportable as CSV."),

    "pillar_issues_eyebrow":   ("Pilier · Risques",             "Pillar · Risks"),
    "pillar_issues_title":     ("Problèmes signalés sur le terrain",
                                "Issues reported in the field"),
    "pillar_issues_desc":      ("Top des problèmes les plus récurrents documentés par les enquêteurs.",
                                "Most recurring issues documented by enumerators."),

    "pillar_timeline_eyebrow": ("Pilier · Galerie",            "Pillar · Gallery"),
    "pillar_timeline_title":   ("Évolution des activités dans le temps",
                                "Activity evolution over time"),
    "pillar_timeline_desc":    ("Photos terrain triées de la plus récente à la plus ancienne, "
                                "groupées par mois — pour suivre visuellement l'avancement des sites.",
                                "Field photos sorted from most recent to oldest, grouped by month — "
                                "to visually track site progression."),
    "tl_show_count":           ("Nombre max de visites à charger", "Max visits to load"),
    "tl_no_photos":            ("Aucune photo disponible pour les filtres sélectionnés.",
                                "No photos available for the selected filters."),
    "tl_open_full":            ("Ouvrir l'image",                "Open image"),
    "tl_visits":               ("collecte(s)",                   "collection(s)"),
    "tl_latest":               ("Dernière collecte",             "Latest collection"),
    "tl_evolution_hint":       ("Photos groupées par projet, puis par site (mêmes coordonnées GPS). "
                                "Faites défiler horizontalement pour voir l'évolution.",
                                "Photos grouped by project, then by site (same GPS coordinates). "
                                "Scroll horizontally to see the evolution."),
    "tl_sites_shown":          ("{n} site(s)",                   "{n} site(s)"),
    "tl_projects_sites_shown": ("{p} projet(s) · {s} site(s)",   "{p} project(s) · {s} site(s)"),
    "tl_project_sites":        ("site(s)",                       "site(s)"),

    # Explainers (1-line context under each KPI value)
    "expl_sites":            ("Soumissions Kobo cumulées — toutes versions de formulaire confondues.",
                              "Cumulative Kobo submissions — all form versions merged."),
    "expl_countries":        ("Pays africains avec au moins un site collecté.",
                              "African countries with at least one collected site."),
    "expl_active_projects":  ("Projets distincts dont au moins un site est en cours ou planifié.",
                              "Distinct projects with at least one in-progress or planned site."),
    "expl_completion":       ("Part des sites marqués « achevés » sur le total monitoré.",
                              "Share of sites marked completed across the total monitored."),
    "expl_at_risk":          ("Sites au point mort, abandonnés, suspendus ou annulés.",
                              "Stalled, abandoned, suspended or canceled sites."),
    "expl_overdue":          ("Sites dont la date de fin prévue est dépassée et le statut n'est pas « achevé ».",
                              "Sites whose planned end has passed but status is not « completed »."),
    "expl_avg_duration":     ("Moyenne de (date d'achèvement − date de début) sur les sites achevés.",
                              "Mean (completion date − start date) on completed sites."),
    "expl_on_time":          ("Part des sites achevés dans le délai prévu.",
                              "Share of completed sites finished on or before plan."),
    "expl_country_sites":    ("Sites du pays sur la période sélectionnée.",
                              "Country sites within the selected period."),
    "expl_in_progress":      ("Sites actuellement marqués « en cours ».",
                              "Sites currently marked « in progress »."),
    "expl_benef":            ("Total des bénéficiaires directs déclarés sur les sites du pays.",
                              "Total direct beneficiaries declared on country sites."),
    "expl_outputs_infra":    ("Sites dont le nom évoque un ouvrage (latrine, école, route, retenue…).",
                              "Sites whose name evokes a built work (latrine, school, road, dam…)."),
    "expl_outputs_equip":    ("Sites dont le nom évoque un équipement (kit, pompe, motopompe, ruche…).",
                              "Sites whose name evokes equipment (kit, pump, beehive…)."),
    "expl_outputs_deliv":    ("Sites dont le nom évoque une livraison d'intrants (semences, plants, poussins…).",
                              "Sites whose name evokes input delivery (seeds, seedlings, chicks…)."),
    "expl_outputs_per_proj": ("Total des outputs détectés divisé par le nombre de projets distincts.",
                              "Total detected outputs divided by the number of distinct projects."),

    "chart_completion_map":  ("Taux d'achèvement par pays",     "Completion rate by country"),
    "chart_status_map":      ("Sites par statut",               "Sites by status"),
    "chart_top_countries":   ("Top pays par nombre de sites",   "Top countries by sites"),
    "chart_sector_split":    ("Répartition sectorielle",        "Sectoral split"),
    "chart_trend":           ("Activité de collecte et avancement","Data collection & completion trend"),
    "chart_funder":          ("Sources de financement",         "Funding sources"),
    "chart_funnel":          ("Pipeline (Planifié → Achevé)",   "Pipeline (Planned → Completed)"),
    "chart_region_status":   ("Sites par région et statut",     "Sites by region and status"),
    "chart_delay_dist":      ("Distribution du retard",         "Delay distribution"),

    "submissions":           ("Sites collectés",                "Sites collected"),
    "cumulative_completed":  ("Cumul achèvements",              "Cumulative completions"),
    "completion_rate_pct":   ("Taux d'achèvement (%)",          "Completion rate (%)"),

    # table columns
    "tbl_project":           ("Projet",                         "Project"),
    "tbl_site":              ("Site",                           "Site"),
    "tbl_region":            ("Région",                         "Region"),
    "tbl_sector":            ("Secteur",                        "Sector"),
    "tbl_status":            ("Statut",                         "Status"),
    "tbl_progress":          ("Avancement",                     "Progress"),
    "tbl_planned_start":     ("Début prévu",                    "Planned start"),
    "tbl_planned_end":       ("Fin prévue",                     "Planned end"),
    "tbl_completion":        ("Achèvement",                     "Completion"),
    "tbl_delay":             ("Retard (j)",                     "Delay (d)"),
    "tbl_funder":            ("Bailleur",                       "Funder"),
    "tbl_agency":            ("Agence d'exécution",             "Implementing agency"),

    # other
    "no_data":               ("Aucune donnée pour les filtres sélectionnés.", "No data for the selected filters."),
    "no_geo_data":           ("Aucune donnée géolocalisée.",    "No geolocated data."),
    "loading":               ("Chargement…",                    "Loading…"),
    "view_status":           ("Par statut",                     "By status"),
    "view_sector":           ("Par secteur",                    "By sector"),
    "export_csv":            ("Exporter CSV",                   "Export CSV"),
    "n_records":             ("{n} enregistrements",            "{n} records"),
    "issue_count":           ("Occurrences",                    "Occurrences"),
    "approved":              ("Validé",                         "Approved"),
    "not_approved":          ("Non validé",                     "Not approved"),
    "on_hold":               ("En attente",                     "On hold"),
    "above_69":              ("Plus de 69 %",                   "Above 69%"),
    "between_50_69":         ("Entre 50 % et 69 %",             "Between 50% and 69%"),
    "between_30_49":         ("Entre 30 % et 49 %",             "Between 30% and 49%"),
    "between_15_29":         ("Entre 15 % et 29 %",             "Between 15% and 29%"),
    "less_15":               ("Moins de 15 %",                  "Less than 15%"),

    # insights
    "insight_top_sector":    ("Le secteur **{sector}** concentre {pct}% des sites avec un taux d'achèvement de {rate}%.",
                              "The **{sector}** sector represents {pct}% of sites with a completion rate of {rate}%."),
    "insight_at_risk":       ("**{n}** sites sont signalés au point mort, abandonnés ou suspendus ({pct}% du portefeuille).",
                              "**{n}** sites are flagged stalled, abandoned or suspended ({pct}% of the portfolio)."),
    "insight_top_country":   ("**{country}** est le pays le plus représenté ({n} sites · {pct}% achevés).",
                              "**{country}** leads the portfolio ({n} sites · {pct}% completed)."),
    "insight_recent":        ("**{n}** nouvelles collectes au cours des 30 derniers jours.",
                              "**{n}** new submissions during the last 30 days."),
}


def t(key: str, lang: str = "FR", **fmt) -> str:
    pair = I18N.get(key)
    if pair is None:
        return key
    s = pair[0] if lang == "FR" else pair[1]
    return s.format(**fmt) if fmt else s
