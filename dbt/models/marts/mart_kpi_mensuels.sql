{#
    Indicateurs nationaux par mois et grand poste, avec évolution d'un mois sur
    l'autre. Sert aux cartes de score et à la courbe d'évolution du tableau de bord.
#}

with mensuel as (

    select
        mois_traitement,
        grand_poste,
        sum(montant_depense)        as montant_depense,
        sum(montant_rembourse)      as montant_rembourse,
        sum(montant_depassement)    as montant_depassement,
        sum(nb_actes)               as nb_actes
    from {{ ref('int_depenses_libellees') }}
    group by 1, 2

)

select
    mois_traitement,
    grand_poste,
    montant_depense,
    montant_rembourse,
    montant_depense - montant_rembourse                             as reste_a_charge_amo,
    montant_depassement,
    nb_actes,
    safe_divide(montant_rembourse, montant_depense)                 as taux_prise_en_charge,
    safe_divide(montant_depense, sum(montant_depense) over (partition by mois_traitement))
                                                                    as part_depense_du_mois,
    lag(montant_depense) over (partition by grand_poste order by mois_traitement)
                                                                    as montant_depense_mois_precedent,
    safe_divide(
        montant_depense - lag(montant_depense) over (partition by grand_poste order by mois_traitement),
        lag(montant_depense) over (partition by grand_poste order by mois_traitement)
    )                                                               as evolution_mensuelle
from mensuel
