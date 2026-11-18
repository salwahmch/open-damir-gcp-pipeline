.PHONY: help install test lint gcp-setup ingest-sample ingest dbt-build dbt-docs airflow-up airflow-down

MONTH ?= 2024-01

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install:  ## Installe les dépendances Python dans l'environnement courant
	pip install -r requirements-dev.txt

lint:  ## Vérifie le style du code Python
	ruff check .

test:  ## Lance les tests unitaires
	pytest -q tests/test_ingestion.py

gcp-setup:  ## Crée bucket, datasets et compte de service (une fois)
	bash infra/setup_gcp.sh

ingest-sample:  ## Ingestion d'un mois limitée à 200 000 lignes (MONTH=AAAA-MM)
	python -m ingestion run --month $(MONTH) --max-rows 200000

ingest:  ## Ingestion complète d'un mois (MONTH=AAAA-MM)
	python -m ingestion run --month $(MONTH)

dbt-build:  ## dbt deps + seed + run + test
	cd dbt && dbt deps --profiles-dir . && dbt seed --profiles-dir . && dbt run --profiles-dir . && dbt test --profiles-dir .

dbt-docs:  ## Génère et ouvre la documentation dbt (http://localhost:8081)
	cd dbt && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir . --port 8081

airflow-up:  ## Démarre Airflow en local (http://localhost:8080)
	docker compose up --build -d

airflow-down:  ## Arrête Airflow
	docker compose down
