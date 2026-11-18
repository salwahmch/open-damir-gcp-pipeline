"""Description du fichier Open DAMIR (série « A », depuis 2015).

Chaque ligne de prestation est décrite par 55 variables. On en conserve un
sous-ensemble utile à l'analyse des dépenses, ce qui divise environ par deux
le volume stocké dans BigQuery (offre gratuite : 10 Go de stockage).
"""

from __future__ import annotations

# Liste attendue des 55 variables de la série A (lexique officiel Open DAMIR).
EXPECTED_COLUMNS: list[str] = [
    "FLX_ANN_MOI", "ORG_CLE_REG", "AGE_BEN_SNDS", "BEN_RES_REG", "BEN_CMU_TOP",
    "BEN_QLT_COD", "BEN_SEX_COD", "DDP_SPE_COD", "ETE_CAT_SNDS", "ETE_REG_COD",
    "ETE_TYP_SNDS", "ETP_REG_COD", "ETP_CAT_SNDS", "MDT_TYP_COD", "MFT_COD",
    "PRS_FJH_TYP", "PRS_ACT_COG", "PRS_ACT_NBR", "PRS_ACT_QTE", "PRS_DEP_MNT",
    "PRS_PAI_MNT", "PRS_REM_BSE", "PRS_REM_MNT", "FLT_ACT_COG", "FLT_ACT_NBR",
    "FLT_ACT_QTE", "FLT_DEP_MNT", "FLT_PAI_MNT", "FLT_REM_MNT", "SOI_ANN",
    "SOI_MOI", "ASU_NAT", "ATT_NAT", "CPL_COD", "CPT_ENV_TYP", "DRG_AFF_NAT",
    "ETE_IND_TAA", "EXO_MTF", "MTM_NAT", "PRS_NAT", "PRS_PPU_SEC", "PRS_REM_TAU",
    "PRS_REM_TYP", "PRS_PDS_QCP", "EXE_INS_REG", "PSE_ACT_SNDS", "PSE_ACT_CAT",
    "PSE_SPE_SNDS", "PSE_STJ_SNDS", "PRE_INS_REG", "PSP_ACT_SNDS", "PSP_ACT_CAT",
    "PSP_SPE_SNDS", "PSP_STJ_SNDS", "TOP_PS5_TRG",
]

# Colonnes conservées dans la zone brute BigQuery.
KEPT_COLUMNS: list[str] = [
    # Temps
    "FLX_ANN_MOI", "SOI_ANN", "SOI_MOI",
    # Prestation
    "PRS_NAT", "ASU_NAT", "CPT_ENV_TYP", "PRS_PPU_SEC", "EXO_MTF", "PRS_REM_TAU",
    "PRS_PDS_QCP",
    # Bénéficiaire
    "AGE_BEN_SNDS", "BEN_SEX_COD", "BEN_RES_REG", "BEN_CMU_TOP",
    # Professionnel exécutant / prescripteur
    "PSE_ACT_CAT", "PSE_SPE_SNDS", "PSP_ACT_CAT",
    # Indicateurs
    "PRS_ACT_NBR", "PRS_ACT_QTE", "PRS_PAI_MNT", "PRS_REM_MNT", "PRS_REM_BSE",
    "PRS_DEP_MNT",
]

# Colonnes sans lesquelles le fichier est inutilisable : on arrête l'ingestion.
REQUIRED_COLUMNS: set[str] = {"FLX_ANN_MOI", "PRS_NAT", "PRS_PAI_MNT", "PRS_REM_MNT"}

# Anciens noms (série P, 2009-2014, découpage ZEAT) -> noms de la série A.
COLUMN_ALIASES: dict[str, str] = {
    "BEN_RES_ZEAT": "BEN_RES_REG",
    "ORG_CLE_ZEAT": "ORG_CLE_REG",
    "EXE_INS_ZEAT": "EXE_INS_REG",
    "PRE_INS_ZEAT": "PRE_INS_REG",
    "ETE_ZEAT_COD": "ETE_REG_COD",
    "ETP_ZEAT_COD": "ETP_REG_COD",
}

# Colonnes techniques ajoutées par l'ingestion.
META_COLUMNS: list[str] = ["_flx_month", "_source_file", "_ingested_at"]
