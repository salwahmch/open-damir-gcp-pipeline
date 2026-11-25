{#
    Fait central : dépenses agrégées par mois et par combinaison d'axes.
    Passe de plusieurs millions de lignes par mois à quelques
    centaines de milliers.

    Mode standard : incrémental en insert_overwrite. À chaque exécution, seuls
    les mois (re)chargés depuis la dernière exécution sont recalculés, et leur
    partition est remplacée entièrement. Rejouer un mois ne crée donc jamais
    de doublons.

    Mode sandbox (BQ_SANDBOX=true) : pas de DML ni de partition datée (voir
    macros/sandbox.sql). La table est recréée en entier à chaque exécution
    (CREATE OR REPLACE TABLE), ce qui reste rapide sur quelques mois, et
    clusterisée par mois de traitement.
#}

{% if is_sandbox() %}
{{
    config(
        materialized='table',
        cluster_by=['mois_traitement', 'prefixe_prestation', 'code_region']
    )
}}
{% else %}
{{
    config(
        materialized='incremental',
        incremental_strategy='insert_overwrite',
        partition_by={'field': 'mois_traitement', 'data_type': 'date', 'granularity': 'month'},
        cluster_by=['prefixe_prestation', 'code_region'],
        on_schema_change='append_new_columns'
    )
}}
{% endif %}

with prestations as (

    select * from {{ ref('stg_damir__prestations') }}

    {% if is_incremental() %}
    where mois_traitement in (
        select distinct mois_traitement
        from {{ ref('stg_damir__prestations') }}
        where ingere_le > (select max(derniere_ingestion) from {{ this }})
    )
    {% endif %}

)

select
    mois_traitement,
    code_prestation,
    prefixe_prestation,
    code_enveloppe,
    code_nature_assurance,
    code_secteur,
    code_region,
    code_tranche_age,
    code_sexe,
    code_categorie_executant,

    count(*)                                as nb_lignes_source,
    sum(nb_actes)                           as nb_actes,
    sum(quantite)                           as quantite,
    sum(montant_depense)                    as montant_depense,
    sum(montant_rembourse)                  as montant_rembourse,
    sum(base_remboursement)                 as base_remboursement,
    sum(montant_depassement)                as montant_depassement,
    max(ingere_le)                          as derniere_ingestion

from prestations
group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
