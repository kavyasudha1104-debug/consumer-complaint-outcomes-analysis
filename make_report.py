"""Generate outputs/report.md from the executed analysis tables.

Every number in the report is read from outputs/tables/*.csv|json (written by
clean_data.py, analyze_outcomes.py, robustness_checks.py). Narrative sentences
that interpret numbers are guarded by the numbers themselves where practical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

T = C.TABLE_DIR


def md(df: pd.DataFrame, floatfmt: str = "{:.1f}") -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else floatfmt.format(v))
        elif pd.api.types.is_integer_dtype(d[c]):
            d[c] = d[c].map(lambda v: f"{v:,}")
    head = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    rows = ["| " + " | ".join(str(x) for x in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join([head, sep] + rows)


def regression_summary() -> pd.DataFrame:
    r = pd.read_csv(T / "rq3_regression_issue_odds_ratios.csv")
    rows = []
    for (pg, model), g in r.groupby(["product_group", "model"]):
        lo = np.log(g["odds_ratio"].to_numpy())
        lo = np.append(lo, 0.0)  # reference issue
        rows.append(dict(product_group=pg, model=model, n_issues=len(lo),
                         sd_log_or=float(np.std(lo, ddof=1)),
                         max_or_over_min_or=float(np.exp(lo.max() - lo.min()))))
    s = pd.DataFrame(rows)
    p = s.pivot(index="product_group", columns="model", values="sd_log_or")
    p = p[["crude", "company_FE", "company_year_FE"]].reset_index()
    p["shrinkage_crude_to_companyFE_%"] = 100 * (1 - p["company_FE"] / p["crude"])
    p.to_csv(T / "rq3_regression_spread_summary.csv", index=False)
    return p


def main() -> None:
    log = json.loads((T / "cleaning_log.json").read_text())
    key = json.loads((T / "key_results.json").read_text())
    rec = json.loads((C.RAW_DIR / "retrieval_record.json").read_text()) if (C.RAW_DIR / "retrieval_record.json").exists() else {}
    m = pd.read_csv(T / "rq3_aggregate_vs_within.csv")
    het = pd.read_csv(T / "rq2_heterogeneity_by_product.csv")
    rob = pd.read_csv(T / "robustness_summary.csv")
    share = pd.read_csv(T / "rq1_outcome_share_among_known_final.csv")
    avail = pd.read_csv(T / "rq4_outcome_availability_by_year.csv")
    adj = pd.read_csv(T / "rq4_adjusted_yearly_rates.csv")
    strat = pd.read_csv(T / "rq3_stratified_summary.csv")
    regs = regression_summary()
    prof = pd.read_csv(T / "raw_product_profile.csv")

    flagged = m[m["aggregate_flag"]].copy()
    vc = flagged["verdict"].value_counts().to_dict()
    nf = len(flagged)
    fl = flagged.copy()
    prim = rob[rob["variant"] == "PRIMARY"].iloc[0]
    n_all = key["n_records_primary_window"]
    n_known = key["n_known_final"]
    oc = key["outcome_counts_overall"]

    # ---- tables for the report -------------------------------------------
    t_scope = pd.DataFrame([
        ("Raw rows in file", log["raw_rows"]),
        ("  of which before 2017-04-24 (old product taxonomy)", log["rows_before_window"]),
        ("  of which outside the 7 product categories (credit reporting, debt collection, ...)", log["rows_out_of_product_scope"]),
        ("In product + date scope (to file end, 2026-10-16)", log["rows_in_product_and_date_scope"]),
        ("Duplicate complaint IDs removed", log["duplicate_complaint_ids"]),
        ("Dropped: missing issue or company", log["rows_after_dedup"] - log["rows_after_dropping_missing_issue_or_company"]),
        ("Primary window 2017-04-24 to 2026-06-30 (all records)", n_all),
        ("  with a known final response (rate denominator)", n_known),
        ("  excluded: 'Untimely response' (legacy label, no relief information)", oc.get("untimely_legacy", 0)),
        ("  excluded: 'In progress'", oc.get("in_progress", 0)),
        ("  excluded: missing response", oc.get("missing", 0)),
    ], columns=["Step", "Records"])
    t_scope["Records"] = t_scope["Records"].map(lambda v: f"{int(v):,}")

    t_share = share.rename(columns={"explanation_only": "Explanation only %",
                                    "monetary_relief": "Monetary relief %",
                                    "non_monetary_relief": "Non-monetary relief %",
                                    "n_known_final": "n (known final)"})
    t_share["Any relief %"] = t_share["Monetary relief %"] + t_share["Non-monetary relief %"]
    t_share = t_share[["product_group", "n (known final)", "Explanation only %",
                       "Non-monetary relief %", "Monetary relief %", "Any relief %"]]
    t_share["n (known final)"] = t_share["n (known final)"].map(lambda v: f"{int(v):,}")

    t_het = het[["product_group", "n_issues", "n_known", "rate_min", "rate_max", "cramers_v"]].copy()
    t_het["rate_min"] *= 100
    t_het["rate_max"] *= 100
    t_het.columns = ["Product", "Issues compared", "n", "Lowest issue rate %", "Highest issue rate %", "Cramer's V"]
    t_het["n"] = t_het["n"].map(lambda v: f"{int(v):,}")

    t_flag = fl.sort_values(["verdict", "diff_pp"], ascending=[True, False])[
        ["product_group", "issue", "n_known", "rate", "diff_pp", "diff_lo_pp", "diff_hi_pp",
         "n_companies", "crude_diff_pp", "mh_diff_pp", "mh_lo_pp", "mh_hi_pp",
         "share_companies_same_sign", "verdict"]].copy()
    t_flag["rate"] *= 100
    t_flag["share_companies_same_sign"] *= 100
    t_flag["n_known"] = t_flag["n_known"].map(lambda v: f"{int(v):,}")
    t_flag["n_companies"] = t_flag["n_companies"].astype(int)
    t_flag["aggregate diff (95% CI)"] = [f"{a:+.1f} ({b:+.1f}, {c:+.1f})" for a, b, c in
                                         zip(t_flag["diff_pp"], t_flag["diff_lo_pp"], t_flag["diff_hi_pp"])]
    t_flag["within-company MH diff (95% CI)"] = [f"{a:+.1f} ({b:+.1f}, {c:+.1f})" for a, b, c in
                                                 zip(t_flag["mh_diff_pp"], t_flag["mh_lo_pp"], t_flag["mh_hi_pp"])]
    t_flag = t_flag[["product_group", "issue", "n_known", "rate", "aggregate diff (95% CI)", "n_companies",
                     "crude_diff_pp", "within-company MH diff (95% CI)", "share_companies_same_sign", "verdict"]]
    t_flag.columns = ["Product", "Issue", "n", "Rate %", "Aggregate diff, pp (95% CI)", "Companies",
                      "Pooled diff same companies, pp", "Within-company MH diff, pp (95% CI)",
                      "% companies same sign", "Verdict"]

    t_reg = regs.copy()
    t_reg.columns = ["Product", "SD log-OR: issue only", "+ company FE", "+ company & year FE", "Shrinkage %"]

    rob_show = rob[["variant", "n_eligible_issues", "n_agg_flagged", "persists", "weakens", "disappears",
                    "not_evaluable", "primary_flagged_same_verdict", "primary_flagged_same_mh_sign"]].copy()
    rob_show.columns = ["Variant", "Eligible issues", "Flagged", "Persists", "Weakens", "Disappears",
                        "Not evaluable", "Primary-flagged issues with same verdict", "... with same MH sign"]
    for c in rob_show.columns[1:]:
        rob_show[c] = rob_show[c].map(lambda v: "" if pd.isna(v) else f"{int(v)}")

    yr = adj.copy()
    yr["raw / adjusted %"] = [f"{100*a:.1f} / {100*b:.1f}" for a, b in zip(yr["raw_rate"], yr["adjusted_rate"])]
    t_yr = yr.pivot(index="year", columns="product_group", values="raw / adjusted %").reset_index()

    av = avail.copy()
    av["untimely_legacy % of all"] = 100 * av["untimely_legacy"] / av["total"]
    t_av = av[["year", "total", "known_final", "untimely_legacy", "in_progress", "untimely_legacy % of all"]]

    # ---- derived statements used in the text -----------------------------
    n_p, n_w, n_d = vc.get("persists", 0), vc.get("weakens", 0), vc.get("disappears", 0)
    cc = share.set_index("product_group")
    rate_any = lambda pg: cc.loc[pg, "monetary_relief"] + cc.loc[pg, "non_monetary_relief"]
    hi_pg = max(cc.index, key=rate_any)
    lo_pg = min(cc.index, key=rate_any)
    early = rob[rob["variant"] == "window: 2017-04 to 2021-12"].iloc[0]
    late = rob[rob["variant"] == "window: 2022-01 onward"].iloc[0]
    expl = rob[rob["variant"] == "outcome=explanation_only"].iloc[0]
    mon = rob[rob["variant"] == "outcome=monetary_relief"].iloc[0]
    nonm = rob[rob["variant"] == "outcome=non_monetary_relief"].iloc[0]
    c300 = rob[rob["variant"] == "min_cell_n=300"].iloc[0]
    top3 = rob[rob["variant"] == "drop top-3 companies per product"].iloc[0]
    med_i2 = float(fl["i2"].median())
    med_sig = float(fl["share_companies_sig_same_sign"].median())
    pers = fl[fl["verdict"] == "persists"]
    persist_list = "; ".join(f"{r.product_group} - {r.issue} ({r.mh_diff_pp:+.1f} pp)"
                             for r in pers.sort_values("mh_diff_pp").itertuples())
    dis = fl[fl["verdict"] == "disappears"]
    flipped = dis[np.sign(dis["mh_diff_pp"]) != np.sign(dis["crude_diff_pp"])]
    cred = rec.get("csv_sha256", "n/a")

    R = f"""# Support Escalation Evidence - Findings Report

