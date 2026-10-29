"""Download the five official lists into data/raw/.

1. ICoCA (International Code of Conduct Association): its member companies, from the
   member list on icoca.ch (the site's own data service, wp-json/members/v1/get-members).
2. UK Security Industry Authority (SIA): the Register of Approved Contractors, and each
   contractor's entry page (activities, expiry date, town and postcode).
3. US Securities and Exchange Commission (SEC): companies filed under industry code (SIC) 7381,
   "Services-Detective, Guard & Armored Car Services", and each company's filing record.
4. UK Companies House: the Free Company Data Product (every live company); only companies
   whose nature of business includes SIC 80100 "Private security activities" are kept.
5. US federal guard contracts: every recipient of a guard-service contract (PSC S206),
   FY2008-2026, from the Mercenomics dataset us-guard-spending v1.0.0.

Usage: python code/01_download.py [icoca] [sia] [sec] [ch] [usa]   (no argument = all)
"""
import csv
import gzip
import hashlib
import html
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
UA = {"User-Agent": "Mercenomics research data download (mercenomics@gmail.com)"}
LOG = RAW / "download_log.json"
TODAY = time.strftime("%Y-%m-%d")


def fetch(url, timeout=300, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def log(key, **info):
    d = json.loads(LOG.read_text()) if LOG.exists() else {}
    d[key] = info | {"accessed": TODAY}
    LOG.write_text(json.dumps(d, indent=1, ensure_ascii=False))


def sha(b):
    return hashlib.sha256(b).hexdigest()


def text(fragment):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def icoca():
    url = "https://icoca.ch/wp-json/members/v1/get-members?entityTypes=Company&language=en_US"
    data = fetch(url)
    (RAW / "icoca" / "icoca_member_companies.json").write_bytes(data)
    log("icoca/icoca_member_companies.json", url=url, bytes=len(data), sha256=sha(data), records=len(json.loads(data)))
    print("ICoCA:", len(json.loads(data)), "member companies")


SIA = "https://www.services.sia.homeoffice.gov.uk/Pages/acs-roac.aspx"


def sia():
    page = fetch(SIA + "?all")
    (RAW / "sia" / "sia_register_of_approved_contractors.html").write_bytes(page)
    t = page.decode("utf-8", "replace")
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", t, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        ref = re.search(r'\?contractor=([^"]+)"', tr)
        if len(cells) == 3 and ref:
            # the reference is kept exactly as in the register; a few begin with a space
            rows.append({"acs_reference": html.unescape(ref.group(1)), "name": text(cells[0]), "sectors_codes": text(cells[1]),
                         "expiry_date": text(cells[2])})

    def detail(r):
        try:
            d = fetch(f"{SIA}?contractor={urllib.parse.quote(r['acs_reference'], safe='~')}", tries=6).decode("utf-8", "replace")
        except Exception as e:  # a page that keeps failing is recorded, not guessed
            return r | {"detail_error": str(e)}
        body = re.sub(r"<script.*?</script>|<style.*?</style>", "", d, flags=re.S)
        lines = [x for x in (text(p) for p in re.split(r"<[^>]+>", body)) if x]
        def after(label, n=1):
            if label not in lines:
                return []
            i = lines.index(label)
            return lines[i + 1:i + 1 + n]
        addr = []
        if "Postal Address" in lines:
            i = lines.index("Postal Address")
            for x in lines[i + 1:]:
                if x in ("Website", "Assessing Body", "LDN Status"):
                    break
                addr.append(x)
        time.sleep(0.3)
        return r | {"sectors": "; ".join(_until(lines, "Activities (Sectors) Approved", "Expiry Date of Approval")),
                    "detail_expiry_date": (after("Expiry Date of Approval") or [""])[0],
                    "postcode": _postcode(" ".join(addr)),
                    "website": "; ".join(_until(lines, "Website", "Assessing Body")),
                    "assessing_body": "; ".join(_until(lines, "Assessing Body", "LDN Status")),
                    "additional_conditions": "; ".join(_until(lines, "Additional Conditions of Approval", "Other Services Provided"))}

    with ThreadPoolExecutor(2) as pool:
        out = list(pool.map(detail, rows))
    with open(RAW / "sia" / "sia_approved_contractors.jsonl", "w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    log("sia/sia_register_of_approved_contractors.html", url=SIA + "?all", bytes=len(page), sha256=sha(page), records=len(rows))
    log("sia/sia_approved_contractors.jsonl", url=SIA + "?contractor=REFERENCE", records=len(out),
        note="Fields read from each contractor's entry page; phone numbers and street addresses are not kept")
    print("SIA:", len(out), "approved contractors")


UK_POSTCODE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})\b")


