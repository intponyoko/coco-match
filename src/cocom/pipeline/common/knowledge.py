from pathlib import Path

import pandas as pd

from cocom.pipeline.common.csv_io import read_tables


def read_past_case_data(knowledge_dir: Path) -> dict[str, pd.DataFrame]:
    return read_tables(
        knowledge_dir / "past_cases",
        ["past_cases", "past_case_roles", "past_case_links"],
    )
