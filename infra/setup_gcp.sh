#!/usr/bin/env bash
# Crée les ressources Google Cloud du projet (à lancer une seule fois).
#
# Prérequis : gcloud et bq installés, `gcloud auth login` fait, fichier .env rempli.
#
#   bash infra/setup_gcp.sh
#
# Deux modes, selon BQ_SANDBOX dans .env :
# - true (par défaut) : BigQuery sandbox, aucune carte bancaire ni compte de
#   facturation. Crée le projet, les datasets et le compte de service ; pas de bucket.
# - false : projet avec facturation (crédit d'essai). Crée en plus le bucket
#   Cloud Storage.
#
# Le script est rejouable : chaque ressource déjà existante est ignorée.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; source .env; set +a

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID manquant dans .env}"
SANDBOX="$(echo "${BQ_SANDBOX:-true}" | tr '[:upper:]' '[:lower:]')"
case "${SANDBOX}" in 1|true|yes|oui|on) SANDBOX=true ;; *) SANDBOX=false ;; esac
if [ "${SANDBOX}" = false ]; then
  : "${GCS_BUCKET:?GCS_BUCKET manquant dans .env (obligatoire si BQ_SANDBOX=false)}"
fi
LOCATION="${BQ_LOCATION:-EU}"
SA_NAME="damir-pipeline"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="secrets/gcp-key.json"

echo "==> Projet ${GCP_PROJECT_ID} (mode sandbox : ${SANDBOX})"
if ! gcloud projects describe "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
  gcloud projects create "${GCP_PROJECT_ID}" --name="Open DAMIR pipeline"
  if [ "${SANDBOX}" = false ]; then
    echo "!! Rattachez maintenant un compte de facturation au projet (console > Facturation), puis relancez."
    exit 1
  fi
fi
gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

echo "==> Activation des API"
if [ "${SANDBOX}" = true ]; then
  gcloud services enable bigquery.googleapis.com iam.googleapis.com
else
  gcloud services enable bigquery.googleapis.com storage.googleapis.com iam.googleapis.com
fi

if [ "${SANDBOX}" = false ]; then
  echo "==> Bucket gs://${GCS_BUCKET}"
  if ! gcloud storage buckets describe "gs://${GCS_BUCKET}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${GCS_BUCKET}" \
      --location="${LOCATION}" --uniform-bucket-level-access --public-access-prevention
  fi
  # Les CSV bruts sont supprimés après 30 jours (le Parquet reste) pour limiter le coût.
  gcloud storage buckets update "gs://${GCS_BUCKET}" --lifecycle-file=infra/gcs_lifecycle.json
fi

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
# Droits minimaux : lancer des jobs BigQuery, écrire dans les datasets (et le bucket).
for role in roles/bigquery.jobUser roles/bigquery.dataEditor; do
  gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="${role}" --condition=None >/dev/null
done
if [ "${SANDBOX}" = false ]; then
  gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
    --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.objectAdmin" >/dev/null
fi

if [ ! -f "${KEY_FILE}" ]; then
  echo "==> Clé du compte de service -> ${KEY_FILE} (ne jamais la versionner)"
  mkdir -p secrets
  gcloud iam service-accounts keys create "${KEY_FILE}" --iam-account="${SA_EMAIL}"
fi

echo
if [ "${SANDBOX}" = true ]; then
  echo "Terminé (sandbox). Rien n'est facturé. Les tables expirent 60 jours après leur"
  echo "création : faites les captures du tableau de bord dès qu'il est prêt."
else
  echo "Terminé. Pensez à créer une alerte budgétaire (console > Facturation > Budgets et alertes),"
  echo "par exemple 5 EUR avec alertes à 50 %, 90 % et 100 %."
fi
