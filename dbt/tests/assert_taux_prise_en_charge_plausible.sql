-- Sur un mois complet et au niveau national, l'Assurance Maladie rembourse une
-- part importante mais pas plus que la dépense. Un taux hors de [0,3 ; 1,05]
-- signale presque toujours un problème de parsing des montants (virgule,
-- colonnes décalées) ou un fichier tronqué.

{{ config(severity='warn') }}

select
    mois_traitement,
    sum(montant_depense)                                        as depense,
    sum(montant_rembourse)                                      as rembourse,
    safe_divide(sum(montant_rembourse), sum(montant_depense))   as taux
from {{ ref('mart_kpi_mensuels') }}
group by 1
having taux is null or taux < 0.3 or taux > 1.05
