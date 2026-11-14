# Data-quality log
Created: 2026-11-13 19:53

## WEO edition
Expected: WEO October 2026. COUNTRY_UPDATE_DATE by country:
- TJK: 9/23/2026
- KGZ: 9/25/2026
- UZB: 9/23/2026
- KAZ: 9/24/2026
- RUS: 9/28/2026
- CHN: 9/29/2026

## Trade by partner (IMF IMTS)
- Observations dropped because the partner is a region or group: 4757
- Placeholder values (99,999 / 999,999 / 9,999,999) set to missing: 19
  Examples: TJK-AFG 2001 imports_cif; TJK-BHS 2006 imports_cif; TJK-CAN 2001 imports_cif; TJK-CAN 2002 imports_cif; TJK-COG 2001 imports_cif; TJK-FRA 2000 imports_cif; TJK-GIB 2006 imports_cif; TJK-HUN 2000 imports_cif; TJK-SVK 2001 imports_cif; TJK-BGR 2001 exports
- Observations flagged as estimated by the IMF (status 'e'): 1479
## Trade: sum over partner countries vs world total
- KAZ 1999 exports: partners sum to 93.1% of the world total
- KAZ 2000 exports: partners sum to 78.8% of the world total
- KAZ 2001 exports: partners sum to 90.2% of the world total
- KGZ 2025 exports: partners sum to 93.6% of the world total
- UZB 2016 exports: partners sum to 78.4% of the world total
- UZB 2017 exports: partners sum to 69.3% of the world total
- UZB 2018 exports: partners sum to 63.7% of the world total
- UZB 2019 exports: partners sum to 59.4% of the world total
- UZB 2020 exports: partners sum to 51.3% of the world total
- UZB 2021 exports: partners sum to 76.4% of the world total
- UZB 2022 exports: partners sum to 59.0% of the world total
- UZB 2023 exports: partners sum to 53.5% of the world total
- UZB 2024 exports: partners sum to 55.9% of the world total
- UZB 2025 exports: partners sum to 47.8% of the world total
- Weights use the world total as denominator, so trade with unidentified partners lowers the coverage of the partner index instead of being spread over known partners.

## Migrant stocks (UN DESA 2024)
- Largest unmapped destinations (all origins, all years): Australia/New Zealand; Libya; Mali; Bolivia (Plurinational State of); Dominican Republic; Liechtenstein; Costa Rica; Guinea
- Unmapped destinations are dropped from the remittance weights and the remaining weights are rescaled.

## Historical WEO forecasts file
- Last edition in the file: 2022 (S = April, F = September/October).
- Fall editions with a Tajikistan growth forecast: 1993 to 2022

