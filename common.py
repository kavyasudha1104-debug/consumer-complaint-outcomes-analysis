"""Shared constants, mappings and statistical helpers.

Everything that defines the analysis (scope, outcome mapping, eligibility
thresholds) lives here so the cleaning, analysis, robustness and test code all
use one definition.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"
OUT_DIR = ROOT / "outputs"
TABLE_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"

# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------
# 2017-04-24 is the date the CFPB introduced the current product taxonomy
# (e.g. "Checking or savings account"), so earlier records are not comparable.
WINDOW_START = pd.Timestamp("2017-04-24")
PLANNED_END = pd.Timestamp("2026-06-30")  # planned end of primary window

# raw CFPB "Product" value -> harmonised product group
PRODUCT_MAP = {
    "Checking or savings account": "Checking & savings",
    "Bank account or service": "Checking & savings",
    "Mortgage": "Mortgage",
    "Credit card": "Credit card",
    "Credit card or prepaid card": "Credit card",
    "Student loan": "Student loan",
    "Vehicle loan or lease": "Vehicle loan",
    "Payday loan, title loan, or personal loan": "Payday & personal loan",
    "Payday loan, title loan, personal loan, or advance loan": "Payday & personal loan",
    "Payday loan": "Payday & personal loan",
    "Consumer Loan": "Payday & personal loan",
    "Money transfer, virtual currency, or money service": "Money transfer",
    "Money transfers": "Money transfer",
}

# --------------------------------------------------------------------------
# Outcome mapping (raw 'Company response to consumer' -> analysis category)
# --------------------------------------------------------------------------
OUTCOME_MAP = {
    "Closed with monetary relief": "monetary_relief",
    "Closed with non-monetary relief": "non_monetary_relief",
    "Closed with relief": "relief_unspecified",   # legacy value
    "Closed with explanation": "explanation_only",
    "Closed without relief": "no_relief_legacy",    # legacy value
    "Closed": "closed_unspecified",                # legacy value
    "Untimely response": "untimely_legacy",        # legacy value
    "In progress": "in_progress",                  # not a final outcome
}
MISSING_OUTCOME = "missing"

# Final, informative outcomes: used as the denominator of every primary rate.
# 'closed_unspecified' (bare "Closed") and 'untimely_legacy' carry no
# information on relief vs. explanation, so they are excluded from rate
# denominators (and counted separately in the exclusion table).
KNOWN_FINAL = {
    "monetary_relief", "non_monetary_relief", "relief_unspecified",
    "explanation_only", "no_relief_legacy",
}
ANY_RELIEF = {"monetary_relief", "non_monetary_relief", "relief_unspecified"}

# Binary outcome definitions: name -> set of categories counted as the event.
OUTCOMES = {
    "any_relief": ANY_RELIEF,                       # PRIMARY
    "monetary_relief": {"monetary_relief"},
    "non_monetary_relief": {"non_monetary_relief"},
    "explanation_only": {"explanation_only"},
}
PRIMARY_OUTCOME = "any_relief"

# Eligibility thresholds (n = complaints with a known final outcome).
MIN_ISSUE_N = 1000          # aggregate issue groups
MIN_CELL_N = 30             # company x issue cell inside a within-company test
MIN_COMPANY_ISSUES = 2      # a company needs >=2 eligible issues in a product
ALPHA = 0.05
MIN_PRACTICAL_PP = 5.0      # "practically important" difference in pct points


# --------------------------------------------------------------------------
# Text normalisation
# --------------------------------------------------------------------------
_SUFFIX = re.compile(
    r"(?:\s+(?:INC|LLC|LP|LLP|LTD|CORP|CORPORATION|CO|COMPANY|NA|N A|PLC|INCORPORATED|LIMITED|AND))+$"
)


def normalize_company(name: object) -> str | None:
    """Conservative company-name standardisation.

    Upper-case, strip punctuation, collapse whitespace, drop trailing legal
    suffixes (INC, LLC, N.A., ...). Does NOT merge different brands or parents.
    """
    if name is None or (isinstance(name, float) and math.isnan(name)):
        return None
    s = str(name).upper().replace("&", " AND ")
    s = re.sub(r"[.,'\"]", "", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _SUFFIX.sub("", s).strip()
    return s or None


def map_outcome(raw: object) -> str:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return MISSING_OUTCOME
    return OUTCOME_MAP.get(str(raw).strip(), "unmapped_" + str(raw).strip())


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------
def wilson_ci(k: float, n: float, alpha: float = ALPHA) -> tuple[float, float]:
    """Wilson score interval for a single proportion."""
    if n <= 0:
        return (float("nan"), float("nan"))
    z = stats.norm.ppf(1 - alpha / 2)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_diff_ci(k1: float, n1: float, k2: float, n2: float,
                     alpha: float = ALPHA) -> tuple[float, float, float]:
    """Newcombe (1998) hybrid-score CI for p1 - p2 (independent samples).

    Returns (diff, lower, upper) as proportions.
    """
    if n1 <= 0 or n2 <= 0:
        return (float("nan"),) * 3
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_ci(k1, n1, alpha)
    l2, u2 = wilson_ci(k2, n2, alpha)
    d = p1 - p2
    lower = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, lower, upper


def two_prop_pvalue(k1: float, n1: float, k2: float, n2: float) -> float:
    """Two-sided pooled z-test p-value for equality of two proportions."""
    if n1 <= 0 or n2 <= 0:
        return float("nan")
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (k1 / n1 - k2 / n2) / se
    return float(2 * stats.norm.sf(abs(z)))


def holm_adjust(pvals: np.ndarray) -> np.ndarray:
    """Holm step-down adjusted p-values (NaN preserved)."""
    p = np.asarray(pvals, dtype=float)
    out = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    m = len(pv)
    order = np.argsort(pv)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pv[idx])
        adj[idx] = min(1.0, running)
    out[ok] = adj
    return out


def bh_adjust(pvals: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (NaN preserved)."""
    p = np.asarray(pvals, dtype=float)
    out = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    m = len(pv)
    order = np.argsort(-pv)
    adj = np.empty(m)
    running = 1.0
    for i, idx in enumerate(order):
        rank = m - i
        running = min(running, pv[idx] * m / rank)
        adj[idx] = running
    out[ok] = adj
    return out