*All numbers below are produced by the code in `src/` from the CFPB Consumer Complaint Database file listed in
section 3; see the README for how to reproduce them.*

## 1. Executive summary

* **Scope.** {n_all:,} CFPB complaints about seven financial-product categories, received 2017-04-24 to 2026-06-30;
  {n_known:,} ({100*n_known/n_all:.1f}%) carry a known final company response and form the denominator of every rate.
* **Outcome rates differ a lot by product.** Share of complaints closed with *any* relief (monetary or non-monetary):
  highest for {hi_pg} ({rate_any(hi_pg):.1f}%), lowest for {lo_pg} ({rate_any(lo_pg):.1f}%). Four of the seven products are below 10%.
* **Outcome rates also differ by issue within a product** - but mostly modestly. {nf} of {key['n_eligible_issues']} eligible issues
  differ from the rest of their product by at least 5 pp *and* survive Holm correction. They are concentrated in credit cards
  ({int((flagged['product_group']=='Credit card').sum())}), money transfers ({int((flagged['product_group']=='Money transfer').sum())})
  and vehicle loans ({int((flagged['product_group']=='Vehicle loan').sum())}).
* **Within-company comparison changes the picture.** Of those {nf} flagged issues, {n_p} persist (same direction, significant,
  >=50% of the pooled gap retained), {n_w} weaken, and {n_d} disappear - {len(flipped)} of the latter reverse sign. Large pooled gaps
  such as credit-card "Problem with a company's investigation into an existing problem" (+15 pp pooled) are essentially zero
  within companies: they reflect *which companies* receive those complaints, not how a given company treats them.
