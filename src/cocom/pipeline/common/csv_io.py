from pathlib import Path
from typing import Iterable

import pandas as pd


def read_csv(data_dir: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(data_dir / f"{name}.csv")


def read_tables(data_dir: Path, names: Iterable[str]) -> dict[str, pd.DataFrame]:
    return {name: read_csv(data_dir, name) for name in names}


def write_tables(output_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)
