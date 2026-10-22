"""Clean the raw CFPB complaint file into an analysis-ready table.

Reads the raw CSV in chunks (the file is >5 GB), keeps only the columns needed,
applies the documented inclusion rules and writes:

  data/processed/complaints_scope.parquet   cleaned in-scope records
  outputs/tables/cleaning_log.json          every count needed to audit the cleaning
  outputs/tables/raw_product_profile.csv    all raw products: rows, dates (whole file)

Usage:  python src/clean_data.py [--raw data/raw/complaints.csv]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (MISSING_OUTCOME, OUTCOME_MAP, PLANNED_END, PRODUCT_MAP,  # noqa: E402
                    PROC_DIR, RAW_DIR, TABLE_DIR, WINDOW_START,
                    map_outcome, normalize_company)

USECOLS = ["Date received", "Product", "Sub-product", "Issue", "Sub-issue",
           "Company", "Submitted via", "Company response to consumer",
           "Timely response?", "Complaint ID"]


def clean_chunk(ch: pd.DataFrame) -> pd.DataFrame:
    """Parse/standardise one chunk of in-scope rows (pure function, tested)."""
    out = pd.DataFrame({
        "complaint_id": ch["Complaint ID"].astype("string").str.strip(),
        "date_received": pd.to_datetime(ch["Date received"], errors="coerce"),
        "product_raw": ch["Product"],
        "sub_product": ch["Sub-product"],
        "issue": ch["Issue"].astype("string").str.strip(),
        "company_raw": ch["Company"].astype("string").str.strip(),
        "response_raw": ch["Company response to consumer"],
        "timely": ch["Timely response?"],
    })
    out["product_group"] = out["product_raw"].map(PRODUCT_MAP)
    out["company"] = out["company_raw"].map(normalize_company)
    out["outcome"] = out["response_raw"].map(map_outcome)
    return out


def main(raw_path: Path) -> None:
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    prof: dict[str, dict] = {}
    log = dict(raw_file=str(raw_path), raw_rows=0, invalid_dates=0,
               rows_before_window=0, rows_after_window_end_file=0,
               rows_out_of_product_scope=0)
    kept = []
    for ch in pd.read_csv(raw_path, usecols=USECOLS, dtype=str, chunksize=1_000_000):
        log["raw_rows"] += len(ch)
        d = pd.to_datetime(ch["Date received"], errors="coerce")
        log["invalid_dates"] += int(d.isna().sum())
        # whole-file product profile (for the data-quality section)
        g = pd.DataFrame({"p": ch["Product"], "d": d}).groupby("p", dropna=False)["d"]
        for p, (n, mn, mx) in g.agg(["size", "min", "max"]).iterrows():
            e = prof.setdefault(p, dict(rows=0, min=mn, max=mx))
            e["rows"] += int(n)
            e["min"] = min(e["min"], mn) if pd.notna(e["min"]) else mn
            e["max"] = max(e["max"], mx) if pd.notna(e["max"]) else mx
        pre = (d < WINDOW_START)
        log["rows_before_window"] += int(pre.sum())
        in_prod = ch["Product"].isin(PRODUCT_MAP)
        log["rows_out_of_product_scope"] += int((~pre & ~in_prod).sum())
        keep = ~pre & in_prod & d.notna()
        if keep.any():
            kept.append(clean_chunk(ch[keep]))

    df = pd.concat(kept, ignore_index=True)
    log["rows_in_product_and_date_scope"] = int(len(df))
    log["file_max_date"] = str(df["date_received"].max().date())
    log["file_min_date_in_scope"] = str(df["date_received"].min().date())

    # ---- duplicates --------------------------------------------------------
    log["duplicate_complaint_ids"] = int(df["complaint_id"].duplicated().sum())
    log["fully_duplicated_rows"] = int(df.duplicated().sum())
    df = df.drop_duplicates(subset="complaint_id", keep="first")
    log["rows_after_dedup"] = int(len(df))

    # ---- missing values in key fields -------------------------------------
    key = ["issue", "company", "response_raw", "timely", "sub_product"]
    log["missing_by_field_after_dedup"] = {c: int(df[c].isna().sum()) for c in key}
    df = df[df["issue"].notna() & df["company"].notna()].copy()
    log["rows_after_dropping_missing_issue_or_company"] = int(len(df))

    # ---- outcomes ----------------------------------------------------------
    log["unmapped_response_values"] = sorted(
        v for v in df["outcome"].unique() if str(v).startswith("unmapped_"))
    log["outcome_counts_all_scope"] = {k: int(v) for k, v in df["outcome"].value_counts().items()}

    # ---- company-name normalisation audit ---------------------------------
    log["distinct_company_raw"] = int(df["company_raw"].nunique())
    log["distinct_company_normalised"] = int(df["company"].nunique())
    g = df.groupby("company")["company_raw"].nunique()
    log["normalised_companies_merging_multiple_raw_names"] = int((g > 1).sum())

    df["year"] = df["date_received"].dt.year.astype("int16")
    df["in_primary_window"] = df["date_received"] <= PLANNED_END
    df.to_parquet(PROC_DIR / "complaints_scope.parquet", index=False)

    pp = pd.DataFrame(prof).T.reset_index().rename(columns={"index": "product_raw"})
    pp["in_scope_product"] = pp["product_raw"].isin(PRODUCT_MAP)
    pp["product_group"] = pp["product_raw"].map(PRODUCT_MAP)
    pp.sort_values("rows", ascending=False).to_csv(TABLE_DIR / "raw_product_profile.csv", index=False)
    log["outcome_mapping"] = OUTCOME_MAP
    log["missing_outcome_label"] = MISSING_OUTCOME
    (TABLE_DIR / "cleaning_log.json").write_text(json.dumps(log, indent=2, default=str))
    print(json.dumps({k: v for k, v in log.items() if k != "outcome_mapping"}, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(RAW_DIR / "complaints.csv"))
    a = ap.parse_args()
    main(Path(a.raw))
