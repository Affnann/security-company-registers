"""Draw figures/lists_overlap.png: entries on each list and how many also appear on another list.

Usage: python code/05_figure.py
"""
import csv
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
rows = list(csv.DictReader(open(ROOT / "data" / "clean" / "directory.csv", encoding="utf-8")))
order = ["Companies House SIC 80100", "US federal guard contracts", "SIA Approved Contractor", "ICoCA", "SEC SIC 7381"]
label = {"Companies House SIC 80100": "UK Companies House\n(private security activities)",
         "US federal guard contracts": "US federal guard-contract\nrecipients, FY2008-2026",
         "SIA Approved Contractor": "UK SIA Approved\nContractors", "ICoCA": "ICoCA member\ncompanies",
         "SEC SIC 7381": "SEC filers, guard and\narmoured-car code (7381)"}
total = Counter(r["list"] for r in rows)
linked = Counter(r["list"] for r in rows if r["also_on"])

fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1, 1]})
y = range(len(order))[::-1]
for ax, keys, title in ((a, order[:2], "Large lists"), (b, order[2:], "Small lists")):
    ys = list(range(len(keys)))[::-1]
    ax.barh(ys, [total[k] for k in keys], color="#D9D5CE", label="on this list only")
    ax.barh(ys, [linked[k] for k in keys], color="#8B2E2E", label="also on another list (same name and country)")
    for yy, k in zip(ys, keys):
        ax.text(total[k], yy, f"  {total[k]:,} ({linked[k]:,} linked)", va="center", fontsize=8.5)
    ax.set_yticks(ys)
    ax.set_yticklabels([label[k] for k in keys], fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, max(total[k] for k in keys) * 1.45)
    ax.tick_params(axis="x", labelsize=8)
    ax.set_title(title, loc="left", fontsize=10)
a.legend(frameon=False, fontsize=8, loc="lower right")
fig.suptitle("Private security companies on five official lists", x=0.01, ha="left", fontsize=11)
fig.text(0.01, 0.01, "A link means the names match after legal-form words are removed and the country agrees; it does not prove "
         "the entries are the same legal entity.", fontsize=7.5, color="#4A4F57")
fig.tight_layout(rect=(0, 0.04, 1, 0.95))
(ROOT / "figures").mkdir(exist_ok=True)
fig.savefig(ROOT / "figures" / "lists_overlap.png", dpi=150)
print("figures/lists_overlap.png")
