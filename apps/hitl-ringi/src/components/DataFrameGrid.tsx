import { useMemo } from "react";
import { AgGridReact } from "ag-grid-react";
import type {
  CellValueChangedEvent,
  ColDef,
  GridOptions,
} from "ag-grid-community";
import { AllCommunityModule, ModuleRegistry } from "ag-grid-community";
import type { Row } from "../lib/data";

ModuleRegistry.registerModules([AllCommunityModule]);

type DataFrameGridColumn = {
  key: string;
  label?: string;
  editable?: boolean;
  type?: "text" | "number" | "boolean" | "select";
  options?: string[];
};

type DataFrameGridProps = {
  rows: Row[];
  columns: DataFrameGridColumn[];
  rowKey: (row: Row, index: number) => string;
  onRowsChange: (rows: Row[]) => void;
  height?: number;
};

export default function DataFrameGrid({
  rows,
  columns,
  rowKey,
  onRowsChange,
  height = 520,
}: DataFrameGridProps) {
  const keyedRows = useMemo(
    () =>
      rows.map((row, index) => ({
        ...row,
        __row_id: rowKey(row, index),
      })),
    [rows, rowKey],
  );

  const columnDefs = useMemo<ColDef[]>(
    () =>
      columns.map((column) => ({
        field: column.key,
        headerName: column.label ?? column.key,
        editable: column.editable ?? true,
        sortable: true,
        filter: true,
        resizable: true,
        cellDataType: agGridType(column.type),
        cellEditor: column.type === "select" ? "agSelectCellEditor" : undefined,
        cellEditorParams:
          column.type === "select" ? { values: column.options ?? [] } : undefined,
      })),
    [columns],
  );

  const defaultColDef = useMemo<ColDef>(
    () => ({
      minWidth: 130,
      flex: 1,
      editable: true,
    }),
    [],
  );

  const gridOptions = useMemo<GridOptions>(
    () => ({
      animateRows: false,
      stopEditingWhenCellsLoseFocus: true,
      singleClickEdit: true,
      getRowId: (params) => String(params.data.__row_id),
    }),
    [],
  );

  function handleCellValueChanged(event: CellValueChangedEvent) {
    const field = event.colDef.field;
    if (!field) return;
    const rowId = String(event.data.__row_id);
    onRowsChange(
      rows.map((row, index) =>
        rowKey(row, index) === rowId
          ? { ...row, [field]: coerceValue(event.newValue, columns.find((column) => column.key === field)?.type) }
          : row,
      ),
    );
  }

  if (columns.length === 0) {
    return <p className="muted">No columns.</p>;
  }

  return (
    <div className="dataframe-grid ag-theme-quartz" style={{ height }}>
      <AgGridReact
        rowData={keyedRows}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        gridOptions={gridOptions}
        onCellValueChanged={handleCellValueChanged}
      />
    </div>
  );
}

function agGridType(type: DataFrameGridColumn["type"]) {
  if (type === "number") return "number";
  if (type === "boolean") return "boolean";
  return "text";
}

function coerceValue(value: unknown, type: DataFrameGridColumn["type"]) {
  if (type === "number") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  if (type === "boolean") {
    return value === true || value === "true";
  }
  return value == null ? "" : String(value);
}

