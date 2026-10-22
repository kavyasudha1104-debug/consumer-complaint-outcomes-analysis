"""Main analysis: outcome composition, issue comparisons, within-company
(stratified) comparisons, regression, and time patterns.

Usage:  python src/analyze_outcomes.py
Reads data/processed/complaints_scope.parquet, writes outputs/tables/*.csv and
outputs/tables/key_results.json.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as cm  # noqa: E402


# ---------------------------------------------------------------------------
# Building blocks (unit-tested)
# ---------------------------------------------------------------------------
def add_outcome_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add `known_final` and one 0/1 `ev_<outcome>` column per binary outcome."""
    df = df.copy()
    df["known_final"] = df["outcome"].isin(cm.KNOWN_FINAL)
    for name, cats in cm.OUTCOMES.items():
        df[f"ev_{name}"] = df["outcome"].isin(cats)
    return df


def rate_table(df: pd.DataFrame, keys: list[str], outcome: str = cm.PRIMARY_OUTCOME) -> pd.DataFrame:
    """Rate of `outcome` per group. Denominator = records with a known final
    response; everything else is reported as `n_excluded` (never as a failure)."""
    ev = f"ev_{outcome}"
    d = df.assign(_k=df["known_final"].astype(int), _e=(df[ev] & df["known_final"]).astype(int))
    g = d.groupby(keys, observed=True).agg(n_all=("_k", "size"), n_known=("_k", "sum"),
                                           events=("_e", "sum")).reset_index()
    g["n_excluded"] = g["n_all"] - g["n_known"]
    g["rate"] = np.where(g["n_known"] > 0, g["events"] / g["n_known"].where(g["n_known"] > 0), np.nan)
    ci = [cm.wilson_ci(k, n) for k, n in zip(g["events"], g["n_known"])]
    g["ci_lo"] = [c[0] for c in ci]
    g["ci_hi"] = [c[1] for c in ci]
    return g


def company_cells(df: pd.DataFrame, outcome: str, min_cell: int,
                  company_col: str = "company") -> pd.DataFrame:
    """Company x product-group x issue cells (known final responses only),
    keeping cells with at least `min_cell` observations."""
    k = df[df["known_final"]]
    g = (k.assign(_e=k[f"ev_{outcome}"].astype(int))
          .groupby([company_col, "product_group", "issue"], observed=True)
          .agg(n=("_e", "size"), events=("_e", "sum")).reset_index()
          .rename(columns={company_col: "company"}))
    return g[g["n"] >= min_cell].reset_index(drop=True)


def within_company_contrasts(cells: pd.DataFrame, min_issues: int = cm.MIN_COMPANY_ISSUES) -> pd.DataFrame:
    """For every company x product group with >= `min_issues` eligible issues,
    compare each issue's rate with the rate over that company's *other*
    eligible issues in the same product group."""
    cells = cells.copy()
    grp = cells.groupby(["company", "product_group"])
    cells["_N"] = grp["n"].transform("sum")
    cells["_E"] = grp["events"].transform("sum")
    cells["_ni"] = grp["issue"].transform("nunique")
    c = cells[cells["_ni"] >= min_issues].copy()
    if c.empty:
        return pd.DataFrame()
    c["n_other"] = c["_N"] - c["n"]
    c["events_other"] = c["_E"] - c["events"]
    res = [cm.newcombe_diff_ci(e, n, eo, no) for e, n, eo, no in
           zip(c["events"], c["n"], c["events_other"], c["n_other"])]
    out = c.rename(columns={"n": "n_issue", "events": "events_issue"})[
        ["company", "product_group", "issue", "n_issue", "events_issue", "n_other", "events_other"]].copy()
    out["rate_issue"] = out["events_issue"] / out["n_issue"]
    out["rate_other"] = out["events_other"] / out["n_other"]
    out["diff_pp"] = [100 * r[0] for r in res]
    out["lo_pp"] = [100 * r[1] for r in res]
    out["hi_pp"] = [100 * r[2] for r in res]
    out["p"] = [cm.two_prop_pvalue(e, n, eo, no) for e, n, eo, no in
                zip(out["events_issue"], out["n_issue"], out["events_other"], out["n_other"])]
    return out.reset_index(drop=True)


