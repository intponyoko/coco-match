import { byCode, rows, type AppData, type Row } from "./data";

export function downloadAssignmentPlan(data: AppData | null): void {
  if (!data) {
    return;
  }
  const assignments = rows(data, "planning", "opportunity_assignments");
  if (assignments.length === 0) {
    return;
  }

  const requests = byCode(rows(data, "planning", "opportunity_requests"));
  const opportunities = byCode(rows(data, "planning", "opportunities"));
  const staffs = byCode(rows(data, "sample", "staffs"));
  const titles = byCode(rows(data, "sample", "titles"));

  const exportRows = assignments.map((assignment) => {
    const request = requests.get(String(assignment.opportunity_request_code ?? ""));
    const opportunity = opportunities.get(String(request?.opportunity_code ?? ""));
    const staff = staffs.get(String(assignment.staff_code ?? ""));
    const title = titles.get(String(staff?.title_code ?? ""));
    return {
      assignment_code: String(assignment.code ?? ""),
      staff_code: String(assignment.staff_code ?? ""),
      staff_name: String(staff?.name ?? ""),
      department_code: String(staff?.department_code ?? ""),
      title_code: String(staff?.title_code ?? ""),
      title_name: String(title?.name ?? ""),
      opportunity_request_code: String(assignment.opportunity_request_code ?? ""),
      opportunity_code: String(request?.opportunity_code ?? ""),
      role_code: String(request?.role_code ?? ""),
      assignment_type: String(assignment.assignment_type ?? ""),
      start_period_code: String(request?.start_period_code ?? ""),
      end_period_code: String(request?.end_period_code ?? ""),
      allocation_percentage: String(request?.allocation_percentage ?? ""),
      headcount: String(request?.headcount ?? ""),
      theme: String(opportunity?.theme ?? ""),
      account_code: String(opportunity?.account_code ?? ""),
      solution_code: String(opportunity?.solution_code ?? ""),
      estimated_revenue: String(opportunity?.estimated_revenue ?? ""),
    };
  });

  downloadCsv("assignment-plan.csv", exportRows);
}

function downloadCsv(filename: string, rowsToExport: Row[]): void {
  const csv = toCsv(rowsToExport);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function toCsv(rowsToExport: Row[]): string {
  if (rowsToExport.length === 0) {
    return "";
  }
  const headers = Array.from(
    rowsToExport.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(key));
      return keys;
    }, new Set<string>()),
  );
  const lines = [
    headers.join(","),
    ...rowsToExport.map((row) => headers.map((header) => escapeCsv(row[header])).join(",")),
  ];
  return `\uFEFF${lines.join("\n")}`;
}

function escapeCsv(value: unknown): string {
  const text = String(value ?? "");
  if (!/[",\n]/.test(text)) {
    return text;
  }
  return `"${text.replaceAll('"', '""')}"`;
}
