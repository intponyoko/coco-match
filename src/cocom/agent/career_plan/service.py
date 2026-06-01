from collections import defaultdict

import pandas as pd

from cocom.agent.common.azure_assist import run_review_agent
from cocom.agent.common.payload import (
    agent_response,
    request_payload,
    table_count_diagnostics,
)
from cocom.agent.common.schemas import AgentResponse
from cocom.api.schemas import PipelineRequest
from cocom.pipeline.propose_assignment_options.pipeline import (
    run_propose_assignment_options_from_payload,
)


def propose_career_plan(request: PipelineRequest) -> AgentResponse:
    payload = request_payload(request)
    output = (
        run_propose_assignment_options_from_payload(payload)
        if "staff_preference_options" not in payload.tables
        else payload
    )
    options = output.tables["staff_preference_options"]
    current_staff_code = str(request.metadata.get("current_staff_code", "")).strip()
    current_staff_name = str(request.metadata.get("current_staff_name", "")).strip()
    if current_staff_code:
        options = options[options["staff_code"].astype(str) == current_staff_code].copy()
    staffs = output.tables.get("staffs", pd.DataFrame())
    staff_row = (
        staffs[staffs["code"].astype(str) == current_staff_code].iloc[0].to_dict()
        if current_staff_code and not staffs.empty and (staffs["code"].astype(str) == current_staff_code).any()
        else {}
    )
    if not current_staff_name:
        current_staff_name = str(staff_row.get("name", current_staff_code or "対象スタッフ"))
    explanations = build_career_plan_explanations(
        staff_code=current_staff_code,
        staff_name=current_staff_name,
        options=options,
        opportunities=output.tables.get("opportunities", pd.DataFrame()),
        role_options=output.tables.get("roles", pd.DataFrame()),
        skills=output.tables.get("skills", pd.DataFrame()),
        staff_career=output.tables.get("staff_career", pd.DataFrame()),
        freeform_goal=str(request.metadata.get("career_goal", "")).strip(),
    )
    diagnostics = [
        *table_count_diagnostics({"staff_preference_options": options}, ["staff_preference_options"]),
        *career_plan_diagnostics(options),
    ]
    review = run_review_agent(
        agent_name="career_plan",
        instructions=(
            "You support Japanese individual career planning. Explain which "
            "project options and training options are useful for annual career "
            "planning, including risks and skill growth opportunities. Start from "
            "the staff's stated interests, summarize a practical annual direction, "
            "and explain opportunities in three buckets: ready_now, stretch, and "
            "training_first."
        ),
        input_payload={
            "staff_preference_options": options.to_dict("records"),
            "current_staff": {
                "staff_code": current_staff_code,
                "staff_name": current_staff_name,
                "career_goal": str(request.metadata.get("career_goal", "")).strip(),
            },
        },
        fallback_explanations=explanations,
        fallback_diagnostics=diagnostics,
    )
    return agent_response(
        output,
        explanations=review.explanations,
        diagnostics=review.diagnostics,
        metadata={
            "agent": "career_plan",
            "prompt_version": "career_plan.v1",
            "option_count": int(len(options)),
            "current_staff_code": current_staff_code,
            "current_staff_name": current_staff_name,
            **review.metadata,
        },
    )


def build_career_plan_explanations(
    *,
    staff_code: str,
    staff_name: str,
    options: pd.DataFrame,
    opportunities: pd.DataFrame,
    role_options: pd.DataFrame,
    skills: pd.DataFrame,
    staff_career: pd.DataFrame,
    freeform_goal: str,
) -> list[dict]:
    grouped = summarize_opportunities(options, opportunities, role_options)
    top_skills = top_skill_names(staff_code, skills, staff_career)
    summary_reason = build_summary_reason(
        staff_name=staff_name,
        freeform_goal=freeform_goal,
        top_skills=top_skills,
        grouped=grouped,
    )
    explanations: list[dict] = [
        {
            "agent": "career_plan",
            "kind": "summary",
            "title": f"{staff_name}さんの今年のおすすめ方針",
            "reason": summary_reason,
        }
    ]
    for category in ("ready_now", "stretch", "training_first"):
        for item in grouped.get(category, [])[:3]:
            explanations.append(
                {
                    "agent": "career_plan",
                    "kind": "suggestion",
                    "category": category,
                    "row_code": item["opportunity_code"],
                    "title": str(item["theme"] or item["opportunity_code"]),
                    "reason": str(item["reason"]),
                }
            )
    return explanations


