# Guide pas à pas

Ce guide suit le **mode sandbox** de BigQuery : aucune carte bancaire, aucun compte de
facturation, rien n'est facturé. Le mode standard (avec facturation) est décrit à la fin.

Ordre conseillé, avec un point de contrôle ✅ à chaque étape. Compter une à deux soirées pour les
étapes 1 à 5, puis une pour le tableau de bord et le README.

**Ce qu'il faut savoir sur le sandbox avant de commencer**

- Il suffit d'un compte Google. Limites : 10 Go de stockage et 1 To de requêtes par mois.
- Pas de Cloud Storage et pas de requêtes `MERGE`/`INSERT` : le code le gère déjà
  (`BQ_SANDBOX=true` dans `.env`).
- **Toutes les tables sont supprimées 60 jours après leur création.** Faire les captures du
  tableau de bord dès qu'il est prêt (étape 7). Pour tout remettre en ligne plus tard, il suffit de
  relancer l'étape 5.

## 0. Prérequis

- Python 3.11 ou plus, Git, Docker Desktop, VS Code
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud` et `bq`) : sous Windows,
  l'installateur ajoute aussi « Google Cloud SDK Shell »
- Sous Windows, lancer les commandes de ce guide dans **Git Bash** (installé avec Git) : il fournit
  `bash` et `cp`. `make` n'existe pas sous Windows : chaque commande `make` a son équivalent écrit
  à côté.

Récupérer le dépôt (déjà publié sur GitHub) :

```bash
git clone https://github.com/salwahmch/open-damir-gcp-pipeline.git
cd open-damir-gcp-pipeline

