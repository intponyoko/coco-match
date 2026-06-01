import type { Row } from "./data";

export function labelFromMap(
  itemsByCode: Map<string, Row>,
  code: unknown,
  nameKey = "name",
): string {
  const normalizedCode = String(code ?? "");
  if (!normalizedCode) {
    return "";
  }
  return String(itemsByCode.get(normalizedCode)?.[nameKey] ?? normalizedCode);
}

export function labelRows(
  rows: { label: string; value: number; description?: string }[],
  itemsByCode: Map<string, Row>,
): { label: string; value: number; description?: string }[] {
  return rows.map((row) => ({
    ...row,
    label: labelFromMap(itemsByCode, row.label),
  }));
}
