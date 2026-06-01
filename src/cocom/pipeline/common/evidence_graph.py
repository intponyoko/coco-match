from __future__ import annotations

from typing import Any

import pandas as pd

from cocom.pipeline.common.io import table_records
from cocom.pipeline.common.table import split_tokens
from cocom.schema import KnowledgeEdge, KnowledgeNode


def build_case_knowledge_graph(
    *,
    accounts: pd.DataFrame,
    past_cases: pd.DataFrame,
    past_case_roles: pd.DataFrame,
    past_case_links: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(node_id: str, node_type: str, label: str, source: str) -> None:
        nodes.setdefault(
            node_id,
            {
                "node_id": node_id,
                "node_type": node_type,
                "label": label,
                "source": source,
            },
        )

    def add_edge(source_id: str, target_id: str, edge_type: str, source: str) -> None:
        edges.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
                "weight": 1.0,
                "source": source,
            }
        )

    for account in table_records(accounts):
        account_id = str(account.get("code", ""))
        if not account_id:
            continue
        industry_code = str(account.get("industry_code", ""))
        account_node = f"account:{account_id}"
        industry_node = f"industry:{industry_code}"
        add_node(account_node, "account", str(account.get("name", account_id)), account_id)
        if industry_code:
            add_node(industry_node, "industry", industry_code, account_id)
            add_edge(account_node, industry_node, "account_in_industry", account_id)

    for case in table_records(past_cases):
        case_id = str(case.get("case_id", ""))
        if not case_id:
            continue
        case_node = f"case:{case_id}"
        account_code = str(case.get("account_code", ""))
        solution_code = str(case.get("solution_code", ""))
        add_node(case_node, "past_case", str(case.get("title", case_id)), case_id)
        if solution_code:
            add_node(
                f"solution:{solution_code}",
                "solution",
                solution_code,
                case_id,
            )
            add_edge(
                case_node,
                f"solution:{solution_code}",
                "case_uses_solution",
                case_id,
            )
        if account_code:
            add_edge(case_node, f"account:{account_code}", "case_for_account", case_id)
        for theme in split_tokens(case.get("theme", "")):
            theme_node = f"theme:{theme}"
            add_node(theme_node, "theme", theme, case_id)
            add_edge(case_node, theme_node, "case_has_theme", case_id)
        for pain in split_tokens(case.get("customer_pain", "")):
            pain_node = f"pain:{pain}"
            add_node(pain_node, "customer_pain", pain, case_id)
            add_edge(case_node, pain_node, "case_addresses_pain", case_id)

    for role in table_records(past_case_roles):
        case_id = str(role.get("case_id", ""))
        role_code = str(role.get("role_code", ""))
        phase = str(role.get("phase", ""))
        if not case_id or not role_code:
            continue
        role_node = f"role:{role_code}"
        add_node(role_node, "role", role_code, case_id)
        add_edge(f"case:{case_id}", role_node, "case_requires_role", case_id)
        if phase:
            phase_node = f"phase:{phase}"
            add_node(phase_node, "phase", phase, case_id)
            add_edge(role_node, phase_node, "role_runs_in_phase", case_id)

    for link in table_records(past_case_links):
        source_case_id = str(link.get("source_case_id", ""))
        target_case_id = str(link.get("target_case_id", ""))
        relation_type = str(link.get("relation_type", "related"))
        if not source_case_id or not target_case_id:
            continue
        add_edge(
            f"case:{source_case_id}",
            f"case:{target_case_id}",
            relation_type,
            source_case_id,
        )

    return (
        KnowledgeNode.data_frame(nodes.values()),
        KnowledgeEdge.data_frame(edges),
    )


def build_rag_knowledge_graph(
    *,
    accounts: pd.DataFrame,
    past_cases: pd.DataFrame,
    past_case_roles: pd.DataFrame,
    past_case_links: pd.DataFrame,
    retrieved_evidence_chunks: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    case_ids = case_ids_from_retrieved_chunks(retrieved_evidence_chunks)
    if not case_ids:
        return KnowledgeNode.empty(), KnowledgeEdge.empty()

    filtered_cases = past_cases[
        past_cases["case_id"].astype(str).isin(sorted(case_ids))
    ].copy()
    filtered_case_roles = past_case_roles[
        past_case_roles["case_id"].astype(str).isin(sorted(case_ids))
    ].copy()
    filtered_case_links = past_case_links[
        past_case_links["source_case_id"].astype(str).isin(sorted(case_ids))
        | past_case_links["target_case_id"].astype(str).isin(sorted(case_ids))
    ].copy()
    account_ids = sorted(
        {
            str(value)
            for value in filtered_cases.get("account_code", pd.Series(dtype=str))
            .astype(str)
            .tolist()
            if value
        }
    )
    filtered_accounts = accounts[
        accounts["code"].astype(str).isin(account_ids)
    ].copy()
    return build_case_knowledge_graph(
        accounts=filtered_accounts,
        past_cases=filtered_cases,
        past_case_roles=filtered_case_roles,
        past_case_links=filtered_case_links,
    )


def case_ids_from_retrieved_chunks(retrieved_evidence_chunks: pd.DataFrame) -> set[str]:
    case_ids: set[str] = set()
    for row in table_records(retrieved_evidence_chunks):
        for candidate in (
            canonical_case_id(row.get("evidence_id")),
            canonical_case_id(row.get("source")),
        ):
            if candidate:
                case_ids.add(candidate)
    return case_ids


def canonical_case_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith("case:"):
        text = text[5:]
    return text.split(":", 1)[0].strip()
