# Consumer Finance Complaint Outcomes: Issue vs. Company Effects

A real-data product analytics investigation using the U.S. Consumer Financial Protection Bureau (CFPB) Consumer Complaint Database.

**Research question:** Do recorded company-response outcomes differ by complaint issue, and do those differences persist when comparing issues within the same company?

## Key findings

- Analysed 1,493,277 complaints across seven consumer-finance product groups, with 1,482,724 having a known final response.
- 20 of 69 eligible issues showed statistically significant, practically meaningful differences in aggregate comparisons.
- In within-company comparisons, 8 differences persisted, 3 weakened, and 9 disappeared.
- Several aggregate differences were consistent with company-mix effects.
- Persistent differences varied substantially across companies and were sensitive to outcome definitions and time periods.

See [`outputs/report.md`](outputs/report.md) for detailed results, figures, statistical methods, and caveats.

## Data and approach

**Source:** [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/)

The analysis covers complaints received from April 24, 2017, through June 30, 2026, across checking and savings, mortgage, credit card, student loan, vehicle loan, payday and personal loan, and money transfer products.

The primary outcome is **any recorded relief** (monetary or non-monetary), measured among complaints with a known final response.

The pipeline includes data cleaning, issue-level comparisons, confidence intervals, multiple-testing corrections, within-company Mantel–Haenszel analysis, fixed-effects logistic regression, time analysis, and 20 robustness variants.

## Product implications

Pooled averages may conceal differences in the companies receiving complaints. Within-company comparisons help identify which issue-level patterns warrant further investigation.

The results can inform follow-up research, but they do not establish why outcomes differ or justify a specific support policy.

## Reproduce

Python dependencies are listed in `requirements.txt`. Download the CFPB data ZIP and run:

```bash
pip install -r requirements.txt
python src/download_data.py --zip /path/to/complaints_csv.zip
python src/clean_data.py
python src/analyze_outcomes.py
python src/robustness_checks.py
python src/make_figures.py
python src/make_report.py
python -m pytest -q tests
```

The extracted source CSV is approximately 5.6 GB. Raw and processed data are excluded from Git.

Validation includes automated tests, reconciliation checks, and output reproducibility checks. The direct CFPB download workflow was not independently verified in the analysis environment.

## Limitations

CFPB complaints are self-selected, and company-recorded responses are not verified customer resolutions. Within-company comparisons cannot eliminate all confounding. The dataset contains no complaint narratives, chatbot interactions, human handoffs, or escalation decisions.

**This project does not measure AI escalation effectiveness or determine an optimal escalation threshold.** It investigates recorded complaint-response outcomes and the limits of aggregate comparisons.

## Validation and Reproducibility

The project includes automated tests, statistical reconciliation checks, and a fresh-environment reproduction check. The fixed-effects regressions have not been independently reproduced, and the direct-download workflow remains untested.

See [VALIDATION_STATUS.md](VALIDATION_STATUS.md) for the checks performed and the remaining limitations.