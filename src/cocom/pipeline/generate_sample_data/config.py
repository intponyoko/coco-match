import math
from typing import Any, cast


def config_table(config: dict[str, Any], key: str) -> dict[str, Any]:
    return cast(dict[str, Any], config[key])


def config_list(config: dict[str, Any], key: str) -> list[str]:
    masters = config_table(config, "masters")
    return cast(list[str], masters[key])


def config_str_lists(config: dict[str, Any], key: str) -> dict[str, list[str]]:
    return cast(dict[str, list[str]], config[key])


def positive_int(name: str, value: int) -> int:
    if value < 1:
        raise ValueError(f"{name} must be positive: {value}")
    return value


def allocate_int(total: int, weights: dict[str, float]) -> dict[str, int]:
    weight_total = sum(weights.values())
    if weight_total <= 0:
        raise ValueError("weight total must be positive")
    raw = {key: total * weight / weight_total for key, weight in weights.items()}
    allocated = {key: math.floor(value) for key, value in raw.items()}
    remainder = total - sum(allocated.values())
    order = sorted(raw, key=lambda key: raw[key] - allocated[key], reverse=True)
    for key in order[:remainder]:
        allocated[key] += 1
    return allocated