def stratified_summary(contrasts: pd.DataFrame) -> pd.DataFrame:
    """Per (product group, issue): Mantel-Haenszel within-company risk
    difference vs. the crude difference over the *same* companies, plus
    consistency across companies. One row per issue; each company contributes
    one comparison per issue, so company-level counts are independent units."""
    rows = []
    for (pg, issue), g in contrasts.groupby(["product_group", "issue"]):
        tabs = g[["events_issue", "n_issue", "events_other", "n_other"]].to_numpy(float)
        mh = cm.mh_risk_difference(tabs)
        crude = (g["events_issue"].sum() / g["n_issue"].sum()
                 - g["events_other"].sum() / g["n_other"].sum())
        sign = np.sign(crude) if crude != 0 else 1.0
        d = g["diff_pp"].to_numpy()
        same = np.sign(d) == sign
        sig_same = same & ((g["lo_pp"] > 0) | (g["hi_pp"] < 0)).to_numpy()
        sig_any = ((g["lo_pp"] > 0) | (g["hi_pp"] < 0)).to_numpy()
        # sign test on companies with a non-zero difference
        nz = d != 0
        k_same = int(same[nz].sum())
        p_sign = float(stats.binomtest(k_same, int(nz.sum()), 0.5).pvalue) if nz.sum() > 0 else np.nan
        # Cochran's Q on per-company risk differences (inverse-variance)
        p1, p0 = g["rate_issue"].to_numpy(), g["rate_other"].to_numpy()
        var = p1 * (1 - p1) / g["n_issue"].to_numpy() + p0 * (1 - p0) / g["n_other"].to_numpy()
        var = np.where(var <= 0, 1e-12, var)
        w = 1 / var
        rd = p1 - p0
        rd_fixed = np.sum(w * rd) / np.sum(w)
        q = float(np.sum(w * (rd - rd_fixed) ** 2))
        dfq = len(rd) - 1
        i2 = max(0.0, (q - dfq) / q) if q > 0 and dfq > 0 else np.nan
        mhw = (g["n_issue"] * g["n_other"] / (g["n_issue"] + g["n_other"])).to_numpy()
        top = int(np.argmax(mhw))
        loo = cm.mh_risk_difference(np.delete(tabs, top, axis=0)) if len(tabs) > 1 else dict(rd=np.nan)
        rows.append(dict(
            product_group=pg, issue=issue, n_companies=len(g),
            n_issue_total=int(g["n_issue"].sum()), n_other_total=int(g["n_other"].sum()),
            crude_diff_pp=100 * crude, mh_diff_pp=100 * mh["rd"],
            mh_lo_pp=100 * mh["lo"], mh_hi_pp=100 * mh["hi"], mh_p=mh["p"],
            retained_share=(mh["rd"] / crude) if crude != 0 else np.nan,
            share_companies_same_sign=float(same.mean()),
            share_companies_sig_same_sign=float(sig_same.mean()),
            share_companies_sig_any=float(sig_any.mean()),
            sign_test_p=p_sign, cochran_q=q, i2=i2,
            top_company=g["company"].iloc[top], top_company_weight_share=float(mhw[top] / mhw.sum()),
            mh_diff_pp_without_top_company=100 * loo["rd"],
        ))
    return pd.DataFrame(rows)


def classify_persistence(agg_row: pd.Series, wc_row: pd.Series | None,
                         min_companies: int = 3, alpha_adj: float = cm.ALPHA) -> str:
    """Pre-specified rule applied to issues that differ in the aggregate.

    persists          : within-company MH difference has the same sign, adjusted
                        p < alpha and retains >= 50% of the crude difference
    weakens           : same sign and significant but retains < 50%
    disappears        : MH CI includes 0 (adjusted p >= alpha) or sign reverses
    not_evaluable     : fewer than `min_companies` eligible companies
    """
    if wc_row is None or wc_row.get("n_companies", 0) < min_companies:
        return "not_evaluable"
    same_sign = np.sign(wc_row["mh_diff_pp"]) == np.sign(wc_row["crude_diff_pp"])
    if not same_sign or wc_row["mh_p_adj"] >= alpha_adj:
        return "disappears"
    return "persists" if wc_row["retained_share"] >= 0.5 else "weakens"


