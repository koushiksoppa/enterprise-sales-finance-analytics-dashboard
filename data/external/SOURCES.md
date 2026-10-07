# External data sources

The files in this folder are **real, published data**, unlike `data/raw/` and `data/processed/`, which are synthetic.

**Publisher:** FADA (Federation of Automobile Dealers Associations, India), monthly *Vehicle Retail Data* press releases. FADA collects retail registrations with the Ministry of Road Transport & Highways from about 1,468 of 1,469 RTOs.

| Report | Covers | Link |
|---|---|---|
| February 2026 | Feb 2026 vs Feb 2025 | [PDF](https://fada.in/images/press-release/169a8f8bd834feFADA%20releases%20February%202026%20Vehicle%20Retail%20Data.pdf) |
| March 2026 (with FY26) | Mar 2026 vs Mar 2025 | [PDF](https://fada.in/images/press-release/169d329fc83770FADA%20releases%20FY%202026%20and%20March%202026%20Vehicle%20Retail%20Data.pdf) |
| April 2026 | Apr 2026 vs Apr 2025 | [PDF](https://fada.in/images/press-release/169f9644078df6FADA%20Releases%20April%202026%20Vehicle%20Retail%20Data.pdf) |
| May 2026 | May 2026 vs May 2025 | [PDF](https://fada.in/images/press-release/16a26372eac5e2FADA%20Releases%20May%202026%20Vehicle%20Retail%20Data.pdf) |
| June 2026 | Jun 2026 vs Jun 2025 | [PDF](https://fada.in/images/press-release/16a74145d12b0dFADA%20Releases%20June%202026%20Vehicle%20Retail%20Data.pdf) |
| July 2026 | Jul 2026 vs Jul 2025 | [PDF](https://fada.in/images/press-release/16a7445b80cd73FADA%20Releases%20July%202026%20Vehicle%20Retail%20Data.pdf) |
| August 2026 | Aug 2026 vs Aug 2025 | [PDF](https://fada.in/images/press-release/16a9e2ff1d6502FADA%20Releases%20August%202026%20Vehicle%20Retail%20Data.pdf) |
| September 2026 | Sep 2026 vs Sep 2025 | [PDF](https://fada.in/images/press-release/16ac46ad2e0388FADA%20Releases%20September%202026%20Vehicle%20Retail%20Data.pdf) |

## Files

| File | Contents | Taken from |
|---|---|---|
| `fada_oem_retail_2026.csv` | Monthly retail units per OEM, passenger vehicles (PV) and two-wheelers (2W), current month and same month of the previous year | "OEM wise Market Share Data" annexure tables |
| `fada_segment_totals_2026.csv` | Total retail units per segment per month | Total row of the same tables |
| `fada_ev_share_2026.csv` | EV share of retail per segment per month | "Fuel Wise Vehicle Retail Data" table |

## How the data was extracted and checked

- The text of each PDF was extracted programmatically (pdf.js), and the OEM tables were parsed row by row.
- **Every row was checked against its own published market share** (units ÷ total within ±0.01 percentage points).
- **Every month's OEM rows sum exactly to FADA's published segment total**, for both years. `python/auto_retail_analysis.py` re-runs this check on every load and stops if it fails.
- Group sub-rows (for example Mercedes-Benz India and Mercedes-Benz AG under Mercedes-Benz Group) were dropped so each company is counted once at group level.
- EV shares were cross-checked across consecutive reports, since each report also restates the previous month (for example August's PV EV share of 7.63% appears identically in the August and September reports).

## Limits

- All-India only: FADA publishes no OEM-by-state split.
- OEMs below FADA's display threshold are pooled into "Others". Altigreen (electric three-wheeler cargo) is not listed separately.
- Months covered: February–September 2026. Earlier 2026 reports were not on FADA's current press-release page.
