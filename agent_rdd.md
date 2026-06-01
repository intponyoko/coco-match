# coco-match AI Agent RDD

## 目的

`coco-match` のHITL Pipelineに対して、LLM Agentが支援できる領域を定義する。対象は以下の4つのAgentとする。

1. Opportunity Portfolio提案 Agent
2. Project / Request設計 Agent
3. Matching Review Agent
4. 個人キャリア計画 Agent

本RDDでは、Agentは最終意思決定者ではなく、人間の承認・編集を支援する補助者として扱う。Pipelineの確定状態は従来通りTable単位のApproveで管理する。

## 前提

- 実行環境はMicrosoft Azureを想定する。
- LLMはAzure OpenAIまたはAzure AI Foundry Agent Service経由で利用する。
- 過去案件、提案書、PJ実績、Role構成、Skill定義などはAzure AI Searchにindexし、RAGで参照する。
- Pipeline本体は既存のFastAPI / stateless pipeline APIをToolとして呼び出す。
- Agentの出力は必ず構造化JSONまたはTable形式に変換し、UIで人間が確認・編集・承認する。
- Agentが直接DBを更新しない。更新はHITL承認後のPipelineで行う。

## 全体アーキテクチャ

```text
Astro UI
  |
  | HITL review / approve
  v
FastAPI Stateless Pipeline API
  |
  | function/tool call
  v
Azure AI Foundry Agent Service
  |
  | RAG
  v
Azure AI Search
  |
  | indexed knowledge
  v
Past cases / proposals / project records / skill-role definitions
```

## 共通Agent要件

### Functional Requirements

- Agentは、入力Table、検索根拠、生成結果、説明文を返す。
- Agent出力には必ず `evidence_case_ids` または検索根拠のIDを含める。
- Agent出力は、UIで編集可能なTableまたはカード表示に変換できる形式にする。
- Agentは既存Pipeline APIをToolとして呼び出せる。
- Agentは不確実な場合、候補を複数提示し、推奨理由とリスクを返す。
- Agentは承認済みTableを勝手に上書きしない。

### Non-functional Requirements

- Agent出力は再現性のため、使用したinput hash、prompt version、retrieval query、model nameをmetadataに残す。
- 個人情報や人事情報を扱うため、staff単位の出力は必要最小限にする。
- Prompt injection対策として、RAG文書は命令ではなく根拠データとして扱う。
- 生成結果はSchema validationを通す。
- Token costを抑えるため、Agentに渡すRaw Tableは必要列だけに絞る。

## Agent 1: Opportunity Portfolio提案 Agent

### 対象画面

- `2. Theme / Solution`

### 目的

SalesPlanから、過去事例を根拠にしたTheme / Solution候補を提案する。人間は候補カードを追加・削除・編集し、最終的にTableとして承認する。

### Input

- `sales_plans`
- `industries`
- `solutions`
- 過去案件Knowledge
  - industry
  - solution
  - theme
  - customer pain
  - observed revenue
  - observed duration
  - delivery model
  - evidence document ids

### Output

- `theme_recommendations`
  - `sales_plan_code`
  - `industry_code`
  - `theme_rank`
  - `theme`
  - `solution_code`
  - `planned_revenue`
  - `customer_pain`
  - `evidence_case_ids`
  - `theme_score`
  - `observed_revenue_mean`
  - `observed_duration_mean`
  - `delivery_model`
  - `agent_reason`
  - `risk_note`

### Agent Tasks

- SalesPlanごとに、狙うべきTheme/Solution候補を提案する。
- 過去案件から類似テーマを検索し、根拠を提示する。
- 売上目標に対して過小/過大なThemeを検出する。
- 重複Themeや粒度が細かすぎるThemeを統合候補として提示する。
- 人間が追加したThemeに対して類似事例を補完検索する。

### Tools

- `search_past_cases(industry_code, solution_code, target_revenue, period_code)`
- `score_theme_candidates(sales_plan, cases)`
- `propose_theme_solutions(tables)`

### HITL

- 人間はTheme/Solution候補カードを確認する。
- 人間はThemeを追加・削除・編集できる。
- 承認単位は `theme_recommendations` Table全体。

## Agent 2: Project / Request設計 Agent

### 対象画面

- `3. Project / Request`

### 目的

