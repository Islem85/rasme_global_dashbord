-- ================================================================
-- NETTOYAGE ET CONSOLIDATION DE kobo_all_global
-- Résultat : table kobo_clean avec colonnes consolidées
-- ================================================================
-- Principe : COALESCE(col1, col2, col3) → prend la 1ère valeur non NULL
-- Photo URL : photo_of_activity_*_url est en 1er pour couvrir les
--             formulaires _new (8000+ lignes sinon perdues).
-- ================================================================

DROP TABLE IF EXISTS kobo_clean;

CREATE TABLE kobo_clean AS
SELECT

    -- ── IDENTIFIANTS ─────────────────────────────────────────────
    origin_table,
    country,
    form_version,
    submission_uuid,
    uuid,
    submission_time,
    status,
    synced_at,

    -- ── PROJET ───────────────────────────────────────────────────
    COALESCE(
        name_of_the_project,
        name_of_the_project_programme
    ) AS nom_projet,

    activity_sector AS secteur_activite,

    COALESCE(
        aim_of_the_project,
        aim_of_the_project_programme,
        aim_of_the_activity
    ) AS objectif_projet,

    -- ── COORDONNÉES GPS ──────────────────────────────────────────
    COALESCE(
        longitude,
        gps_coordinates_longitude,
        localization_using_gps_longitude,
        gps_location_longitude
    )::DOUBLE PRECISION AS longitude,

    COALESCE(
        latitude,
        gps_coordinates_latitude,
        localization_using_gps_latitude,
        gps_location_latitude
    )::DOUBLE PRECISION AS latitude,

    COALESCE(
        altitude,
        gps_coordinates_altitude,
        localization_using_gps_altitude,
        gps_location_altitude
    )::DOUBLE PRECISION AS altitude,

    COALESCE(
        gps_coordinates_precision,
        localization_using_gps_precision,
        gps_location_precision
    )::DOUBLE PRECISION AS gps_precision,

    -- ── LOCALISATION ADMINISTRATIVE ───────────────────────────────
    COALESCE(
        region,
        veuillez_selectionner_la_region_dans_laquel_se_trouve_ce_site_o,
        veuillez_selectionner_la_region_dans_laquelle_se_trouve_ce_site,
        admin1,
        wilaya,
        gouvernorat,
        state
    ) AS region,

    COALESCE(
        province,
        veuillez_selectionner_le_province_dans_lequel_se_trouve_ce_site,
        veuillez_selectionner_la_province_dans_laquelle_se_trouve_ce_si,
        admin2,
        provinces
    ) AS province,

    COALESCE(
        departement,
        department,
        prefecture,
        veuillez_selectionner_le_prefecture_dans_lequel_se_trouve_ce_si,
        veuillez_selectionner_le_gouvernorat_dans_lequel_se_trouve_ce_s,
        veuillez_selectionner_le_departement_dans_lequel_se_trouve_ce_s
    ) AS departement,

    COALESCE(
        commune,
        municipality,
        city_council,
        veuillez_selectionner_la_commune_dans_laquelle_se_trouve_ce_sit,
        veuillez_selectionner_la_municipalite_dans_laquelle_se_trouve_c,
        moughataa
    ) AS commune,

    COALESCE(
        sub_prefecture,
        veuillez_selectionner_la_sous_prefecture_dans_laquelle_se_trouv,
        arrondissement,
        cercle,
        veuillez_selectionner_le_cercle_dans_lequel_se_trouve_ce_site_o,
        veuillez_selectionner_le_canton_dans_lequel_se_trouve_ce_site_o,
        veuillez_selectionner_le_district_dans_lequel_se_trouve_ce_site,
        canton,
        chiefdom,
        counties,
        county,
        sub_county,
        constituency,
        division,
        administrative_post,
        local_government_area,
        district
    ) AS sous_prefecture,

    COALESCE(
        village,
        ward_village,
        ward,
        ward_gvh_village_town_neighborhood,
        village_neighborhood,
        veuillez_entrer_le_nom_de_la_ville_du_village_ou_du_quartier_da,
        veuillez_entrer_le_nom_de_la_localite_dans_laquelle_ce_site_ou_,
        locality,
        payam,
        boma,
        neighborhood,
        zone,
        woreda,
        fokontany
    ) AS village,

    COALESCE(
        municipalite,
        community_council
    ) AS municipalite,

    -- ── SITE / DESCRIPTION ────────────────────────────────────────
    COALESCE(
        project_site_name,
        activity_site_name,
        project_programme_site_name,
        name_of_the_activity_site_or_location
    ) AS nom_site,

    COALESCE(
        brief_activity_description,
        brief_project_description,
        brief_project_programme_description,
        brief_description_of_the_activity_at_this_site
    ) AS description_activite,

    pa_id AS identifiant_pa,
    village_id AS identifiant_village,

    -- ── STATUT D'IMPLÉMENTATION ───────────────────────────────────
    COALESCE(
        project_implementation_status,
        activity_implementation_status,
        project_programme_implementation_status,
        status_of_implementation_of_this_activity
    ) AS statut_implementation,

    COALESCE(
        project_start_date,
        activity_start_date,
        project_programme_start_date
    ) AS date_debut,

    COALESCE(
        project_expected_completion_date,
        activity_expected_completion_date,
        project_programme_expected_completion_date,
        expected_end_date_of_the_activity_if_known
    ) AS date_fin_prevue,

    COALESCE(
        project_completion_date,
        activity_completion_date,
        project_programme_completion_date,
        date_of_completion_of_the_activity
    ) AS date_fin_reelle,

    level_of_activity_achievement AS niveau_realisation,

    COALESCE(
        expected_project_results,
        expected_activity_results
    ) AS resultats_attendus,

    COALESCE(
        results_already_achieved_by_the_project,
        results_already_achieved_by_the_project_programme,
        results_already_achieved_by_the_activity
    ) AS resultats_obtenus,

    -- ── FINANCEMENT ──────────────────────────────────────────────
    COALESCE(
        institution_s_funding_the_project,
        institution_s_funding_the_activity,
        institution_s_funding_the_project_programme,
        institution_s_financing_the_visited_activity
    ) AS institutions_financement,

    COALESCE(
        if_other_institution_s_funding_the_project_please_specify,
        if_other_institution_s_funding_the_activity_please_specify,
        if_other_institution_s_funding_the_project_programme_please_spe
    ) AS autre_institution_financement,

    what_is_the_estimated_total_cost_of_this_activity::DOUBLE PRECISION AS cout_estime,
    what_is_the_reporting_currency                                       AS devise,
    can_you_specify_the_cost_of_this_activity                            AS cout_specifie,

    -- ── AGENCE D'EXÉCUTION ───────────────────────────────────────
    COALESCE(
        name_of_project_implementing_agency,
        name_of_the_activity_implementing_agency,
        name_of_project_programme_implementing_agency,
        name_of_activity_implementing_agency,
        name_of_executive_agency_partner
    ) AS nom_agence_execution,

    COALESCE(
        type_of_implementing_agency
    ) AS type_agence_execution,

    -- ── BÉNÉFICIAIRES ────────────────────────────────────────────
    COALESCE(
        number_of_direct_beneficiaries_reached_by_this_project,
        number_of_beneficiaries_directly_affected_by_this_activity,
        number_of_direct_beneficiaries_reached_by_this_project_activity,
        number_of_direct_beneficiaries_reached_by_this_project_programm,
        number_of_direct_beneficiaries_reached_by_this_activity
    )::DOUBLE PRECISION AS nb_beneficiaires_directs,

    COALESCE(
        number_of_female_beneficiaries_directly_affected_by_this_projec,
        number_of_female_beneficiaries_directly_affected_by_this_activt,
        number_of_females_beneficiaries_directly_affected_by_this_activ,
        number_of_female_beneficiaries_directly_affected_by_this_activi
    )::DOUBLE PRECISION AS nb_beneficiaires_femmes,

    number_of_male_beneficiaries_directly_affected_by_this_activity
        ::DOUBLE PRECISION AS nb_beneficiaires_hommes,

    COALESCE(
        number_of_other_beneficiaries_affected_by_this_activity
    )::DOUBLE PRECISION AS nb_beneficiaires_autres,

    -- Bénéficiaires par catégorie
    number_of_children_between_the_ages_of_5_and_18_reached_by_this
        ::DOUBLE PRECISION AS nb_enfants_5_18_ans,

    number_of_children_under_5_years_of_age_affected_by_this_activi
        ::DOUBLE PRECISION AS nb_enfants_moins_5_ans,

    number_of_females_beneficiaries_directly_affected_by_this_activ
        ::DOUBLE PRECISION AS nb_femmes_beneficiaires,

    number_of_internally_displaced_persons_idps_affected_by_this_ac
        ::DOUBLE PRECISION AS nb_deplaces_internes,

    number_of_people_over_60_years_of_age_affected_by_this_activity
        ::DOUBLE PRECISION AS nb_personnes_plus_60_ans,

    number_of_persons_with_disabilities_or_special_needs_affected_b
        ::DOUBLE PRECISION AS nb_personnes_handicapees,

    number_of_refugees_affected_by_this_activity
        ::DOUBLE PRECISION AS nb_refugies,

    number_of_returnees_affected_by_this_activity
        ::DOUBLE PRECISION AS nb_retournes,

    COALESCE(
        select_the_type_s_of_beneficiaries_targeted
    ) AS types_beneficiaires,

    COALESCE(
        does_this_project_target_a_particular_category_of_beneficiaries,
        does_this_activity_target_a_particular_category_of_beneficiarie,
        does_this_activty_target_a_particular_category_of_beneficiaries
    ) AS cible_categorie_specifique,

    -- ── PROBLÈMES RENCONTRÉS ─────────────────────────────────────
    COALESCE(
        has_this_project_encountered_any_significant_problems_in_the_pa,
        has_this_activity_encountered_any_significant_problems_in_the_p,
        has_this_project_programme_encountered_any_significant_problems
    ) AS problemes_rencontres,

    COALESCE(
        if_yes_please_specify_what_type_of_problem_s_were_encountered
    ) AS type_probleme,

    COALESCE(
        if_other_please_specify_the_type_of_problem,
        other_than_covid19_and_insecurity,
        please_briefly_describe_the_problem_s_encountered
    ) AS detail_probleme,

    COALESCE(
        due_to_the_problem_s_the_activiry_was
    ) AS impact_probleme,

    -- ── ENGAGEMENT CITOYEN ───────────────────────────────────────
    COALESCE(
        is_there_one_or_more_citizen_engagement_mechanisms_used_for_thi,
        are_there_one_or_more_citizen_engagement_mechanisms_used_for_th
    ) AS mecanisme_engagement_citoyen,

    COALESCE(
        what_types_of_citizen_engagement_tools_are_being_used_for_this_,
        what_types_of_citizen_engagement_tools_are_used_for_this_activi
    ) AS outils_engagement_citoyen,

    -- ── CONTACT TERRAIN ──────────────────────────────────────────
    full_name_of_the_field_contact  AS nom_contact,
    role_of_contact                 AS role_contact,
    phone_number_s_of_name_contact  AS telephone_contact,

    -- ── COLLECTE ─────────────────────────────────────────────────
    COALESCE(
        collector_name,
        name_of_data_collector
    ) AS nom_collecteur,

    COALESCE(
        phone_number_name_enum,
        name_enum_s_phone_number
    ) AS telephone_collecteur,

    COALESCE(
        comment_or_observation_from_name_enum_if_necessary,
        comment_or_observation_if_necessary,
        name_enum_s_comment_or_observation_if_necessary,
        comment_or_observation_from_if_necessary
    ) AS commentaire_collecteur,

    COALESCE(
        date_of_data_collection,
        today
    ) AS date_collecte,

    -- Date « Today » Kobo : date saisie par l'enquêteur au moment d'ouvrir le
    -- formulaire (utilisée pour le filtre date et la timeline d'activité de
    -- collecte). Conservée en plus de date_collecte qui combine plusieurs
    -- champs via COALESCE.
    today AS today,

    -- ── PHOTOS ───────────────────────────────────────────────────
    COALESCE(
        photo_of_project_1,
        activity_photo,
        photo_of_activity_1,
        photo_of_project_programme_1
    ) AS photo_1,

    COALESCE(
        photo_of_activity_1_url,
        photo_of_project_1_url,
        activity_photo_url,
        photo_of_project_programme_1_url
    ) AS photo_1_url,

    COALESCE(
        photo_of_project_2_if_needed,
        activity_photo_2_if_needed,
        photo_of_activity_2_if_needed,
        photo_of_project_programme_2_if_needed
    ) AS photo_2,

    COALESCE(
        photo_of_activity_2_if_needed_url,
        photo_of_project_2_if_needed_url,
        activity_photo_2_if_needed_url,
        photo_of_project_programme_2_if_needed_url
    ) AS photo_2_url,

    -- ── IDENTIFIANTS TECHNIQUES ──────────────────────────────────
    username,
    deviceid,
    start   AS heure_debut_saisie,
    "end"   AS heure_fin_saisie,
    validation_status,
    meta_rootuuid,
    submitted_by

