from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from io_utils import ensure_dir


@dataclass
class MetricsConfig:
    out_dir: str


def compute_per_employee(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["employees"] = pd.to_numeric(panel["employees"], errors="coerce")
    panel["revenue_usd"] = pd.to_numeric(panel["revenue_usd"], errors="coerce")
    panel["net_income_usd"] = pd.to_numeric(panel["net_income_usd"], errors="coerce")

    valid = panel["employees"].notna() & (panel["employees"] > 0)
    panel["revenue_per_employee"] = np.where(
        valid & panel["revenue_usd"].notna(), panel["revenue_usd"] / panel["employees"], np.nan
    )
    panel["earnings_per_employee"] = np.where(
        valid & panel["net_income_usd"].notna(), panel["net_income_usd"] / panel["employees"], np.nan
    )
    panel["used_in_metrics"] = panel["revenue_per_employee"].notna() & panel["earnings_per_employee"].notna()
    return panel


def aggregate_yearly(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = []
    for year, group in panel.groupby("year"):
        coverage_total = len(group)
        used = group[group["used_in_metrics"]]
        coverage_used = len(used)
        coverage_pct = coverage_used / coverage_total if coverage_total else 0
        grouped.append(
            {
                "year": year,
                "mean_revenue_per_employee": used["revenue_per_employee"].mean(),
                "median_revenue_per_employee": used["revenue_per_employee"].median(),
                "mean_earnings_per_employee": used["earnings_per_employee"].mean(),
                "median_earnings_per_employee": used["earnings_per_employee"].median(),
                "coverage_n_total": coverage_total,
                "coverage_n_used": coverage_used,
                "coverage_pct_used": coverage_pct,
            }
        )
    return pd.DataFrame(grouped).sort_values("year")


def save_outputs(metrics: pd.DataFrame, config: MetricsConfig) -> None:
    out_dir = ensure_dir(config.out_dir)
    csv_path = Path(out_dir) / "sp500_rev_earn_per_employee_by_year.csv"
    xlsx_path = Path(out_dir) / "sp500_rev_earn_per_employee_by_year.xlsx"
    metrics.to_csv(csv_path, index=False)
    with pd.ExcelWriter(xlsx_path) as writer:
        metrics.to_excel(writer, sheet_name="metrics", index=False)
