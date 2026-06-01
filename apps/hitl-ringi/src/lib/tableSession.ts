import { readSessionTables, writeSessionTables, type AppData, type Row } from "./data";
import { tablesFromAppData } from "./workflowRunner";

export function sessionRows(
  data: AppData | null,
  source: "sample" | "planning",
  tableName: string,
): Row[] {
  return readSessionTables()[tableName] ?? data?.[source]?.[tableName] ?? [];
}

export function saveSessionTable(
  data: AppData | null,
  tableName: string,
  rows: Row[],
): void {
  writeSessionTables({
    ...tablesFromAppData(data),
    [tableName]: rows,
  });
}
