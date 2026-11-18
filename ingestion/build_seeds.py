"""Génère les seeds dbt (tables de libellés) à partir du lexique officiel Open DAMIR.

Le lexique est un classeur Excel avec un onglet par variable (colonne 1 : code,
colonne 2 : libellé). Usage :

    python -m ingestion.build_seeds chemin/vers/lexique_open_damir.xls

Les seeds écrits dans dbt/seeds/ sont versionnés : on ne relance ce script que
lorsque l'Assurance Maladie publie un nouveau lexique.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

SEEDS_DIR = Path(__file__).resolve().parents[1] / "dbt" / "seeds"

# onglet du lexique -> (nom du seed, colonne code, colonne libellé)
# Seules les nomenclatures longues sont générées ; les petites (âge, sexe,
# région, enveloppe...) sont écrites à la main dans dbt/seeds/ avec des
# libellés accentués et lisibles dans le tableau de bord.
SHEETS = {
    "PRS_NAT": ("ref_prestation", "code_prestation", "libelle_prestation"),
    "PSE_SPE_SNDS": ("ref_specialite_executant", "code_specialite_executant",
                     "libelle_specialite_executant"),
}


def clean_label(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value.capitalize() if value.isupper() else value


def build(lexique: Path, out_dir: Path = SEEDS_DIR) -> list[Path]:
    sheets = pd.read_excel(lexique, sheet_name=None, header=None, dtype=str)
    written = []
    for sheet, (seed, code_col, label_col) in SHEETS.items():
        if sheet not in sheets:
            print(f"[avertissement] onglet {sheet} absent du lexique, seed {seed} non régénéré")
            continue
        df = sheets[sheet].iloc[1:, :2].dropna(how="any")
        df.columns = [code_col, label_col]
        df[code_col] = df[code_col].str.strip().str.replace(r"\.0$", "", regex=True)
        df[label_col] = df[label_col].map(clean_label)
        df = df[df[code_col].str.fullmatch(r"\d+")].drop_duplicates(code_col, keep="first")
        df = df.sort_values(code_col, key=lambda s: s.astype(int))
        path = out_dir / f"{seed}.csv"
        df.to_csv(path, index=False)
        written.append(path)
        print(f"{path.name}: {len(df)} codes")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lexique", type=Path, help="Fichier Excel du lexique Open DAMIR")
    parser.add_argument("--out", type=Path, default=SEEDS_DIR)
    args = parser.parse_args()
    build(args.lexique, args.out)


if __name__ == "__main__":
    main()
