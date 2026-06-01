from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from cocom.agent.common.azure_assist import run_insight_agent
from cocom.agent.common.schemas import (
    AgentEvidence,
    AgentInsightRequest,
    AgentInsightResponse,
)


def generate_workflow_insight(request: AgentInsightRequest) -> AgentInsightResponse:
    stage = request.stage.strip() or "unknown"
    fallback = build_stage_insight(stage, request.tables, request.focus)
    insight = run_insight_agent(
        agent_name="workflow_insight",
        instructions=stage_instructions(stage),
        input_payload={
            "stage": stage,
            "focus": request.focus,
            **request.tables,
        },
        fallback_output=fallback,
        schema_name=f"workflow_insight_{stage}",
    )
    merged = merge_insight_output(stage, fallback, insight.output)
    merged = normalize_insight_output(merged)
    merged = reconcile_stage_insight(stage, request.tables, request.focus, merged)
    merged["metadata"] = {
        "agent": "workflow_insight",
        "prompt_version": "workflow_insight.v1",
        "input_hash": input_hash_from_tables(request.tables),
        **request.metadata,
        **merged.get("metadata", {}),
        **insight.metadata,
    }
    return AgentInsightResponse(**merged)


def build_stage_insight(
    stage: str,
    tables: dict[str, list[dict[str, Any]]],
    focus: dict[str, Any],
) -> dict[str, Any]:
    builders = {
        "sales_plan": build_sales_plan_insight,
        "theme_solution": build_theme_solution_insight,
        "project_request": build_project_request_insight,
        "project_interest": build_project_interest_insight,
        "matching": build_matching_insight,
    }
    return builders.get(stage, build_generic_insight)(tables, focus)


def build_sales_plan_insight(
    tables: dict[str, list[dict[str, Any]]],
    _: dict[str, Any],
) -> dict[str, Any]:
    plans = tables.get("sales_plans", [])
    revenues = [number_value(row.get("target_revenue")) for row in plans]
    periods = sorted({str(row.get("period_code", "")) for row in plans if row.get("period_code")})
    industry_totals = aggregate_totals(plans, "industry_code", "target_revenue")
    top_industry, top_value = top_pair(industry_totals)
    total_revenue = sum(revenues)
    average_revenue = total_revenue / max(len(periods), 1)
    volatility = 0.0
    if periods and average_revenue > 0:
        month_totals = aggregate_totals(plans, "period_code", "target_revenue").values()
        variance = sum((value - average_revenue) ** 2 for value in month_totals) / max(len(periods), 1)
        volatility = (variance**0.5 / average_revenue) * 100
    concentration = (top_value / total_revenue) * 100 if total_revenue else 0.0
    confidence = clamp(0.45 + min(concentration / 200, 0.2) + min(len(periods) / 24, 0.15))
    return {
        "stage": "sales_plan",
        "headline": f"AIは {top_industry or '主要業界'} を起点に次のTheme群を組み立てる想定です。",
        "summary": (
            f"年間売上 {format_number(total_revenue)} を {len(periods)} 期間で観測し、"
            f"{top_industry or '主要業界'} への集中度と月次変動から次工程のテーマ探索優先度を判定しています。"
        ),
        "confidence_label": confidence_label(confidence),
        "confidence_score": confidence,
        "rationale": [
            {
                "title": "Coverage",
                "body": f"{len(plans)} 行のSalesPlanを入力として portfolio seed を作成します。",
                "tag": "input",
            },
            {
                "title": "Industry pull",
                "body": f"最大業界は {top_industry or 'N/A'} で {format_number(top_value)} の売上を持ちます。",
                "tag": "revenue",
            },
            {
                "title": "Seasonality",
                "body": f"月次変動は {volatility:.1f}% で、案件開始タイミングの偏りに効きます。",
                "tag": "timing",
            },
        ],
        "watchouts": [
            {
                "title": "Revenue concentration",
                "body": "特定業界への集中が高いほど、Theme候補の多様性が落ちやすくなります。"
                if concentration >= 45
                else "業界集中は極端ではありませんが、下位業界の取りこぼしは要確認です。",
                "severity": "medium",
            },
            {
                "title": "Monthly spread",
                "body": "月次変動が大きい場合は、Theme承認後のPJ開始月にギャップが出やすくなります。 "
                if volatility >= 30
                else "月次配分は比較的安定しています。",
                "severity": "medium" if volatility >= 30 else "low",
            },
        ],
        "alternatives": [
            {
                "title": "Conservative portfolio",
                "body": "上位業界に寄せてTheme数を絞り、PJ規模見積りのブレを抑える案です。",
            },
            {
                "title": "Exploration portfolio",
                "body": "下位業界にもThemeを残し、過去案件の類似度が弱くても仮説を広げる案です。",
            },
        ],
        "suggested_actions": [
            {"label": "主要業界の売上配分を再確認", "intent": "review"},
            {"label": "Theme/Solution生成へ進める", "intent": "approve"},
        ],
        "impact": [
            {"label": "Annual revenue", "value": format_number(total_revenue)},
            {"label": "Top industry share", "value": f"{concentration:.1f}%"},
            {"label": "Monthly volatility", "value": f"{volatility:.1f}%"},
        ],
        "evidence_refs": [
            offline_evidence(
                "sales_plan_distribution",
                "Current sales plan distribution",
                "Derived directly from the loaded SalesPlan rows in offline/stateless mode.",
            )
        ],
        "metadata": {"stage_source": "sales_plans"},
    }


