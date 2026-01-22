import pandas as pd
import pytest

from main import parse_years
from metrics import compute_per_employee
from sp500_constituents import _validate_schema


def test_parse_years():
    assert parse_years(2010, 2012) == [2010, 2011, 2012]
    with pytest.raises(ValueError):
        parse_years(2020, 2010)


def test_constituents_schema_validation():
    df = pd.DataFrame({"date": ["2020-01-01"], "ticker": ["ABC"], "action": ["add"]})
    _validate_schema(df)
    df_bad = pd.DataFrame({"date": ["2020-01-01"], "ticker": ["ABC"]})
    with pytest.raises(ValueError):
        _validate_schema(df_bad)


def test_per_employee_guards():
    panel = pd.DataFrame(
        {
            "year": [2020, 2020, 2020],
            "revenue_usd": [100.0, 200.0, None],
            "net_income_usd": [10.0, None, 5.0],
            "employees": [10, 0, 5],
        }
    )
    result = compute_per_employee(panel)
    assert result.loc[0, "revenue_per_employee"] == 10.0
    assert result.loc[0, "earnings_per_employee"] == 1.0
    assert pd.isna(result.loc[1, "revenue_per_employee"])
    assert pd.isna(result.loc[1, "earnings_per_employee"])
    assert pd.isna(result.loc[2, "revenue_per_employee"])