# ---------------------------------------------------------------------------
# Aggregate issue comparison
# ---------------------------------------------------------------------------
def aggregate_issue_table(df: pd.DataFrame, outcome: str, min_issue_n: int) -> pd.DataFrame:
    """Each eligible issue vs. all other known-outcome complaints in the same
    product group (Newcombe CI for the difference, Holm/BH across all tests)."""
    t = rate_table(df, ["product_group", "issue"], outcome)
    pg = t.groupby("product_group").agg(pg_n=("n_known", "sum"), pg_e=("events", "sum")).reset_index()
    t = t.merge(pg, on="product_group")
    t = t[t["n_known"] >= min_issue_n].copy()
    t["n_rest"] = t["pg_n"] - t["n_known"]
    t["events_rest"] = t["pg_e"] - t["events"]
    t["rate_rest"] = t["events_rest"] / t["n_rest"]
    res = [cm.newcombe_diff_ci(e, n, er, nr) for e, n, er, nr in
           zip(t["events"], t["n_known"], t["events_rest"], t["n_rest"])]
    t["diff_pp"] = [100 * r[0] for r in res]
    t["diff_lo_pp"] = [100 * r[1] for r in res]
    t["diff_hi_pp"] = [100 * r[2] for r in res]
    t["p"] = [cm.two_prop_pvalue(e, n, er, nr) for e, n, er, nr in
              zip(t["events"], t["n_known"], t["events_rest"], t["n_rest"])]
    t["p_holm"] = cm.holm_adjust(t["p"].to_numpy())
    t["p_bh"] = cm.bh_adjust(t["p"].to_numpy())
    t["sig_holm"] = t["p_holm"] < cm.ALPHA
    t["practical"] = t["diff_pp"].abs() >= cm.MIN_PRACTICAL_PP
    t["aggregate_flag"] = t["sig_holm"] & t["practical"]
    return t.drop(columns=["pg_n", "pg_e"]).sort_values(["product_group", "diff_pp"], ascending=[True, False]).reset_index(drop=True)


def heterogeneity_by_product(df: pd.DataFrame, outcome: str, min_issue_n: int) -> pd.DataFrame:
    """Chi-square test of homogeneity across eligible issues + Cramer's V."""
    rows = []
    t = rate_table(df, ["product_group", "issue"], outcome)
    t = t[t["n_known"] >= min_issue_n]
    for pg, g in t.groupby("product_group"):
        if len(g) < 2:
            continue
        tab = np.column_stack([g["events"], g["n_known"] - g["events"]])
        tab = tab[tab.sum(axis=1) > 0]
        if (tab.sum(axis=0) == 0).any():
            continue
        chi2, p, dof, _ = stats.chi2_contingency(tab, correction=False)
        n = tab.sum()
        v = np.sqrt(chi2 / n)  # 2 columns -> min(r-1, c-1) = 1
        rows.append(dict(product_group=pg, n_issues=len(g), n_known=int(n), chi2=chi2,
                         dof=dof, p=p, cramers_v=v,
                         rate_min=g["rate"].min(), rate_max=g["rate"].max()))
    return pd.DataFrame(rows)


def full_issue_pipeline(df: pd.DataFrame, outcome: str = cm.PRIMARY_OUTCOME,
                        min_issue_n: int = cm.MIN_ISSUE_N, min_cell: int = cm.MIN_CELL_N,
                        min_issues: int = cm.MIN_COMPANY_ISSUES, company_col: str = "company") -> dict:
    """Aggregate + within-company analysis for one analytical configuration."""
    agg = aggregate_issue_table(df, outcome, min_issue_n)
    cells = company_cells(df, outcome, min_cell, company_col)
    # restrict within-company analysis to issues eligible in the aggregate table
    elig = agg[["product_group", "issue"]]
    cells = cells.merge(elig, on=["product_group", "issue"])
    contrasts = within_company_contrasts(cells, min_issues)
    strat = stratified_summary(contrasts) if len(contrasts) else pd.DataFrame()
    if len(strat):
        strat["mh_p_adj"] = cm.holm_adjust(strat["mh_p"].to_numpy())
        m = agg.merge(strat, on=["product_group", "issue"], how="left", suffixes=("", "_wc"))
        verdict = []
        for _, r in m.iterrows():
            if not r["aggregate_flag"]:
                verdict.append("no_aggregate_difference")
            elif pd.isna(r.get("n_companies")):
                verdict.append("not_evaluable")
            else:
                verdict.append(classify_persistence(r, r))
        m["verdict"] = verdict
    else:
        m = agg.assign(verdict="not_evaluable")
    return dict(aggregate=agg, cells=cells, contrasts=contrasts, stratified=strat, merged=m)