## Coverage by variable and country (non-missing values)
| variable | country | first | last | n | gaps | min | max |
|---|---|---|---|---|---|---|---|
| current_account | CHN | 1997 | 2031 | 35 |  | 0.17 | 9.8 |
| current_account | KAZ | 1992 | 2031 | 40 |  | -51.66 | 7.3 |
| current_account | KGZ | 1992 | 2031 | 40 |  | -44.92 | 10.13 |
| current_account | RUS | 1992 | 2031 | 40 |  | -1.68 | 16.31 |
| current_account | TJK | 1992 | 2031 | 40 |  | -32.16 | 17.21 |
| current_account | UZB | 1992 | 2031 | 40 |  | -7.25 | 7.99 |
| debt_to_china_usd | TJK | 1993 | 2025 | 33 |  | 0.0 | 1187398391.1 |
| debt_to_russia_usd | TJK | 1993 | 2008 | 16 |  | 0.0 | 342868000.0 |
| exchange_rate | CHN | 1990 | 2025 | 36 |  | 4.78 | 8.62 |
| exchange_rate | KAZ | 1994 | 2025 | 32 |  | 35.54 | 521.04 |
| exchange_rate | KGZ | 1994 | 2025 | 32 |  | 10.82 | 87.86 |
| exchange_rate | RUS | 1993 | 2025 | 31 | 1994, 1995 | 0.99 | 92.55 |
| exchange_rate | TJK | 1992 | 2025 | 34 |  | 0.0 | 11.31 |
| exchange_rate | UZB | 1995 | 2025 | 19 | 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012 | 29.78 | 12652.29 |
| gdp_growth | CHN | 1980 | 2031 | 52 |  | 2.34 | 15.2 |
| gdp_growth | KAZ | 1993 | 2031 | 39 |  | -12.58 | 13.5 |
| gdp_growth | KGZ | 1993 | 2031 | 39 |  | -19.81 | 11.54 |
| gdp_growth | RUS | 1993 | 2031 | 39 |  | -12.7 | 10.05 |
| gdp_growth | TJK | 1993 | 2031 | 39 |  | -21.4 | 10.6 |
| gdp_growth | UZB | 1992 | 2031 | 40 |  | -11.1 | 9.5 |
| gdp_usd | CHN | 1980 | 2031 | 52 |  | 284457752000.0 | 28553668740000.0 |
| gdp_usd | KAZ | 1992 | 2031 | 40 |  | 2875117000.0 | 553358887000.0 |
| gdp_usd | KGZ | 1992 | 2031 | 40 |  | 664531000.0 | 39891738000.0 |
| gdp_usd | RUS | 1992 | 2031 | 40 |  | 71603087000.0 | 2861155843000.0 |
| gdp_usd | TJK | 1992 | 2031 | 40 |  | 291336000.0 | 31128667000.0 |
| gdp_usd | UZB | 1992 | 2031 | 40 |  | 4971244000.0 | 304124391000.0 |
| government_debt | CHN | 1995 | 2031 | 37 |  | 20.4 | 122.12 |
| government_debt | KAZ | 2002 | 2031 | 30 |  | 4.09 | 29.75 |
| government_debt | KGZ | 2000 | 2031 | 32 |  | 30.81 | 123.3 |
| government_debt | RUS | 1997 | 2031 | 35 |  | 7.45 | 135.19 |
| government_debt | TJK | 1998 | 2031 | 34 |  | 18.25 | 111.43 |
| government_debt | UZB | 1997 | 2031 | 35 |  | 5.39 | 40.38 |
| inflation | CHN | 1981 | 2031 | 51 |  | -1.4 | 24.21 |
| inflation | KAZ | 1993 | 2031 | 39 |  | 5.0 | 1662.27 |
| inflation | KGZ | 1993 | 2031 | 39 |  | 0.39 | 1086.19 |
| inflation | RUS | 1991 | 2031 | 41 |  | 2.88 | 1569.08 |
| inflation | TJK | 1993 | 2031 | 39 |  | 3.38 | 2600.72 |
| inflation | UZB | 1992 | 2031 | 40 |  | 5.0 | 1568.33 |
| ppg_external_debt_usd | CHN | 1990 | 2025 | 36 |  | 45515193868.2 | 554292253836.6 |
| ppg_external_debt_usd | KAZ | 1992 | 2025 | 34 |  | 25747844.5 | 44414705680.3 |
| ppg_external_debt_usd | KGZ | 1992 | 2025 | 34 |  | 5527412.0 | 5140959288.4 |
| ppg_external_debt_usd | RUS | 1992 | 2022 | 31 |  | 64571299242.1 | 273847740156.1 |
| ppg_external_debt_usd | TJK | 1992 | 2025 | 34 |  | 9731000.0 | 3164763003.5 |
| ppg_external_debt_usd | UZB | 1992 | 2025 | 34 |  | 59702042.9 | 47264391398.8 |
| remittances_gdp | CHN | 1990 | 2025 | 36 |  | 0.03 | 0.47 |
| remittances_gdp | KAZ | 1995 | 2025 | 31 |  | 0.01 | 0.57 |
| remittances_gdp | KGZ | 1993 | 2024 | 32 |  | 0.06 | 32.56 |
| remittances_gdp | RUS | 1994 | 2025 | 32 |  | 0.03 | 1.15 |
| remittances_gdp | TJK | 2002 | 2025 | 24 |  | 6.43 | 57.66 |
| remittances_gdp | UZB | 2005 | 2025 | 21 |  | 4.96 | 16.45 |
| remittances_usd | CHN | 1990 | 2025 | 36 |  | 195940000.0 | 33104675861.87 |
| remittances_usd | KAZ | 1995 | 2025 | 31 |  | 1200000.0 | 618039381.05 |
| remittances_usd | KGZ | 1993 | 2024 | 32 |  | 1001999.97 | 3266631755.95 |
| remittances_usd | RUS | 1994 | 2025 | 32 |  | 101500000.0 | 10432480000.0 |
| remittances_usd | TJK | 2002 | 2025 | 24 |  | 78562800.0 | 10183973155.34 |
| remittances_usd | UZB | 2005 | 2025 | 21 |  | 1026125524.12 | 21100902510.69 |

## Values outside plausible ranges (from 1998; flagged, not removed)
- None.

## Year-on-year changes above 50% in US$ level series (flagged)
- TJK remittances_usd 2003: 86%
- TJK remittances_usd 2004: 73%
- TJK remittances_usd 2005: 124%
- TJK remittances_usd 2006: 73%
- TJK remittances_usd 2007: 55%
- TJK remittances_usd 2008: 50%
- TJK remittances_usd 2022: 83%
- KGZ remittances_usd 2000: 96%
- KGZ remittances_usd 2001: 102%
- KGZ remittances_usd 2002: 568%
- KGZ remittances_usd 2003: 132%
- KGZ remittances_usd 2004: 155%
- KGZ remittances_usd 2005: 75%
- KGZ remittances_usd 2006: 51%
- KGZ remittances_usd 2008: 74%
- UZB remittances_usd 2008: 113%
- UZB remittances_usd 2010: 58%
- UZB remittances_usd 2022: 67%
- KAZ remittances_usd 2000: 1774%
- KAZ remittances_usd 2003: -62%
- KAZ remittances_usd 2007: 71%
- KAZ remittances_usd 2009: 58%
- KAZ remittances_usd 2012: 57%
- KAZ remittances_usd 2022: 55%
- RUS remittances_usd 2001: 97%
- RUS remittances_usd 2004: 98%
- RUS remittances_usd 2005: 56%
- RUS remittances_usd 2022: -66%
- CHN remittances_usd 1999: 54%
- CHN remittances_usd 2001: 59%
- CHN remittances_usd 2002: 95%
- CHN remittances_usd 2003: 97%
- CHN remittances_usd 2007: 58%
- CHN remittances_usd 2014: 68%
- UZB ppg_external_debt_usd 2019: 54%
- KAZ ppg_external_debt_usd 2010: 55%
- KAZ ppg_external_debt_usd 2012: 64%
- KAZ ppg_external_debt_usd 2013: 88%

