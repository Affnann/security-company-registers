"""Build data/clean/directory.csv: one row per company per official list.

Usage: python code/02_build.py
"""
import csv
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"

COLS = ["list", "list_id", "name", "trading_name", "country", "place", "status", "since", "detail", "source_url"]

US_STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC "
                "ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR GU VI AS MP".split())
# sector codes used on the SIA register list (the contractor pages spell them out, with some typing variations)
SIA_SECTORS = {"SG": "Security Guarding", "KH": "Key Holding", "DS": "Door Supervision", "CCTV": "Public Space Surveillance (CCTV)",
               "CP": "Close Protection", "CViT": "Cash and Valuables in Transit", "VI": "Vehicle Immobilising"}
ICOCA_COUNTRY = {"United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
                 "United States of America": "United States"}


UK_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) ?\d[A-Z]{2}$")


def outward(postcode):
    """The first half of a UK postcode (the postcode district), e.g. 'E14 9TS' -> 'E14'; '' if not a postcode."""
    m = UK_POSTCODE.match((postcode or "").strip().upper())
    return m.group(1) if m else ""


def town(value):
    """A post town, or '' where the field holds street details instead (digits or commas)."""
    v = (value or "").strip()
    return "" if re.search(r"[\d,]", v) else v.title()


def dmy(s, sep):
    """'31/05/2027' or '20.01.2023' -> '2027-05-31'."""
    if not s:
        return ""
    d, m, y = s.strip().split(sep)
    return f"{y}-{m.zfill(2)}-{d.zfill(2)}"


def split_trading(name):
    m = re.split(r"\s+(?:t/a|T/A|trading as|Trading as|\(trading as)\s+", name, maxsplit=1)
    if len(m) == 2:
        return m[0].strip(), m[1].strip().rstrip(")")
    return name.strip(), ""


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    rows = []

    for m in json.loads((RAW / "icoca" / "icoca_member_companies.json").read_text()):
        cert = m.get("certificationInfo") or {}
        detail = [f"service type: {m['serviceType']}" if m.get("serviceType") else ""]
        if cert.get("standard"):
            detail.append(f"certified to {cert['standard']} until {dmy(cert.get('expiration_date'), '.')}"
                          if cert.get("expiration_date") else f"certified to {cert['standard']}")
        hq = m["headquarter"]["headquarter_country"]
        rows.append({"list": "ICoCA", "list_id": m["ID"], "name": m["post_title"].strip(), "trading_name": "",
                     "country": ICOCA_COUNTRY.get(hq, hq), "place": "", "status": m["companyCategory"],
                     "since": dmy(m.get("joiningDate"), "."), "detail": "; ".join(x for x in detail if x),
                     "source_url": "https://icoca.ch/membership/"})

    for line in open(RAW / "sia" / "sia_approved_contractors.jsonl", encoding="utf-8"):
        r = json.loads(line)
        name, trading = split_trading(r["name"])
        rows.append({"list": "SIA Approved Contractor", "list_id": r["acs_reference"].strip(), "name": name,
                     "trading_name": trading, "country": "United Kingdom", "place": outward(r.get("postcode")),
                     "status": f"approved until {dmy(r['expiry_date'], '/')}", "since": "",
                     "detail": "sectors: " + "; ".join(SIA_SECTORS.get(c, c) for c in re.split(r"[,. ]+", r["sectors_codes"]) if c),
                     "source_url": "https://www.services.sia.homeoffice.gov.uk/Pages/acs-roac.aspx?contractor="
                                   + r["acs_reference"].strip()})

    codes = json.loads((RAW / "sec" / "edgar_state_country_codes.json").read_text())
    for line in open(RAW / "sec" / "sec_sic7381_companies.jsonl", encoding="utf-8"):
        r = json.loads(line)
        st = r.get("business_state") or ""
        detail = []
        if r.get("tickers"):
            detail.append("tickers: " + ", ".join(f"{t} ({e})" for t, e in zip(r["tickers"], r.get("exchanges") or [])))
        if r.get("latest_annual_report"):
            detail.append(f"latest annual report filed {r['latest_annual_report']}")
        rows.append({"list": "SEC SIC 7381", "list_id": r["cik"], "name": r["name"].strip(), "trading_name": "",
                     "country": "United States" if st in US_STATES else codes.get(st, st).title(),
                     "place": ", ".join(x for x in [(r.get("business_city") or "").title(), st] if x),
                     "status": f"latest filing {r['latest_filing_date']}" if r.get("latest_filing_date") else "",
                     "since": "", "detail": "; ".join(detail),
                     "source_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={r['cik']}"})

    with gzip.open(RAW / "companies_house" / "companies_house_sic80100.csv.gz", "rt", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            sics = [r[f"SICCode.SicText_{i}"] for i in range(1, 5) if r.get(f"SICCode.SicText_{i}")]
            rows.append({"list": "Companies House SIC 80100", "list_id": r["CompanyNumber"], "name": r["CompanyName"].strip(),
                         "trading_name": "", "country": "United Kingdom",
                         "place": ", ".join(x for x in [town(r["RegAddress.PostTown"]), outward(r["RegAddress.PostCode"])] if x),
                         "status": r["CompanyStatus"], "since": dmy(r["IncorporationDate"], "/"),
                         "detail": "; ".join(sics) + f"; {r['CompanyCategory']}",
                         "source_url": f"https://find-and-update.company-information.service.gov.uk/company/{r['CompanyNumber']}"})

    with open(RAW / "us_guard_contracts" / "s206_recipients.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            names = r["recipient_names"].split(" | ")
            rows.append({"list": "US federal guard contracts", "list_id": r["recipient_uei"], "name": names[0],
                         "trading_name": " | ".join(names[1:]), "country": r["recipient_country_codes"], "place": "",
                         "status": f"last contract action FY{r['last_fiscal_year']}", "since": f"FY{r['first_fiscal_year']}",
                         "detail": f"guard-contract obligations FY2008-2026: ${float(r['obligations_usd']):,.0f} on {r['awards']} awards"
                                   + (f"; parent: {r['parent_names']}" if r["parent_names"] else ""),
                         "source_url": "https://doi.org/10.5281/zenodo.23750993"})

    with open(CLEAN / "directory.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    for k, v in Counter(r["list"] for r in rows).items():
        print(f"{k}: {v}")
    print(len(rows), "rows -> data/clean/directory.csv")


if __name__ == "__main__":
    main()