# ---------------------------------------------------------------------------
# Regression (binomial GLM on grouped counts)
# ---------------------------------------------------------------------------
def regression_by_product(df: pd.DataFrame, outcome: str, min_issue_n: int,
                          min_company_n: int = 100) -> pd.DataFrame:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    k = df[df["known_final"]].copy()
    k["ev"] = k[f"ev_{outcome}"].astype(int)
    rows = []
    for pg, g in k.groupby("product_group"):
        vc = g["issue"].value_counts()
        keep_issue = vc[vc >= min_issue_n].index
        g = g[g["issue"].isin(keep_issue)]
        if len(keep_issue) < 2:
            continue
        cn = g.groupby("company")["ev"].agg(["size", "sum"])
        # fixed effects are uninformative for companies with all/no events
        ok = cn[(cn["size"] >= min_company_n) & (cn["sum"] > 0) & (cn["sum"] < cn["size"])].index
        g = g[g["company"].isin(ok)]
        if g["company"].nunique() < 3:
            continue
        cell = (g.groupby(["company", "issue", "year"], observed=True)["ev"]
                 .agg(events="sum", n="size").reset_index())
        cell["company"] = cell["company"].astype(str)
        cell["issue"] = cell["issue"].astype(str)
        cell["non"] = cell["n"] - cell["events"]
        ref = cell.groupby("issue")["n"].sum().idxmax()
        cell["issue"] = pd.Categorical(cell["issue"], [ref] + sorted(set(cell["issue"]) - {ref}))
        # Q() quoting so arbitrary text levels are safe
        specs = {"crude": "events + non ~ C(issue)",
                 "company_FE": "events + non ~ C(issue) + C(company)",
                 "company_year_FE": "events + non ~ C(issue) + C(company) + C(year)"}
        fits = {}
        for name, f in specs.items():
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fits[name] = smf.glm(f, data=cell, family=sm.families.Binomial()).fit(
                        cov_type="cluster", cov_kwds={"groups": pd.factorize(cell["company"])[0]})
            except Exception as e:  # pragma: no cover
                fits[name] = None
                print("model failed", pg, name, e)
        base = {}
        for name in ("company_FE", "company_year_FE"):
            pass
        for name, res in fits.items():
            if res is None:
                continue
            for term in res.params.index:
                if not term.startswith("C(issue)"):
                    continue
                level = term.split("[T.", 1)[1][:-1]
                lo, hi = res.conf_int().loc[term]
                rows.append(dict(product_group=pg, model=name, reference_issue=ref, issue=level,
                                 odds_ratio=float(np.exp(res.params[term])),
                                 or_lo=float(np.exp(lo)), or_hi=float(np.exp(hi)),
                                 p_cluster=float(res.pvalues[term]),
                                 n_companies=int(cell["company"].nunique()),
                                 n_known=int(cell["n"].sum())))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------
