import { lazy, Suspense } from "react";
import type { Row } from "../lib/data";

const DataFrameGrid = lazy(() => import("./DataFrameGrid"));

type RawDataDisclosureProps<T extends Row> = {
  title: string;
  rows: T[];
  columns: { key: keyof T | string; label: string; format?: (value: unknown, row: T) => string }[];
};

export default function RawDataDisclosure<T extends Row>({
  title,
  rows,
  columns,
}: RawDataDisclosureProps<T>) {
  return (
    <details className="raw-disclosure">
      <summary>{title}</summary>
      <Suspense fallback={<p className="muted">Loading table...</p>}>
        <DataFrameGrid
          rows={rows}
          columns={columns.map((column) => ({
            key: String(column.key),
            label: column.label,
            editable: false,
          }))}
          rowKey={(row, index) => String(row.code ?? row.id ?? index)}
          onRowsChange={() => undefined}
          height={360}
        />
      </Suspense>
    </details>
  );
}
