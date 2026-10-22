"""Unit tests on small constructed fixtures (never real complaint data)."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import common as C  # noqa: E402
import clean_data  # noqa: E402
import analyze_outcomes as A  # noqa: E402


# ---------------------------------------------------------------- outcome map
def test_outcome_mapping_known_values():
    assert C.map_outcome("Closed with monetary relief") == "monetary_relief"
    assert C.map_outcome("Closed with non-monetary relief") == "non_monetary_relief"
    assert C.map_outcome("Closed with explanation") == "explanation_only"
    assert C.map_outcome("In progress") == "in_progress"
    assert C.map_outcome("Closed") == "closed_unspecified"


def test_missing_outcome_not_treated_as_no_relief():
    assert C.map_outcome(np.nan) == "missing"
    assert C.map_outcome(None) == "missing"
    assert "missing" not in C.KNOWN_FINAL
    assert "in_progress" not in C.KNOWN_FINAL


def test_unknown_value_is_flagged_not_silently_mapped():
    assert C.map_outcome("Brand new value").startswith("unmapped_")


# ------------------------------------------------------------ company names
def test_company_normalisation():
    assert C.normalize_company("Wells Fargo & Company") == "WELLS FARGO"
    assert C.normalize_company("BANK OF AMERICA, N.A.") == "BANK OF AMERICA"
    assert C.normalize_company("Navient Solutions, LLC.") == "NAVIENT SOLUTIONS"
    assert C.normalize_company("navient solutions llc") == "NAVIENT SOLUTIONS"
    assert C.normalize_company(np.nan) is None
    # different brands must not be merged
    assert C.normalize_company("Citibank, N.A.") != C.normalize_company("Citizens Bank")


# ---------------------------------------------------------------- chunk clean
def _raw_chunk():
    return pd.DataFrame({
        "Date received": ["2018-01-05", "bad-date"],
        "Product": ["Mortgage", "Credit card"],
        "Sub-product": ["x", "y"], "Issue": [" Trouble ", "Fees"],
        "Sub-issue": [None, None], "Company": ["Acme, Inc.", "ACME INC"],
        "Submitted via": ["Web", "Web"],
        "Company response to consumer": ["Closed with explanation", np.nan],
        "Timely response?": ["Yes", "No"], "Complaint ID": [" 1", "2"],
    })


def test_clean_chunk_dates_and_mapping():
    out = clean_data.clean_chunk(_raw_chunk())
    assert pd.isna(out.loc[1, "date_received"])          # invalid date -> NaT
    assert out.loc[0, "product_group"] == "Mortgage"
    assert out.loc[1, "product_group"] == "Credit card"
    assert out.loc[0, "issue"] == "Trouble"               # whitespace trimmed
    assert out.loc[0, "company"] == out.loc[1, "company"] == "ACME"
    assert out.loc[1, "outcome"] == "missing"
    assert out.loc[0, "complaint_id"] == "1"


def test_window_start_constant():
    assert C.WINDOW_START == pd.Timestamp("2017-04-24")


# ---------------------------------------------------------------- statistics
def test_wilson_matches_reference_values():
    # reference computed independently (e.g. R binom::binom.wilson)
    lo, hi = C.wilson_ci(10, 100)
    assert lo == pytest.approx(0.05523, abs=2e-4)
    assert hi == pytest.approx(0.17437, abs=2e-4)
    lo, hi = C.wilson_ci(0, 20)
    assert lo == 0.0 and hi == pytest.approx(0.16113, abs=2e-4)
    assert all(math.isnan(x) for x in C.wilson_ci(0, 0))


def test_wilson_contains_point_estimate_and_shrinks_with_n():
    for k, n in [(1, 10), (50, 100), (99, 100)]:
        lo, hi = C.wilson_ci(k, n)
        assert lo <= k / n <= hi
    w_small = np.subtract(*C.wilson_ci(5, 50)[::-1])
    w_big = np.subtract(*C.wilson_ci(500, 5000)[::-1])
    assert w_big < w_small


def test_newcombe_difference():
    d, lo, hi = C.newcombe_diff_ci(40, 100, 20, 100)
    assert d == pytest.approx(0.20)
    # hand-computed from Wilson limits (.3094,.4980) and (.1333,.2893)
    assert lo == pytest.approx(0.0731, abs=1e-3)
    assert hi == pytest.approx(0.3185, abs=1e-3)
    d0, lo0, hi0 = C.newcombe_diff_ci(30, 100, 30, 100)
    assert d0 == 0 and lo0 < 0 < hi0


def test_percentage_point_difference_sign():
    d, _, _ = C.newcombe_diff_ci(10, 100, 30, 100)
    assert d == pytest.approx(-0.20)


def test_two_prop_pvalue():
    assert C.two_prop_pvalue(30, 100, 30, 100) == pytest.approx(1.0)
    assert C.two_prop_pvalue(60, 100, 40, 100) == pytest.approx(0.00466, abs=2e-4)


def test_holm_and_bh():
    p = np.array([0.01, 0.04, 0.03, np.nan])
    h = C.holm_adjust(p)
    assert h[0] == pytest.approx(0.03) and h[2] == pytest.approx(0.06)
    assert h[1] == pytest.approx(0.06) and math.isnan(h[3])
    b = C.bh_adjust(p)
    assert b[0] == pytest.approx(0.03) and b[1] == pytest.approx(0.04)
    assert b[2] == pytest.approx(0.04)


def test_mh_single_stratum_matches_wald():
    r = C.mh_risk_difference(np.array([[30, 100, 10, 200]]))
    se = math.sqrt(.3 * .7 / 100 + .05 * .95 / 200)
    assert r["rd"] == pytest.approx(0.25)
    assert (r["hi"] - r["lo"]) / 2 == pytest.approx(1.959964 * se, rel=1e-3)


def test_mh_removes_simpsons_paradox():
    # Two companies. Issue X is concentrated at the high-relief company, so the
    # crude difference is large, but within each company X == other issues.
    tabs = np.array([[80, 100, 400, 500],      # company A: 80% vs 80%
                     [10, 500, 2, 100]])       # company B: 2% vs 2%
    crude_x = (80 + 10) / 600
    crude_o = (400 + 2) / 600
    assert crude_x - crude_o < -0.5 or abs(crude_x - crude_o) > 0.5
    r = C.mh_risk_difference(tabs)
    assert r["rd"] == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------- analysis helpers
def _toy():
    rows = []
    def add(co, pg, issue, outcomes):
        for o in outcomes:
            rows.append(dict(company=co, product_group=pg, issue=issue, outcome=o,
                             year=2020, company_raw=co))
    add("A", "P", "i1", ["non_monetary_relief"] * 3 + ["explanation_only"] * 7)
    add("A", "P", "i2", ["explanation_only"] * 10)
    add("A", "P", "i1", ["in_progress"] * 5 + ["missing"] * 2 + ["closed_unspecified"] * 3)
    add("B", "P", "i1", ["monetary_relief"] * 2 + ["explanation_only"] * 8)
    return pd.DataFrame(rows)


def test_denominator_excludes_pending_missing_and_bare_closed():
    df = A.add_outcome_flags(_toy())
    known = df[df["known_final"]]
    assert len(known) == 10 + 10 + 10   # 5+2+3 non-final rows dropped
    t = A.rate_table(df, ["issue"], "any_relief")
    r = t.set_index("issue").loc["i1"]
    assert r["n_known"] == 20 and r["events"] == 5
    assert r["rate"] == pytest.approx(0.25)
    assert r["n_all"] == 30 and r["n_excluded"] == 10


def test_exclusion_counts_sum_to_total():
    df = A.add_outcome_flags(_toy())
    t = A.rate_table(df, ["issue"], "any_relief")
    assert (t["n_known"] + t["n_excluded"]).sum() == len(df)


def test_within_company_logic():
    df = A.add_outcome_flags(_toy())
    cells = A.company_cells(df, "any_relief", min_cell=5)
    # company A has two issues (i1: 3/10, i2: 0/10); B has only one -> ineligible
    comp = A.within_company_contrasts(cells, min_issues=2)
    assert set(comp["company"]) == {"A"}
    r = comp[comp["issue"] == "i1"].iloc[0]
    assert r["diff_pp"] == pytest.approx(30.0)
    assert r["n_issue"] == 10 and r["n_other"] == 10