def _postcode(address):
    """The UK postcode in an address, or '' if there is none (the street lines are not kept)."""
    m = UK_POSTCODE.search(address.upper())
    return f"{m.group(1)} {m.group(2)}" if m else ""


def _until(lines, start, stop):
    if start not in lines:
        return []
    i = lines.index(start) + 1
    out = []
    for x in lines[i:]:
        if x == stop:
            break
        out.append(x)
    return out


# SEC filers under SIC 7381 that are individuals, not companies; left out so that no person is listed
SEC_PERSONS = {"0001092857"}


def sec():
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&SIC=7381&type=&dateb=&owner=include&start=0&count=100"
    page = fetch(url)
    t = page.decode("latin-1")
    ciks = re.findall(r'CIK=(\d{10})[^"]*">\d{10}</a>', t)
    persons = [c for c in ciks if c in SEC_PERSONS]
    ciks = [c for c in ciks if c not in SEC_PERSONS]
    (RAW / "sec" / "sec_sic7381_ciks.txt").write_text("\n".join(ciks) + "\n")
    recs = []
    for c in ciks:
        d = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{c}.json"))
        f = d.get("filings", {}).get("recent", {})
        recs.append({"cik": c, "name": d.get("name"), "sic": d.get("sic"), "sicDescription": d.get("sicDescription"),
                     "tickers": d.get("tickers"), "exchanges": d.get("exchanges"), "entityType": d.get("entityType"),
                     "stateOfIncorporation": d.get("stateOfIncorporation"),
                     "business_state": (d.get("addresses", {}).get("business") or {}).get("stateOrCountry"),
                     "business_city": (d.get("addresses", {}).get("business") or {}).get("city"),
                     "formerNames": d.get("formerNames"),
                     "first_filing_date": min(f.get("filingDate") or [""]) if f.get("filingDate") else "",
                     "latest_filing_date": max(f.get("filingDate") or [""]) if f.get("filingDate") else "",
                     "latest_annual_report": max([dt for dt, fm in zip(f.get("filingDate", []), f.get("form", []))
                                                  if fm in ("10-K", "20-F", "40-F")] or [""]),
                     "older_filing_files": len(d.get("filings", {}).get("files", []))})
        time.sleep(0.2)
    with open(RAW / "sec" / "sec_sic7381_companies.jsonl", "w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    codes_url = "https://www.sec.gov/submit-filings/filer-support-resources/edgar-state-country-codes"
    ct = fetch(codes_url).decode("utf-8", "replace")
    codes = {text(a): text(b) for a, b in re.findall(r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", ct, re.S)}
    (RAW / "sec" / "edgar_state_country_codes.json").write_text(json.dumps(codes, indent=1, ensure_ascii=False))
    log("sec/edgar_state_country_codes.json", url=codes_url, records=len(codes))
    log("sec/sec_sic7381_ciks.txt", url=url, records=len(ciks), listed_by_sec=len(ciks) + len(persons),
        note=f"{len(persons)} filer registered under a person's name, not a company, is left out")
    log("sec/sec_sic7381_companies.jsonl", url="https://data.sec.gov/submissions/CIK##########.json", records=len(recs),
        note="Selected fields from each company's EDGAR submissions record. first_filing_date is the earliest date in the recent-filings list only")
    print("SEC:", len(recs), "companies with SIC 7381")


CH = "https://download.companieshouse.gov.uk/"


def companies_house():
    idx = fetch(CH + "en_output.html").decode("utf-8", "replace")
    parts = sorted(set(re.findall(r'href="(BasicCompanyData-\d{4}-\d\d-\d\d-part\d_\d\.zip)"', idx)))
    out_rows, header, seen, info = [], None, 0, {}
    for p in parts:
        data = fetch(CH + p, timeout=1800)
        info[p] = {"bytes": len(data), "sha256": sha(data)}
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            name = z.namelist()[0]
            rd = csv.reader(io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace"))
            h = [x.strip() for x in next(rd)]
            header = header or h
            sic_cols = [i for i, x in enumerate(h) if x.startswith("SICCode.SicText")]
            for row in rd:
                seen += 1
                if any(row[i].startswith("80100") for i in sic_cols if i < len(row)):
                    out_rows.append(dict(zip(h, row)))
        print(p, "->", len(out_rows), "so far", flush=True)
        del data
    keep = ["CompanyName", "CompanyNumber", "RegAddress.PostTown", "RegAddress.County", "RegAddress.Country",
            "RegAddress.PostCode", "CompanyCategory", "CompanyStatus", "CountryOfOrigin", "IncorporationDate",
            "SICCode.SicText_1", "SICCode.SicText_2", "SICCode.SicText_3", "SICCode.SicText_4", "URI"]
    with gzip.open(RAW / "companies_house" / "companies_house_sic80100.csv.gz", "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)
    log("companies_house/companies_house_sic80100.csv.gz", url=CH + "en_output.html", source_files=info,
        live_companies_read=seen, records=len(out_rows),
        note="Rows of the Free Company Data Product with SIC 80100 among the company's SIC codes; street address lines dropped")
    print("Companies House:", len(out_rows), "of", seen, "live companies")


USA = "https://github.com/Affnann/us-guard-spending/raw/v1.0.0/data/clean/s206_transactions.csv.gz"
PLACEHOLDERS = {"DOMESTIC AWARDEES (UNDISCLOSED)", "MISCELLANEOUS FOREIGN AWARDEES"}


def usa():
    data = fetch(USA)
    rows = csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(data)), encoding="utf-8"))
    agg = defaultdict(lambda: {"names": set(), "parents": set(), "countries": set(), "usd": 0.0, "awards": set(),
                               "fy": set()})
    for r in rows:
        name = r["recipient_name"]
        if not name or name in PLACEHOLDERS:
            continue
        key = r["recipient_uei"] or "NAME:" + name
        a = agg[key]
        a["names"].add(name)
        if r["recipient_parent_name"]:
            a["parents"].add(r["recipient_parent_name"])
        if r["recipient_country_code"]:
            a["countries"].add(r["recipient_country_code"])
        a["usd"] += float(r["obligation_usd"] or 0)
        a["awards"].add(r["award_key"])
        a["fy"].add(int(r["fiscal_year"]))
    with open(RAW / "us_guard_contracts" / "s206_recipients.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["recipient_uei", "recipient_names", "parent_names", "recipient_country_codes", "obligations_usd",
                    "awards", "first_fiscal_year", "last_fiscal_year"])
        for k, a in sorted(agg.items(), key=lambda kv: -kv[1]["usd"]):
            w.writerow(["" if k.startswith("NAME:") else k, " | ".join(sorted(a["names"])), " | ".join(sorted(a["parents"])),
                        " | ".join(sorted(a["countries"])), f'{a["usd"]:.2f}', len(a["awards"]), min(a["fy"]), max(a["fy"])])
    log("us_guard_contracts/s206_recipients.csv", url=USA, source_sha256=sha(data), records=len(agg),
        note="One row per recipient Unique Entity ID (or name where no ID is given), placeholders left out")
    print("US guard contracts:", len(agg), "recipients")


if __name__ == "__main__":
    jobs = {"icoca": icoca, "sia": sia, "sec": sec, "ch": companies_house, "usa": usa}
    for j in sys.argv[1:] or list(jobs):
        (RAW).mkdir(parents=True, exist_ok=True)
        jobs[j]()
