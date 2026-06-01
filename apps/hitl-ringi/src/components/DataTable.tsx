type DataTableProps<T extends Record<string, unknown>> = {
  rows: T[];
  columns: { key: keyof T | string; label: string; format?: (value: unknown, row: T) => string }[];
  emptyMessage?: string;
};

export default function DataTable<T extends Record<string, unknown>>({
  rows,
  columns,
  emptyMessage = "No rows.",
}: DataTableProps<T>) {
  if (rows.length === 0) {
    return <p className="muted">{emptyMessage}</p>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th scope="col" key={String(column.key)}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={String(row.code ?? row.id ?? rowIndex)}>
              {columns.map((column) => {
                const value = row[column.key as keyof T];
                return (
                  <td key={String(column.key)}>
                    {column.format ? column.format(value, row) : String(value ?? "")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
