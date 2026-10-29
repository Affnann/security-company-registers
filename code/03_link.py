"""Find companies that appear on more than one list.

Two entries are linked when (1) their names are the same after legal-form words (Limited, Ltd,
LLC, Inc., Corporation ...), "The", bracketed notes, punctuation and case are removed, and "&" is
read as "and"; and (2) they are in the same country (ICoCA: headquarters country; SIA and
Companies House: United Kingdom; SEC: business address; US contracts: the recipient's country).
Names that reduce to a generic phrase such as "Security Services" are not linked. A link means
the names and country match; it does not prove the entries are the same legal entity. Every
link is in data/clean/cross_listed.csv for checking.

Adds `name_key` and `also_on` to data/clean/directory.csv and writes data/clean/cross_listed.csv.

Usage: python code/03_link.py
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

import pycountry

CLEAN = Path(__file__).resolve().parents[1] / "data" / "clean"

LEGAL = {"LIMITED", "LTD", "LLC", "L L C", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "PLC",
         "LP", "LLP", "L P", "GMBH", "SA", "S A", "AB", "NV", "BV", "PTY", "PVT", "PRIVATE", "THE", "SAC", "SARL",
         "SPA", "SRL", "AG", "AS", "OY", "FZE", "FZCO", "FZ LLC", "WLL", "W L L", "LTDA", "JSC", "OOO"}
GENERIC = {"SECURITY", "SECURITY SERVICES", "SECURITY SERVICE", "PROTECTION", "PROTECTION SERVICES", "GUARDING",
           "SECURITY GROUP", "SECURITY SOLUTIONS", "GUARD SERVICES", "SECURITY AND PROTECTION", "PRIVATE SECURITY",
           "SECURITY AND GUARDING", "SECURITY CONSULTANTS", "SECURITY MANAGEMENT", "TOTAL SECURITY", "GLOBAL SECURITY"}


# country names the standard list does not recognise, as written in the sources
COUNTRY_FIX = {"Turkey": "TUR", "TURKEY": "TUR", "Congo (Democratic Republic of the)": "COD",
               "Myanmar (formerly Burma)": "MMR", "Virgin Islands (British)": "VGB", "Quebec, Canada": "CAN",
               "RUSSIA": "RUS"}


def countries(value):
    """ISO 3166 three-letter codes for a country field (several may be given, separated by ' | ')."""
    out = set()
    for t in (x.strip() for x in value.split(" | ")):
        if not t:
            continue
        if t in COUNTRY_FIX:
            out.add(COUNTRY_FIX[t])
            continue
        try:
            out.add(pycountry.countries.lookup(t).alpha_3)
        except LookupError:
            pass  # unknown codes such as 'NAN' are left without a country and are not linked
    return out


def name_key(name):
    t = name.upper().replace("&", " AND ")
    t = re.sub(r"\(.*?\)", " ", t)              # bracketed notes such as "(UK)" or "(trading as ...)"
    t = re.sub(r"[^A-Z0-9 ]+", " ", t)
    words = t.split()
    changed = True
    while changed and words:
        changed = False
        for n in (3, 2, 1):                      # legal-form words at either end, also when spelled 'L L C'
            if len(words) >= n and " ".join(words[-n:]) in LEGAL:
                words, changed = words[:-n], True
                break
            if len(words) >= n and " ".join(words[:n]) in LEGAL:
                words, changed = words[n:], True
                break
    return " ".join(words)


def main():
    with open(CLEAN / "directory.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    groups = defaultdict(list)
    for r in rows:
        keys = {name_key(r["name"])}
        if r["list"] == "SIA Approved Contractor" and r["trading_name"]:
            keys.add(name_key(r["trading_name"]))
        if r["list"] == "US federal guard contracts" and r["trading_name"]:
            keys |= {name_key(n) for n in r["trading_name"].split(" | ")}
        r["name_key"] = name_key(r["name"])
        r["country_codes"] = "; ".join(sorted(countries(r["country"])))
        for k in keys:
            if k and k not in GENERIC:
                for c in countries(r["country"]):
                    groups[(k, c)].append(r)

    linked = {k: v for k, v in groups.items() if len({r["list"] for r in v}) > 1}
    also = defaultdict(set)
    for k, v in linked.items():
        lists = {r["list"] for r in v}
        for r in v:
            also[(r["list"], r["list_id"], r["name"])] |= lists - {r["list"]}
    for r in rows:
        r["also_on"] = "; ".join(sorted(also.get((r["list"], r["list_id"], r["name"]), [])))

    cols = list(rows[0].keys())
    with open(CLEAN / "directory.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    out = []
    for (k, c), v in sorted(linked.items()):
        for r in v:
            out.append({"name_key": k, "country_code": c, "lists": "; ".join(sorted({x["list"] for x in v})), "list": r["list"],
                        "list_id": r["list_id"], "name": r["name"], "country": r["country"], "place": r["place"],
                        "status": r["status"]})
    with open(CLEAN / "cross_listed.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{len(linked)} name-and-country pairs appear on more than one list ({len(out)} entries) -> data/clean/cross_listed.csv")


if __name__ == "__main__":
    main()
