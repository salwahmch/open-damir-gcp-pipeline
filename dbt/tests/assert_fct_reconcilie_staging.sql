-- L'agrégation ne doit ni perdre ni dupliquer de montants :
-- pour chaque mois, les totaux du fait égalent ceux du staging (au centime près).
-- Le test échoue s'il renvoie au moins une ligne.

with stg as (
    select
        mois_traitement,
        count(*)                            as nb_lignes,
        coalesce(sum(montant_depense), 0)   as depense,
        coalesce(sum(montant_rembourse), 0) as rembourse
    from {{ ref('stg_damir__prestations') }}
    group by 1
),

fct as (
    select
        mois_traitement,
        sum(nb_lignes_source)               as nb_lignes,
        coalesce(sum(montant_depense), 0)   as depense,
        coalesce(sum(montant_rembourse), 0) as rembourse
    from {{ ref('fct_depenses_mensuelles') }}
    group by 1
)

select
    coalesce(stg.mois_traitement, fct.mois_traitement) as mois_traitement,
    stg.nb_lignes as nb_lignes_staging,
    fct.nb_lignes as nb_lignes_fait,
    stg.depense   as depense_staging,
    fct.depense   as depense_fait
from stg
full outer join fct using (mois_traitement)
where stg.nb_lignes is distinct from fct.nb_lignes
   or abs(coalesce(stg.depense, 0) - coalesce(fct.depense, 0)) > 0.01
   or abs(coalesce(stg.rembourse, 0) - coalesce(fct.rembourse, 0)) > 0.01