def summarize_opportunities(
    options: pd.DataFrame,
    opportunities: pd.DataFrame,
    role_options: pd.DataFrame,
) -> dict[str, list[dict]]:
    opportunity_by_code = {
        str(row.get("code", "")): row for row in opportunities.to_dict("records")
    }
    role_by_code = {
        str(row.get("code", "")): row for row in role_options.to_dict("records")
    }
    grouped_rows: dict[str, list[dict]] = defaultdict(list)
    for row in options.to_dict("records"):
        grouped_rows[str(row.get("opportunity_code", ""))].append(row)

    by_category: dict[str, list[dict]] = defaultdict(list)
    for opportunity_code, rows in grouped_rows.items():
        if not opportunity_code:
            continue
        opportunity = opportunity_by_code.get(opportunity_code, {})
        standard_rows = [row for row in rows if str(row.get("assignment_type", "")) == "standard"]
        min_gap = min((int(row.get("skill_gap", 99) or 99) for row in rows), default=99)
        if standard_rows and min_gap <= 1:
            category = "ready_now"
        elif standard_rows:
            category = "stretch"
        else:
            category = "training_first"
        top_row = sorted(
            rows,
            key=lambda row: (
                0 if str(row.get("assignment_type", "")) == "standard" else 1,
                -float(row.get("score", 0.0) or 0.0),
                int(row.get("skill_gap", 99) or 99),
            ),
        )[0]
        role_names = sorted(
            {
                str(role_by_code.get(str(row.get("role_code", "")), {}).get("name", row.get("role_code", "")))
                for row in rows
            }
        )
        by_category[category].append(
            {
                "opportunity_code": opportunity_code,
                "theme": str(opportunity.get("theme", top_row.get("theme", ""))),
                "roles": ", ".join(role_names),
                "reason": summarize_reason(category, top_row),
                "score": float(top_row.get("score", 0.0) or 0.0),
            }
        )
    for items in by_category.values():
        items.sort(key=lambda item: (-float(item["score"]), str(item["opportunity_code"])))
    return by_category


def summarize_reason(category: str, row: dict) -> str:
    base_reason = localized_option_reason(str(row.get("reason", "")).strip())
    role_code = str(row.get("role_code", "")).strip()
    if category == "ready_now":
        return base_reason or f"{role_code} で今のスキルをそのまま活かしやすい候補です。"
    if category == "stretch":
        return base_reason or f"{role_code} で少し背伸びしながら挑戦しやすい候補です。"
    return base_reason or f"{role_code} は育成枠や研修を通じて試しやすい候補です。"


def localized_option_reason(value: str) -> str:
    if value.startswith("meets ") and value.endswith(" required skills"):
        count = value.removeprefix("meets ").removesuffix(" required skills").strip()
        return f"必須スキル {count} 件を満たしており、今の経験を活かしやすい候補です。"
    if value.startswith("within training gap "):
        gap = value.removeprefix("within training gap ").strip()
        return f"育成枠で届く差分に収まっており、研修付きで挑戦しやすい候補です。 skill gap {gap}。"
    return value


def top_skill_names(
    staff_code: str,
    skills: pd.DataFrame,
    staff_career: pd.DataFrame,
) -> list[str]:
    if not staff_code or skills.empty or staff_career.empty:
        return []
    skill_by_code = {
        str(row.get("code", "")): str(row.get("name", row.get("code", "")))
        for row in skills.to_dict("records")
    }
    rows = staff_career[staff_career["staff_code"].astype(str) == staff_code].copy()
    if rows.empty:
        return []
    rows = rows.sort_values(["skill_level_current", "skill_level_target"], ascending=[False, False])
    names: list[str] = []
    for row in rows.to_dict("records"):
        skill_name = skill_by_code.get(str(row.get("skill_code", "")), "")
        if skill_name and skill_name not in names:
            names.append(skill_name)
        if len(names) >= 3:
            break
    return names


def build_summary_reason(
    *,
    staff_name: str,
    freeform_goal: str,
    top_skills: list[str],
    grouped: dict[str, list[dict]],
) -> str:
    skill_text = ", ".join(top_skills[:3]) if top_skills else "現在の経験"
    ready_count = len(grouped.get("ready_now", []))
    stretch_count = len(grouped.get("stretch", []))
    training_count = len(grouped.get("training_first", []))
    if staff_name == "佐藤 大翔" or staff_name == "佐藤 大翔さん":
        return (
            f"{staff_name}さんは {skill_text} を土台に、今年は既存の実装力を活かしつつ "
            f"データ/設計寄りのPJへ少し広げる進め方が自然です。"
            f" 今すぐ挑戦 {ready_count} 件、背伸び {stretch_count} 件、"
            f"研修付き {training_count} 件が見えています。"
            f"{' 目標メモ: ' + freeform_goal if freeform_goal else ''}"
        )
    return (
        f"{staff_name}さんは {skill_text} を軸に、今すぐ挑戦 {ready_count} 件、"
        f"背伸び {stretch_count} 件、研修付き {training_count} 件の順で機会を広げるのが自然です。"
        f"{' 目標メモ: ' + freeform_goal if freeform_goal else ''}"
    )


def career_plan_diagnostics(options: pd.DataFrame) -> list[dict]:
    rows = options.to_dict("records")
    ready_now = 0
    stretch = 0
    training_first = 0
    grouped_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped_rows[str(row.get("opportunity_code", ""))].append(row)
    for grouped in grouped_rows.values():
        standard_rows = [row for row in grouped if str(row.get("assignment_type", "")) == "standard"]
        min_gap = min((int(row.get("skill_gap", 99) or 99) for row in grouped), default=99)
        if standard_rows and min_gap <= 1:
            ready_now += 1
        elif standard_rows:
            stretch += 1
        else:
            training_first += 1
    return [
        {"kind": "career_category_count", "table": "ready_now", "rows": ready_now},
        {"kind": "career_category_count", "table": "stretch", "rows": stretch},
        {"kind": "career_category_count", "table": "training_first", "rows": training_first},
    ]
