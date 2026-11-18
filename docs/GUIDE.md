# Guide pas à pas

Ordre conseillé, avec un point de contrôle à chaque étape. Compter une à deux soirées pour les
étapes 1 à 5, puis une pour le tableau de bord et le README.

## 0. Prérequis

- Python 3.11 ou plus, Git, Docker Desktop
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud` et `bq`)
- Un compte Google Cloud avec le crédit d'essai gratuit activé (une carte est demandée, rien n'est
  prélevé pendant l'essai)

Créer un dépôt vide `open-damir-gcp-pipeline` sur GitHub (sans README), puis depuis le dossier
décompressé :

```bash
cd open-damir-gcp-pipeline
git init -b main && git add . && git commit -m "Pipeline Open DAMIR : ingestion, dbt, Airflow, CI"
git remote add origin https://github.com/<votre-compte>/open-damir-gcp-pipeline.git
git push -u origin main

python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
make test    # ✅ 10 tests passent, sans aucun accès au cloud
```

## 1. Projet Google Cloud

```bash
gcloud auth login
gcloud auth application-default login   # utilisé par Python et dbt en local
cp .env.example .env
```

Dans `.env`, choisir un identifiant de projet unique (ex. `damir-salwa-2026`) et un nom de bucket
unique (ex. `damir-salwa-2026-landing`). Créer le projet et rattacher la facturation dans la
console, puis :

```bash
bash infra/setup_gcp.sh
```

✅ Contrôle : la console BigQuery montre 4 datasets `damir_raw`, `damir_ref`, `damir_staging`,
`damir_marts`, et le fichier `secrets/gcp-key.json` existe (ne jamais le pousser sur GitHub ; il
est dans `.gitignore`).

Créer aussi une **alerte budgétaire** à 5 € (console › Facturation › Budgets et alertes).

## 2. Vérifier l'URL des fichiers

Sur la page Ameli « Open Damir : base complète sur les dépenses d'assurance maladie », faire un
clic droit sur le lien d'un mois › *Copier l'adresse du lien*, et comparer avec
`DAMIR_URL_TEMPLATE` dans `.env` (le mois s'écrit `{yyyymm}`, ex. `A{yyyymm}.csv.gz`).

Si le lien passe par une page intermédiaire ou un zip annuel, télécharger le fichier à la main et
utiliser `--local-file` (étape suivante).

## 3. Premier mois, en mode échantillon

```bash
python -m ingestion run --month 2024-01 --steps download,transform --max-rows 200000
python -m ingestion inspect data/landing/A202401.csv.gz
```

`inspect` affiche le séparateur détecté et les colonnes absentes ou inattendues par rapport au
lexique. Si des colonnes conservées manquent (ex. région nommée autrement), ajouter
l'ancien nom dans `COLUMN_ALIASES` (`ingestion/schema.py`).

Avec un fichier téléchargé à la main :

```bash
python -m ingestion run --month 2024-01 --local-file ~/Downloads/A202401.csv.gz --max-rows 200000
```

Puis envoi vers GCP :

```bash
python -m ingestion run --month 2024-01 --steps upload,load
```

✅ Contrôle dans BigQuery :

```sql
select _flx_month, count(*) from damir_raw.prestations group by 1;
```

## 4. dbt

```bash
cd dbt
dbt debug --profiles-dir .     # ✅ "All checks passed!"
dbt deps --profiles-dir .
dbt seed --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir . --port 8081
```

Les avertissements (`WARN`) des tests de relations sur la région ou la catégorie d'exécutant
signalent des codes absents des seeds : regarder les valeurs avec
`dbt test --select fct_depenses_mensuelles --store-failures`, puis compléter le seed concerné.
Faire une capture du graphe de lignage pour le README.

**Lexique à jour** : télécharger le « Descriptif des variables » sur la page Ameli et lancer
`python -m ingestion.build_seeds chemin/du/lexique.xls` pour régénérer `ref_prestation` et
`ref_specialite_executant` (ceux du dépôt viennent du lexique 2015).

## 5. Données réelles : 3 mois complets

Une fois l'échantillon validé, recharger les mois en entier (le chargement remplace la partition,
aucun doublon) :

```bash
python -m ingestion run --from 2024-01 --to 2024-03
cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir .
```

Après le premier mois complet, regarder la taille de la table (BigQuery › `prestations` ›
*Détails* › taille logique) et en déduire combien de mois tiennent dans les 10 Go de stockage
gratuit ; viser 3 mois.

## 6. Airflow

```bash
echo "AIRFLOW_UID=$(id -u)" >> .env    # Linux uniquement
make airflow-up                        # premier démarrage : quelques minutes de build
```

Ouvrir http://localhost:8080, activer le DAG `open_damir_pipeline`, puis *Trigger DAG w/ config* :

```json
{"months": ["2024-04"], "max_rows": 200000}
```

✅ Contrôle : toutes les tâches en vert, dont `dbt_test`. Faire une capture de la vue *Graph*.

## 7. Tableau de bord Looker Studio

Voir [`dashboard/LOOKER_STUDIO.md`](../dashboard/LOOKER_STUDIO.md). Exporter des captures dans
`docs/img/` et le lien public dans le README et dans `dbt/models/exposures.yml`.

## 8. Enseignements et publication

1. Exécuter les requêtes de `dbt/analyses/enseignements.sql` (`dbt compile`, puis copier le SQL
   compilé de `target/compiled/open_damir/analyses/` dans la console BigQuery).
2. Écrire 3 ou 4 constats chiffrés dans la section « Enseignements » du README, chacun avec le
   chiffre et sa lecture métier.
3. Remplacer `<votre-compte>` dans le README, pousser sur GitHub.
4. CI : dans *Settings › Secrets and variables › Actions*, ajouter la variable `GCP_PROJECT_ID` et
   le secret `GCP_SA_KEY` (contenu de `secrets/gcp-key.json`) pour activer les tests dbt mensuels.

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| « Le serveur a renvoyé une page HTML » | URL du fichier incorrecte | Étape 2, ou `--local-file` |
| `colonnes obligatoires absentes` | En-tête différent du lexique | `python -m ingestion inspect …` puis `COLUMN_ALIASES` |
| Montants tous NULL dans le staging | Format numérique inattendu | Regarder quelques valeurs brutes et adapter la macro `parse_number` |
| `Access Denied` dans BigQuery | Mauvais compte ou rôle | `gcloud auth application-default login` ; rôles du compte de service |
| dbt : `Query exceeded limit for bytes billed` | Garde-fou de 20 Go par requête | Normal sur trop de mois ; réduire la période ou relever `maximum_bytes_billed` |
| Airflow : `Permission denied` sur `data/` | UID du conteneur (Linux) | `AIRFLOW_UID=$(id -u)` dans `.env` |