def build_theme_solution_insight(
    tables: dict[str, list[dict[str, Any]]],
    focus: dict[str, Any],
) -> dict[str, Any]:
    themes = tables.get("theme_recommendations", [])
    selected = select_row(
        themes,
        lambda row: (
            str(row.get("sales_plan_code", "")) == str(focus.get("sales_plan_code", ""))
            and str(row.get("theme", "")) == str(focus.get("theme", ""))
        ),
    ) or (themes[0] if themes else {})
    evidence_ids = split_ids(selected.get("evidence_case_ids"))
    alternatives = [
        {
            "title": str(row.get("theme", "Alternative")),
            "body": f"{str(row.get('solution_code', 'solution'))} / {format_number(number_value(row.get('planned_revenue')))}"
        }
        for row in themes[:3]
        if row is not selected
    ][:2]
    global_coverage = consistency_metric(
        tables,
        metric_name="theme_revenue_coverage",
        metric_scope="global",
    )
    industry_coverage = consistency_metric(
        tables,
        metric_name="theme_revenue_coverage",
        metric_scope=f"industry:{str(selected.get('industry_code', ''))}",
    )
    global_delta_ratio = metric_delta_ratio(global_coverage)
    industry_delta_ratio = metric_delta_ratio(industry_coverage)
    confidence = clamp(
        0.5
        + min(len(evidence_ids) * 0.08, 0.24)
        + min(number_value(selected.get("theme_score")) / 10, 0.18)
        - min(global_delta_ratio * 0.45, 0.22)
        - min(industry_delta_ratio * 0.35, 0.18)
    )
    evidence_refs = evidence_for_theme(tables, evidence_ids)
    coverage_watchouts = []
    if global_delta_ratio > 0:
        coverage_watchouts.append(
            {
                "title": "Sales coverage gap",
                "body": str(global_coverage.get("summary", "Theme revenue does not fully align with SalesPlan totals.")),
                "severity": "high" if global_delta_ratio >= 0.1 else "medium",
            }
        )
    elif len(evidence_ids) < 2:
        coverage_watchouts.append(
            {
                "title": "Evidence strength",
                "body": "Evidenceが少ないため、Themeの説明責任は人手レビュー寄りです。",
                "severity": "medium",
            }
        )
    return {
        "stage": "theme_solution",
        "headline": f"AIは「{str(selected.get('theme', 'Theme候補'))}」を優先候補として提示しています。",
        "summary": (
            f"{str(selected.get('industry_code', 'industry'))} x {str(selected.get('solution_code', 'solution'))} の組み合わせを"
            f"中心に、想定売上 {format_number(number_value(selected.get('planned_revenue')))} のThemeを提示しています。"
        ),
        "confidence_label": confidence_label(confidence),
        "confidence_score": confidence,
        "rationale": [
            {
                "title": "Theme fit",
                "body": str(selected.get("customer_pain", "Customer pain is used as the entry point for the theme hypothesis.")),
                "tag": "pain",
            },
            {
                "title": "Revenue weight",
                "body": f"Planned revenue {format_number(number_value(selected.get('planned_revenue')))} を優先度に反映しています。",
                "tag": "revenue",
            },
            {
                "title": "Historical grounding",
                "body": f"Evidence {len(evidence_ids)} 件を参照対象として保持しています。",
                "tag": "evidence",
            },
        ],
        "watchouts": coverage_watchouts or [
            {
                "title": "Evidence strength",
                "body": "過去案件の grounding は一定量ありますが、業界の偏りは確認が必要です。",
                "severity": "medium",
            }
        ],
        "alternatives": alternatives or [
            {
                "title": "No clear alternative",
                "body": "現在の候補群では上位Themeとの差分がまだ小さい状態です。",
            }
        ],
        "suggested_actions": [
            {"label": "Theme文言を磨く", "intent": "edit"},
            {"label": "次のPJ規模推定へ進める", "intent": "approve"},
        ],
        "impact": [
            {"label": "Theme rank", "value": str(selected.get("theme_rank", "N/A"))},
            {"label": "Planned revenue", "value": format_number(number_value(selected.get("planned_revenue")))},
            {"label": "Evidence count", "value": str(len(evidence_ids))},
            {"label": "Theme delta", "value": format_number(number_value(global_coverage.get("delta_value")))},
        ],
        "evidence_refs": evidence_refs,
        "metadata": {"stage_source": "theme_recommendations"},
    }


