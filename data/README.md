# Data sources

All lists were downloaded on 29 October 2026. Addresses, sizes, SHA-256 fingerprints and record counts are in [`raw/download_log.json`](raw/download_log.json).

| File | Source | What it is |
|---|---|---|
| `raw/icoca/icoca_member_companies.json` | International Code of Conduct Association, member list on icoca.ch (the list's own data service, `https://icoca.ch/wp-json/members/v1/get-members?entityTypes=Company`) | The 198 member companies, with membership category, joining date, headquarters country, countries of operation, service type, website and certification details. Governments, civil society organisations and observers are not downloaded |
| `raw/sia/sia_register_of_approved_contractors.html`, `raw/sia/sia_approved_contractors.jsonl` | UK Security Industry Authority, Register of Approved Contractors (`https://www.services.sia.homeoffice.gov.uk/Pages/acs-roac.aspx?all`) and each contractor's entry page | 719 approved contractors with their ACS reference, approved sectors and approval end date; from each entry page, the postcode, website and assessing body. Telephone numbers and street addresses are not kept |
| `raw/sec/sec_sic7381_ciks.txt`, `raw/sec/sec_sic7381_companies.jsonl`, `raw/sec/edgar_state_country_codes.json` | US Securities and Exchange Commission, EDGAR company search by industry code 7381 and each company's submissions record (`https://data.sec.gov/submissions/`); EDGAR state and country codes | 52 companies, with name, tickers, exchanges, business city and state, and filing dates. One filer registered under a person's name is left out |
| `raw/companies_house/companies_house_sic80100.csv.gz` | UK Companies House, Free Company Data Product, snapshot of 1 October 2026 (`https://download.companieshouse.gov.uk/en_output.html`), seven files | The 16,923 live companies, of 5,704,712, with SIC 80100 "Private security activities" among their activity codes: name, number, post town, county, postcode, company type and status, incorporation date and activity codes. Street address lines are not kept, and the source files are not stored |
| `raw/us_guard_contracts/s206_recipients.csv` | [us-guard-spending v1.0.0](https://doi.org/10.5281/zenodo.23750993) (Mercenomics), from USAspending.gov | Every recipient of a US federal guard-service contract (product and service code S206), fiscal years 2008 to 2026: 2,744 recipients by Unique Entity ID, with names, parent companies, country codes, obligations, awards and years |

## Terms

- **ICoCA:** the member list is published on the association's website. No licence is stated for it, so only the factual entries are reused, with a link to the source.
- **SIA:** the register is published on the Security Industry Authority's website, a UK public body. Crown copyright.
- **Companies House:** the Free Company Data Product is published free of charge. Its pages are marked Crown copyright, and the download page states no other licence.
- **SEC and USAspending:** works of the US government, in the public domain.

## Notes

- The SIA entry page for Pro Security Group Ltd (reference SSGLTDSC01) returned a server error on every attempt. The register entry is kept, without a postcode.
- A few SIA references begin with a space in the register; they are kept exactly, because the entry page needs it.
- Some Companies House "post town" fields contain street details instead of a town. In the directory these are left blank, and only the postcode district is given.
