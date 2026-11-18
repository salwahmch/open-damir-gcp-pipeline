-- Requêtes d'analyse utilisées pour rédiger la section « Enseignements » du README.
-- Compiler avec `dbt compile --select analysis:enseignements`, puis exécuter
-- chaque bloc dans la console BigQuery (target/compiled/.../enseignements.sql).

-- 1. Poids de chaque poste de soins dans la dépense (période chargée)
select
    grand_poste,
    poste_soins,
    round(sum(montant_depense) / 1e6, 1)                                    as depense_m_eur,
    round(100 * sum(montant_depense) / sum(sum(montant_depense)) over (), 1) as part_pct,
    round(100 * safe_divide(sum(montant_rembourse), sum(montant_depense)), 1) as taux_pec_pct
from {{ ref('mart_depenses_postes') }}
group by 1, 2
order by depense_m_eur desc
limit 15;

-- 2. Concentration par âge : part de la dépense des 60 ans et plus
select
    tranche_age,
    round(sum(montant_depense) / 1e6, 1)                                    as depense_m_eur,
    round(100 * sum(montant_depense) / sum(sum(montant_depense)) over (), 1) as part_pct
from {{ ref('mart_depenses_postes') }}
where grand_poste = 'Soins de ville'
group by tranche_age, tranche_age_ordre
order by tranche_age_ordre;

-- 3. Reste à charge (avant complémentaire) et dépassements par poste
select
    poste_soins,
    round(sum(reste_a_charge_amo) / 1e6, 1)                                 as reste_a_charge_m_eur,
    round(100 * safe_divide(sum(montant_depassement), sum(montant_depense)), 1) as part_depassements_pct
from {{ ref('mart_depenses_postes') }}
where grand_poste = 'Soins de ville'
group by 1
order by reste_a_charge_m_eur desc
limit 10;

-- 4. Répartition régionale et écart à la moyenne nationale du taux de prise en charge
select
    region,
    round(sum(montant_depense) / 1e6, 1)                                    as depense_m_eur,
    round(100 * safe_divide(sum(montant_rembourse), sum(montant_depense)), 1) as taux_pec_pct
from {{ ref('mart_depenses_postes') }}
where code_iso_3166_2 is not null
group by 1
order by depense_m_eur desc;

-- 5. Évolution mensuelle par grand poste
select mois_traitement, grand_poste, round(montant_depense / 1e6, 1) as depense_m_eur,
       round(100 * evolution_mensuelle, 1) as evolution_pct
from {{ ref('mart_kpi_mensuels') }}
order by grand_poste, mois_traitement;

-- 6. Top 10 des prestations les plus coûteuses du dernier mois chargé
select libelle_prestation, poste_soins, round(montant_depense / 1e6, 1) as depense_m_eur
from {{ ref('mart_top_prestations') }}
where mois_traitement = (select max(mois_traitement) from {{ ref('mart_top_prestations') }})
  and rang_dans_le_mois <= 10
order by rang_dans_le_mois;