FROM kobo_all_global;

-- ── ACTIVATION POSTGIS (à exécuter une seule fois par base) ──────
CREATE EXTENSION IF NOT EXISTS postgis;

-- ── COLONNE GEOMETRY (PostGIS) ────────────────────────────────────
ALTER TABLE kobo_clean
    ADD COLUMN geom GEOMETRY(Point, 4326);

UPDATE kobo_clean
SET geom = ST_SetSRID(
               ST_MakePoint(longitude, latitude),
               4326
           )
WHERE longitude IS NOT NULL
  AND latitude  IS NOT NULL
  AND longitude BETWEEN -180 AND 180
  AND latitude  BETWEEN -90  AND 90;

CREATE INDEX idx_clean_geom ON kobo_clean USING GIST(geom);

-- ── OBJECTID pour ArcGIS Pro ──────────────────────────────────────
ALTER TABLE kobo_clean ADD COLUMN objectid SERIAL;
CREATE UNIQUE INDEX idx_clean_objectid ON kobo_clean(objectid);

-- ── INDEX ATTRIBUTAIRES ───────────────────────────────────────────
CREATE INDEX idx_clean_country       ON kobo_clean(country);
CREATE INDEX idx_clean_version       ON kobo_clean(form_version);
CREATE INDEX idx_clean_uuid          ON kobo_clean(submission_uuid);
CREATE INDEX idx_clean_statut        ON kobo_clean(statut_implementation);
CREATE INDEX idx_clean_secteur       ON kobo_clean(secteur_activite);
CREATE INDEX idx_clean_date_collecte ON kobo_clean(date_collecte);

-- ── CONSOLIDATION SOMALIE ──────────────────────────────────────
UPDATE kobo_clean
SET country = 'somalia'
WHERE country ILIKE 'Somaliland';
