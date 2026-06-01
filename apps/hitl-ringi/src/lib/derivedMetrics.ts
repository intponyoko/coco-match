import type { ApprovalRecord } from "./approvalState";
import { byCode, numberValue, rows, sumBy, type AppData, type Row } from "./data";
import { workflowNodesFromAppData, workflowStepperRows } from "./workflowState";

export function workflowSteps(data: AppData | null, records: ApprovalRecord[] = []) {
  return workflowStepperRows(workflowNodesFromAppData(data, records));
}

export function managementSummary(data: AppData | null) {
  const salesPlans = rows(data, "sample", "sales_plans");
  const opportunities = rows(data, "planning", "opportunities");
  const requests = rows(data, "planning", "opportunity_requests");
  const trace = rows(data, "planning", "matching_trace");
  const staffs = byCode(rows(data, "sample", "staffs"));
  const titles = byCode(rows(data, "sample", "titles"));
  const averageTitlePrice = average(rows(data, "sample", "titles").map((row) => numberValue(row.price)));

  const assignedTrace = trace.filter((row) => String(row.status) === "assigned");
  const unassignedTrace = trace.filter((row) => String(row.status) !== "assigned");
  const requestByCode = byCode(requests);

  const capacityRevenue = (items: Row[]) =>
    items.reduce((total, item) => {
      const request = requestByCode.get(String(item.opportunity_request_code ?? ""));
      const staff = staffs.get(String(item.staff_code ?? ""));
      const title = titles.get(String(staff?.title_code ?? ""));
      const titlePrice = numberValue(title?.price) || averageTitlePrice;
      return (
        total
        + titlePrice
          * (numberValue(request?.allocation_percentage) / 100)
          * Math.max(1, numberValue(item.period_count))
      );
    }, 0);

  return {
    planRevenue: sumBy(salesPlans, "target_revenue"),
    opportunityRevenue: sumBy(opportunities, "estimated_revenue"),
    assignedCapacityRevenue: capacityRevenue(assignedTrace),
    unfilledCapacityRevenue: capacityRevenue(unassignedTrace),
    matchingRate: trace.length ? assignedTrace.length / trace.length : 0,
  };
}

function average(values: number[]): number {
  const valid = values.filter((value) => Number.isFinite(value) && value > 0);
  if (valid.length === 0) {
    return 0;
  }
  return valid.reduce((total, value) => total + value, 0) / valid.length;
}
