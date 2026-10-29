# Check report

Made by `code/04_check.py`.

| Check | Result | Detail |
|---|---|---|
| Every source record is in the directory | PASS | ICoCA 198, SIA Approved Contractor 719, SEC SIC 7381 52, Companies House SIC 80100 16,923, US federal guard contracts 2,744 |
| No identifier appears twice within a list | PASS | 0 duplicates |
| Only US contract recipients without an entity ID lack an identifier | PASS | 2 recipients without an ID |
| SIA: the expiry date on the register list and on each contractor's own page agree | PASS | 718 of 718 pages read; page not available: SSGLTDSC01 |
| SEC: every company's own filing record gives industry code 7381 | PASS | 52 companies |
| Companies House: every company kept has SIC 80100 among its activity codes | PASS | 16,923 of 5,704,712 live companies in the 7-part October 2026 snapshot |
| ICoCA: every entry is a company (not a government, civil society group or observer) | PASS | 198 companies |
| US contracts: recipients add up to us-guard-spending's total less its two placeholder entries | PASS | $76,107.8 million vs $76,107.8 million |
| No telephone numbers in the directory | PASS | 0 rows |
| UK locations are given only as town and postcode district (no street addresses) | PASS | 17,626 of 17,633 match the town-and-district pattern; others: 12310888, 10024849, 11707859, 13965610, 15306920, 02269560, 08067643 |
| Every linked group spans at least two lists | PASS | 523 groups |
| Every link joins entries with the same name key and the same country | PASS |  |
| SIA and Companies House links: share of linked pairs whose postcode districts also agree (information) | PASS | 380 of 497 (76%); the rest have a different registered office and trading address, or are different companies |
