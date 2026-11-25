"""Configuration lue depuis les variables d'environnement (fichier .env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv est facultatif (inutile dans Airflow, où l'env est injecté)
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# Modèle d'URL des fichiers mensuels. À vérifier sur la page Ameli
# (clic droit sur le lien d'un mois > « Copier l'adresse du lien ») et à
# surcharger via DAMIR_URL_TEMPLATE si le site change.
DEFAULT_URL_TEMPLATE = (
    "https://open-data-assurance-maladie.ameli.fr/depenses/download_file.php"
    "?file=Open_DAMIR/A{yyyymm}.csv.gz"
)


def env_flag(name: str, default: bool) -> bool:
    """Lit un booléen d'environnement (true/false, 1/0, oui/non)."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "oui", "on"}


@dataclass(frozen=True)
class Settings:
    project_id: str
    bucket: str
    raw_dataset: str
    raw_table: str
    location: str
    url_template: str
    data_dir: Path
    # Mode « BigQuery sandbox » : projet sans compte de facturation. Pas de Cloud
    # Storage ni de DML ; chaque mois est chargé depuis le poste dans sa propre table.
    sandbox: bool = True

    @property
    def raw_table_id(self) -> str:
        return f"{self.project_id}.{self.raw_dataset}.{self.raw_table}"


def get_settings() -> Settings:
    return Settings(
        project_id=os.getenv("GCP_PROJECT_ID", ""),
        bucket=os.getenv("GCS_BUCKET", ""),
        raw_dataset=os.getenv("BQ_RAW_DATASET", "damir_raw"),
        raw_table=os.getenv("BQ_RAW_TABLE", "prestations"),
        location=os.getenv("BQ_LOCATION", "EU"),
        url_template=os.getenv("DAMIR_URL_TEMPLATE", DEFAULT_URL_TEMPLATE),
        data_dir=Path(os.getenv("DATA_DIR", "data")).resolve(),
        sandbox=env_flag("BQ_SANDBOX", True),
    )


def require(settings: Settings, *fields: str) -> None:
    """Vérifie que les paramètres GCP nécessaires sont renseignés."""
    missing = [f for f in fields if not getattr(settings, f)]
    if missing:
        env_names = {"project_id": "GCP_PROJECT_ID", "bucket": "GCS_BUCKET"}
        names = ", ".join(env_names.get(f, f) for f in missing)
        raise SystemExit(f"Variables d'environnement manquantes : {names} (voir .env.example)")
