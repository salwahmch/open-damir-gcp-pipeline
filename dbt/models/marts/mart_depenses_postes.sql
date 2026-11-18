{#
    Table principale du tableau de bord : une ligne par mois, poste de soins,
    région, tranche d'âge et sexe, avec libellés. Assez petite pour Looker Studio
    (quelques dizaines de milliers de lignes par mois).
#}

select
    mois_traitement,
    annee,
    grand_poste,
    poste_soins,
    code_region,
    region,
    code_iso_3166_2,
    est_outre_mer,
    code_tranche_age,
    tranche_age,
    tranche_age_ordre,
    code_sexe,
    sexe,

    sum(nb_actes)                                                   as nb_actes,
    sum(montant_depense)                                            as montant_depense,
    sum(montant_rembourse)                                          as montant_rembourse,
    sum(montant_depense) - sum(montant_rembourse)                   as reste_a_charge_amo,
    sum(montant_depassement)                                        as montant_depassement,
    safe_divide(sum(montant_rembourse), sum(montant_depense))       as taux_prise_en_charge

from {{ ref('int_depenses_libellees') }}
group by 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13