def build_project_request_insight(
    tables: dict[str, list[dict[str, Any]]],
    focus: dict[str, Any],
) -> dict[str, Any]:
    specs = tables.get("project_sizing_recommendations", [])
    requests = tables.get("request_recommendations", [])
    project = select_row(
        specs,
        lambda row: str(row.get("project_spec_code", "")) == str(focus.get("project_spec_code", "")),
    ) or (specs[0] if specs else {})
    project_code = str(project.get("project_spec_code", ""))
    project_requests = [
        row for row in requests if str(row.get("project_spec_code", "")) == project_code
    ]
    headcount = sum(number_value(row.get("headcount")) for row in project_requests)
    training_slots = sum(number_value(row.get("training_slots")) for row in project_requests)
    unique_roles = len({str(row.get("role_code", "")) for row in project_requests if row.get("role_code")})
    evidence_ids = split_ids(project.get("evidence_case_ids"))
    review_metric = consistency_metric(
        tables,
        metric_name="projects_needing_review",
        metric_scope="global",
    )
    has_project_issue = any(
        str(row.get("project_spec_code", "")) == project_code
        for row in tables.get("project_review_issues", [])
    )
    positive_request_metric = consistency_metric(
        tables,
        metric_name="positive_request_count",
        metric_scope="global",
    )
    confidence = clamp(
        0.48
        + min(unique_roles * 0.04, 0.16)
        + min(len(evidence_ids) * 0.08, 0.24)
        - (0.18 if has_project_issue else 0.0)
        - min(metric_delta_ratio(positive_request_metric) * 0.2, 0.12)
    )
    return {
        "stage": "project_request",
        "headline": f"AIは {str(project.get('account_name', project.get('account_code', '対象Account')))} 向けにこのPJ設計を推しています。",
        "summary": (
            f"{str(project.get('theme', 'Theme'))} を {number_value(project.get('duration_months')):.0f} か月想定で展開し、"
            f"{unique_roles} Role / {headcount:.0f} headcount のRequestへ落としています。"
        ),
        "confidence_label": confidence_label(confidence),
        "confidence_score": confidence,
        "rationale": [
            {
                "title": "Scale estimate",
                "body": f"Revenue {format_number(number_value(project.get('estimated_revenue')))} を起点にPJ規模を設定しています。",
                "tag": "scale",
            },
            {
                "title": "Role mix",
                "body": f"{unique_roles} Roleで {len(project_requests)} request row を作成しています。",
                "tag": "roles",
            },
            {
                "title": "Training capacity",
                "body": f"Training slot は合計 {training_slots:.0f} 枠です。",
                "tag": "training",
            },
        ],
        "watchouts": [
            {
                "title": "Project review issue",
                "body": current_project_issue_summary(tables, project_code)
                if has_project_issue
                else "Role配置は成立していますが、期間と稼働率の整合は確認してください。",
                "severity": "high" if has_project_issue else "medium",
            },
            {
                "title": "Request density",
                "body": "Role数の割にheadcountが薄く、受注後に再設計が必要になる可能性があります。"
                if headcount <= max(unique_roles, 1)
                else str(review_metric.get("summary", "Generated requests should be checked against surviving projects.")),
                "severity": "medium",
            },
        ],
        "alternatives": [
            {
                "title": "Lean team",
                "body": "Role数を維持したまま training slot を絞り、初期体制を軽くする案です。",
            },
            {
                "title": "Growth team",
                "body": "育成枠を厚くし、後段のAssignment optionsを増やす案です。",
            },
        ],
        "suggested_actions": [
            {"label": "Role別requestを再調整", "intent": "edit"},
            {"label": "Opportunity化して個人候補生成へ進む", "intent": "approve"},
        ],
        "impact": [
            {"label": "Duration", "value": f"{number_value(project.get('duration_months')):.0f} months"},
            {"label": "Headcount", "value": f"{headcount:.0f}"},
            {"label": "Training slots", "value": f"{training_slots:.0f}"},
            {"label": "Projects needing review", "value": str(int(number_value(review_metric.get("metric_value"))))},
        ],
        "evidence_refs": evidence_for_theme(tables, evidence_ids),
        "metadata": {"stage_source": "project_sizing_recommendations"},
    }