def yearly_tables(df: pd.DataFrame, outcome: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rate = rate_table(df, ["product_group", "year"], outcome)
    # composition / availability
    avail = (df.assign(cat=np.where(df["known_final"], "known_final", df["outcome"]))
             .groupby(["year", "cat"]).size().unstack(fill_value=0))
    avail["total"] = avail.sum(axis=1)
    return rate, avail.reset_index()


def adjusted_year_effects(df: pd.DataFrame, outcome: str, min_issue_n: int,
                          min_company_n: int = 100) -> pd.DataFrame:
    """Model-adjusted yearly rates: binomial GLM with issue + company + year
    effects, standardised to the pooled company/issue mix of the product group."""
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    k = df[df["known_final"]].copy()
    k["ev"] = k[f"ev_{outcome}"].astype(int)
    out = []
    for pg, g in k.groupby("product_group"):
        vc = g["issue"].value_counts()
        g = g[g["issue"].isin(vc[vc >= min_issue_n].index)]
        cn = g.groupby("company")["ev"].agg(["size", "sum"])
        ok = cn[(cn["size"] >= min_company_n) & (cn["sum"] > 0) & (cn["sum"] < cn["size"])].index
        g = g[g["company"].isin(ok)]
        yrs = g.groupby("year").size()
        g = g[g["year"].isin(yrs[yrs >= 500].index)]
        if g["company"].nunique() < 3 or g["year"].nunique() < 3:
            continue
        cell = (g.groupby(["company", "issue", "year"], observed=True)["ev"]
                 .agg(events="sum", n="size").reset_index())
        cell["company"] = cell["company"].astype(str)
        cell["issue"] = cell["issue"].astype(str)
        cell["non"] = cell["n"] - cell["events"]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = smf.glm("events + non ~ C(issue) + C(company) + C(year)", data=cell,
                              family=sm.families.Binomial()).fit()
        except Exception as e:  # pragma: no cover
            print("adj model failed", pg, e)
            continue
        raw = g.groupby("year")["ev"].mean()
        for y in sorted(cell["year"].unique()):
            pred = res.predict(cell.assign(year=y))
            out.append(dict(product_group=pg, year=int(y),
                            raw_rate=float(raw.loc[y]),
                            adjusted_rate=float(np.average(pred, weights=cell["n"])),
                            n_known=int(cell.loc[cell["year"] == y, "n"].sum())))
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
def load_scope(primary_window: bool = True) -> pd.DataFrame:
    df = pd.read_parquet(cm.PROC_DIR / "complaints_scope.parquet")
    if primary_window:
        df = df[df["in_primary_window"]]
    for c in ("product_group", "issue", "company", "company_raw", "outcome"):
        df[c] = df[c].astype("category")
    return add_outcome_flags(df)


def main() -> None:
    cm.TABLE_DIR.mkdir(parents=True, exist_ok=True)
    T = cm.TABLE_DIR
    df = load_scope(True)
    key: dict = dict(n_records_primary_window=int(len(df)),
                     date_min=str(df["date_received"].min().date()),
                     date_max=str(df["date_received"].max().date()))

    # ---- RQ1: composition --------------------------------------------------
    comp = (df.groupby(["product_group", "outcome"], observed=True).size().unstack(fill_value=0))
    comp["total"] = comp.sum(axis=1)
    comp.reset_index().to_csv(T / "rq1_outcome_counts_by_product.csv", index=False)
    kn = df[df["known_final"]]
    share = (kn.groupby(["product_group", "outcome"], observed=True).size().unstack(fill_value=0))
    share = share.div(share.sum(axis=1), axis=0) * 100
    share["n_known_final"] = kn.groupby("product_group", observed=True).size()
    share.reset_index().to_csv(T / "rq1_outcome_share_among_known_final.csv", index=False)
    ex = df.assign(cat=np.where(df["known_final"], "known_final", df["outcome"].astype(str)))
    ex.groupby(["product_group", "cat"], observed=True).size().unstack(fill_value=0).reset_index().to_csv(
        T / "rq1_denominator_exclusions_by_product.csv", index=False)
    key["outcome_counts_overall"] = {k: int(v) for k, v in df["outcome"].value_counts().items()}
    key["n_known_final"] = int(df["known_final"].sum())
    key["overall_any_relief_rate"] = float(df.loc[df["known_final"], "ev_any_relief"].mean())

    # ---- RQ2 / RQ3: primary configuration ---------------------------------
    for oc in cm.OUTCOMES:
        r = full_issue_pipeline(df, oc)
        suffix = "" if oc == cm.PRIMARY_OUTCOME else f"_{oc}"
        r["aggregate"].to_csv(T / f"rq2_issue_aggregate{suffix}.csv", index=False)
        r["contrasts"].to_csv(T / f"rq3_company_contrasts{suffix}.csv", index=False)
        r["stratified"].to_csv(T / f"rq3_stratified_summary{suffix}.csv", index=False)
        r["merged"].to_csv(T / f"rq3_aggregate_vs_within{suffix}.csv", index=False)
        if oc == cm.PRIMARY_OUTCOME:
            prim = r
            heterogeneity_by_product(df, oc, cm.MIN_ISSUE_N).to_csv(T / "rq2_heterogeneity_by_product.csv", index=False)

    m = prim["merged"]
    key["n_eligible_issues"] = int(len(m))
    key["verdict_counts"] = {k: int(v) for k, v in m["verdict"].value_counts().items()}
    key["n_company_product_units"] = int(prim["contrasts"].groupby(["company", "product_group"]).ngroups) if len(prim["contrasts"]) else 0

    # ---- regression ---------------------------------------------------------
    reg = regression_by_product(df, cm.PRIMARY_OUTCOME, cm.MIN_ISSUE_N)
    reg.to_csv(T / "rq3_regression_issue_odds_ratios.csv", index=False)

    # ---- time ----------------------------------------------------------------
    yr, avail = yearly_tables(df, cm.PRIMARY_OUTCOME)
    yr.to_csv(T / "rq4_yearly_rates_by_product.csv", index=False)
    avail.to_csv(T / "rq4_outcome_availability_by_year.csv", index=False)
    adj = adjusted_year_effects(df, cm.PRIMARY_OUTCOME, cm.MIN_ISSUE_N)
    adj.to_csv(T / "rq4_adjusted_yearly_rates.csv", index=False)

    (T / "key_results.json").write_text(json.dumps(key, indent=2, default=str))
    print(json.dumps(key, indent=2, default=str))


if __name__ == "__main__":
    main()
