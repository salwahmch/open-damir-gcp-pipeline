ARG AIRFLOW_VERSION=3.4.0
ARG PYTHON_VERSION=3.12
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}

ARG AIRFLOW_VERSION

# Dépendances de l'ingestion, installées avec la version d'Airflow figée pour
# éviter que pip ne la mette à jour.
COPY airflow/requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/requirements-airflow.txt

# dbt dans un environnement virtuel séparé : ses dépendances entrent souvent en
# conflit avec celles d'Airflow. Le DAG l'appelle via /opt/airflow/dbt_venv/bin/dbt.
RUN python -m venv /opt/airflow/dbt_venv \
    && /opt/airflow/dbt_venv/bin/pip install --no-cache-dir "dbt-bigquery~=1.12"