承認済みTheme/Solutionを元に、Account、PJ規模、期間、Role/人数/稼働率、Training枠を提案する。

### Input

- `theme_recommendations`
- `sales_plans`
- `accounts` またはAccount候補Knowledge
- `roles`
- `role_skills`
- `staffs`
- `titles`
- 過去案件Knowledge
  - account segment
  - project size
  - duration
  - role mix
  - phase
  - allocation
  - training feasibility

### Output

- `project_sizing_recommendations`
  - `project_spec_code`
  - `sales_plan_code`
  - `account_code`
  - `account_name`
  - `solution_code`
  - `start_period_code`
  - `duration_months`
  - `estimated_revenue`
  - `theme`
  - `customer_pain`
  - `evidence_case_ids`
  - `project_training_allowed`
  - `project_training_max_skill_gap`
  - `agent_reason`
- `request_recommendations`
  - `request_recommendation_code`
  - `project_spec_code`
  - `role_code`
  - `phase`
  - `headcount`
  - `allocation_percentage`
  - `training_slots`
  - `training_max_skill_gap`
  - `start_period_code`
  - `end_period_code`
  - `evidence_case_ids`
  - `agent_reason`

### Agent Tasks

- Themeごとに実施可能なAccount候補を提案する。
- 類似案件からPJ規模・期間を推定する。
- 類似案件からRole構成と人数を提案する。
- Role/人数/Allocationが過剰または不足していないか説明する。
- Training slotを入れやすいPJかどうかを判断する。
- 人間の編集後に、売上・FTE・期間・Role構成への影響を説明する。

### Tools

- `search_similar_projects(theme, solution_code, account_segment)`
- `estimate_project_size(theme_recommendation, similar_cases)`
- `estimate_request_mix(project_spec, similar_cases)`
- `preview_capacity(project_specs, request_recommendations)`
- `propose_project_requests(tables)`
- `materialize_opportunities(tables)`

### HITL

- 人間はProject timelineでPJ期間・規模を確認する。
- 人間はRole設定を編集する。
- 承認単位は `project_sizing_recommendations` と `request_recommendations`。

## Agent 3: Matching Review Agent

### 対象画面

- `5. Matching Approval`

### 目的

Matching結果を部署層が承認できるように、未割当、育成枠、高稼働、0% staff、Assignee変更の影響を説明する。

### Input

- `opportunity_requests`
- `assignment_recommendations`
- `matching_trace`
- `staff_utilization`
- `staffs`
- `titles`
- `staff_career`
- `roles`
- `role_skills`
- `staff_preference_options`
- `staff_preference_submissions`

### Output

- `matching_review_summary`
  - matching rate
  - assigned / training / unassigned
  - utilization distribution
  - risk flags
  - recommended actions
- `assignment_change_suggestions`
  - `opportunity_request_code`
  - current assignee
  - suggested assignee
  - reason
  - expected risk
  - expected utilization impact

### Agent Tasks

- 未割当Requestの原因を自然言語で説明する。
- Tough assignmentが妥当か判断材料を提示する。
- 高稼働Staffのリスクを説明する。
- 0% Staffが生まれている理由を説明する。
- Assignee変更時に、Skill gapと稼働率への影響を説明する。
- 承認コメントをドラフトする。

### Tools

- `explain_unassigned(matching_trace, role_skills, staff_career)`
- `suggest_alternative_assignees(request, staff_pool, utilization)`
- `preview_assignment_change(request_code, staff_code)`
- `finalize_assignments(tables)`

### HITL

- 人間はOpportunity単位でAssigneeを確認・変更する。
- 人間は通常/育成を切り替えられる。
- Agentは変更の影響説明を返す。
- 承認単位は `assignment_recommendations`。

## Agent 4: 個人キャリア計画 Agent

### 対象画面

- `4. Personal Interest`

### 目的

個人が一年間のPJ希望・研修希望・キャリア方針を決めるために、自分のSkill、Title、Role目標に基づく提案を行う。

### Input

- `staffs`
- `titles`
- `staff_career`
- `roles`
- `role_skills`
- `opportunities`
- `opportunity_requests`
- `staff_preference_options`
- `staff_preference_submissions`

### Output

- `career_plan_suggestions`
  - recommended projects by month
  - recommended training role by month
  - project interest recommendation
  - skill growth rationale
  - career comment draft