def build_project_interest_insight(
    tables: dict[str, list[dict[str, Any]]],
    focus: dict[str, Any],
) -> dict[str, Any]:
    options = tables.get("staff_preference_options", [])
    staff_code = str(focus.get("staff_code", ""))
    period_code = str(focus.get("period_code", ""))
    staff_options = [row for row in options if str(row.get("staff_code", "")) == staff_code]
    month_options = [row for row in staff_options if str(row.get("period_code", "")) == period_code]
    recommended = max(month_options or staff_options, key=lambda row: number_value(row.get("score")), default={})
    standard_count = sum(1 for row in month_options if str(row.get("assignment_type", "")) == "standard")
    training_count = sum(1 for row in month_options if str(row.get("assignment_type", "")) == "training")
    confidence = clamp(0.42 + min(len(month_options) * 0.04, 0.18) + (0.14 if recommended else 0.0))
    opportunity_code = str(recommended.get("opportunity_code", focus.get("opportunity_code", "")))
    return {
        "stage": "project_interest",
        "headline": f"AIは {period_code or '対象月'} に {opportunity_code or 'PJ候補'} を第一候補として見ています。",
        "summary": (
            f"Staff {staff_code or 'selected'} に対して {period_code or '対象月'} の候補を比較し、"
            f"通常枠 {standard_count} / 育成枠 {training_count} の中から推奨順を作っています。"
        ),
        "confidence_label": confidence_label(confidence),
        "confidence_score": confidence,
        "rationale": [
            {
                "title": "Recommended slot",
                "body": str(recommended.get("reason", "Top option is derived from score, skill gap, and assignment type ordering.")),
                "tag": "ranking",
            },
            {
                "title": "Monthly optionality",
                "body": f"{period_code or '対象月'} は {len(month_options)} option を持ちます。",
                "tag": "optionality",
            },
            {
                "title": "Career mix",
                "body": "通常枠と育成枠を同時に見せ、個人の年間計画として選びやすくしています。",
                "tag": "career",
            },
        ],
        "watchouts": [
            {
                "title": "Choice scarcity",
                "body": "この月の候補が少ないため、年間計画全体での前後調整が必要です。"
                if len(month_options) <= 1
                else "候補はありますが、月ごとの選択が偏ると稼働率が不均衡になり得ます。",
                "severity": "medium",
            }
        ],
        "alternatives": [
            {
                "title": "Training-first month",
                "body": "PJを選ばず role-based training を置き、後月で本命PJに寄せる案です。",
            },
            {
                "title": "Commit early",
                "body": "推奨PJを先に確保し、残り月で研修を調整する案です。",
            },
        ],
        "suggested_actions": [
            {"label": "推奨PJを採用", "intent": "select"},
            {"label": "研修月を明示して年間計画を整える", "intent": "review"},
        ],
        "impact": [
            {"label": "Month options", "value": str(len(month_options))},
            {"label": "Standard slots", "value": str(standard_count)},
            {"label": "Training slots", "value": str(training_count)},
        ],
        "evidence_refs": [
            offline_evidence(
                "preference_option_ranking",
                "Current option ranking",
                "Derived from current staff_preference_options ordering in offline/stateless mode.",
            )
        ],
        "metadata": {"stage_source": "staff_preference_options"},
    }


