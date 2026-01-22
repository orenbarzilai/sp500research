import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd
from tqdm import tqdm

from fundamentals import ApiConfig, FundamentalsProvider
from io_utils import ensure_dir


@dataclass
class PanelConfig:
    years: Iterable[int]
    constituents_by_year: dict[int, List[str]]
    cache_dir: str
    out_dir: str
    api_config: ApiConfig


def build_panel(config: PanelConfig) -> pd.DataFrame:
    provider = FundamentalsProvider(config.cache_dir, config.api_config)
    all_rows = []

    for year in config.years:
        tickers = config.constituents_by_year.get(year, [])
        rows = []
        logging.info("Fetching fundamentals for %s tickers in %s", len(tickers), year)
        for ticker in tqdm(tickers, desc=f"{year} fundamentals"):
            result = provider.get_fundamentals(ticker, year)
            rows.append(
                {
                    "year": year,
                    "ticker": ticker,
                    "cik": provider.sec.ticker_to_cik(ticker) if provider.sec else None,
                    "company_name": None,
                    "revenue_usd": result.revenue_usd,
                    "net_income_usd": result.net_income_usd,
                    "employees": result.employees,
                    "revenue_tag_used": result.revenue_tag,
                    "income_tag_used": result.income_tag,
                    "employees_tag_used": result.employees_tag,
                    "data_source_revenue": result.revenue_source,
                    "data_source_income": result.income_source,
                    "data_source_employees": result.employees_source,
                    "fiscal_year_end_date": result.fiscal_year_end,
                    "missing_revenue": result.revenue_usd is None,
                    "missing_income": result.net_income_usd is None,
                    "missing_employees": result.employees is None,
                }
            )
        frame = pd.DataFrame(rows)
        year_path = ensure_dir(config.out_dir) / f"panel_{year}.csv"
        frame.to_csv(year_path, index=False)
        all_rows.append(frame)

    combined = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    combined_path = ensure_dir(config.out_dir) / "panel_all_years.parquet"
    if not combined.empty:
        combined.to_parquet(combined_path, index=False)
    return combined
