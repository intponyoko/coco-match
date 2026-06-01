from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelinePaths:
    root_dir: Path
    sample_data_config_path: Path
    sample_data_dir: Path
    planning_data_dir: Path
    knowledge_data_dir: Path
    opportunity_config_dir: Path


def default_pipeline_paths() -> PipelinePaths:
    root_dir = Path(__file__).resolve().parents[4]
    return PipelinePaths(
        root_dir=root_dir,
        sample_data_config_path=(
            root_dir / "configs" / "sample_data" / "generation.toml"
        ),
        sample_data_dir=root_dir / "data" / "sample",
        planning_data_dir=root_dir / "data" / "planning",
        knowledge_data_dir=root_dir / "knowledge",
        opportunity_config_dir=root_dir / "configs" / "opportunity_creation",
    )