def build_matching_insight(
    tables: dict[str, list[dict[str, Any]]],
    focus: dict[str, Any],
) -> dict[str, Any]:
    trace = tables.get("matching_trace", [])
    utilization = tables.get("staff_utilization", [])
    assignments = tables.get("assignment_recommendations", [])
    requests = tables.get("opportunity_requests", [])
    opportunity_code = str(focus.get("opportunity_code", ""))
    relevant_requests = [
        row for row in requests if not opportunity_code or str(row.get("opportunity_code", "")) == opportunity_code
    ]
    request_codes = {str(row.get("code", row.get("opportunity_request_code", ""))) for row in relevant_requests}
    relevant_assignments = [
        row for row in assignments
        if not request_codes or str(row.get("opportunity_request_code", "")) in request_codes
    ]
    relevant_trace = [
        row for row in trace
        if not request_codes or str(row.get("opportunity_request_code", "")) in request_codes
    ]
    assigned = sum(1 for row in relevant_trace if str(row.get("status", "")) == "assigned")
    tough = sum(1 for row in relevant_trace if str(row.get("status", "")) == "tough_assigned")
    unassigned = sum(1 for row in relevant_trace if str(row.get("status", "")) == "unassigned")
    full_utilization = sum(1 for row in utilization if number_value(row.get("utilization_percentage")) >= 100)
    evaluated = max(len(relevant_requests), assigned + tough + unassigned, 1)
    effective_assigned = assigned + (0.5 * tough)
    fill_rate = effective_assigned / evaluated
    unassigned_rate = unassigned / evaluated
    overload_penalty = min(full_utilization * 0.01, 0.12)
    confidence = clamp(0.18 + (fill_rate * 0.58) - (unassigned_rate * 0.28) - overload_penalty)
    return {
        "stage": "matching",
        "headline": f"AIは {opportunity_code or '全体Matching'} を {assigned} 件の充足ベースで見ています。",
        "summary": (
            f"割当済み {assigned}、育成枠 {tough}、未割当 {unassigned} を比較し、"
            f"承認前に capacity と未充足Roleを強調しています。"
        ),
        "confidence_label": confidence_label(confidence),
        "confidence_score": confidence,
        "rationale": [
            {
                "title": "Coverage",
                "body": f"対象requestに対して {len(relevant_assignments)} recommendation を保持しています。",
                "tag": "coverage",
            },
            {
                "title": "Risk scan",
                "body": f"未割当 {unassigned} と 100%稼働 {full_utilization} staff-month を同時に見ています。",
                "tag": "risk",
            },
            {
                "title": "Training balance",
                "body": f"育成枠 {tough} が delivery risk と育成余地の両面に効きます。",
                "tag": "training",
            },
        ],
        "watchouts": [
            {
                "title": "Unassigned roles",
                "body": "未割当が残っているため、承認前に role mix か candidate pool の見直しが必要です。"
                if unassigned > 0
                else "未割当は見えていませんが、過負荷staffの偏りは確認してください。",
                "severity": "high" if unassigned > 0 else "medium",
            }
        ],
        "alternatives": [
            {
                "title": "Stability-first",
                "body": "育成枠を減らし、既存充足率を優先する案です。",
            },
            {
                "title": "Growth-first",
                "body": "一部の tough assignment を残し、将来のskill拡張を取る案です。",
            },
        ],
        "suggested_actions": [
            {"label": "未割当Roleを確認", "intent": "review"},
            {"label": "OpportunityAssignmentとして確定", "intent": "approve"},
        ],
        "impact": [
            {"label": "Assigned", "value": str(assigned)},
            {"label": "Tough assigned", "value": str(tough)},
            {"label": "Unassigned", "value": str(unassigned)},
            {"label": "Fill rate", "value": f"{fill_rate * 100:.0f}%"},
        ],
        "evidence_refs": [
            offline_evidence(
                "matching_trace_review",
                "Current matching trace",
                "Derived directly from matching_trace and staff_utilization in offline/stateless mode.",
            )
        ],
        "metadata": {"stage_source": "matching_trace"},
    }


