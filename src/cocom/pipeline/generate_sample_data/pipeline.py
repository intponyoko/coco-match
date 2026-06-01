from pathlib import Path

import pandas as pd

from cocom.pipeline.common.base import StatelessPipeline
from cocom.pipeline.common.io import PipelinePayload
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths
from .io import (
    GenerateDataInput,
    GenerateDataOutput,
    GenerateSampleDataRequest,
)
from .generator import (
    generate_sample_rows,
    load_config,
    parse_args,
    validate_generated_rows,
    write_generated_rows,
)


def load_role_demand_rows(config_path: Path) -> list[dict] | None:
    role_demand_path = config_path.parent / "knowledge" / "past_cases" / "past_case_roles.csv"
    if not role_demand_path.exists() and len(config_path.parents) >= 3:
        role_demand_path = (
            config_path.parents[2] / "knowledge" / "past_cases" / "past_case_roles.csv"
        )
    if not role_demand_path.exists():
        return None
    return pd.read_csv(role_demand_path).to_dict("records")


def run_generate_data(pipeline_input: GenerateDataInput) -> GenerateDataOutput:
    config = load_config(pipeline_input.config_path)
    generated_rows = generate_sample_rows(
        config=config,
        rows=pipeline_input.rows,
        staffs=pipeline_input.staffs,
        fiscal_months=pipeline_input.fiscal_months,
        staff_career_skills_per_staff=pipeline_input.staff_career_skills_per_staff,
        role_demand_rows=pipeline_input.role_demand_rows,
    )
    tables = validate_generated_rows(generated_rows)
    return GenerateDataOutput(tables=tables)


class GenerateSampleDataPipeline(
    StatelessPipeline[GenerateDataInput, GenerateDataOutput]
):
    name = "generate_sample_data"

    def run(self, pipeline_input: GenerateDataInput) -> GenerateDataOutput:
        return run_generate_data(pipeline_input)

    def input_from_request(
        self,
        request: GenerateSampleDataRequest | None = None,
        paths: PipelinePaths | None = None,
    ) -> GenerateDataInput:
        resolved_paths = paths or default_pipeline_paths()
        resolved_request = request or GenerateSampleDataRequest()
        config_path = (
            resolved_request.config_path or resolved_paths.sample_data_config_path
        )
        return GenerateDataInput(
            config_path=config_path,
            rows=resolved_request.rows,
            staffs=resolved_request.staffs,
            fiscal_months=resolved_request.fiscal_months,
            staff_career_skills_per_staff=(
                resolved_request.staff_career_skills_per_staff
            ),
            role_demand_rows=load_role_demand_rows(config_path),
        )

    def output_to_payload(
        self,
        output: GenerateDataOutput,
        base: PipelinePayload,
    ) -> PipelinePayload:
        return PipelinePayload(
            tables={**base.tables, **output.tables},
            config=base.config,
            metadata={"stage": "sample_data_ready"},
            approvals=base.approvals,
        )

    def write_output(
        self,
        output: GenerateDataOutput,
        paths: PipelinePaths | None = None,
    ) -> None:
        resolved_paths = paths or default_pipeline_paths()
        write_sample_tables(resolved_paths.sample_data_dir, output.tables)


def run_generate_sample_data(
    request: GenerateSampleDataRequest | None = None,
    paths: PipelinePaths | None = None,
) -> PipelinePayload:
    pipeline = GenerateSampleDataPipeline()
    pipeline_input = pipeline.input_from_request(request, paths)
    output = pipeline.run(pipeline_input)
    return pipeline.output_to_payload(output, PipelinePayload(tables={}))


def write_sample_tables(output_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)


def main() -> None:
    paths = default_pipeline_paths()
    args = parse_args()
    output = run_generate_data(
        GenerateDataInput(
            config_path=args.config,
            rows=args.rows,
            staffs=args.staffs,
            fiscal_months=args.fiscal_months,
            staff_career_skills_per_staff=args.staff_career_skills_per_staff,
            role_demand_rows=load_role_demand_rows(args.config),
        )
    )
    write_generated_rows(
        {name: table.to_dict("records") for name, table in output.tables.items()},
        paths.sample_data_dir,
    )

    print(f"Generated sample data in {paths.sample_data_dir}")
    for name, table in output.tables.items():
        print(f"- {name}: {len(table)} rows")
