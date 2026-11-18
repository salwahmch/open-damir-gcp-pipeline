{#
    Ajoute les libellés et le regroupement en postes de soins au fait agrégé.
    Éphémère : compilé comme une CTE dans les marts qui l'utilisent.
    Les codes absents des nomenclatures restent visibles avec un libellé explicite
    plutôt que de disparaître dans une jointure interne.
#}

with fct as (
    select * from {{ ref('fct_depenses_mensuelles') }}
),

prestation as (select * from {{ ref('ref_prestation') }}),
poste      as (select * from {{ ref('ref_poste_soins') }}),
region     as (select * from {{ ref('ref_region') }}),
age        as (select * from {{ ref('ref_tranche_age') }}),
sexe       as (select * from {{ ref('ref_sexe') }}),
categorie  as (select * from {{ ref('ref_categorie_executant') }}),
enveloppe  as (select * from {{ ref('ref_enveloppe') }})

select
    fct.mois_traitement,
    extract(year from fct.mois_traitement)                              as annee,

    fct.code_prestation,
    coalesce(prestation.libelle_prestation, 'Code ' || fct.code_prestation || ' (hors lexique)')
                                                                        as libelle_prestation,
    coalesce(poste.poste_soins, 'Non classé')                           as poste_soins,
    coalesce(poste.grand_poste, 'Non classé')                           as grand_poste,

    fct.code_enveloppe,
    coalesce(enveloppe.libelle_enveloppe, 'Non renseignée')             as libelle_enveloppe,
    fct.code_nature_assurance,
    fct.code_secteur,
    case fct.code_secteur when '1' then 'Public' when '2' then 'Privé' else 'Non renseigné' end
                                                                        as secteur,

    fct.code_region,
    coalesce(region.libelle_region, 'Région inconnue')                  as region,
    region.code_iso_3166_2,
    coalesce(region.est_outre_mer, false)                               as est_outre_mer,

    fct.code_tranche_age,
    coalesce(age.libelle_tranche_age, 'Âge inconnu')                    as tranche_age,
    coalesce(age.ordre_tri, 99)                                         as tranche_age_ordre,

    fct.code_sexe,
    coalesce(sexe.libelle_sexe, 'Valeur inconnue')                      as sexe,

    fct.code_categorie_executant,
    coalesce(categorie.libelle_categorie_executant, 'Non renseignée')  as categorie_executant,

    fct.nb_lignes_source,
    fct.nb_actes,
    fct.quantite,
    fct.montant_depense,
    fct.montant_rembourse,
    fct.base_remboursement,
    fct.montant_depassement

from fct
left join prestation on fct.code_prestation = prestation.code_prestation
left join poste      on fct.prefixe_prestation = poste.prefixe_prestation
left join region     on fct.code_region = region.code_region
left join age        on fct.code_tranche_age = age.code_tranche_age
left join sexe       on fct.code_sexe = sexe.code_sexe
left join categorie  on fct.code_categorie_executant = categorie.code_categorie_executant
left join enveloppe  on fct.code_enveloppe = enveloppe.code_enveloppe
