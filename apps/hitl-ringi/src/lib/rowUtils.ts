import type { Row } from "./data";

export function uniqueCount(items: Row[], key: string): number {
  return new Set(items.map((row) => String(row[key] ?? ""))).size;
}

export function uniqueStringValues(items: Row[], key: string): string[] {
  return Array.from(new Set(items.map((item) => String(item[key] ?? "")).filter(Boolean))).sort();
}

export function rowByCode(
  items: Row[],
  code: string,
  codeKey = "code",
): Row | undefined {
  return items.find((row) => String(row[codeKey] ?? "") === code);
}
