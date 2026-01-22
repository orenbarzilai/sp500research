import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from io_utils import CacheManager, HttpClient, RateLimiter

DEFAULT_CHANGES_URL = (
    "https://raw.githubusercontent.com/leonarditc/sp500-constituents-history/master/data/sp500_changes.csv"
)

REQUIRED_COLUMNS = {"date", "ticker", "action"}


@dataclass
class ConstituentsConfig:
    provider: str = "auto"
    csv_path: str | None = None
    cache_dir: str = "./cache"


def _validate_schema(frame: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Constituents CSV missing required columns: {sorted(missing)}")


def _load_changes_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    _validate_schema(frame)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any():
        raise ValueError("Invalid dates in constituents CSV")
    frame["ticker"] = frame["ticker"].str.upper().str.strip()
    frame["action"] = frame["action"].str.lower().str.strip()
    return frame


def _download_changes_csv(client: HttpClient, cache_dir: str) -> pd.DataFrame:
    logging.info("Attempting to download historical constituents changes from %s", DEFAULT_CHANGES_URL)
    cache_path = Path(cache_dir) / "sp500_changes.csv"
    if cache_path.exists():
        return _load_changes_csv(cache_path)

    response = client.session.get(DEFAULT_CHANGES_URL, timeout=30)
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(response.text, encoding="utf-8")
    return _load_changes_csv(cache_path)


def load_constituents_changes(config: ConstituentsConfig) -> pd.DataFrame:
    cache = CacheManager(config.cache_dir)
    client = HttpClient(cache, RateLimiter())
    if config.provider == "csv":
        if not config.csv_path:
            raise ValueError("CSV provider requires --constituents-csv")
        return _load_changes_csv(Path(config.csv_path))

    if config.provider == "auto":
        try:
            return _download_changes_csv(client, config.cache_dir)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Auto provider failed. Supply --constituents-provider csv and --constituents-csv path."
            ) from exc

    raise ValueError(f"Unknown constituents provider: {config.provider}")


def constituents_for_year(changes: pd.DataFrame, year: int) -> List[str]:
    end_date = pd.Timestamp(year=year, month=12, day=31)
    filtered = changes[changes["date"] <= end_date].sort_values("date")
    members: set[str] = set()
    for _, row in filtered.iterrows():
        action = row["action"]
        ticker = row["ticker"]
        if action in {"add", "added", "include", "included"}:
            members.add(ticker)
        elif action in {"remove", "removed", "exclude", "deleted"}:
            members.discard(ticker)
    return sorted(members)


def get_constituents_by_year(changes: pd.DataFrame, years: Iterable[int]) -> dict[int, List[str]]:
    result: dict[int, List[str]] = {}
    for year in years:
        result[year] = constituents_for_year(changes, year)
        logging.info("Year %s constituents: %s", year, len(result[year]))
    return result
