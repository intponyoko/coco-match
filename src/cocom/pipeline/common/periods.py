import math

import pandas as pd

from cocom.pipeline.common.table import records


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("weight total must be positive")
    return {key: value / total for key, value in weights.items() if value > 0}


def allocate_int(total: int, weights: dict[str, float]) -> dict[str, int]:
    normalized = normalize_weights(weights)
    raw = {key: total * weight for key, weight in normalized.items()}
    allocated = {key: int(math.floor(value)) for key, value in raw.items()}
    remainder = total - sum(allocated.values())
    order = sorted(raw, key=lambda key: raw[key] - allocated[key], reverse=True)
    for key in order[:remainder]:
        allocated[key] += 1
    return allocated


def fiscal_period_end_code(
    fiscal_periods: pd.DataFrame,
    start_period_code: str,
    months: int,
) -> str:
    periods = records(fiscal_periods.sort_values("start"))
    start = pd.Timestamp(start_period_code)
    end_exclusive = start + pd.DateOffset(months=months)
    eligible = [
        str(period["code"])
        for period in periods
        if start <= pd.Timestamp(period["start"]) < end_exclusive
    ]
    if eligible:
        return eligible[-1]
    return start_period_code


def fiscal_period_code_by_offset(
    fiscal_periods: pd.DataFrame,
    start_period_code: str,
    offset_months: int,
) -> str:
    periods = records(fiscal_periods.sort_values("start"))
    start = pd.Timestamp(start_period_code)
    target = start + pd.DateOffset(months=offset_months)
    eligible = [
        str(period["code"])
        for period in periods
        if pd.Timestamp(period["start"]) <= target
    ]
    if eligible:
        return eligible[-1]
    return start_period_code


def fiscal_period_count(
    fiscal_periods: pd.DataFrame,
    start_period_code: str,
    end_period_code: str,
) -> int:
    start = pd.Timestamp(start_period_code)
    end = pd.Timestamp(end_period_code)
    return sum(
        1
        for period in records(fiscal_periods)
        if start <= pd.Timestamp(period["start"]) <= end
    )
