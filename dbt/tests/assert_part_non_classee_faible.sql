-- Les prestations sans poste de soins (préfixe absent de ref_poste_soins) doivent
-- rester marginales : au-delà de 1 % de la dépense du mois, il faut compléter le seed.

{{ config(severity='warn') }}

select
    mois_traitement,
    safe_divide(
        sum(case when grand_poste = 'Non classé' then montant_depense else 0 end),
        sum(montant_depense)
    ) as part_non_classee
from {{ ref('mart_depenses_postes') }}
group by 1
having part_non_classee > 0.01
