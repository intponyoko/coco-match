from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[4]
OUTPUT_DIR = ROOT_DIR / "data" / "sample"
DEFAULT_CONFIG_PATH = ROOT_DIR / "configs" / "sample_data" / "generation.toml"
ROW_COUNT_KEYS = ["staffs"]
