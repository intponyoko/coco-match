import tomllib
from pathlib import Path
from typing import Any

def merge_config(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = [*merged[key], *value]
        else:
            merged[key] = value
    return merged


def load_config(path: Path) -> dict[str, Any]:
    if path.is_dir():
        config: dict[str, Any] = {}
        for toml_path in sorted(path.glob("*.toml")):
            with toml_path.open("rb") as f:
                config = merge_config(config, tomllib.load(f))
        return config

    with path.open("rb") as f:
        return tomllib.load(f)
