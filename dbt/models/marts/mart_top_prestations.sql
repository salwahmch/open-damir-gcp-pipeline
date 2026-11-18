{#
    Détail par nature de prestation : quelles prestations pèsent le plus dans
    chaque poste, avec leur rang dans le mois.
#}

with par_prestation as (

    select
        mois_traitement,
        code_prestation,
        libelle_prestation,
        poste_soins,
        grand_poste,
        sum(nb_actes)               as nb_actes,
        sum(quantite)               as quantite,
        sum(montant_depense)        as montant_depense,
        sum(montant_rembourse)      as montant_rembourse,
        sum(montant_depassement)    as montant_depassement
    from {{ ref('int_depenses_libellees') }}
    group by 1, 2, 3, 4, 5

)

select
    *,
    safe_divide(montant_rembourse, montant_depense)                 as taux_prise_en_charge,
    safe_divide(montant_depense, nb_actes)                          as depense_moyenne_par_acte,
    rank() over (partition by mois_traitement order by montant_depense desc)
                                                                    as rang_dans_le_mois,
    rank() over (partition by mois_traitement, poste_soins order by montant_depense desc)
                                                                    as rang_dans_le_poste
from par_prestation
