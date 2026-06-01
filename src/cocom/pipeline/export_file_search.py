from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from cocom.pipeline.common.knowledge import read_past_case_data
from cocom.pipeline.common.paths import default_pipeline_paths


def split_tokens(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [token.strip() for token in str(value).split(";") if token.strip()]


def as_int(value: Any) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    return int(float(value))


def as_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def currency_text(value: Any) -> str:
    amount = as_int(value)
    return f"{amount:,} JPY" if amount else "n/a"


def collect_role_rows(past_case_roles: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in past_case_roles.fillna("").to_dict(orient="records"):
        grouped[as_str(row.get("case_id"))].append(row)
    return grouped


def collect_links(past_case_links: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in past_case_links.fillna("").to_dict(orient="records"):
        grouped[as_str(row.get("source_case_id"))].append(row)
    return grouped


def summarize_roles(role_rows: list[dict[str, Any]]) -> list[str]:
    summary: dict[str, dict[str, Any]] = {}
    for row in role_rows:
        role_code = as_str(row.get("role_code")) or "UNKNOWN"
        current = summary.setdefault(
            role_code,
            {
                "headcount": 0,
                "training_headcount": 0,
                "allocations": [],
                "phases": set(),
            },
        )
        current["headcount"] += as_int(row.get("headcount"))
        current["training_headcount"] += as_int(row.get("training_headcount"))
        allocation = as_int(row.get("allocation_percentage"))
        if allocation:
            current["allocations"].append(allocation)
        phase = as_str(row.get("phase"))
        if phase:
            current["phases"].add(phase)

    lines: list[str] = []
    for role_code, current in sorted(summary.items()):
        allocation_text = (
            f"{round(sum(current['allocations']) / len(current['allocations']))}% avg allocation"
            if current["allocations"]
            else "allocation n/a"
        )
        phases_text = ", ".join(sorted(current["phases"])) or "n/a"
        lines.append(
            f"- {role_code}: {current['headcount']} total headcount, "
            f"{current['training_headcount']} training headcount, "
            f"{allocation_text}, phases {phases_text}"
        )
    return lines or ["- No recorded role demand"]


def format_role_detail(row: dict[str, Any]) -> str:
    return (
        f"- phase {as_str(row.get('phase')) or 'n/a'} | role {as_str(row.get('role_code')) or 'n/a'}"
        f" | headcount {as_int(row.get('headcount'))}"
        f" | allocation {as_int(row.get('allocation_percentage'))}%"
        f" | months {as_int(row.get('phase_start_month'))}-{as_int(row.get('phase_end_month'))}"
        f" | training {as_int(row.get('training_headcount'))}"
        f" | max skill gap {as_int(row.get('role_phase_training_max_skill_gap'))}"
    )


def render_case_document(
    case: dict[str, Any],
    role_rows: list[dict[str, Any]],
    related_rows: list[dict[str, Any]],
) -> str:
    themes = split_tokens(case.get("theme"))
    pains = split_tokens(case.get("customer_pain"))
    related_lines = [
        f"- {as_str(row.get('relation_type')) or 'related_to'} -> {as_str(row.get('target_case_id')) or 'n/a'}"
        for row in related_rows
    ] or ["- No explicit related cases"]

    lines = [
        f"# Past Case {as_str(case.get('case_id'))}",
        "",
        "## Metadata",
        f"- Case ID: {as_str(case.get('case_id'))}",
        f"- Title: {as_str(case.get('title')) or 'n/a'}",
        f"- Account code: {as_str(case.get('account_code')) or 'n/a'}",
        f"- Industry code: {as_str(case.get('industry_code')) or 'n/a'}",
        f"- Solution code: {as_str(case.get('solution_code')) or 'n/a'}",
        f"- Observed revenue: {currency_text(case.get('observed_revenue'))}",
        f"- Duration months: {as_int(case.get('duration_months')) or 'n/a'}",
        f"- Outcome: {as_str(case.get('outcome')) or 'n/a'}",
        f"- Period hint: {as_int(case.get('period_hint')) or 'n/a'}",
        f"- Delivery model: {as_str(case.get('delivery_model')) or 'n/a'}",
        "",
        "## Themes",
    ]
    lines.extend([f"- {theme}" for theme in themes] or ["- n/a"])
    lines.extend(
        [
            "",
            "## Customer pain",
            *([f"- {pain}" for pain in pains] or ["- n/a"]),
            "",
            "## Role demand summary",
            *summarize_roles(role_rows),
            "",
            "## Role phase details",
            *([format_role_detail(row) for row in role_rows] or ["- No phase detail"]),
            "",
            "## Related cases",
            *related_lines,
        ]
    )
    return "\n".join(lines) + "\n"


def output_dir(root_dir: Path) -> Path:
    return root_dir / "data" / "file_search"


def export_documents(root_dir: Path) -> Path:
    paths = default_pipeline_paths()
    past_case_data = read_past_case_data(paths.knowledge_data_dir)
    out_dir = output_dir(root_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for existing in out_dir.glob("case-*.md"):
        existing.unlink()

    role_rows_by_case = collect_role_rows(past_case_data["past_case_roles"])
    links_by_case = collect_links(past_case_data["past_case_links"])

    manifest_documents: list[dict[str, Any]] = []
    for case in past_case_data["past_cases"].fillna("").to_dict(orient="records"):
        case_id = as_str(case.get("case_id"))
        path = out_dir / f"case-{case_id}.md"
        role_rows = role_rows_by_case.get(case_id, [])
        related_rows = links_by_case.get(case_id, [])
        path.write_text(
            render_case_document(case, role_rows, related_rows),
            encoding="utf-8",
        )
        manifest_documents.append(
            {
                "case_id": case_id,
                "path": path.name,
                "title": as_str(case.get("title")),
                "role_rows": len(role_rows),
                "related_cases": len(related_rows),
            }
        )

    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_tables": [
                    "knowledge/past_cases/past_cases.csv",
                    "knowledge/past_cases/past_case_roles.csv",
                    "knowledge/past_cases/past_case_links.csv",
                ],
                "document_count": len(manifest_documents),
                "documents": manifest_documents,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_dir


def main() -> None:
    root_dir = default_pipeline_paths().root_dir
    out_dir = export_documents(root_dir)
    print(f"Wrote file_search documents to {out_dir.relative_to(root_dir)}")


if __name__ == "__main__":
    main()
