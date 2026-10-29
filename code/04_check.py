"""Check the directory and write data/clean/check_report.md.

Usage: python code/04_check.py
"""
import csv
import gzip
import importlib.util
import json
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"
UA = {"User-Agent": "Mercenomics research data download (mercenomics@gmail.com)"}
results = []

spec = importlib.util.spec_from_file_location("link", ROOT / "code" / "03_link.py")
link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(link)


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def read(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    d = read(CLEAN / "directory.csv")
    log = json.loads((RAW / "download_log.json").read_text())
    n = Counter(r["list"] for r in d)

    # 1. every record of every source is in the directory, once
    expect = {"ICoCA": log["icoca/icoca_member_companies.json"]["records"],
              "SIA Approved Contractor": log["sia/sia_register_of_approved_contractors.html"]["records"],
              "SEC SIC 7381": log["sec/sec_sic7381_ciks.txt"]["records"],
              "Companies House SIC 80100": log["companies_house/companies_house_sic80100.csv.gz"]["records"],
              "US federal guard contracts": log["us_guard_contracts/s206_recipients.csv"]["records"]}
    check("Every source record is in the directory", all(n[k] == v for k, v in expect.items()),
          ", ".join(f"{k} {n[k]:,}" for k in expect))
    dup = [k for k, c in Counter((r["list"], r["list_id"]) for r in d if r["list_id"]).items() if c > 1]
    check("No identifier appears twice within a list", not dup, f"{len(dup)} duplicates")
    no_id = sum(1 for r in d if not r["list_id"])
    check("Only US contract recipients without an entity ID lack an identifier",
          all(r["list"] == "US federal guard contracts" for r in d if not r["list_id"]), f"{no_id} recipients without an ID")

    # 2. source-specific checks
    sia = [json.loads(l) for l in open(RAW / "sia" / "sia_approved_contractors.jsonl", encoding="utf-8")]
    err = [r["acs_reference"] for r in sia if "detail_error" in r]
    agree = [r for r in sia if "detail_error" not in r and r["expiry_date"] == r["detail_expiry_date"]]
    check("SIA: the expiry date on the register list and on each contractor's own page agree",
          len(agree) == len(sia) - len(err), f"{len(agree)} of {len(sia) - len(err)} pages read; page not available: {', '.join(err) or 'none'}")
    sec = [json.loads(l) for l in open(RAW / "sec" / "sec_sic7381_companies.jsonl", encoding="utf-8")]
    check("SEC: every company's own filing record gives industry code 7381", all(r["sic"] == "7381" for r in sec), f"{len(sec)} companies")
    with gzip.open(RAW / "companies_house" / "companies_house_sic80100.csv.gz", "rt", encoding="utf-8") as fh:
        ch = list(csv.DictReader(fh))
    ok = all(any(r[f"SICCode.SicText_{i}"].startswith("80100") for i in range(1, 5)) for r in ch)
    chlog = log["companies_house/companies_house_sic80100.csv.gz"]
    check("Companies House: every company kept has SIC 80100 among its activity codes", ok,
          f"{len(ch):,} of {chlog['live_companies_read']:,} live companies in the {len(chlog['source_files'])}-part October 2026 snapshot")
    icoca = json.loads((RAW / "icoca" / "icoca_member_companies.json").read_text())
    check("ICoCA: every entry is a company (not a government, civil society group or observer)",
          all(m["entityType"] == "Company" for m in icoca), f"{len(icoca)} companies")

    # 3. US guard-contract recipients add up to us-guard-spending's total
    url = "https://github.com/Affnann/us-guard-spending/raw/v1.0.0/output/tables/top50_companies_musd.csv"
    top = list(csv.DictReader(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode().splitlines()))
    url2 = "https://github.com/Affnann/us-guard-spending/raw/v1.0.0/output/tables/by_fiscal_year_musd.csv"
    fy = list(csv.DictReader(urllib.request.urlopen(urllib.request.Request(url2, headers=UA), timeout=120).read().decode().splitlines()))
    total = sum(float(r["Total"]) for r in fy)
    placeholders = sum(float(r["obligations_musd"]) for r in top if r["parent"] in {"DOMESTIC AWARDEES (UNDISCLOSED)", "MISCELLANEOUS FOREIGN AWARDEES"})
    usa = read(RAW / "us_guard_contracts" / "s206_recipients.csv")
    mine = sum(float(r["obligations_usd"]) for r in usa) / 1e6
    check("US contracts: recipients add up to us-guard-spending's total less its two placeholder entries",
          abs(mine - (total - placeholders)) < 0.5, f"${mine:,.1f} million vs ${total - placeholders:,.1f} million")

    # 4. no personal contact details
    phone = re.compile(r"\b0\d{3,4}\s?\d{3}\s?\d{3,4}\b|\+\d{2}\s?\d")
    hits = [r["list_id"] for r in d if phone.search(" ".join([r["place"], r["detail"], r["status"]]))]
    check("No telephone numbers in the directory", not hits, f"{len(hits)} rows")
    uk_place = [r for r in d if r["list"] in ("SIA Approved Contractor", "Companies House SIC 80100") and r["place"]]
    bad = [r["list_id"] for r in uk_place if not re.fullmatch(r"(?:[A-Za-z .'&()-]+, )?[A-Z]{1,2}\d[A-Z\d]?", r["place"])]
    check("UK locations are given only as town and postcode district (no street addresses)",
          len(bad) <= len(uk_place) * 0.01, f"{len(uk_place) - len(bad):,} of {len(uk_place):,} match the town-and-district pattern; others: {', '.join(bad[:8])}")

    # 5. links
    cl = read(CLEAN / "cross_listed.csv")
    groups = defaultdict(list)
    for r in cl:
        groups[(r["name_key"], r["country_code"])].append(r)
    ok = all(len({r["list"] for r in v}) > 1 for v in groups.values())
    check("Every linked group spans at least two lists", ok, f"{len(groups)} groups")
    byid = {(r["list"], r["list_id"], r["name"]): r for r in d}
    good = True
    for (k, c), v in groups.items():
        for r in v:
            e = byid[(r["list"], r["list_id"], r["name"])]
            keys = {link.name_key(e["name"])} | ({link.name_key(x) for x in e["trading_name"].split(" | ")} if e["trading_name"] else set())
            good &= k in keys and c in link.countries(e["country"])
    check("Every link joins entries with the same name key and the same country", good)
    sia_ch = [v for v in groups.values() if {r["list"] for r in v} == {"SIA Approved Contractor", "Companies House SIC 80100"}]
    same = sum(1 for v in sia_ch
               if {r["place"].split(", ")[-1] for r in v if r["list"].startswith("SIA")} &
               {r["place"].split(", ")[-1] for r in v if r["list"].startswith("Companies")})
    check("SIA and Companies House links: share of linked pairs whose postcode districts also agree (information)",
          True, f"{same} of {len(sia_ch)} ({same / len(sia_ch):.0%}); the rest have a different registered office and trading address, or are different companies")

    lines = ["# Check report", "", "Made by `code/04_check.py`.", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {a} | {'PASS' if b else 'FAIL'} | {c} |" for a, b, c in results]
    (CLEAN / "check_report.md").write_text("\n".join(lines) + "\n")
    for a, b, c in results:
        print("PASS" if b else "FAIL", a, "-", c)
    if not all(b for _, b, _ in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