- optional:
  - `aspirational_project_interests`
    - skillが足りないが関心があるPJ
    - learning reason
    - required skill gap

### Agent Tasks

- 月ごとの推奨PJを説明する。
- PJに入らない月の研修Roleを提案する。
- 参画したいPJがキャリアにどう効くか説明する。
- 全くSkillが足りないPJでも、学習テーマとして関心を記録できるよう補助する。
- 年間キャリアコメントをドラフトする。

### Tools

- `rank_preference_options(staff, options, career_goal)`
- `explain_project_fit(staff, opportunity, request, role_skills)`
- `suggest_training_months(staff, roles, staff_career)`
- `submit_staff_preferences(tables)`

### HITL

- 個人は月ごとのPJ/研修/空き月を決める。
- 個人はPJ別の参画意思を設定する。
- Agentは推奨一括入力とコメント生成を支援する。
- Demoでは1人の提出後、他スタッフはデフォルト提出される。

## Azure実装案

### Azure Resources

- Azure AI Foundry Agent Service
- Azure OpenAI
- Azure AI Search
- Azure Blob Storage
- Azure Functions
- Azure App Service or Container Apps for FastAPI
- Azure Static Web Apps for Astro UI
- Application Insights
- Key Vault

### Tool/API設計

Agentが呼び出すToolは、既存FastAPIのstateless pipeline APIを薄くラップする。

```text
POST /agent/opportunity-portfolio/propose
POST /agent/project-requests/propose
POST /agent/matching/review
POST /agent/career-plan/propose
GET  /agent/evidence/{evidence_id}
```

実装では上記に加えて、互換性を維持したままversioned APIも提供する。

```text
POST /api/v1/agent/opportunity-portfolio/propose
POST /api/v1/agent/project-requests/propose
POST /api/v1/agent/matching/review
POST /api/v1/agent/career-plan/propose
GET  /api/v1/agent/evidence/{evidence_id}
```

各APIは以下を返す。

```json
{
  "tables": {},
  "explanations": [],
  "evidence": [],
  "metadata": {
    "agent_name": "...",
    "model": "...",
    "prompt_version": "...",
    "retrieval_query": "...",
    "input_hash": "..."
  }
}
```

## 実装フェーズ

### Phase 1: Explanation-only Agent

- 既存Pipeline結果を読み、説明だけを生成する。
- Tableは変更しない。
- 対象:
  - Matching Review Agent
  - Project / Request設計 Agent

### Phase 2: Suggestion Agent

- Agentが候補Tableを生成する。
- 人間がUIで編集・承認する。
- 対象:
  - Opportunity Portfolio提案 Agent
  - 個人キャリア計画 Agent

### Phase 3: Tool-calling Agent

- AgentがRAG検索、Pipeline preview、capacity previewをToolとして呼び出す。
- Agent出力はSchema validation後にUIへ返す。

### Phase 4: Continuous Knowledge Update

- 過去案件・提案書・実績データを取り込み、Knowledgeを更新する。
- KG更新案もHITLレビュー対象にする。

## 最初に作るべきMVP

最初は以下の2つが最も効果が高い。

1. `Opportunity Portfolio提案 Agent`
   - SalesPlanからTheme/Solution候補を説明付きで出す。
2. `Matching Review Agent`
   - 既存Matching結果を要約し、未割当・育成枠・稼働偏りを説明する。

この2つは、既存UIに追加しやすく、Agentが最終決定を持たないため導入リスクが低い。

## 現在の実装状態

- FastAPIに上記Agent APIを追加済み。
- v1はAzure未接続の場合deterministic fallbackとして、既存stateless pipelineをToolのように呼び出し、説明・診断・Evidence参照を返す。
- Azure OpenAI環境変数が設定されている場合、structured outputsで説明・診断を生成する。
- Azure AI Search環境変数が設定されている場合、Agent入力から検索queryを作り、grounding documentをLLM入力に加える。
- Astro UIはSalesPlan、Theme/Request、個人希望、Matchingの各HITL画面からAgent APIを呼び、返却されたTableをsession tableとして保存する。
- Azure OpenAI / Azure AI Searchへの接続は `src/cocom/agent/common/client.py` に実装済み。将来Foundry Agent Serviceを使う場合は同じclient interfaceを差し替える。
