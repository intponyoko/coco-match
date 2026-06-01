from typing import Any, cast

import pandas as pd

from .config import (
    allocate_int,
    config_table,
)


def generate_sales_plans(
    config: dict[str, Any],
    industries: list[dict],
    fiscal_periods: list[dict],
) -> list[dict]:
    sales_plan_config = config_table(config, "sales_plan_generation")
    sales_plan_months = int(sales_plan_config["sales_plan_months"])
    active_min = int(sales_plan_config["active_industries_per_period_min"])
    active_max = int(sales_plan_config["active_industries_per_period_max"])
    if active_max < active_min:
        raise ValueError(
            "active_industries_per_period_max must be greater than or equal to "
            "active_industries_per_period_min"
        )
    active_max = min(active_max, len(industries))
    active_min = min(active_min, active_max)
    annual_target_revenue = int(sales_plan_config["annual_target_revenue"])
    period_growth_weight = float(sales_plan_config["period_growth_weight"])
    industry_weight_step = float(sales_plan_config["industry_weight_step"])
    seasonal_industry_weight_step = float(
        sales_plan_config["seasonal_industry_weight_step"]
    )
    monthly_demand_weight = cast(
        dict[str, float],
        sales_plan_config["monthly_demand_weight"],
    )
    industry_demand_weight = cast(
        dict[str, float],
        sales_plan_config.get("industry_demand_weight", {}),
    )

    weighted_rows = []
    first_period_start = pd.Timestamp(fiscal_periods[0]["start"])
    sales_plan_end = first_period_start + pd.DateOffset(months=sales_plan_months)
    for period_index, period in enumerate(fiscal_periods):
        period_start = pd.Timestamp(period["start"])
        if period_start >= sales_plan_end:
            continue
        if period_start.day != 1:
            continue
        month = period_start.month
        month_weight = float(monthly_demand_weight.get(str(month), 1.0))
        active_count = active_min + period_index % (active_max - active_min + 1)
        if month_weight >= 1.2:
            active_count = active_max
        elif month_weight <= 0.85:
            active_count = active_min
        start_index = (period_index * 2) % len(industries)
        active_industries = [
            industries[(start_index + offset) % len(industries)]
            for offset in range(active_count)
        ]
        for local_index, industry in enumerate(active_industries):
            industry_index = industries.index(industry)
            seasonal_industry_adjustment = (
                (period_index + industry_index) % 4 - 1
            ) * seasonal_industry_weight_step
            weight = max(
                0.01,
                (
                    1.0
                    + period_index * period_growth_weight
                    + local_index * industry_weight_step
                    + seasonal_industry_adjustment
                )
                * month_weight,
            )
            industry_multiplier = float(
                industry_demand_weight.get(
                    str(industry["name"]),
                    industry_demand_weight.get(str(industry["code"]), 1.0),
                )
            )
            weight *= max(0.01, industry_multiplier)
            weighted_rows.append(
                {
                    "code": f"SP-{period['code']}-{industry['code']}",
                    "industry_code": industry["code"],
                    "period_code": period["code"],
                    "weight": weight,
                }
            )
    allocated_revenues = allocate_int(
        annual_target_revenue,
        {str(row["code"]): float(row["weight"]) for row in weighted_rows},
    )
    return [
        {
            "code": row["code"],
            "industry_code": row["industry_code"],
            "period_code": row["period_code"],
            "target_revenue": allocated_revenues[str(row["code"])],
        }
        for row in weighted_rows
    ]
