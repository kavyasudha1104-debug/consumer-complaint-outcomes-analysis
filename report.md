# Consumer Finance Complaint Outcomes: Findings Report

*All numbers below are produced by the code in `src/` from the CFPB Consumer Complaint Database file listed in section 3; see the README for how to reproduce them.*

## 1. Executive summary

- **Scope.** 1,493,277 CFPB complaints about seven financial-product categories, received 2017-04-24 to 2026-06-30; 1,482,724 (99.3%) carry a known final company response and form the denominator of every rate.
- **Outcome rates differ a lot by product.** Share of complaints closed with *any* relief (monetary or non-monetary): highest for Credit card (31.9%), lowest for Mortgage (6.0%). Four of the seven products are below 10%.
- **Outcome rates also differ by issue within a product** - but mostly modestly. 20 of 69 eligible issues differ from the rest of their product by at least 5 percentage points and survive Holm correction. They are concentrated in credit cards (12), money transfers (7) and vehicle loans (1).
- **Within-company comparison changes the picture.** Of those 20 flagged issues, 8 persist (same direction, significant, at least 50% of the pooled gap retained), 3 weaken, and 9 disappear - 9 of the latter reverse sign. Large pooled gaps such as credit-card "Problem with a company's investigation into an existing problem" (+15 percentage points pooled) are essentially zero within companies: they reflect *which companies* receive those complaints, not how a given company treats them.
- **The surviving effects are heterogeneous across companies.** Median I-squared across flagged issues is 0.96; typically fewer than half of companies (median 23% across flagged issues) show a statistically significant gap in the same direction. The pooled within-company figure is an average, not a rule that holds at every firm.
- **Robustness (sections 9, 9a):** stable to eligibility thresholds, mapping, company-name choices, the January 2025 surge and the August 2023 taxonomy change for a core set of issues (four credit-card issues, plus money-transfer and vehicle-loan issues with smaller effects); *not* stable to the outcome definition (monetary vs non-monetary relief rank issues differently).
- **What this is not.** Recorded response categories are not customer satisfaction or resolution, and nothing here observes AI handling, handoffs, or escalation. The defensible use is to prioritise *where to investigate*, not to set an escalation policy.

## 2. Research question

Among selected banking and lending complaints submitted to the CFPB, how do recorded company-response outcomes differ across complaint issue types, and which differences remain when comparing issues within the same company?

## 3. Data source and actual scope

