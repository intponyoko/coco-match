import argparse
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from .paths import DEFAULT_CONFIG_PATH


@dataclass(frozen=True)
class GenerateSampleDataRequest:
    rows: int | None = None
    staffs: int | None = None
    fiscal_months: int | None = None
    staff_career_skills_per_staff: int | None = None
    config_path: Path | None = None


@dataclass(frozen=True)
class GenerateDataInput:
    config_path: Path
    rows: int | None = None
    staffs: int | None = None
    fiscal_months: int | None = None
    staff_career_skills_per_staff: int | None = None
    role_demand_rows: list[dict] | None = None


@dataclass(frozen=True)
class GenerateDataOutput:
    tables: dict[str, pd.DataFrame]


def load_config(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate schema-valid sample CSVs.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the dummy data TOML config.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=None,
        help="Set the row count for generated non-fixed row-count tables.",
    )
    parser.add_argument(
        "--staffs",
        type=int,
        default=None,
        help="Set the row count for staffs.",
    )
    parser.add_argument(
        "--fiscal-months",
        type=int,
        default=None,
        help="Set how many months of weekly fiscal periods to generate from 2026-01-01.",
    )
    parser.add_argument(
        "--staff-career-skills-per-staff",
        type=int,
        default=None,
        help="Set how many skills each staff member declares per career year.",
    )
    return parser.parse_args()


def validate_sample(
    schema: type[pa.DataFrameModel],
    rows: list[dict],
) -> pd.DataFrame:
    columns = list(schema.to_schema().columns.keys())
    return schema.validate(pd.DataFrame(rows, columns=columns))


def write_sample(
    name: str,
    schema: type[pa.DataFrameModel],
    rows: list[dict],
    output_dir: Path,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = validate_sample(schema, rows)
    frame.to_csv(output_dir / f"{name}.csv", index=False)
    return frame
