type MetricCardProps = {
  label: string;
  value: string | number;
  description?: string;
  className?: string;
};

export default function MetricCard({ label, value, description, className }: MetricCardProps) {
  return (
    <section className={`metric-card ${className ?? ""}`.trim()} aria-label={label}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {description ? <div className="metric-description">{description}</div> : null}
    </section>
  );
}
