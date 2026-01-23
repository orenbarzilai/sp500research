<!--
Data sources used:
- Historical constituents: auto attempts to download a public S&P 500 changes CSV (adds/removes). If unavailable, provide your own CSV via --constituents-provider csv.
- Revenue/net income: SEC XBRL companyfacts (us-gaap:Revenues or SalesRevenueNet; NetIncomeLoss).
- Employees: SEC XBRL DEI tag EntityNumberOfEmployees. If missing, leave null and record provenance.
Fallbacks:
- Constituents: user-provided CSV with columns date, ticker, action.
- Fundamentals: optional API providers can be wired in (not implemented beyond SEC scaffolding).
-->

# S&P 500 Revenue & Earnings per Employee (2010–2025)

This project builds a reproducible panel dataset of S&P 500 constituents by year, fetches annual revenue, net income, and employee counts, and computes per-employee aggregates (mean/median) across companies.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Data sources

- **Historical constituents**: The default `auto` provider attempts to download a public changes file (adds/removes) for S&P 500 membership. If it fails or you prefer your own data, pass `--constituents-provider csv` and `--constituents-csv` with a file that has columns: `date`, `ticker`, `action`.
- **Fundamentals**: The SEC XBRL `companyfacts` endpoint provides annual revenue and net income for 10-K filings and the DEI employee tag.

### Constituents CSV schema

Your CSV should look like:

| date | ticker | action | company_name |
| --- | --- | --- | --- |
| 2014-09-21 | ABC | add | ABC Corp |
| 2015-01-15 | XYZ | remove | XYZ Inc |

`company_name` is optional. `action` should be `add`/`remove` (case-insensitive). The loader will interpret close variants like `added`/`removed`.

## Usage

```bash
python main.py \
  --start-year 2010 \
  --end-year 2025 \
  --cache-dir ./cache \
  --out-dir ./outputs \
  --constituents-provider auto \
  --use-sec true
```

To use your own constituents file:

```bash
python main.py \
  --start-year 2010 \
  --end-year 2025 \
  --constituents-provider csv \
  --constituents-csv /path/to/sp500_changes.csv
```

## Outputs

- `outputs/panel_{year}.csv`: per-year panel dataset
- `outputs/panel_all_years.parquet`: combined panel
- `outputs/sp500_rev_earn_per_employee_by_year.csv`
- `outputs/sp500_rev_earn_per_employee_by_year.xlsx`

## Caveats

- Employee counts are frequently missing in SEC filings. Missing values are left null and excluded from per-employee calculations.
- Revenue is expected to be non-negative; net income can be negative.
- Fiscal year alignment uses the `fy` field from the SEC facts. If a company has multiple filings in a year, the latest filed entry is used.

## Extending data providers

The `fundamentals.py` module is structured to allow optional API providers. You can add providers (FMP, Polygon, Alpha Vantage, EODHD) and switch via CLI flags. Ensure provider implementations return the same fields for consistent downstream processing.
