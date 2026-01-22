import argparse
import logging
from typing import List

from build_panel import PanelConfig, build_panel
from fundamentals import ApiConfig
from io_utils import configure_logging
from metrics import MetricsConfig, aggregate_yearly, compute_per_employee, save_outputs
from sp500_constituents import ConstituentsConfig, get_constituents_by_year, load_constituents_changes


def parse_years(start_year: int, end_year: int) -> List[int]:
    if start_year > end_year:
        raise ValueError("start-year must be <= end-year")
    return list(range(start_year, end_year + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description="S&P 500 revenue/earnings per employee analysis")
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--cache-dir", type=str, default="./cache")
    parser.add_argument("--out-dir", type=str, default="./outputs")
    parser.add_argument("--constituents-provider", type=str, default="auto", choices=["auto", "csv"])
    parser.add_argument("--constituents-csv", type=str, default=None)
    parser.add_argument("--use-sec", type=str, default="true")
    parser.add_argument("--api-provider", type=str, default="none")
    parser.add_argument("--api-key", type=str, default=None)
    args = parser.parse_args()

    configure_logging(logging.INFO)
    years = parse_years(args.start_year, args.end_year)

    constituents_config = ConstituentsConfig(
        provider=args.constituents_provider,
        csv_path=args.constituents_csv,
        cache_dir=args.cache_dir,
    )
    changes = load_constituents_changes(constituents_config)
    constituents_by_year = get_constituents_by_year(changes, years)

    api_config = ApiConfig(
        use_sec=str(args.use_sec).lower() in {"true", "1", "yes"},
        api_provider=args.api_provider,
        api_key=args.api_key,
    )

    panel_config = PanelConfig(
        years=years,
        constituents_by_year=constituents_by_year,
        cache_dir=args.cache_dir,
        out_dir=args.out_dir,
        api_config=api_config,
    )
    panel = build_panel(panel_config)
    panel = compute_per_employee(panel)
    metrics = aggregate_yearly(panel)
    save_outputs(metrics, MetricsConfig(out_dir=args.out_dir))

    logging.info("Completed metrics for %s years", len(metrics))


if __name__ == "__main__":
    main()
