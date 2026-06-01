from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import pandas as pd

from cocom.schema import ProposalDiagnostic, ProposalRun


@dataclass(frozen=True)
class DeterministicProposalArtifacts:
    proposal_runs: pd.DataFrame
    proposal_diagnostics: pd.DataFrame
    proposal_metadata: dict[str, Any]


def proposal_input_hash(tables: dict[str, pd.DataFrame]) -> str:
    signature = "|".join(
        f"{name}:{len(frame)}:{','.join(frame.columns)}"
        for name, frame in sorted(tables.items())
    )
    return sha256(signature.encode("utf-8")).hexdigest()[:16]


def build_deterministic_proposal_artifacts(
    *,
    task_name: str,
    prompt_version: str,
    input_tables: dict[str, pd.DataFrame],
    output_tables: dict[str, pd.DataFrame],
    description: str,
) -> DeterministicProposalArtifacts:
    input_hash = proposal_input_hash(input_tables)
    run_id = f"{task_name}-deterministic-{input_hash[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    proposal_runs = ProposalRun.data_frame(
        [
            {
                "run_id": run_id,
                "task_name": task_name,
                "mode": "deterministic",
                "provider": "deterministic",
                "prompt_version": prompt_version,
                "input_hash": input_hash,
                "output_tables": ";".join(sorted(output_tables)),
                "fallback_used": False,
                "created_at": created_at,
            }
        ]
    )
    proposal_diagnostics = ProposalDiagnostic.data_frame(
        [
            {
                "run_id": run_id,
                "task_name": task_name,
                "kind": "proposal_mode",
                "severity": "info",
                "description": description,
            }
        ]
    )
    proposal_metadata = {
        "proposal_run_id": run_id,
        "proposal_task": task_name,
        "proposal_mode": "deterministic",
        "proposal_provider": "deterministic",
        "proposal_prompt_version": prompt_version,
        "proposal_input_hash": input_hash,
        "proposal_fallback_used": False,
    }
    return DeterministicProposalArtifacts(
        proposal_runs=proposal_runs,
        proposal_diagnostics=proposal_diagnostics,
        proposal_metadata=proposal_metadata,
    )