def mh_risk_difference(tables: np.ndarray, alpha: float = ALPHA) -> dict:
    """Mantel-Haenszel common risk difference across strata (Greenland-Robins
    variance).

    ``tables`` is an (S, 4) array with columns
    [events_group, n_group, events_other, n_other] per stratum.
    Returns dict with rd, lo, hi, p (all proportions) and n_strata.
    """
    t = np.asarray(tables, dtype=float)
    a, n1, c, n0 = t[:, 0], t[:, 1], t[:, 2], t[:, 3]
    n = n1 + n0
    ok = (n1 > 0) & (n0 > 0)
    a, n1, c, n0, n = a[ok], n1[ok], c[ok], n0[ok], n[ok]
    if len(n) == 0:
        return dict(rd=float("nan"), lo=float("nan"), hi=float("nan"),
                    p=float("nan"), n_strata=0)
    w = n1 * n0 / n
    sw = float(np.sum(w))
    rd = float(np.sum(w * (a / n1 - c / n0)) / sw)
    # Greenland & Robins (1985) variance of the MH risk difference
    P = (n1 ** 2 * c - n0 ** 2 * a + n1 * n0 * (n0 - n1) / 2) / n ** 2
    Q = (a * (n0 - c) + c * (n1 - a)) / (2 * n)
    var = max(float((rd * np.sum(P) + np.sum(Q)) / sw ** 2), 0.0)
    se = math.sqrt(var)
    z = stats.norm.ppf(1 - alpha / 2)
    pval = float(2 * stats.norm.sf(abs(rd / se))) if se > 0 else 1.0
    return dict(rd=rd, lo=rd - z * se, hi=rd + z * se, p=pval, n_strata=int(len(n)))
