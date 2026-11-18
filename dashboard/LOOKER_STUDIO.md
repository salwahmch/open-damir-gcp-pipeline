# Tableau de bord Looker Studio

## Sources de données

Dans [Looker Studio](https://lookerstudio.google.com) : *Créer › Source de données › BigQuery*,
projet du pipeline, dataset `damir_marts`. Ajouter trois sources :

| Source | Table | Usage |
|---|---|---|
| Dépenses | `mart_depenses_postes` | Filtres, répartition par poste, région, âge, sexe |
| KPI | `mart_kpi_mensuels` | Cartes de score, évolution mensuelle |
| Prestations | `mart_top_prestations` | Tableau des prestations les plus coûteuses |

Réglages de champs dans la source *Dépenses* :

- `code_iso_3166_2` : type *Géo › Subdivision de pays (1er niveau)* (pour la carte).
- `montant_depense`, `montant_rembourse`, `reste_a_charge_amo`, `montant_depassement` : type
  *Devise (EUR)*, agrégation *Somme*.
- Ne pas utiliser la colonne `taux_prise_en_charge` agrégée (une moyenne de taux est fausse) :
  créer le champ calculé `Taux de prise en charge = SUM(montant_rembourse) / SUM(montant_depense)`,
  au format pourcentage.

## Pages

**1. Vue d'ensemble**
- Commandes : période (`mois_traitement`), grand poste, région.
- Cartes de score : dépense totale, montant remboursé, taux de prise en charge, dépassements.
- Série temporelle : dépense par mois, une ligne par grand poste (source *KPI*).

**2. Postes de soins**
- Barres horizontales : dépense par `poste_soins`, triées, 15 premiers.
- Tableau : poste, dépense, remboursé, reste à charge, taux de prise en charge (mise en forme
  conditionnelle sur le taux).

**3. Territoires**
- Carte géographique remplie : `code_iso_3166_2`, mesure dépense (filtrer `est_outre_mer` si besoin
  pour mieux voir la métropole).
- Tableau : région, dépense, taux de prise en charge.

**4. Âge et sexe**
- Barres groupées : `tranche_age` (trier par `tranche_age_ordre`) × `sexe`, mesure dépense.
- Barres empilées 100 % : répartition des postes par tranche d'âge.

**5. Prestations**
- Tableau (source *Prestations*) : `libelle_prestation`, `poste_soins`, dépense, nombre d'actes,
  dépense moyenne par acte, filtré sur `rang_dans_le_mois <= 20`.

## Publication

*Partager › Gérer l'accès › Toute personne disposant du lien peut consulter*, puis copier le lien
dans le README et dans `dbt/models/exposures.yml`. Exporter chaque page en PNG
(*Fichier › Télécharger › PNG* ou capture d'écran) dans `docs/img/`.

Coût : Looker Studio est gratuit ; chaque actualisation interroge les marts (quelques Mo), ce qui
reste négligeable dans le quota BigQuery gratuit de 1 To de requêtes par mois.
