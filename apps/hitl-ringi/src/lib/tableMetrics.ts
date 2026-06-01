import { numberValue, type Row } from "./data";

export type ChartRow = {
  label: string;
  value: number;
};

export function groupSumRows(
  rows: Row[],
  groupKey: string,
  valueKey: string,
  limit = 12,
): ChartRow[] {
  return groupedRows(rows, groupKey, (row) => numberValue(row[valueKey]), limit);
}

export function groupCountRows(
  rows: Row[],
  groupKey: string,
  limit = 12,
): ChartRow[] {
  return groupedRows(rows, groupKey, () => 1, limit);
}

function groupedRows(
  rows: Row[],
  groupKey: string,
  value: (row: Row) => number,
  limit: number,
): ChartRow[] {
  const grouped = new Map<string, number>();
  for (const row of rows) {
    const label = String(row[groupKey] ?? "N/A");
    grouped.set(label, (grouped.get(label) ?? 0) + value(row));
  }
  return Array.from(grouped.entries())
    .map(([label, rowValue]) => ({ label, value: rowValue }))
    .sort((a, b) => b.value - a.value)
    .slice(0, limit);
}
