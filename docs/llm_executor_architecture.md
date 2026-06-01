# LLM Executor Architecture

LLMの呼び出し種別は、Pipeline単位ではなく以下の3種類に限定する。

1. `Proposal`
2. `Review`
3. `Insight`

## Goal

- Pipelineが増えても、LLM clientの呼び出し方を増やさない
- 出力Schemaの正本をアプリケーション側に置く
- Foundryは推論実行基盤としてのみ扱い、業務Schemaの所有者にしない

## Executors

### Proposal

構造化Tableを生成する実行器。

- Entry point: `run_table_proposal`
- Input:
  - summarized input tables
  - retrieved evidence chunks
  - output table specs
- Output:
  - `tables`
  - `diagnostics`
- Schema owner:
  - Pandera schema
  - fallback table columns

対象:

- `propose_theme_solutions`
- `propose_project_requests`
- `propose_assignment_options`
- `propose_assignments`

### Review

既存のTableや提案結果をレビューし、説明と診断を返す実行器。

- Entry point: `run_review_agent`
- Input:
  - summarized review tables
  - fallback explanations
  - fallback diagnostics
- Output:
  - `explanations`
  - `diagnostics`

対象:

- `opportunity_portfolio`
- `project_requests`
- `matching_review`
- `career_plan`

### Insight

画面やworkflow stage全体の状態を要約して返す実行器。

- Entry point: `run_insight_agent`
- Input:
  - summarized stage tables
  - focus
  - fallback insight object
- Output:
  - `stage`
  - `headline`
  - `summary`
  - `confidence_*`
  - `rationale`
  - `watchouts`
  - `alternatives`
  - `suggested_actions`
  - `impact`
  - `evidence_refs`
  - `metadata`

対象:

- `workflow_insight`

## Ownership Boundary

### Application owns

- business table names
- row schema
- normalization
- validation
- fallback behavior
- provenance and diagnostics

### Foundry owns

- model execution
- JSON schema enforcement
- retrieval/tool execution in online mode

## Pipeline Mapping

| Pipeline / API | Executor | Notes |
|---|---|---|
| `propose_theme_solutions` | `Proposal` | Theme / Solution and evidence tables |
| `propose_project_requests` | `Proposal` | Project sizing and request tables |
| `propose_assignment_options` | `Proposal` | Staff option tables |
| `propose_assignments` | `Proposal` | Assignment, trace, utilization tables |
| `agent/opportunity-portfolio/propose` | `Review` | Theme proposal explanation |
| `agent/project-requests/propose` | `Review` | Project / request explanation |
| `agent/matching/review` | `Review` | Matching review explanation |
| `agent/career-plan/propose` | `Review` | Career option explanation |
| `agent/insights` | `Insight` | Stage summary and actions |

## Rule For New Work

新しいPipelineやAgent APIを追加するときは、最初に以下を決める。

1. その機能は `Proposal`, `Review`, `Insight` のどれか
2. アプリ側で何をfallbackとして保持するか
3. どのTableまたはstage objectをSchema正本として扱うか

この3つに入らない場合だけ、新しいexecutor種別を検討する。
