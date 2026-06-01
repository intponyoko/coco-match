from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = APP_DIR.parents[1]
SAMPLE_DIR = ROOT_DIR / "data" / "sample"
PLANNING_DIR = ROOT_DIR / "data" / "planning"
OUTPUT_PATH = APP_DIR / "public" / "data" / "app-data.json"

SAMPLE_TABLES = [
    "sales_plans",
    "staffs",
    "titles",
    "departments",
    "roles",
    "role_skills",
    "staff_career",
    "accounts",
    "industries",
    "solutions",
    "skills",
    "fiscal_periods",
]

PLANNING_TABLES = [
    "theme_recommendations",
    "project_sizing_recommendations",
    "request_recommendations",
    "opportunities",
    "opportunity_requests",
    "opportunity_assignments",
    "matching_trace",
    "staff_utilization",
    "allocation_trace",
    "knowledge_nodes",
    "knowledge_edges",
    "project_knowledge_nodes",
    "project_knowledge_edges",
    "opportunity_recommendations",
    "account_recommendations",
    "retrieved_evidence_chunks",
    "proposal_runs",
    "proposal_diagnostics",
    "consistency_metrics",
    "project_review_issues",
]

NUMERIC_SUFFIXES = (
    "_revenue",
    "_score",
    "_mean",
    "_months",
    "_percentage",
    "_count",
    "_price",
    "_level",
    "_rank",
    "_slot",
    "_slots",
    "_gap",
)

NUMERIC_NAMES = {
    "target_revenue",
    "estimated_revenue",
    "planned_revenue",
    "price",
    "headcount",
    "training_slots",
    "allocation_percentage",
    "utilization_percentage",
    "grounding_score",
    "theme_score",
    "account_score",
    "matchingRate",
    "metric_value",
    "reference_value",
    "delta_value",
}

BOOLEAN_NAMES = {"required", "project_training_allowed", "assigned"}


def coerce_value(key: str, value: str) -> str | int | float | bool | None:
    if value == "":
        return None
    if key in BOOLEAN_NAMES:
        return value.lower() in {"1", "true", "yes"}
    if key in NUMERIC_NAMES or key.endswith(NUMERIC_SUFFIXES):
        try:
            number = float(value)
        except ValueError:
            return value
        return int(number) if number.is_integer() else number
    return value


def read_table(directory: Path, table: str) -> list[dict[str, Any]]:
    path = directory / f"{table}.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {key: coerce_value(key, value) for key, value in row.items()}
            for row in reader
        ]


def sum_field(rows: list[dict[str, Any]], field: str) -> float:
    total = 0.0
    for row in rows:
        value = row.get(field)
        if isinstance(value, (int, float)):
            total += float(value)
    return total


def count_by(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "N/A")
        counts[key] = counts.get(key, 0) + 1
    return [
        {"key": key, "count": count}
        for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def missing_sample_tables() -> list[str]:
    return [table for table in SAMPLE_TABLES if not (SAMPLE_DIR / f"{table}.csv").exists()]


def ensure_sample_data() -> None:
    missing_tables = missing_sample_tables()
    if not missing_tables:
        return

    uv_path = shutil.which("uv")
    if uv_path is None:
        missing_text = ", ".join(missing_tables)
        raise RuntimeError(
            "Sample data is missing and `uv` is not available to generate it. "
            f"Missing tables: {missing_text}"
        )

    print(
        "Sample data is missing. Generating repository-level CSVs with "
        "`uv run generate-sample`..."
    )
    subprocess.run(
        [uv_path, "run", "generate-sample"],
        cwd=ROOT_DIR,
        check=True,
    )

    remaining_tables = missing_sample_tables()
    if remaining_tables:
        missing_text = ", ".join(remaining_tables)
        raise RuntimeError(
            "Sample data generation completed but required CSVs are still missing: "
            f"{missing_text}"
        )


def build_derived(
    sample: dict[str, list[dict[str, Any]]],
    planning: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    trace = planning["matching_trace"]
    assigned = [row for row in trace if row.get("status") == "assigned"]
    return {
        "workflowSummary": {
            "salesPlanCount": len(sample["sales_plans"]),
            "themeRecommendationCount": len(planning["theme_recommendations"]),
            "projectSpecCount": len(planning["project_sizing_recommendations"]),
            "requestCount": len(planning["opportunity_requests"]),
            "assignmentCount": len(planning["opportunity_assignments"]),
        },
        "managementAccounting": {
            "planRevenue": sum_field(sample["sales_plans"], "target_revenue"),
            "opportunityRevenue": sum_field(planning["opportunities"], "estimated_revenue"),
            "matchingRate": len(assigned) / len(trace) if trace else 0,
        },
        "roleDemand": count_by(planning["opportunity_requests"], "role_code"),
        "matchingStatus": count_by(trace, "status"),
    }


def main() -> None:
    try:
        ensure_sample_data()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    sample = {table: read_table(SAMPLE_DIR, table) for table in SAMPLE_TABLES}
    # The UI is a workflow demo: it should start with SalesPlan/master data only.
    # Downstream planning tables are populated through HITL pipeline API calls and
    # stored in browser session tables.
    planning = {table: [] for table in PLANNING_TABLES}
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sample": sample,
        "planning": planning,
        "derived": build_derived(sample, planning),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
