from typing import Any, Iterable

import pandas as pd


Record = dict[str, Any]
Records = list[Record]


def records(frame: pd.DataFrame) -> Records:
    return frame.to_dict("records")


def split_tokens(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    return [
        token.strip()
        for token in str(value).replace(",", ";").split(";")
        if token.strip()
    ]


def stable_join(values: Iterable[str]) -> str:
    return ";".join(sorted(set(values)))
