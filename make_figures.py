"""Figures, generated only from the CSV tables in outputs/tables/."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

T, F = C.TABLE_DIR, C.FIG_DIR
BLUE, ORANGE, AQUA, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#9a9a95", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#c9c8c2", "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": MUTED, "text.color": INK, "figure.dpi": 130,
                     "axes.grid": True, "grid.color": "#e8e7e2", "grid.linewidth": .6,
                     "axes.axisbelow": True})
wrap = lambda s, w=46: "\n".join(textwrap.wrap(s, w))


def fig_composition():
    s = pd.read_csv(T / "rq1_outcome_share_among_known_final.csv")
    cols = [("explanation_only", "Explanation only", GRAY), ("non_monetary_relief", "Non-monetary relief", AQUA),
            ("monetary_relief", "Monetary relief", BLUE)]
    s = s.sort_values("explanation_only", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    left = np.zeros(len(s))
    for c, lab, col in cols:
        ax.barh(s["product_group"], s[c], left=left, color=col, label=lab, edgecolor="white", linewidth=1.5)
        for i, (v, l) in enumerate(zip(s[c], left)):
            if v >= 6:
                ax.text(l + v / 2, i, f"{v:.0f}%", ha="center", va="center", color="white", fontsize=8)
        left += s[c].to_numpy()
    for i, n in enumerate(s["n_known_final"]):
        ax.text(101, i, f"n={n:,.0f}", va="center", fontsize=8, color=MUTED)
    ax.set_xlim(0, 118); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
    ax.set_xlabel("% of complaints with a known final company response")
    ax.set_title("Recorded company responses by product (Apr 2017 - Jun 2026)", loc="left", fontsize=10)
    ax.legend(ncol=3, frameon=False, loc="lower center", bbox_to_anchor=(.45, -.32))
    fig.tight_layout(); fig.savefig(F / "fig1_outcome_composition.png"); plt.close(fig)


def _flagged():
    m = pd.read_csv(T / "rq3_aggregate_vs_within.csv")
    return m[m["aggregate_flag"]].copy()


def fig_forest():
    m = _flagged().sort_values("diff_pp")
    fig, ax = plt.subplots(figsize=(9.5, 8.2))
    y = np.arange(len(m))
    ax.hlines(y, m["diff_lo_pp"], m["diff_hi_pp"], color=BLUE, lw=1.6)
    ax.plot(m["diff_pp"], y, "o", color=BLUE, ms=6, mec="white", mew=1)
    ax.axvline(0, color=INK, lw=.8)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{wrap(i, 62)}  [{p}]" if False else f"{wrap(i, 62)}\n{p} (n={n:,})"
                        for i, p, n in zip(m["issue"], m["product_group"], m["n_known"])], fontsize=6.5)
    ax.set_xlabel("Any-relief rate: issue minus rest of its product group (percentage points, 95% CI)")
    ax.set_title("Issues that differ in the aggregate (Holm-adjusted p<0.05 and |diff| >= 5 pp)", loc="left", fontsize=10)
    ax.grid(axis="y", visible=False)
    fig.tight_layout(); fig.savefig(F / "fig2_issue_differences_aggregate.png"); plt.close(fig)


def fig_within():
    m = _flagged().sort_values("crude_diff_pp")
    col = {"persists": BLUE, "weakens": AQUA, "disappears": ORANGE, "not_evaluable": GRAY}
    fig, ax = plt.subplots(figsize=(9.5, 8.2))
    y = np.arange(len(m))
    ax.hlines(y, m["crude_diff_pp"], m["mh_diff_pp"], color="#c9c8c2", lw=1.5)
    ax.plot(m["crude_diff_pp"], y, "o", mfc="white", mec=INK, ms=6, label="Pooled over the same companies")
    for yy, (_, r) in zip(y, m.iterrows()):
        ax.hlines(yy, r["mh_lo_pp"], r["mh_hi_pp"], color=col[r["verdict"]], lw=1.2)
        ax.plot(r["mh_diff_pp"], yy, "D", color=col[r["verdict"]], ms=6, mec="white", mew=1)
    ax.axvline(0, color=INK, lw=.8)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{wrap(i, 62)}\n{p} ({int(c)} companies)" for i, p, c in
                        zip(m["issue"], m["product_group"], m["n_companies"])], fontsize=6.5)
    ax.set_xlabel("Difference vs. other issues (percentage points)")
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", mfc="white", mec=INK, label="Pooled across companies (circle)")]
    h += [Line2D([], [], marker="D", ls="", color=c, label=f"Within-company MH (diamond): {k.replace('_', ' ')}")
          for k, c in col.items() if k != "not_evaluable"]
    ax.legend(handles=h, frameon=False, fontsize=7, loc="lower right")
    ax.set_title("Do aggregate differences survive comparing issues within the same company?", loc="left", fontsize=10)
    ax.grid(axis="y", visible=False)
    fig.tight_layout(); fig.savefig(F / "fig3_aggregate_vs_within_company.png"); plt.close(fig)


def fig_time():
    a = pd.read_csv(T / "rq4_adjusted_yearly_rates.csv")
    pgs = sorted(a["product_group"].unique())
    fig, axes = plt.subplots(2, 4, figsize=(10, 5), sharex=True)
    for ax, pg in zip(axes.flat, pgs):
        d = a[a["product_group"] == pg]
        ax.plot(d["year"], 100 * d["raw_rate"], "-o", color=BLUE, ms=3.5, lw=1.5, label="Raw")
        ax.plot(d["year"], 100 * d["adjusted_rate"], "--s", color=ORANGE, ms=3.5, lw=1.5, label="Mix-adjusted")
        ax.set_title(pg, fontsize=9, loc="left"); ax.set_ylim(bottom=0)
        ax.set_xticks([2018, 2020, 2022, 2024, 2026])
    for ax in axes.flat[len(pgs):]:
        ax.axis("off")
    axes.flat[0].legend(frameon=False, fontsize=7)
    fig.supylabel("Any-relief rate, % of known final responses", fontsize=8)
    fig.suptitle("Recorded any-relief rate by year (2017 and 2026 are partial years)", x=.02, ha="left", fontsize=10)
    fig.tight_layout(); fig.savefig(F / "fig4_yearly_rates_raw_vs_adjusted.png"); plt.close(fig)


def fig_robust():
    r = pd.read_csv(T / "robustness_summary.csv")
    r = r[~r["variant"].str.startswith("outcome=")]
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    y = np.arange(len(r))[::-1]
    left = np.zeros(len(r))
    for c, col, lab in [("persists", BLUE, "Persists"), ("weakens", AQUA, "Weakens"),
                        ("disappears", ORANGE, "Disappears"), ("not_evaluable", GRAY, "Not evaluable")]:
        ax.barh(y, r[c], left=left, color=col, label=lab, edgecolor="white", linewidth=1.5)
        left += r[c].to_numpy()
    ax.set_yticks(y); ax.set_yticklabels([wrap(v, 52) for v in r["variant"]], fontsize=7)
    ax.set_xlabel("Number of aggregate-flagged issues, by within-company verdict")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(.4, -.14), fontsize=8)
    ax.set_title("Within-company verdicts under alternative analytical choices", loc="left", fontsize=10)
    fig.tight_layout(); fig.savefig(F / "fig5_robustness_verdicts.png"); plt.close(fig)


if __name__ == "__main__":
    F.mkdir(parents=True, exist_ok=True)
    for f in (fig_composition, fig_forest, fig_within, fig_time, fig_robust):
        f()
    print("figures written to", F)
