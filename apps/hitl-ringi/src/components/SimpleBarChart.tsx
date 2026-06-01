type SimpleBarChartProps = {
  title?: string;
  rows: { label: string; value: number; description?: string }[];
  valueFormatter?: (value: number) => string;
};

export default function SimpleBarChart({ title, rows, valueFormatter }: SimpleBarChartProps) {
  const max = Math.max(...rows.map((row) => row.value), 1);
  return (
    <section className="chart" aria-label={title}>
      {title ? <h3>{title}</h3> : null}
      <div className="bar-chart">
        {rows.map((row) => (
          <div className="bar-row" key={row.label}>
            <div className="bar-label">{row.label}</div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${Math.max(2, (row.value / max) * 100)}%` }} />
            </div>
            <div className="bar-value">{valueFormatter ? valueFormatter(row.value) : row.value.toLocaleString()}</div>
            {row.description ? <div className="bar-description">{row.description}</div> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