- **Source:** CFPB Consumer Complaint Database bulk file (official: https://www.consumerfinance.gov/data-research/consumer-complaints/; bulk file https://files.consumerfinance.gov/ccdb/complaints.csv.zip). The file used was supplied as `complaints_csv.zip` (the CFPB host was not reachable from the analysis environment, so `download_data.py` was run in its `--zip` mode). CSV SHA-256: `784cf32122368a5a83bafdbc2d43d57b8976064e361dc4ff9f614252bb45256c`.
- **Fields available:** date received, product, sub-product, issue, sub-issue, company public response, company, state, ZIP, tags, submitted via, date sent to company, company response to consumer, timely response?, complaint ID. **The consumer-dispute field and complaint narratives are not in this file** and were not used.
- **Actual coverage:** file covers 2011-12-01 to 2026-10-17. The **primary window is 2017-04-24 to 2026-06-30** (the planned period). 2017-04-24 is when the current product taxonomy began (verified in `raw_product_profile.csv`: old products such as "Bank account or service" and "Consumer Loan" end 2017-04-22). Records after 2026-06-30 are used only in a robustness check.
- **Products kept (7):** checking & savings, mortgage, credit card (including "Credit card or prepaid card"), student loan, vehicle loan, payday & personal loan, money transfer. Credit reporting and debt collection (the great majority of the file) are out of scope by design.

| Step | Records |
|---|---:|
| Raw rows in file | 18,486,121 |
| Of which before 2017-04-24 (old product taxonomy) | 767,873 |
| Of which outside the 7 product categories (credit reporting, debt collection, ...) | 16,133,988 |
| In product + date scope (to file end, 2026-10-16) | 1,584,260 |
| Duplicate complaint IDs removed | 0 |
| Dropped: missing issue or company | 5 |
| Primary window 2017-04-24 to 2026-06-30 (all records) | 1,493,277 |
| With a known final response (rate denominator) | 1,482,724 |
| Excluded: "Untimely response" (legacy label, no relief information) | 10,306 |
| Excluded: "In progress" | 246 |
| Excluded: missing response | 1 |

## 4. Data-quality assessment

- **Duplicates:** 0 duplicate complaint IDs and 0 fully duplicated rows in scope.
- **Dates:** 0 unparseable dates in the whole file.
- **Missing:** in scope, 5 missing issue, 0 missing company, 1 missing response, 136 missing sub-product.
- **Response values:** no unmapped values. The legacy labels "Closed", "Closed with relief" and "Closed without relief" do not occur after 2017-04-24.
- **Company names:** 4,964 raw names → 4,948 after conservative normalisation (case, punctuation, trailing legal suffixes); only 16 normalised names merge more than one raw name. Parent/subsidiary groupings are *not* merged, so one corporate group can appear as several "companies".
- **Classification changes (important):** the product label for credit cards, payday/personal loans, and money transfers changed over time, and around **2023-08-24/25** the product and issue labels changed for several products (observed in this file; e.g. credit-card issues "Problem with a credit reporting company's investigation..." end 2023-08 while "Problem with a company's investigation..." begins 2023-08). Several flagged issues therefore exist in only one era. Product labels were harmonised (see `PRODUCT_MAP`); issue labels were **not** merged across eras.
- **Outcome availability:** the legacy-style label "Untimely response" (no relief information) is rare until 2024 (at most 355 per year) but appears 3,988 times in 2025 and 4,234 in 2026. These records are excluded from denominators (not counted as failures) - see table in section 8.

## 5. Outcome definitions

Raw `Company response to consumer` is preserved (`response_raw`) and mapped to: monetary relief, non-monetary relief, explanation only, and non-informative/non-final categories (in progress, "Untimely response", bare "Closed", missing).

- **Denominator for every rate:** complaints with a *known final* response = monetary, non-monetary, relief-unspecified, explanation-only, or no-relief. Pending, missing, bare "Closed" and "Untimely response" are excluded and reported, never treated as failures.
- **Primary outcome:** *any relief* = closed with monetary **or** non-monetary relief. Secondary: monetary only, non-monetary only. "Explanation only" is the exact complement of any relief in this data, so it is not independent evidence.
- No success/failure score is built, and a recorded response is not verified resolution or satisfaction.

## 6. Aggregate results

### 6.1 What outcomes do companies record?

| Product group | n (known final) | Explanation only % | Non-monetary relief % | Monetary relief % | Any relief % |
|---|---:|---:|---:|---:|---:|
| Checking & savings | 378,557 | 79.8 | 5.2 | 15.0 | 20.2 |
| Credit card | 442,644 | 68.1 | 16.5 | 15.4 | 31.9 |
| Money transfer | 183,567 | 90.4 | 3.6 | 6.0 | 9.6 |
| Mortgage | 226,505 | 94.0 | 3.2 | 2.9 | 6.0 |
| Payday & personal loan | 63,708 | 91.3 | 4.4 | 4.2 | 8.7 |
| Student loan | 89,921 | 93.8 | 5.0 | 1.2 | 6.2 |
| Vehicle loan | 97,822 | 90.5 | 6.5 | 3.0 | 9.5 |

Figure: `outputs/figures/fig1_outcome_composition.png`.

### 6.2 Do outcomes differ by issue?

Each issue with at least 1,000 known-outcome complaints is compared with all other complaints in the same product (percentage-point difference, Newcombe 95% CI, two-proportion z test, Holm- and BH-adjusted across all 69 tests). An issue is **flagged** if Holm p < 0.05 **and** the absolute difference is at least 5 percentage points.

Homogeneity across issues is rejected in every product (all p < 0.001, driven partly by very large sample sizes), so effect size matters more than p:

| Product | Issues compared | n | Lowest issue rate % | Highest issue rate % | Cramer's V |
|---|---:|---:|---:|---:|---:|
| Checking & savings | 6 | 377,252 | 17.0 | 22.0 | 0.0 |
| Credit card | 17 | 440,772 | 15.0 | 48.1 | 0.2 |
| Money transfer | 13 | 181,834 | 4.4 | 17.2 | 0.2 |
| Mortgage | 7 | 225,377 | 3.1 | 9.6 | 0.1 |
| Payday & personal loan | 10 | 55,509 | 5.8 | 11.6 | 0.1 |
| Student loan | 7 | 89,030 | 2.6 | 8.0 | 0.1 |
| Vehicle loan | 9 | 97,261 | 5.8 | 14.8 | 0.1 |

Cramer's V is small to moderate (largest for credit cards and money transfers). Checking & savings issues are almost homogeneous (V=0.016).

Full table: `outputs/tables/rq2_issue_aggregate.csv`; forest plot: `fig2_issue_differences_aggregate.png`.

## 7. Within-company findings

For each company × product with at least two eligible issues (cells with at least 30 known responses), each issue is compared with the same company's other eligible issues in that product. Per issue, company-level comparisons are combined with a Mantel-Haenszel risk difference (Greenland-Robins variance, Holm-adjusted across issues). Each company contributes one comparison per issue, so company-level counts are independent units; different issues within a company are *not* independent and are never pooled into one test.

Pre-specified verdict rule: **persists** = same sign, adjusted p < 0.05, retains at least 50% of the pooled gap in the same companies; **weakens** = same sign, significant, less than 50%; **disappears** = not significant or sign reverses.

Result for the 20 flagged issues: **8 persist, 3 weaken, 9 disappear** (9 of the disappearing ones reverse sign).

| Product | Issue | n | Rate % | Aggregate diff, pp (95% CI) | Companies | Pooled diff same companies, pp | Within-company MH diff, pp (95% CI) | % companies same sign | Verdict |
|---|---|---:|---:|---|---:|---:|---|---:|---|
| Credit card | Problem with a company's investigation into an existing problem | 26,063 | 48.1 | +17.2 (+16.6, +17.8) | 22 | 15.4 | -1.2 (-1.8, -0.6) | 40.9 | disappears |
| Credit card | Incorrect information on your report | 38,988 | 39.8 | +8.7 (+8.2, +9.2) | 44 | 8.0 | -0.8 (-1.3, -0.3) | 31.8 | disappears |
| Credit card | Problem with a credit reporting company's investigation into an existing problem | 7,231 | 40.4 | +8.6 (+7.5, +9.8) | 18 | 7.3 | -3.2 (-4.2, -2.3) | 22.2 | disappears |
| Money transfer | Trouble accessing funds in your mobile or digital wallet | 6,885 | 16.2 | +6.9 (+6.0, +7.8) | 14 | 8.5 | -0.0 (-0.9, +0.8) | 35.7 | disappears |
| Money transfer | Managing, opening, or closing your mobile wallet account | 11,724 | 14.5 | +5.3 (+4.6, +6.0) | 16 | 6.7 | -8.9 (-9.6, -8.2) | 12.5 | disappears |
| Credit card | Unexpected or other fees | 2,880 | 26.8 | -5.1 (-6.7, -3.4) | 16 | -2.8 | +2.0 (+0.3, +3.7) | 43.8 | disappears |
| Credit card | Problem with a purchase or transfer | 6,278 | 26.7 | -5.3 (-6.4, -4.2) | 23 | -3.6 | +2.3 (+1.2, +3.5) | 43.5 | disappears |
| Credit card | Problem getting a card or closing an account | 4,543 | 26.5 | -5.5 (-6.7, -4.2) | 19 | -3.3 | +2.9 (+1.6, +4.3) | 63.2 | disappears |
| Money transfer | Other transaction problem | 70,438 | 4.4 | -8.4 (-8.7, -8.2) | 52 | -9.0 | +1.1 (+0.8, +1.4) | 30.8 | disappears |
| Money transfer | Wrong amount charged or received | 1,771 | 17.2 | +7.7 (+6.0, +9.5) | 11 | 9.4 | +6.0 (+3.9, +8.1) | 63.6 | persists |
| Money transfer | Unauthorized transactions or other transaction problem | 16,678 | 16.4 | +7.5 (+6.9, +8.1) | 28 | 7.7 | +4.1 (+3.6, +4.7) | 60.7 | persists |
| Credit card | Fees or interest | 41,233 | 38.6 | +7.4 (+6.9, +7.9) | 49 | 7.8 | +8.3 (+7.8, +8.8) | 77.6 | persists |
| Vehicle loan | Problems at the end of the loan or lease | 16,029 | 14.8 | +6.4 (+5.8, +7.0) | 51 | 7.3 | +5.9 (+5.3, +6.5) | 74.5 | persists |
| Credit card | Improper use of your report | 3,692 | 26.6 | -5.3 (-6.8, -3.9) | 21 | -5.7 | -3.3 (-4.8, -1.7) | 57.1 | persists |
| Credit card | Struggling to pay your bill | 6,661 | 20.1 | -12.0 (-12.9, -11.0) | 23 | -10.0 | -8.9 (-10.0, -7.9) | 87.0 | persists |
| Credit card | Closing your account | 28,774 | 19.6 | -13.1 (-13.6, -12.7) | 48 | -14.2 | -10.9 (-11.4, -10.4) | 75.0 | persists |
| Credit card | Trouble using your card | 15,684 | 15.0 | -17.5 (-18.1, -17.0) | 41 | -15.7 | -15.0 (-15.6, -14.4) | 82.9 | persists |
| Money transfer | Unexpected or other fees | 2,643 | 16.4 | +6.9 (+5.5, +8.4) | 16 | 9.3 | +3.0 (+1.4, +4.7) | 56.2 | weakens |
| Money transfer | Money was not available when promised | 12,149 | 15.0 | +5.8 (+5.2, +6.5) | 46 | 6.5 | +2.9 (+2.2, +3.6) | 60.9 | weakens |
| Credit card | Trouble using the card | 5,385 | 22.1 | -9.9 (-11.0, -8.8) | 19 | -9.5 | -3.2 (-4.4, -1.9) | 84.2 | weakens |

Persisting issues:

- Credit card — Trouble using your card (-15.0 pp)
- Credit card — Closing your account (-10.9 pp)
- Credit card — Struggling to pay your bill (-8.9 pp)
- Credit card — Improper use of your report (-3.3 pp)
- Money transfer — Unauthorized transactions or other transaction problem (+4.1 pp)
- Vehicle loan — Problems at the end of the loan or lease (+5.9 pp)
- Money transfer — Wrong amount charged or received (+6.0 pp)
- Credit card — Fees or interest (+8.3 pp)

Reading the table: pooled gaps driven by company mix collapse - for example, money-transfer "Other transaction problem" (pooled -9 pp) becomes +1 pp within companies. Gaps that persist are largest for credit-card "Trouble using your card" and "Closing your account" (lower relief) and "Fees or interest" (higher relief). Even for these, the gap varies by company (median I-squared 0.96).

Plot: `fig3_aggregate_vs_within_company.png`; per-company contrasts: `rq3_company_contrasts.csv`.

### Regression check

Binomial logistic models by product (issue effects relative to the largest issue; cluster-robust SE by company; companies with fewer than 100 known responses or all/no events excluded). Spread of issue effects (SD of log odds ratios) with and without company fixed effects:

| Product | SD log-OR: issue only | + company FE | + company & year FE | Shrinkage % |
|---|---:|---:|---:|---:|
| Checking & savings | 0.1 | 0.2 | 0.2 | -72.2 |
| Credit card | 0.4 | 0.3 | 0.3 | 25.1 |
| Money transfer | 0.4 | 0.3 | 0.3 | 18.6 |
| Mortgage | 0.3 | 0.3 | 0.3 | 21.9 |
| Payday & personal loan | 0.3 | 0.4 | 0.4 | -41.3 |
| Student loan | 0.5 | 0.4 | 0.4 | 24.5 |
| Vehicle loan | 0.3 | 0.4 | 0.4 | -13.1 |

Company fixed effects shrink issue spread in most products, consistent with the stratified analysis; the model adds limited information beyond the transparent comparison and is reported as a consistency check, not a headline.

Odds ratios: `rq3_regression_issue_odds_ratios.csv`.

## 8. Time-based findings

Raw / mix-adjusted any-relief rate by year, % (adjusted = binomial model with issue + company + year effects, standardised to the product's pooled company-issue mix; 2017 and 2026 are partial years; products/years need enough data):

| Year | Checking & savings | Credit card | Money transfer | Mortgage | Payday & personal loan | Student loan | Vehicle loan |
|---|---|---|---|---|---|---|---|
| 2017 | 28.0 / 24.6 | 28.0 / 29.6 | 13.6 / 8.3 | 6.6 / 6.2 | 12.9 / 11.0 | 8.3 / 7.9 | 13.6 / 13.9 |
| 2018 | 27.5 / 24.3 | 29.6 / 31.3 | 12.9 / 7.8 | 7.2 / 6.7 | 14.6 / 12.4 | 8.6 / 7.5 | 16.2 / 16.6 |
| 2019 | 24.9 / 22.3 | 27.7 / 29.5 | 17.0 / 10.8 | 7.0 / 7.1 | 11.3 / 9.5 | 9.4 / 7.1 | 12.5 / 13.1 |
| 2020 | 20.7 / 19.0 | 27.6 / 29.8 | 16.2 / 12.4 | 7.9 / 7.4 | 11.6 / 9.6 | 12.4 / 9.0 | 12.0 / 12.9 |
| 2021 | 21.4 / 19.7 | 28.4 / 30.7 | 19.3 / 12.8 | 8.2 / 7.8 | 11.6 / 9.9 | 16.8 / 11.0 | 9.4 / 10.4 |
| 2022 | 22.5 / 21.1 | 31.8 / 34.6 | 16.1 / 12.1 | 7.4 / 7.3 | 12.6 / 11.8 | 7.5 / 5.7 | 9.0 / 9.5 |
| 2023 | 20.9 / 20.6 | 36.7 / 36.5 | 13.5 / 10.5 | 5.0 / 5.1 | 11.0 / 10.8 | 12.7 / 14.8 | 8.5 / 8.4 |
| 2024 | 23.1 / 23.9 | 39.8 / 37.1 | 14.5 / 11.1 | 5.1 / 5.8 | 11.3 / 11.2 | 2.7 / 3.5 | 11.1 / 10.5 |
| 2025 | 16.1 / 18.3 | 34.1 / 32.4 | 5.2 / 10.7 | 4.7 / 5.2 | 7.6 / 9.1 | 2.1 / 2.5 | 9.7 / 9.4 |
| 2026 | 19.1 / 20.7 | 27.2 / 28.3 | 16.3 / 13.3 | 4.9 / 5.3 | 6.1 / 7.8 | 2.7 / 3.3 | 9.8 / 9.2 |

- Rates move a lot over time within a product and the movements generally **remain after mix adjustment** (credit cards rise to about 37% in 2023-24 then fall to about 28% in 2026; student loans fall from about 11-15% to about 3%; mortgages fall from about 7-8% to about 5% after 2022).
- Exception: money transfer in 2025 looks very low raw (5.2%) but not after adjustment (10.7%), indicating a mix effect.
- These are descriptive. Changes could reflect reporting/recording practice, the 2023 taxonomy change, or company behaviour; the data cannot say which.

Outcome availability by year:

| Year | Total | Known final | Untimely legacy | In progress | Untimely legacy % of all |
|---|---:|---:|---:|---:|---:|
| 2017 | 64,625 | 64,397 | 228 | 0 | 0.35 |
| 2018 | 94,456 | 94,115 | 341 | 0 | 0.36 |
| 2019 | 92,350 | 92,012 | 337 | 1 | 0.36 |
| 2020 | 106,629 | 106,358 | 271 | 0 | 0.25 |
| 2021 | 118,102 | 117,891 | 211 | 0 | 0.18 |
| 2022 | 136,626 | 136,473 | 153 | 0 | 0.11 |
| 2023 | 174,327 | 174,138 | 188 | 0 | 0.11 |
| 2024 | 204,047 | 203,692 | 355 | 0 | 0.17 |
| 2025 | 338,678 | 334,497 | 3,988 | 193 | 1.18 |
| 2026 | 163,437 | 159,151 | 4,234 | 52 | 2.59 |

## 9. Statistical uncertainty and robustness

| Variant | Eligible issues | Flagged | Persists | Weakens | Disappears | Not evaluable | Primary-flagged issues with same verdict | With same MH sign |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PRIMARY | 69 | 20 | 8 | 3 | 9 | 0 | - | - |
| min_issue_n=300 | 88 | 22 | 8 | 3 | 10 | 1 | 20 | 20 |
| min_issue_n=3000 | 51 | 17 | 7 | 2 | 8 | 0 | 17 | 16 |
| min_cell_n=10 | 69 | 20 | 8 | 3 | 9 | 0 | 20 | 20 |
| min_cell_n=100 | 69 | 20 | 8 | 3 | 9 | 0 | 20 | 20 |
| min_cell_n=300 | 69 | 20 | 6 | 2 | 7 | 5 | 15 | 18 |
| min_company_issues=3 | 69 | 20 | 8 | 3 | 9 | 0 | 20 | 20 |
| outcome=monetary_relief | 69 | 18 | 15 | 3 | 0 | 0 | 7 | 19 |
| outcome=non_monetary_relief | 69 | 17 | 7 | 7 | 3 | 0 | 4 | 7 |
| outcome=explanation_only | 69 | 20 | 8 | 3 | 9 | 0 | 20 | 0 |
| Mapping: bare "Closed"/"Untimely" kept in denominator as non-relief | 70 | 20 | 8 | 3 | 9 | 0 | 20 | 20 |
| Mapping: strict (drop legacy relief values) | 69 | 20 | 8 | 3 | 9 | 0 | 20 | 20 |
| Company: raw (un-normalised) names | 69 | 20 | 8 | 3 | 9 | 0 | 20 | 20 |
| Window: through file end (2026-10-17) | 70 | 17 | 7 | 3 | 7 | 0 | 17 | 19 |
| Window: 2020-01-01 onward | 63 | 20 | 9 | 1 | 10 | 0 | 18 | 19 |
| Window: 2017-04 to 2019-12 only | 37 | 13 | 11 | 0 | 2 | 0 | 5 | 10 |
| Window: 2017-04 to 2021-12 | 47 | 15 | 14 | 0 | 1 | 0 | 6 | 15 |
| Window: 2022-01 onward | 60 | 22 | 7 | 5 | 10 | 0 | 15 | 16 |
| Credit card: prepaid sub-products excluded | 69 | 17 | 9 | 2 | 6 | 0 | 16 | 20 |
| Exclude January 2025 (mass-filing surge) | 68 | 14 | 8 | 1 | 5 | 0 | 13 | 20 |
| Exclude 2025-01-15 to 2025-01-22 only | 69 | 16 | 9 | 1 | 6 | 0 | 15 | 20 |
| Exclude Aug-Sep 2023 (taxonomy transition) | 69 | 19 | 8 | 3 | 8 | 0 | 19 | 20 |
| Issues present in both taxonomy eras only | 55 | 12 | 7 | 2 | 3 | 0 | 12 | 13 |
| Drop top-1 company per product | 66 | 18 | 8 | 2 | 8 | 0 | 18 | 19 |
| Drop top-3 companies per product | 61 | 15 | 7 | 2 | 6 | 0 | 14 | 18 |

### What changed the interpretation, and what did not

- **Stable:** eligibility thresholds (minimum issue n 300-3,000; minimum cell 10-100; at least 3 issues per company), alternative handling of bare "Closed"/"Untimely", strict mapping, un-normalised company names: verdict counts 8/3/9 (persist/weaken/disappear) are unchanged or near-identical and nearly every primary-flagged issue keeps its sign (all 20 in most variants; 16 of 17 at minimum issue n=3,000).
- **Sensitive to sample size per company:** requiring at least 300 known responses per company-issue cell leaves only 6/2/7 with 5 not evaluable (few eligible companies).
- **Dependence on large companies:** dropping the top 3 companies per product leaves 15 flagged issues and 18/20 keep the same within-company sign; conclusions are broadly but not fully robust.
- **Sensitive to the outcome definition:** the ranking of issues by *monetary* relief correlates only 0.34 with the any-relief ranking and by *non-monetary* relief 0.50; only 7/20 and 4/20 primary-flagged issues keep the same verdict. "What gets relief" depends on *which kind* of relief. The explanation-only row mirrors the primary exactly by construction.
- **Time period and taxonomy (investigated in 9a):** persistence is high in 2017-04 to 2021-12 (14 persist / 1 disappear of 15) and lower from 2022 (7 / 10 of 22); section 9a shows this is driven by era-specific issue labels and the January 2025 surge, while a core set of issues is stable.
- **Multiple comparisons:** Holm correction applied across all issue tests and across issue-level MH tests; with 1.5 million records almost everything is "significant", so effect-size thresholds and consistency across companies carry the interpretation.
- **Prepaid cards** (inside the "Credit card or prepaid card" label) excluded: 9 persist / 6 disappear - conclusions do not hinge on them.

### 9a. Investigated caveats: January 2025 surge and the August 2023 taxonomy change

**January 2025.** Complaint volume was 84,637 in January 2025 versus 18,385 in December 2024 and 23,523 in February. Almost all of the excess was money transfer (48,276 above a typical month) and checking & savings (13,709), concentrated in 15-22 January:

| Company | Product | Issue | Complaints 15-22 Jan 2025 | Any-relief % |
|---|---|---|---:|---:|
| BLOCK | Money transfer | Other transaction problem | 25,273 | 0.0 |
| EARLY WARNING SERVICES | Money transfer | Other transaction problem | 13,227 | 0.0 |
| NAVY FEDERAL CREDIT UNION | Checking & savings | Problem caused by your funds being low | 5,610 | 1.3 |
| CAPITAL ONE FINANCIAL | Checking & savings | Managing an account | 4,234 | 0.4 |
| BLOCK | Money transfer | Other service problem | 685 | 0.0 |
| EARLY WARNING SERVICES | Money transfer | Fraud or scam | 613 | 0.0 |

Those records received almost exclusively explanation-only responses. Money transfer "Other transaction problem" has a 4.4% any-relief rate overall, but 0.2% in January 2025 (42,521 complaints) and 10.8% in all other months. Without January 2025 its pooled gap (aggregate difference -2.7 percentage points, no longer flagged) largely vanishes. The data show *what* happened (a one-week, two-company surge with near-zero recorded relief), not *why*; no cause is asserted here.

Effect on conclusions when January 2025 is excluded: flagged issues 20 → 14; verdicts 8 persist / 1 weaken / 5 disappear; 20/20 primary-flagged issues keep the sign of their within-company difference, 13/20 keep the same verdict (the rest lose "flagged" status because their pooled gap falls below 5 percentage points). No persisting finding is reversed. It reinforces the central insight: a large pooled gap can be produced by a few companies in a short period.

Mostly student-loan servicer records (MOHELA and a Federal Student Aid contract servicer) carrying the "Untimely response" label also rise in 2025-26 (see section 4); they are excluded from denominators.

**August 2023 taxonomy.** 96 of 129 product-issue labels appear on both sides of 2023-08-24; 16 appear only before and 17 only after.

Flagged issues by era class and verdict:

| Era | Disappears | Persists | Weakens |
|---|---:|---:|---:|
| Both eras | 6 | 8 | 3 |
| Post-August 2023 only | 2 | 0 | 0 |
| Pre-August 2023 only | 1 | 0 | 0 |

Every issue whose gap persists or weakens exists in both eras; the only single-era flagged issues all disappear within companies. Excluding August-September 2023 leaves 8/3/8 (persist/weaken/disappear) and 19/20 same verdicts; restricting to labels present in both eras leaves 12 flagged issues with 7/2/3. The taxonomy change therefore affects *which* issues can be compared, but not the persisting findings.

**Core findings across variants** (credit-card issues with persisting gaps; within-company MH difference in percentage points and verdict):

| Issue | Primary (MH pp, verdict) | Excluding Jan 2025 | 2017-04 to 2021-12 | 2022-01 onward | Drop top-3 companies |
|---|---|---|---|---|---|
| Trouble using your card | -15.0, persists | -14.9, persists | -15.6, persists | -15.0, persists | -14.6, persists |
| Closing your account | -10.9, persists | -10.9, persists | -11.4, persists | -10.8, persists | -11.4, persists |
| Struggling to pay your bill | -8.9, persists | -8.9, persists | -5.7, persists | -11.0, persists | -8.8, persists |
| Fees or interest | +8.3, persists | +8.5, persists | +12.1, persists | +6.6, persists | +8.9, persists |

## 10. Business implications

The evidence supports three conclusions; each is separated into what the data shows, what is hypothesis, the follow-up, and the metric.

### Finding A - Aggregate issue rankings mislead; benchmark within company first

- **Shows:** 9 of 20 aggregate-flagged issues disappear within companies (9 reverse sign). Credit-card "Problem with a company's investigation..." goes from +17 percentage points pooled to about -1 point; money-transfer "Other transaction problem" goes from -8 points pooled to about +1 point, and its pooled gap is mostly a one-week January 2025 surge at two companies.
- **Hypothesis:** the gaps reflect which companies receive which complaints (and when), not issue-specific handling.
- **Why it matters:** a team that triages or sets targets from a pooled issue ranking would chase company-mix artefacts.
- **Follow-up:** report every issue-level outcome gap alongside its within-company counterpart and the share retained (`retained_share`); screen out single-company or single-month bursts before ranking.
- **Metric:** share of flagged pooled gaps that survive within company (here 11/20 survive in some form); concentration of an issue's volume in its top company/month.
- **Needs more data to act:** the reason a company's volume spikes (campaign, outage, policy change) is not in this dataset.

### Finding B - Four credit-card issues have a consistently different recorded-relief rate within the same company

- **Shows:** within companies, "Trouble using your card" (-15.0 percentage points), "Closing your account" (-10.9 points) and "Struggling to pay your bill" (-8.9 points) end in relief less often than the same company's other credit-card issues, and "Fees or interest" (+8.3 points) more often. Same direction in every variant checked (table in 9a). Heterogeneity across companies is large: same sign in 75-87% of companies, individually significant in 43-59%, I-squared 0.97-0.99.
- **Hypotheses (untested):** low-relief issues are mostly informational or hardship-related and resolved by explanation; "Fees or interest" has a clearer remedy (fee reversal).
- **Follow-up:** root-cause review at 2-3 large issuers: sample complaint narratives for the three low-relief issues; classify whether relief was *requested*, *available*, or *granted*; compare with the "Fees or interest" handling path.
- **Metric:** within-company any-relief rate per issue and, with internal data, relief-granted rate among cases where relief was requested/eligible; time-to-resolution.
- **Needs more data:** narratives, internal case outcomes, relief amounts.

### Finding C - A smaller set of money-transfer and vehicle-loan issues shows a moderate persisting within-company gap

- **Shows:** money transfer "Wrong amount charged or received" (+6.0 points) and "Unauthorized transactions..." (+4.1 points), vehicle loan "Problems at the end of the loan or lease" (+5.9 points) have higher relief; these are smaller and less stable across variants (the unauthorized-transaction gap weakens in 2022 onward and when top companies are dropped).
- **Hypothesis:** transactional errors have a clear corrective action, so relief is more common.
- **Follow-up:** treat as second-priority; re-test on newer data and by company type before investing.
- **Metric:** same within-company relief gap; stability across half-years.

### What this data cannot support

It cannot support an AI-to-human escalation threshold or any claim that issue type *causes* a response. To move from these findings to a support-operations decision one needs internal case-level data: contact channel, bot/human handling and handoffs, resolution and re-contact, satisfaction, handling time/cost, and relief amounts.

## 11. Limitations

- CFPB complaints are a self-selected, non-representative sample; companies and consumers are not randomly assigned to issues.
- "Recorded response" is the company's own classification; it is not verified resolution, satisfaction, or merit of the complaint.
- Within-company comparison removes stable company differences but not differences in time, case complexity, consumer mix, or recording practice; the comparison group ("the company's other eligible issues") changes with each company's mix.
- Issue taxonomy changes (notably August 2023) mean some issues exist in one era only; issues were not mapped across eras.
- Company names were normalised only conservatively; corporate groups were not consolidated.
- No narratives, consumer-dispute field, or timing-of-response detail were analysed; nothing identifies AI-handled complaints, handoffs, or escalations. No causal claims are made.
- The "Untimely response" label rises sharply in 2025-26; its meaning in those years was not verified against CFPB documentation, so those records are excluded rather than interpreted.
- Cross-section results combine 2017-2026; a median I-squared of 0.96 shows that pooled estimates hide large company-to-company variation.

## 12. Recommended next steps

1. Run **root-cause research** (sample narratives, process review) at 2-3 large companies for the persisting low-relief credit-card issues, asking whether relief is rarely *available* or rarely *requested*.
2. Re-run the within-company analysis separately for **post-August 2023 issues**, and add a mapping between old and new issue taxonomies to separate real change from relabelling.
3. Obtain data that actually observes support workflows (contacts, handoffs, resolution) before drawing escalation conclusions; the CFPB data cannot set an AI-to-human threshold.
4. If an experiment is possible internally: test whether a defined handling change for one flagged issue (e.g. a dedicated review step for "Closing your account" complaints) changes the *share of cases receiving relief* and independently measured satisfaction, with the pre-registered denominator used here.
