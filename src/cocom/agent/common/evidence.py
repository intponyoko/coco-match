from cocom.agent.common.schemas import AgentEvidence
from cocom.pipeline.common.csv_io import read_csv
from cocom.pipeline.common.paths import PipelinePaths, default_pipeline_paths


def lookup_evidence(
    evidence_id: str,
    paths: PipelinePaths | None = None,
) -> AgentEvidence:
    resolved_paths = paths or default_pipeline_paths()
    try:
        nodes = read_csv(resolved_paths.planning_data_dir, "knowledge_nodes")
    except FileNotFoundError as exc:
        raise ValueError("knowledge_nodes table is not available") from exc
    match = nodes[
        (nodes["node_id"].astype(str) == evidence_id)
        | (nodes["source"].astype(str) == evidence_id)
    ]
    if match.empty:
        raise ValueError(f"Evidence not found: {evidence_id}")
    row = match.iloc[0].to_dict()
    edges = _edge_summary(evidence_id, resolved_paths)
    return AgentEvidence(
        evidence_id=evidence_id,
        title=str(row.get("label", evidence_id)),
        summary=str(row.get("label", evidence_id)),
        source=str(row.get("source", "")),
        metadata={
            "node_type": str(row.get("node_type", "")),
            "edges": edges or _edge_summary(str(row.get("node_id", "")), resolved_paths),
        },
    )


def _edge_summary(evidence_id: str, paths: PipelinePaths) -> list[dict[str, str]]:
    try:
        edges = read_csv(paths.planning_data_dir, "knowledge_edges")
    except FileNotFoundError:
        return []
    if edges.empty:
        return []
    related = edges[
        (edges["source_id"].astype(str) == evidence_id)
        | (edges["target_id"].astype(str) == evidence_id)
    ]
    return [
        {
            "source_id": str(row.get("source_id", "")),
            "target_id": str(row.get("target_id", "")),
            "edge_type": str(row.get("edge_type", "")),
        }
        for row in related.to_dict("records")
    ]
