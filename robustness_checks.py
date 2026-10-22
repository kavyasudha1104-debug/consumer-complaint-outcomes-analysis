"""Robustness checks: re-run the aggregate + within-company pipeline under
alternative, reasonable analytical choices and compare with the primary run.

Usage:  python src/robustness_checks.py
Writes outputs/tables/robustness_summary.csv and robustness_issue_level.csv
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from analyze_outcomes import add_outcome_flags, full_issue_pipeline  # noqa: E402


def load_full() -> pd.DataFrame:
    df = pd.read_parquet(C.PROC_DIR / "complaints_scope.parquet")
    for c in ("product_group", "issue", "company", "company_raw", "outcome", "sub_product"):
        df[c] = df[c].astype("category")
    return add_outcome_flags(df)


def with_known(df: pd.DataFrame, cats: set[str]) -> pd.DataFrame:
    df = df.copy()
    df["known_final"] = df["outcome"].isin(cats)
    return df


def drop_top_companies(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """Remove, within each product group, the k companies with most known responses."""
    kn = df[df["known_final"]]
    top = (kn.groupby(["product_group", "company"], observed=True).size().rename("n").reset_index()
             .sort_values(["product_group", "n"], ascending=[True, False])
             .groupby("product_group").head(k))
    key = set(zip(top["product_group"].astype(str), top["company"].astype(str)))
    mask = [(p, c) in key for p, c in zip(df["product_group"].astype(str), df["company"].astype(str))]
    return df[~np.array(mask)]


def build_variants(full: pd.DataFrame) -> dict:
    primary = full[full["in_primary_window"]]
    V: dict[str, dict] = {}
    V["PRIMARY"] = dict(df=primary)
    # --- eligibility thresholds
    for n in (300, 3000):
        V[f"min_issue_n={n}"] = dict(df=primary, min_issue_n=n)
    for n in (10, 100, 300):
        V[f"min_cell_n={n}"] = dict(df=primary, min_cell=n)
    V["min_company_issues=3"] = dict(df=primary, min_issues=3)
    # --- outcome definitions / mappings
    for oc in ("monetary_relief", "non_monetary_relief", "explanation_only"):
        V[f"outcome={oc}"] = dict(df=primary, outcome=oc)
    V["mapping: bare 'Closed'/'Untimely' kept in denominator as non-relief"] = dict(
        df=with_known(primary, C.KNOWN_FINAL | {"closed_unspecified", "untimely_legacy"}))
    V["mapping: strict (drop legacy relief values)"] = dict(
        df=with_known(primary, {"monetary_relief", "non_monetary_relief", "explanation_only"}))
    # --- company names
    V["company: raw (un-normalised) names"] = dict(df=primary, company_col="company_raw")
    # --- time window / classification changes
    V["window: through file end (2026-10-17)"] = dict(df=full)
    V["window: 2020-01-01 onward"] = dict(df=primary[primary["date_received"] >= "2020-01-01"])
    V["window: 2017-04 to 2019-12 only"] = dict(df=primary[primary["date_received"] < "2020-01-01"])
    V["window: 2017-04 to 2021-12"] = dict(df=primary[primary["date_received"] < "2022-01-01"])
    V["window: 2022-01 onward"] = dict(df=primary[primary["date_received"] >= "2022-01-01"])
    sp = primary["sub_product"].astype(str).str.contains("prepaid", case=False, na=False)
    V["credit card: prepaid sub-products excluded"] = dict(df=primary[~sp])
    # --- dependence on a few companies
    V["drop top-1 company per product"] = dict(df=drop_top_companies(primary, 1))
    V["drop top-3 companies per product"] = dict(df=drop_top_companies(primary, 3))
    return V


def main() -> None:
    full = load_full()
    V = build_variants(full)
    summ, long = [], []
    base = None
    for name, spec in V.items():
        spec = dict(spec)
        d = spec.pop("df")
        res = full_issue_pipeline(d, **spec)
        m = res["merged"].copy()
        m["variant"] = name
        long.append(m[[c for c in ["variant", "product_group", "issue", "n_known", "rate", "diff_pp",
                                   "p_holm", "aggregate_flag", "n_companies", "crude_diff_pp",
                                   "mh_diff_pp", "mh_lo_pp", "mh_hi_pp", "mh_p_adj", "retained_share",
                                   "verdict"] if c in m.columns]])
        vc = m["verdict"].value_counts().to_dict()
        row = dict(variant=name, n_records_known=int(d["known_final"].sum()),
                   n_eligible_issues=len(m), n_agg_flagged=int(m["aggregate_flag"].sum()),
                   persists=vc.get("persists", 0), weakens=vc.get("weakens", 0),
                   disappears=vc.get("disappears", 0), not_evaluable=vc.get("not_evaluable", 0),
                   n_companies_median=float(m["n_companies"].median()) if "n_companies" in m else np.nan)
        if name == "PRIMARY":
            base = m
        else:
            j = base.merge(m, on=["product_group", "issue"], suffixes=("_p", "_v"))
            row["n_issues_in_common"] = len(j)
            if len(j) > 2:
                ok = j["mh_diff_pp_p"].notna() & j["mh_diff_pp_v"].notna()
                row["spearman_agg_diff"] = float(stats.spearmanr(j["diff_pp_p"], j["diff_pp_v"])[0])
                if ok.sum() > 2:
                    row["spearman_mh_diff"] = float(stats.spearmanr(j.loc[ok, "mh_diff_pp_p"], j.loc[ok, "mh_diff_pp_v"])[0])
                    row["mh_same_sign_share"] = float((np.sign(j.loc[ok, "mh_diff_pp_p"]) == np.sign(j.loc[ok, "mh_diff_pp_v"])).mean())
            pf = j[j["aggregate_flag_p"] == True]  # noqa: E712
            row["primary_flagged_in_common"] = len(pf)
            row["primary_flagged_same_verdict"] = int((pf["verdict_p"] == pf["verdict_v"]).sum())
            row["primary_flagged_same_mh_sign"] = int(
                (np.sign(pf["mh_diff_pp_p"]) == np.sign(pf["mh_diff_pp_v"])).sum())
        summ.append(row)
        print(name, {k: v for k, v in row.items() if k != "variant"})
    C.TABLE_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summ).to_csv(C.TABLE_DIR / "robustness_summary.csv", index=False)
    pd.concat(long).to_csv(C.TABLE_DIR / "robustness_issue_level.csv", index=False)


if __name__ == "__main__":
    main()
