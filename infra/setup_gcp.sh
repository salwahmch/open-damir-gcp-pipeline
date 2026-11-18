#!/usr/bin/env bash
# Crée les ressources Google Cloud du projet (à lancer une seule fois).
#
# Prérequis : gcloud installé, `gcloud auth login` fait, compte de facturation
# (crédit d'essai gratuit) rattaché au projet, fichier .env rempli.
#
#   bash infra/setup_gcp.sh
#
# Le script est rejouable : chaque ressource déjà existante est ignorée.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; source .env; set +a

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID manquant dans .env}"
: "${GCS_BUCKET:?GCS_BUCKET manquant dans .env}"
LOCATION="${BQ_LOCATION:-EU}"
SA_NAME="damir-pipeline"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="secrets/gcp-key.json"

echo "==> Projet ${GCP_PROJECT_ID}"
if ! gcloud projects describe "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
  gcloud projects create "${GCP_PROJECT_ID}" --name="Open DAMIR pipeline"
  echo "!! Rattachez maintenant un compte de facturation au projet (console > Facturation), puis relancez."
  exit 1
fi
gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

echo "==> Activation des API"
gcloud services enable bigquery.googleapis.com storage.googleapis.com iam.googleapis.com

echo "==> Bucket gs://${GCS_BUCKET}"
if ! gcloud storage buckets describe "gs://${GCS_BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${GCS_BUCKET}" \
    --location="${LOCATION}" --uniform-bucket-level-access --public-access-prevention
fi
# Les CSV bruts sont supprimés après 30 jours (le Parquet reste) pour limiter le coût.
gcloud storage buckets update "gs://${GCS_BUCKET}" --lifecycle-file=infra/gcs_lifecycle.json

echo "==> Datasets BigQuery (${LOCATION})"
for ds in damir_raw damir_ref damir_staging damir_marts; do
  if ! bq --location="${LOCATION}" show --dataset "${GCP_PROJECT_ID}:${ds}" >/dev/null 2>&1; then
    bq --location="${LOCATION}" mk --dataset --description "Open DAMIR - ${ds}" "${GCP_PROJECT_ID}:${ds}"
  fi
done

echo "==> Compte de service ${SA_EMAIL}"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" --display-name="Pipeline Open DAMIR"
fi
# Droits minimaux : lancer des jobs BigQuery, écrire dans les datasets, écrire dans le bucket.
for role in roles/bigquery.jobUser roles/bigquery.dataEditor; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="${role}" --condition=None >/dev/null
done
gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectAdmin" >/dev/null

if [ ! -f "${KEY_FILE}" ]; then
  echo "==> Clé du compte de service -> ${KEY_FILE} (ne jamais la versionner)"
  mkdir -p secrets
  gcloud iam service-accounts keys create "${KEY_FILE}" --iam-account="${SA_EMAIL}"
fi

echo
echo "Terminé. Pensez à créer une alerte budgétaire (console > Facturation > Budgets et alertes),"
echo "par exemple 5 EUR avec alertes à 50 %, 90 % et 100 %."
