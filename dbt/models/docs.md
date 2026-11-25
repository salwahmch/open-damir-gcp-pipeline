{% docs __overview__ %}
# Pipeline Open DAMIR (Assurance Maladie)

Ce projet dbt transforme les remboursements mensuels publiés en open data par
l'Assurance Maladie (base **Open DAMIR**, tous régimes) en tables prêtes pour
l'analyse.

Couches :

| Couche | Dataset BigQuery | Rôle |
|---|---|---|
| Sources | `damir_raw` | Fichiers chargés par Python, colonnes en texte, une table par mois (sandbox) ou une partition par mois (standard) |
| Seeds | `damir_ref` | Libellés des nomenclatures (lexique officiel) et regroupement en postes de soins |
| Staging | `damir_staging` | Renommage, typage, nettoyage (vue) |
| Marts | `damir_marts` | Fait agrégé incrémental et tables d'analyse pour Looker Studio |

Le graphe de lignage (bouton en bas à droite) montre le chemin complet,
jusqu'au tableau de bord déclaré comme *exposure*.
{% enddocs %}

{% docs code_prestation %}
Nature de la prestation (variable PRS_NAT), code à 4 chiffres. Les deux premiers
chiffres donnent la famille : 11 consultations, 31 auxiliaires médicaux,
33 médicaments, 42 transports, 61 indemnités journalières, etc. Le regroupement
complet est dans le seed `ref_poste_soins`.
{% enddocs %}

{% docs montant_depense %}
Montant total de la dépense en euros (PRS_PAI_MNT) : ce qui a été payé au
professionnel ou à l'établissement, dépassements compris. Les régularisations
peuvent produire des montants négatifs.
{% enddocs %}

{% docs montant_rembourse %}
Montant versé par l'Assurance Maladie en euros (PRS_REM_MNT), soit la base de
remboursement multipliée par le taux de remboursement. La différence avec la
dépense est le reste à charge avant complémentaire santé.
{% enddocs %}

{% docs taux_prise_en_charge %}
Part de la dépense remboursée par l'Assurance Maladie :
`montant_rembourse / montant_depense`.
{% enddocs %}