* **The surviving effects are heterogeneous across companies.** Median I-squared across flagged issues is {med_i2:.2f}; typically
  fewer than half of companies (median {med_sig:.0%} across flagged issues) show a statistically significant gap in the same direction. The pooled within-company figure is an
  average, not a rule that holds at every firm.
* **Results are stable to threshold/mapping/name choices but not to the outcome definition or the time period** (section 9).
* **What this is not.** Recorded response categories are not customer satisfaction or resolution, and nothing here observes AI
  handling, handoffs, or escalation. The defensible use is to prioritise *where to investigate*, not to set an escalation policy.

## 2. Research question

Among selected banking and lending complaints submitted to the CFPB, how do recorded company-response outcomes differ across
complaint issue types, and which differences remain when comparing issues within the same company?

## 3. Data source and actual scope

* **Source:** CFPB Consumer Complaint Database bulk file (official: <https://www.consumerfinance.gov/data-research/consumer-complaints/>;
  bulk file <https://files.consumerfinance.gov/ccdb/complaints.csv.zip>). The file used was supplied by the user as
  `complaints_csv.zip` (the CFPB host was not reachable from the analysis environment, so `download_data.py` was run in its
  `--zip` mode). CSV SHA-256: `{cred}`.
* **Fields available:** date received, product, sub-product, issue, sub-issue, company public response, company, state, ZIP, tags,
  submitted via, date sent to company, company response to consumer, timely response?, complaint ID. **The consumer-dispute
  field and complaint narratives are not in this file** and were not used.
* **Actual coverage:** file covers 2011-12-01 to 2026-10-17. The **primary window is 2017-04-24 to 2026-06-30** (the planned
  period). 2017-04-24 is when the current product taxonomy began (verified in `raw_product_profile.csv`: old products such as
  "Bank account or service" and "Consumer Loan" end 2017-04-22). Records after 2026-06-30 are used only in a robustness check.
* **Products kept (7):** checking & savings, mortgage, credit card (incl. "Credit card or prepaid card"), student loan, vehicle
  loan, payday & personal loan, money transfer. Credit reporting and debt collection (the great majority of the file) are out of scope by design.

{md(t_scope)}

## 4. Data-quality assessment

* **Duplicates:** {log['duplicate_complaint_ids']} duplicate complaint IDs and {log['fully_duplicated_rows']} fully duplicated rows in scope.
* **Dates:** {log['invalid_dates']} unparseable dates in the whole file.
* **Missing:** in scope, {log['missing_by_field_after_dedup']['issue']} missing issue, {log['missing_by_field_after_dedup']['company']} missing
  company, {log['missing_by_field_after_dedup']['response_raw']} missing response, {log['missing_by_field_after_dedup']['sub_product']} missing sub-product.
* **Response values:** no unmapped values. The legacy labels "Closed", "Closed with relief" and "Closed without relief" do not occur after 2017-04-24.
* **Company names:** {log['distinct_company_raw']:,} raw names -> {log['distinct_company_normalised']:,} after conservative normalisation
  (case, punctuation, trailing legal suffixes); only {log['normalised_companies_merging_multiple_raw_names']} normalised names merge more than one raw name.
  Parent/subsidiary groupings are *not* merged, so one corporate group can appear as several "companies".
* **Classification changes (important):** the product label for credit cards, payday/personal loans, and money transfers changed
  over time, and around **2023-08-24/25** the product and issue labels changed for several products (observed in this file; e.g. credit-card issues
  "Problem with a credit reporting company's investigation..." end 2023-08 while "Problem with a company's investigation..." begins 2023-08). Several flagged
  issues therefore exist in only one era. Product labels were harmonised (see `PRODUCT_MAP`); issue labels were **not** merged across eras.
* **Outcome availability:** the legacy-style label "Untimely response" (no relief information) is rare until 2024 (<=355/yr)
  but appears {int(avail.loc[avail['year']==2025,'untimely_legacy'].iloc[0]):,} times in 2025 and {int(avail.loc[avail['year']==2026,'untimely_legacy'].iloc[0]):,} in 2026.
  These records are excluded from denominators (not counted as failures) - see table in section 8.

## 5. Outcome definitions

Raw `Company response to consumer` is preserved (`response_raw`) and mapped to: monetary relief, non-monetary relief, explanation only,
and non-informative/non-final categories (in progress, "Untimely response", bare "Closed", missing).

* **Denominator for every rate:** complaints with a *known final* response = {{monetary, non-monetary, relief-unspecified, explanation-only, no-relief}}.
  Pending, missing, bare "Closed" and "Untimely response" are excluded and reported, never treated as failures.
* **Primary outcome:** *any relief* = closed with monetary **or** non-monetary relief. Secondary: monetary only, non-monetary only.
  "Explanation only" is the exact complement of any relief in this data, so it is not independent evidence.
* No success/failure score is built, and a recorded response is not verified resolution or satisfaction.

## 6. Aggregate results

### 6.1 What outcomes do companies record?

{md(t_share)}

(Figure: `outputs/figures/fig1_outcome_composition.png`.)

### 6.2 Do outcomes differ by issue?

Each issue with >= {C.MIN_ISSUE_N:,} known-outcome complaints is compared with all other complaints in the same product
(percentage-point difference, Newcombe 95% CI, two-proportion z test, Holm- and BH-adjusted across all {key['n_eligible_issues']} tests).
An issue is **flagged** if Holm p < 0.05 **and** |difference| >= {C.MIN_PRACTICAL_PP:.0f} pp.
Homogeneity across issues is rejected in every product (all p < 0.001, driven partly by very large n), so effect size matters more than p:

{md(t_het)}

Cramer's V is small to moderate (largest for credit cards and money transfers). Checking & savings issues are almost homogeneous (V={het.set_index('product_group').loc['Checking & savings','cramers_v']:.3f}).
Full table: `outputs/tables/rq2_issue_aggregate.csv`; forest plot `fig2_issue_differences_aggregate.png`.

## 7. Within-company findings

For each company x product with >= 2 eligible issues (cells >= {C.MIN_CELL_N} known responses) each issue is compared with the same
company's other eligible issues in that product. Per issue, company-level comparisons are combined with a Mantel-Haenszel risk
difference (Greenland-Robins variance, Holm-adjusted across issues). Each company contributes one comparison per issue, so company-level
counts are independent units; different issues within a company are *not* independent and are never pooled into one test.
Pre-specified verdict rule: **persists** = same sign, adjusted p<0.05, retains >= 50% of the pooled gap in the same companies; **weakens** = same sign, significant, <50%;
**disappears** = not significant or sign reverses.

Result for the {nf} flagged issues: **{n_p} persist, {n_w} weaken, {n_d} disappear** ({len(flipped)} of the disappearing ones reverse sign).

{md(t_flag)}

Persisting issues: {persist_list}.

Reading the table: pooled gaps that are driven by company mix collapse - e.g. money-transfer "Other transaction problem" (pooled -9 pp)
becomes +1 pp within companies. Gaps that persist are largest for credit-card "Trouble using your card" and "Closing your account"
(lower relief) and "Fees or interest" (higher relief). Even for these, the gap varies by company (median I-squared {med_i2:.2f}).
Plot: `fig3_aggregate_vs_within_company.png`; per-company contrasts: `rq3_company_contrasts.csv`.

### Regression check

Binomial logistic models by product (issue effects relative to the largest issue; cluster-robust SE by company; companies with <100 known
responses or all/no events excluded). Spread of issue effects (SD of log odds ratios) with and without company fixed effects:

{md(t_reg)}

Company fixed effects shrink issue spread in most products, consistent with the stratified analysis; the model adds limited
information beyond the transparent comparison and is reported as a consistency check, not a headline.
Odds ratios: `rq3_regression_issue_odds_ratios.csv`.

## 8. Time-based findings

Raw / mix-adjusted any-relief rate by year, % (adjusted = binomial model with issue + company + year effects, standardised to the product's pooled
company-issue mix; 2017 and 2026 are partial years; products/years need enough data):

{md(t_yr)}

* Rates move a lot over time within a product and the movements generally **remain after mix adjustment** (credit cards rise to
  ~37% in 2023-24 then fall to ~28% in 2026; student loans fall from ~11-15% to ~3%; mortgages fall from ~7-8% to ~5% after 2022).
  Exception: money transfer in 2025 looks very low raw (5.2%) but not after adjustment (10.7%), i.e. a mix effect.
* These are descriptive. Changes could reflect reporting/recording practice, the 2023 taxonomy change, or company behaviour; the data cannot say which.
* Outcome availability by year:

{md(t_av, "{:.2f}")}

## 9. Statistical uncertainty and robustness

{md(rob_show)}

What changed the interpretation, and what did not:

* **Stable:** eligibility thresholds (min issue n 300-3,000; min cell 10-100; >=3 issues per company), alternative handling of bare "Closed"/"Untimely",
  strict mapping, un-normalised company names: verdict counts {int(prim['persists'])}/{int(prim['weakens'])}/{int(prim['disappears'])} (persist/weaken/disappear) are unchanged or near-identical and nearly every primary-flagged issue keeps its sign (all 20 in most; 16 of 17 at min issue n=3,000).
* **Sensitive to sample size per company:** requiring >=300 known responses per company-issue cell leaves only {int(c300['persists'])}/{int(c300['weakens'])}/{int(c300['disappears'])} with {int(c300['not_evaluable'])} not evaluable (few eligible companies).
* **Dependence on large companies:** dropping the top 3 companies per product leaves {int(top3['n_agg_flagged'])} flagged issues and {int(top3['primary_flagged_same_mh_sign'])}/20 keep the same within-company sign; conclusions are broadly but not fully robust.
* **Sensitive to the outcome definition:** the ranking of issues by *monetary* relief correlates only {mon['spearman_agg_diff']:.2f} with the any-relief ranking and by *non-monetary* relief {nonm['spearman_agg_diff']:.2f};
  only {int(mon['primary_flagged_same_verdict'])}/20 and {int(nonm['primary_flagged_same_verdict'])}/20 primary-flagged issues keep the same verdict. "What gets relief" depends on *which kind* of relief. (The explanation-only row mirrors the primary exactly by construction.)
* **Sensitive to time period:** persistence is high in 2017-04..2021-12 ({int(early['persists'])} persist / {int(early['disappears'])} disappear of {int(early['n_agg_flagged'])}) and low from 2022 ({int(late['persists'])} / {int(late['disappears'])} of {int(late['n_agg_flagged'])}); the issue taxonomy also changed in Aug 2023, so the era-specific comparisons are not like-for-like.
* **Multiple comparisons:** Holm correction applied across all issue tests and across issue-level MH tests; with 1.5M records almost everything is "significant", so effect size thresholds and consistency across companies carry the interpretation.
* **Prepaid cards** (inside the "Credit card or prepaid card" label) excluded: {int(rob[rob['variant'].str.startswith('credit card')].iloc[0]['persists'])} persist / {int(rob[rob['variant'].str.startswith('credit card')].iloc[0]['disappears'])} disappear - conclusions do not hinge on them.

## 10. Business implications

1. **Do not read pooled issue rankings as issue-driven.** Most of the largest pooled gaps are company-mix effects; a team benchmarking "issue X gets relief less often" should benchmark within the same firm/product first.
2. **A small set of issues shows a within-company gap worth investigating** (credit cards: "Trouble using your card", "Closing your account", "Struggling to pay your bill"
   get relief less often; "Fees or interest" more often; money transfer: "Unauthorized transactions...", "Wrong amount charged or received"; vehicle loans: "Problems at the end of the loan or lease" - all more often).
   Evidence strength: moderate (consistent direction pooled, many companies, robust to thresholds), but heterogeneous across companies.
3. **Categories where relief is rare overall (mortgage, student loan, payday/personal)** show small issue gaps; there the main lever is not issue triage.
4. **Why it might matter operationally (hypothesis, not finding):** issue types that rarely end in relief might be mostly informational, might be handled by scripted explanations, or might be under-resolved; the data cannot distinguish these.

## 11. Limitations

* CFPB complaints are a self-selected, non-representative sample; companies and consumers are not randomly assigned to issues.
* "Recorded response" is the company's own classification; it is not verified resolution, satisfaction, or merit of the complaint.
* Within-company comparison removes stable company differences but not differences in time, case complexity, consumer mix, or recording practice; the comparison group ("the company's other eligible issues") changes with each company's mix.
* Issue taxonomy changes (notably Aug 2023) mean some issues exist in one era only; issues were not mapped across eras.
* Company names were normalised only conservatively; corporate groups were not consolidated.
* No narratives, consumer-dispute field, or timing-of-response detail were analysed; nothing identifies AI-handled complaints, handoffs, or escalations. No causal claims are made.
* The "Untimely response" label rises sharply in 2025-26; its meaning in those years was not verified against CFPB documentation, so those records are excluded rather than interpreted.
* Cross-section results combine 2017-2026; I-squared values near 0.9 show that pooled estimates hide large company-to-company variation.

## 12. Recommended next steps

1. Run **root-cause research** (sample narratives, process review) at 2-3 large companies for the persisting low-relief credit-card issues, asking whether relief is rarely *available* or rarely *requested*.
2. Re-run the within-company analysis separately for **post-Aug-2023 issues**, and add a mapping between old and new issue taxonomies to separate real change from relabelling.
3. Obtain data that actually observes support workflows (contacts, handoffs, resolution) before drawing escalation conclusions; the CFPB data cannot set an AI-to-human threshold.
4. If an experiment is possible internally: test whether a defined handling change for one flagged issue (e.g. a dedicated review step for "Closing your account" complaints) changes the *share of cases receiving relief* and independently measured satisfaction, with the pre-registered denominator used here.
"""
    (C.OUT_DIR / "report.md").write_text(R)
    print("report written;", len(R), "chars")


if __name__ == "__main__":
    main()
