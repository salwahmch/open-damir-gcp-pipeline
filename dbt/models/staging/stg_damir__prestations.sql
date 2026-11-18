{#
    Staging : une ligne par ligne brute, colonnes renommées, typées et nettoyées.
    Matérialisé en vue pour ne pas dupliquer le volume brut (offre gratuite BigQuery) ;
    l'agrégation persistée se fait dans fct_depenses_mensuelles.
#}

with source as (

    select * from {{ source('damir_raw', 'prestations') }}

),

renamed as (

    select
        -- Temps
        _flx_month                                              as mois_traitement,
        safe_cast({{ clean_code('SOI_ANN') }} as int64)         as annee_soins,
        safe_cast({{ clean_code('SOI_MOI') }} as int64)         as mois_soins,

        -- Prestation
        {{ clean_int_code('PRS_NAT') }}                         as code_prestation,
        {{ clean_int_code('ASU_NAT') }}                         as code_nature_assurance,
        {{ clean_int_code('CPT_ENV_TYP') }}                     as code_enveloppe,
        {{ clean_int_code('PRS_PPU_SEC') }}                     as code_secteur,
        {{ clean_int_code('EXO_MTF') }}                         as code_motif_exoneration,
        {{ clean_int_code('PRS_PDS_QCP') }}                     as code_parcours_soins,
        {{ parse_number('PRS_REM_TAU') }}                       as taux_remboursement,

        -- Bénéficiaire
        {{ clean_int_code('AGE_BEN_SNDS') }}                    as code_tranche_age,
        {{ clean_int_code('BEN_SEX_COD') }}                     as code_sexe,
        {{ clean_int_code('BEN_RES_REG') }}                     as code_region,
        {{ clean_int_code('BEN_CMU_TOP') }}                     as code_c2s,

        -- Professionnels
        {{ clean_int_code('PSE_ACT_CAT') }}                     as code_categorie_executant,
        {{ clean_int_code('PSE_SPE_SNDS') }}                    as code_specialite_executant,
        {{ clean_int_code('PSP_ACT_CAT') }}                     as code_categorie_prescripteur,

        -- Indicateurs
        {{ parse_number('PRS_ACT_NBR') }}                       as nb_actes,
        {{ parse_number('PRS_ACT_QTE') }}                       as quantite,
        {{ parse_number('PRS_PAI_MNT') }}                       as montant_depense,
        {{ parse_number('PRS_REM_MNT') }}                       as montant_rembourse,
        {{ parse_number('PRS_REM_BSE') }}                       as base_remboursement,
        {{ parse_number('PRS_DEP_MNT') }}                       as montant_depassement,

        -- Technique
        _source_file                                            as fichier_source,
        _ingested_at                                            as ingere_le

    from source

)

select
    *,
    safe.date(annee_soins, mois_soins, 1)                       as mois_soins_date,
    substr(code_prestation, 1, 2)                               as prefixe_prestation
from renamed