def build_generic_insight(
    tables: dict[str, list[dict[str, Any]]],
    focus: dict[str, Any],
) -> dict[str, Any]:
    return {
        "stage": "unknown",
        "headline": "AI insight is available for the current workflow state.",
        "summary": f"Received {len(tables)} tables and focus keys {sorted(focus.keys())}.",
        "confidence_label": "review",
        "confidence_score": 0.4,
        "rationale": [{"title": "Input received", "body": "The stateless insight API accepted the current tables.", "tag": "api"}],
        "watchouts": [],
        "alternatives": [],
        "suggested_actions": [{"label": "入力を確認", "intent": "review"}],
        "impact": [{"label": "Tables", "value": str(len(tables))}],
        "evidence_refs": [offline_evidence("generic_input", "Current workflow snapshot", "Derived from current request payload.")],
        "metadata": {"stage_source": "generic"},
    }


def stage_instructions(stage: str) -> str:
    return (
        "You are an AI copilot for a Japanese human-in-the-loop staffing workflow. "
        f"Generate a concise structured insight for the '{stage}' stage. "
        "Do not propose a new plan or recommendation. Summarize and diagnose the "
        "provided grounded result only. "
        "Return JSON with headline, summary, confidence_label, confidence_score, "
        "rationale, watchouts, alternatives, suggested_actions, impact, evidence_refs, and metadata. "
        "Ground the content in the provided tables and focus. Keep the tone decisive. "
        "Keep headline and summary to one sentence each. "
        "Return at most 2 rationale items, 2 watchouts, 2 alternatives, 2 suggested_actions, and 3 impact items. "
        f"{stage_guidance(stage)} "
        "Each evidence_refs item must be an object with evidence_id, title, summary, source, and optional metadata."
    )


