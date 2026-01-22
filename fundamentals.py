import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from io_utils import CacheManager, HttpClient, RateLimiter

SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

REVENUE_TAGS = ["Revenues", "SalesRevenueNet"]
INCOME_TAGS = ["NetIncomeLoss"]
EMPLOYEE_TAGS = ["EntityNumberOfEmployees"]


@dataclass
class ApiConfig:
    use_sec: bool = True
    api_provider: str = "none"
    api_key: Optional[str] = None


@dataclass
class FundamentalsResult:
    revenue_usd: Optional[float]
    net_income_usd: Optional[float]
    employees: Optional[float]
    revenue_tag: Optional[str]
    income_tag: Optional[str]
    employees_tag: Optional[str]
    revenue_source: str
    income_source: str
    employees_source: str
    fiscal_year_end: Optional[str]


class SecClient:
    def __init__(self, cache_dir: str) -> None:
        self.cache = CacheManager(cache_dir)
        self.http = HttpClient(self.cache, RateLimiter())
        self.ticker_map = self._load_ticker_map()

    def _load_ticker_map(self) -> Dict[str, str]:
        payload = self.http.get_json(SEC_TICKER_URL, cache_key="sec_ticker_map")
        mapping: Dict[str, str] = {}
        for entry in payload.values():
            ticker = entry["ticker"].upper()
            cik_str = str(entry["cik_str"]).zfill(10)
            mapping[ticker] = cik_str
        return mapping

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        return self.ticker_map.get(ticker.upper())

    def company_facts(self, cik: str) -> Dict[str, Any]:
        url = SEC_COMPANYFACTS_URL.format(cik=cik)
        return self.http.get_json(url, cache_key=f"companyfacts:{cik}")


class FundamentalsProvider:
    def __init__(self, cache_dir: str, api_config: ApiConfig) -> None:
        self.cache_dir = cache_dir
        self.api_config = api_config
        self.sec = SecClient(cache_dir) if api_config.use_sec else None

    def _select_fact(self, facts: Dict[str, Any], tags: list[str], year: int) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        for tag in tags:
            if tag not in us_gaap:
                continue
            items = us_gaap[tag].get("units", {}).get("USD", [])
            candidates = [item for item in items if item.get("fy") == year and item.get("form") == "10-K"]
            if not candidates:
                candidates = [item for item in items if item.get("fy") == year]
            if candidates:
                candidates.sort(key=lambda x: x.get("filed", ""), reverse=True)
                return candidates[0].get("val"), tag, candidates[0].get("end")
        return None, None, None

    def _select_employee(self, facts: Dict[str, Any], year: int) -> Tuple[Optional[float], Optional[str], Optional[str]]:
        dei = facts.get("facts", {}).get("dei", {})
        for tag in EMPLOYEE_TAGS:
            if tag not in dei:
                continue
            items = dei[tag].get("units", {}).get("pure", [])
            candidates = [item for item in items if item.get("fy") == year and item.get("form") in {"10-K", "20-F"}]
            if not candidates:
                candidates = [item for item in items if item.get("fy") == year]
            if candidates:
                candidates.sort(key=lambda x: x.get("filed", ""), reverse=True)
                return candidates[0].get("val"), tag, candidates[0].get("end")
        return None, None, None

    def get_fundamentals(self, ticker: str, year: int) -> FundamentalsResult:
        if not self.sec:
            return FundamentalsResult(
                revenue_usd=None,
                net_income_usd=None,
                employees=None,
                revenue_tag=None,
                income_tag=None,
                employees_tag=None,
                revenue_source="none",
                income_source="none",
                employees_source="none",
                fiscal_year_end=None,
            )

        cik = self.sec.ticker_to_cik(ticker)
        if not cik:
            logging.warning("No CIK for ticker %s", ticker)
            return FundamentalsResult(
                revenue_usd=None,
                net_income_usd=None,
                employees=None,
                revenue_tag=None,
                income_tag=None,
                employees_tag=None,
                revenue_source="sec",
                income_source="sec",
                employees_source="sec",
                fiscal_year_end=None,
            )

        facts = self.sec.company_facts(cik)
        revenue, revenue_tag, rev_end = self._select_fact(facts, REVENUE_TAGS, year)
        income, income_tag, inc_end = self._select_fact(facts, INCOME_TAGS, year)
        employees, employees_tag, emp_end = self._select_employee(facts, year)
        fiscal_end = rev_end or inc_end or emp_end

        return FundamentalsResult(
            revenue_usd=revenue,
            net_income_usd=income,
            employees=employees,
            revenue_tag=revenue_tag,
            income_tag=income_tag,
            employees_tag=employees_tag,
            revenue_source="sec",
            income_source="sec",
            employees_source="sec",
            fiscal_year_end=fiscal_end,
        )


def validate_numeric_series(series: pd.Series, non_negative: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if non_negative:
        values = values.where(values >= 0)
    return values