python -m venv .venv
source .venv/Scripts/activate          # Git Bash sous Windows ; Mac/Linux : source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q tests/test_ingestion.py      # ✅ 14 tests passent, sans aucun accès au cloud
```

## 1. Projet Google Cloud en mode sandbox

```bash
gcloud auth login
gcloud auth application-default login   # utilisé par Python et dbt en local
cp .env.example .env
```

Dans `.env`, choisir un identifiant de projet unique en minuscules, chiffres et tirets
(ex. `damir-salwa-2026`) pour `GCP_PROJECT_ID`, et laisser `BQ_SANDBOX=true` et `GCS_BUCKET` vide.
Puis :

```bash
bash infra/setup_gcp.sh
```

Le script crée le projet s'il n'existe pas, les 4 datasets et un compte de service. Il ne demande
aucune facturation.

> Si `gcloud projects create` échoue (première utilisation de Google Cloud : conditions
> d'utilisation à accepter), créer le projet à la main sur https://console.cloud.google.com
> (« Nouveau projet », avec le même identifiant), puis relancer le script.

✅ Contrôle : sur https://console.cloud.google.com/bigquery (projet sélectionné en haut), un bandeau
« Sandbox » s'affiche et les datasets `damir_raw`, `damir_ref`, `damir_staging`, `damir_marts`
existent. Le fichier `secrets/gcp-key.json` existe (ne jamais le pousser sur GitHub ; il est dans
`.gitignore`).

> Si la console propose « Passer à la version complète » ou d'ajouter une carte : refuser. Le
> sandbox suffit pour tout le projet.

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

Puis chargement dans BigQuery (en sandbox, le fichier part directement du PC, sans Cloud Storage) :

```bash
python -m ingestion run --month 2024-01 --steps load
```

✅ Contrôle : la table `damir_raw.prestations_202401` existe. Dans la console BigQuery :

```sql
select _flx_month, count(*) from `damir_raw.prestations_*` group by 1;
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
cd ..
```

(`make dbt-build` enchaîne `deps`, `seed`, `run` et `test`.)

Les avertissements (`WARN`) des tests de relations sur la région ou la catégorie d'exécutant
signalent des codes absents des seeds : regarder les valeurs avec
`dbt test --select fct_depenses_mensuelles --store-failures`, puis compléter le seed concerné.
Faire une capture du graphe de lignage pour le README.

**Lexique à jour** : télécharger le « Descriptif des variables » sur la page Ameli et lancer
`python -m ingestion.build_seeds chemin/du/lexique.xls` pour régénérer `ref_prestation` et
`ref_specialite_executant` (ceux du dépôt viennent du lexique 2015).

## 5. Données réelles : 3 mois complets

Une fois l'échantillon validé, charger **un seul mois complet** d'abord :

```bash
python -m ingestion run --month 2024-01
```

Puis regarder sa taille : console BigQuery › `damir_raw` › `prestations_202401` › *Détails* ›
« Nombre total d'octets logiques ». Le sandbox autorise 10 Go en tout (tables brutes + fait +
marts) : garder environ 1 Go de marge.

- Si un mois fait moins de 3 Go : charger les deux suivants.
- Sinon : se limiter à 2 mois, ou choisir des mois espacés (ex. janvier et juillet).

```bash
python -m ingestion run --from 2024-02 --to 2024-03     # (make ingest-3-months FROM=2024-01 TO=2024-03)
cd dbt && dbt run --profiles-dir . && dbt test --profiles-dir . && cd ..
```

Rejouer un mois remplace sa table : aucun doublon. Pour libérer de la place, supprimer une table
mensuelle dans la console (le prochain `dbt run` reconstruit le fait sans ce mois).

## 6. Airflow

Sous Windows, Docker Desktop doit être lancé.

```bash
docker compose up --build -d           # (make airflow-up) premier démarrage : quelques minutes
```

Ouvrir http://localhost:8080, activer le DAG `open_damir_pipeline`, puis *Trigger DAG w/ config* :

```json
{"months": ["2024-04"], "max_rows": 200000}
```

En sandbox, la tâche `upload_to_gcs` se termine tout de suite (pas de Cloud Storage) et
`load_to_bigquery` envoie le fichier local. Airflow lit `BQ_SANDBOX` dans `.env`.

✅ Contrôle : toutes les tâches en vert, dont `dbt_test`. Faire une capture de la vue *Graph*.
Ensuite, supprimer la table d'essai `prestations_202404` dans la console si elle n'est pas voulue
dans l'analyse, puis relancer `dbt run`.

## 7. Tableau de bord Looker Studio

Looker Studio est gratuit et se branche sur les tables du sandbox. Voir
[`dashboard/LOOKER_STUDIO.md`](../dashboard/LOOKER_STUDIO.md).

**Faire les captures dès que le tableau de bord est prêt** et les enregistrer dans `docs/img/`
(`dashboard_vue_ensemble.png`, `dashboard_postes.png`). Ajouter le lien public dans le README et
dans `dbt/models/exposures.yml`. Après 60 jours, les tables disparaissent et le lien affiche une
erreur : relancer l'étape 5 (ingestion puis `dbt run`) avant un entretien pour le remettre en ligne.

## 8. Enseignements et publication

1. Exécuter les requêtes de `dbt/analyses/enseignements.sql` (`dbt compile`, puis copier le SQL
   compilé de `target/compiled/open_damir/analyses/` dans la console BigQuery).
2. Écrire 3 ou 4 constats chiffrés dans la section « Enseignements » du README, chacun avec le
   chiffre et sa lecture métier, et indiquer la période analysée.
3. Pousser sur GitHub :

   ```bash
   git add docs/img README.md dbt/models/exposures.yml
   git commit -m "Tableau de bord et enseignements"
   git push
   ```

4. CI (facultatif) : dans *Settings › Secrets and variables › Actions*, ajouter la variable
   `GCP_PROJECT_ID` et le secret `GCP_SA_KEY` (contenu de `secrets/gcp-key.json`) pour activer les
   tests dbt mensuels. Sans ces réglages, la CI vérifie quand même le code Python, le DAG et le
   projet dbt.

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| « Le serveur a renvoyé une page HTML » | URL du fichier incorrecte | Étape 2, ou `--local-file` |
| `colonnes obligatoires absentes` | En-tête différent du lexique | `python -m ingestion inspect …` puis `COLUMN_ALIASES` |
| Montants tous NULL dans le staging | Format numérique inattendu | Regarder quelques valeurs brutes et adapter la macro `parse_number` |
| `Access Denied` dans BigQuery | Mauvais compte ou rôle | `gcloud auth application-default login` ; rôles du compte de service |
| `Billing has not been enabled` / `DML ... not supported` | `BQ_SANDBOX` vaut `false` dans `.env` | Remettre `BQ_SANDBOX=true` |
| dbt : `Not found: Table ... prestations_*` | Aucune table mensuelle chargée, ou expirée (60 jours) | Relancer l'étape 3 ou 5 |
| `Quota exceeded` sur le stockage | Plus de 10 Go dans le projet | Supprimer une table mensuelle, puis `dbt run` |
| dbt : `Query exceeded limit for bytes billed` | Garde-fou de 20 Go par requête | Normal sur trop de mois ; réduire la période ou relever `maximum_bytes_billed` |
| `bash` ou `cp` introuvable (Windows) | Commande lancée dans PowerShell | Utiliser Git Bash |
| Airflow : `Permission denied` sur `data/` | UID du conteneur (Linux) | `AIRFLOW_UID=$(id -u)` dans `.env` |

## Mode standard (avec facturation)

Avec un compte de facturation (par exemple le crédit d'essai de Google Cloud, qui demande une
carte) : mettre `BQ_SANDBOX=false` et un nom de bucket unique dans `GCS_BUCKET`, rattacher la
facturation au projet dans la console, relancer `bash infra/setup_gcp.sh` et créer une alerte
budgétaire à 5 € (console › Facturation › Budgets et alertes). L'ingestion passe alors par Cloud
Storage (`--steps download,transform,upload,load`), la zone brute devient une table partitionnée
par mois et le fait dbt redevient incrémental. Les tables n'expirent plus.
