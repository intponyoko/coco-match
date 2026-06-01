from cocom.schema.axis import BaseModel


class SalesPlan(BaseModel):
    code: str
    industry_code: str
    period_code: str
    target_revenue: int

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        unique = ["code"]


class Opportunity(BaseModel):
    code: str
    sales_plan_code: str
    account_code: str
    solution_code: str
    start_period_code: str
    end_period_code: str
    estimated_revenue: int
    theme: str
    customer_pain: str
    evidence_case_ids: str
    grounding_score: float
    sizing_method: str
    delivery_model: str

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        unique = ["code"]


class OpportunityRequest(BaseModel):
    code: str
    opportunity_code: str
    start_period_code: str
    end_period_code: str
    role_code: str

    allocation_percentage: int
    headcount: int
    training_slots: int
    training_max_skill_gap: int
    phase: str
    evidence_case_ids: str
    grounding_score: float

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        unique = ["code"]


class OpportunityAssignment(BaseModel):
    code: str
    staff_code: str
    opportunity_request_code: str
    assignment_type: str

    class Config:  # pyright: ignore[reportIncompatibleVariableOverride]
        unique = ["code"]


class AssignmentRecommendation(BaseModel):
    assignment_recommendation_code: str
    staff_code: str
    opportunity_request_code: str
    slot: int
    assignment_type: str
    matching_reason: str
    comment: str


class ThemeCandidate(BaseModel):
    sales_plan_code: str
    theme: str
    solution_code: str
    evidence_case_ids: str
    similarity_score: float
    observed_revenue_mean: float
    observed_duration_mean: float
    delivery_model: str
    customer_pain: str


class ThemeRecommendation(BaseModel):
    sales_plan_code: str
    industry_code: str
    theme_rank: int
    theme: str
    solution_code: str
    planned_revenue: int
    evidence_case_ids: str
    theme_score: float
    observed_revenue_mean: float
    observed_duration_mean: float
    delivery_model: str
    customer_pain: str


class AccountRecommendation(BaseModel):
    sales_plan_code: str
    industry_code: str
    theme_rank: int
    account_rank: int
    account_code: str
    account_name: str
    account_segment: str
    theme: str
    solution_code: str
    planned_revenue: int
    evidence_case_ids: str
    theme_score: float
    account_score: float
    observed_revenue_mean: float
    observed_duration_mean: float
    delivery_model: str
    customer_pain: str


class ProjectSizingRecommendation(BaseModel):
    sales_plan_code: str
    project_spec_code: str
    industry_code: str
    account_code: str
    account_name: str
    account_segment: str
    solution_code: str
    start_period_code: str
    estimated_revenue: int
    duration_months: int
    theme: str
    customer_pain: str
    evidence_case_ids: str
    grounding_score: float
    project_training_allowed: bool
    project_training_max_skill_gap: int
    sizing_method: str
    delivery_model: str


class OpportunityRecommendation(BaseModel):
    sales_plan_code: str
    account_code: str
    account_name: str
    account_segment: str
    recommendation_code: str
    retrieval_rank: int
    retrieval_score: float
    case_id: str
    case_title: str
    industry_code: str
    solution_code: str
    revenue_band: str
    estimated_revenue: int
    duration_months: int
    business_theme: str
    customer_pain: str
    evidence: str
    retrieval_tags: str
    theme: str
    sizing_method: str
    delivery_model: str


class RequestRecommendation(BaseModel):
    request_recommendation_code: str
    project_spec_code: str
    start_period_code: str
    end_period_code: str
    role_code: str
    allocation_percentage: int
    headcount: int
    training_slots: int
    project_training_max_skill_gap: int
    role_phase_training_max_skill_gap: int
    training_max_skill_gap: int
    phase: str
    role_revenue: int
    required_person_month: float
    request_months: float
    evidence_case_ids: str
    grounding_score: float
    comment: str


class AllocationTrace(BaseModel):
    sales_plan_code: str
    opportunity_code: str
    request_code: str
    account_code: str
    industry_code: str
    solution_code: str
    case_id: str
    revenue_band: str
    role_code: str
    sales_plan_revenue: int
    capped_sales_plan_revenue: int
    period_opportunity_capacity: int
    project_duration_months: int
    delivery_phase: str
    opportunity_revenue: int
    role_revenue: int
    required_person_month: float
    request_months: float
    kg_headcount: int
    headcount: int
    training_slots: int
    project_training_max_skill_gap: int
    role_phase_training_max_skill_gap: int
    training_max_skill_gap: int
    allocation_percentage: int
    evidence_case_ids: str
    grounding_score: float


class MatchingTrace(BaseModel):
    opportunity_request_code: str
    role_code: str
    slot: int
    staff_code: str
    assignment_type: str
    status: str
    reason: str
    allocation_percentage: int
    period_code: str
    period_count: int
    skill_gap: str
    score: str


class StaffUtilization(BaseModel):
    staff_code: str
    period_code: str
    utilization_percentage: int


class ProposalRun(BaseModel):
    run_id: str
    task_name: str
    mode: str
    provider: str
    prompt_version: str
    input_hash: str
    output_tables: str
    fallback_used: bool
    created_at: str


class ProposalDiagnostic(BaseModel):
    run_id: str
    task_name: str
    kind: str
    severity: str
    description: str


class RetrievedEvidenceChunk(BaseModel):
    task_name: str
    target_table: str
    target_code: str
    evidence_id: str
    evidence_type: str
    title: str
    snippet: str
    score: float
    source: str
    retrieval_rank: int


class ConsistencyMetric(BaseModel):
    metric_scope: str
    metric_name: str
    metric_value: float
    reference_value: float
    delta_value: float
    status: str
    summary: str


class ProjectReviewIssue(BaseModel):
    project_spec_code: str
    sales_plan_code: str
    theme: str
    account_name: str
    issue_kind: str
    severity: str
    summary: str


class KnowledgeNode(BaseModel):
    node_id: str
    node_type: str
    label: str
    source: str


class KnowledgeEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    weight: float
    source: str
