# Validation Status

This file records the checks performed on the analysis and the results that were verified.

| Check | Result | Evidence |
|---|---|---|
| Full pipeline run | Completed in a previous run | `outputs/run_manifest.json` |
| Record counts and denominators | Verified independently | `outputs/tables/reconciliation.csv` |
| Statistical calculations, including confidence intervals and adjusted p-values | 22/22 checks passed | `outputs/tables/reconciliation.csv` |
| Mantel–Haenszel estimates | Point estimates checked independently; confidence intervals tested by simulation | `outputs/tables/reconciliation.csv`, `tests/test_analysis.py` |
| Crude logistic odds ratios | Checked against closed-form calculations | `outputs/tables/reconciliation.csv` |
| Company and year fixed-effects regressions | Partially checked; no independent second implementation | Statsmodels GLM with cluster-robust standard errors |
| Unit tests | 30 passed | `outputs/test_results.txt` |
| Missing values, duplicates, boundary cases, sparse cells and malformed inputs | Covered by tests | `tests/test_analysis.py` |
| January 2025 complaint surge | Investigated; cause not established | Findings report, section 9a; `anomaly_*.csv` |
| August 2023 taxonomy change | Investigated | Findings report, section 9a; `taxonomy_issue_spans.csv` |
| Fresh-environment reproduction | Outputs matched the original run | `outputs/reproduction_check.txt` |
| Direct CFPB download | Not tested successfully; host was unreachable | — |

## Notes

- The regression results have not been independently reproduced using a second implementation.
- The reason for the January 2025 complaint surge and the meaning of the 2025 “Untimely response” label remain unresolved.
- The analysis uses company-reported complaint outcomes. These do not establish customer satisfaction or independently verified resolution.
- The fresh-environment check passed, but the direct-download step still needs testing.

For setup and execution instructions, see `README.md`.