def merge_insight_output(
    stage: str,
    fallback: dict[str, Any],
    completed: dict[str, Any],
) -> dict[str, Any]:
    merged = {**fallback}
    for key in [
        "headline",
        "summary",
        "confidence_label",
        "confidence_score",
        "rationale",
        "watchouts",
        "alternatives",
        "suggested_actions",
        "impact",
        "metadata",
    ]:
        value = completed.get(key)
        if value not in (None, "", [], {}):
            merged[key] = value
    merged["stage"] = stage
    evidence_refs = completed.get("evidence_refs")
    if evidence_refs not in (None, "", [], {}):
        merged["evidence_refs"] = evidence_refs
    else:
        merged["evidence_refs"] = fallback.get("evidence_refs", [])
    return merged


def normalize_insight_output(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    default_titles = {
        "rationale": "Rationale",
        "watchouts": "Watchout",
        "alternatives": "Alternative",
        "suggested_actions": "Suggested Action",
        "impact": "Impact",
    }
    for key in [
        "rationale",
        "watchouts",
        "alternatives",
        "suggested_actions",
        "impact",
    ]:
        normalized[key] = [
            normalize_insight_item(item, default_title=default_titles[key])
            for item in ensure_list(payload.get(key, []))
        ]
    normalized["evidence_refs"] = [
        normalize_evidence_ref(item) for item in ensure_list(payload.get("evidence_refs", []))
    ]
    return normalized


def reconcile_stage_insight(
    stage: str,
    tables: dict[str, list[dict[str, Any]]],
    focus: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    if stage != "matching":
        return payload
    recalculated = build_matching_insight(tables, focus)
    next_payload = dict(payload)
    next_payload["confidence_score"] = recalculated["confidence_score"]
    next_payload["confidence_label"] = recalculated["confidence_label"]
    next_payload.setdefault("metadata", {})
    next_payload["metadata"] = {
        **next_payload["metadata"],
        "confidence_basis": "matching_trace_coverage",
    }
    return next_payload


def normalize_insight_item(item: Any, default_title: str) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if isinstance(item, str):
        return {"title": default_title, "body": item}
    if isinstance(item, (int, float, bool)):
        return {"title": default_title, "value": str(item)}
    return {"title": default_title, "body": json.dumps(item, ensure_ascii=False)}


def normalize_evidence_ref(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    return {
        "evidence_id": "unknown",
        "title": "Evidence",
        "summary": str(item),
        "source": "",
        "metadata": {"origin": "normalized"},
    }


def ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def consistency_metric(
    tables: dict[str, list[dict[str, Any]]],
    *,
    metric_name: str,
    metric_scope: str,
) -> dict[str, Any]:
    for row in tables.get("consistency_metrics", []):
        if (
            str(row.get("metric_name", "")) == metric_name
            and str(row.get("metric_scope", "")) == metric_scope
        ):
            return row
    return {}


def metric_delta_ratio(row: dict[str, Any]) -> float:
    reference = number_value(row.get("reference_value"))
    if reference <= 0:
        return 0.0
    return abs(number_value(row.get("delta_value"))) / reference


def current_project_issue_summary(
    tables: dict[str, list[dict[str, Any]]],
    project_spec_code: str,
) -> str:
    for row in tables.get("project_review_issues", []):
        if str(row.get("project_spec_code", "")) == project_spec_code:
            return str(row.get("summary", "This project needs manual review."))
    return "This project needs manual review."


def evidence_for_theme(
    tables: dict[str, list[dict[str, Any]]],
    evidence_ids: list[str],
) -> list[AgentEvidence]:
    refs = evidence_from_nodes_frame(tables, evidence_ids)
    if refs:
        return refs
    refs = evidence_from_retrieval_chunks_frame(tables, evidence_ids)
    if refs:
        return refs
    return [
        offline_evidence(
            "theme_grounding",
            "Offline grounding placeholder",
            "No retrievable evidence nodes were available in this stateless/offline response.",
        )
    ]


def evidence_from_nodes_frame(
    tables: dict[str, list[dict[str, Any]]],
    evidence_ids: list[str],
) -> list[AgentEvidence]:
    import pandas as pd

    nodes = pd.DataFrame(tables.get("knowledge_nodes", []))
    if nodes.empty or "node_id" not in nodes.columns:
        return []
    wanted = set(evidence_ids)
    refs: list[AgentEvidence] = []
    for row in nodes.to_dict("records"):
        node_id = str(row.get("node_id", ""))
        source = str(row.get("source", ""))
        node_type = str(row.get("node_type", ""))
        direct_match = node_id in wanted
        source_case_match = source in wanted and node_type == "past_case"
        if not direct_match and not source_case_match:
            continue
        refs.append(
            AgentEvidence(
                evidence_id=source or node_id,
                title=str(row.get("label", node_id)),
                summary=str(row.get("label", node_id)),
                source=source,
                metadata={"node_type": node_type},
            )
        )
    return refs


def evidence_from_retrieval_chunks_frame(
    tables: dict[str, list[dict[str, Any]]],
    evidence_ids: list[str],
) -> list[AgentEvidence]:
    wanted = set(evidence_ids)
    refs: list[AgentEvidence] = []
    for row in tables.get("retrieved_evidence_chunks", []):
        evidence_id = str(row.get("evidence_id", ""))
        if evidence_id not in wanted:
            continue
        refs.append(
            AgentEvidence(
                evidence_id=evidence_id,
                title=str(row.get("title", evidence_id)),
                summary=str(row.get("snippet", row.get("title", evidence_id))),
                source=str(row.get("source", "")),
                metadata={"evidence_type": str(row.get("evidence_type", "retrieved_chunk"))},
            )
        )
    return refs


def select_row(rows: list[dict[str, Any]], predicate: Any) -> dict[str, Any] | None:
    for row in rows:
        if predicate(row):
            return row
    return None


def split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def aggregate_totals(
    rows: list[dict[str, Any]],
    group_key: str,
    value_key: str,
) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        key = str(row.get(group_key, "")) or "N/A"
        totals[key] = totals.get(key, 0.0) + number_value(row.get(value_key))
    return totals


def top_pair(values: dict[str, float]) -> tuple[str, float]:
    if not values:
        return "", 0.0
    key = max(values, key=values.get)
    return key, values[key]


def number_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return 0.0
    return 0.0


def format_number(value: float) -> str:
    return f"{value:,.0f}"


def clamp(value: float, minimum: float = 0.15, maximum: float = 0.96) -> float:
    return max(minimum, min(maximum, value))


def confidence_label(score: float) -> str:
    if score >= 0.78:
        return "high"
    if score >= 0.56:
        return "medium"
    return "review"


def offline_evidence(evidence_id: str, title: str, summary: str) -> AgentEvidence:
    return AgentEvidence(
        evidence_id=f"offline:{evidence_id}",
        title=title,
        summary=summary,
        source="offline",
        metadata={"origin": "offline_mock"},
    )


def input_hash_from_tables(tables: dict[str, list[dict[str, Any]]]) -> str:
    table_counts = "|".join(
        f"{name}:{len(rows)}" for name, rows in sorted(tables.items())
    )
    return sha256(table_counts.encode("utf-8")).hexdigest()[:16]


def stage_guidance(stage: str) -> str:
    guidance = {
        "sales_plan": "Focus on portfolio signals, industry concentration, and timing.",
        "theme_solution": "Focus on theme fit, customer pain, historical grounding, and revenue coverage against SalesPlan.",
        "project_request": "Focus on project scale, role mix, training capacity, and whether each project survives request generation.",
        "project_interest": "Focus on personal option quality, monthly optionality, and career tradeoffs.",
        "matching": "Focus on fill rate, overload risk, and assignment confidence.",
    }
    return guidance.get(stage, "Focus on the most decision-relevant signals for the current stage.")
