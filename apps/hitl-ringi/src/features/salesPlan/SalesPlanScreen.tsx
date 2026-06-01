import { useMemo, useState } from "react";
import {
  ArcElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { Doughnut, Line } from "react-chartjs-2";
import AgentAssistSummary from "../../components/AgentAssistSummary";
import HITLStageHeader from "../../components/HITLStageHeader";
import MetricCard from "../../components/MetricCard";
import RawDataDisclosure from "../../components/RawDataDisclosure";
import SubmissionProgress from "../../components/SubmissionProgress";
import type { AgentResponse } from "../../lib/apiClient";
import { useApprovalState } from "../../lib/approvalState";
import { chartColor } from "../../lib/chartColors";
import { byCode, rows, sumBy, useAppData } from "../../lib/data";
import { formatCurrency } from "../../lib/formatting";
import { labelFromMap, labelRows } from "../../lib/labels";
import { sessionRows } from "../../lib/tableSession";
import { groupSumRows } from "../../lib/tableMetrics";
import { approveTable, runAgentWorkflowEndpoint, tablesFromAppData } from "../../lib/workflowRunner";

ChartJS.register(
  ArcElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
);

export default function SalesPlanScreen() {
  const { data, loading, error } = useAppData();
  const approval = useApprovalState();
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [agentResponse, setAgentResponse] = useState<AgentResponse | null>(null);
  const salesPlans = sessionRows(data, "sample", "sales_plans");
  const originalPlans = rows(data, "sample", "sales_plans");
  const industriesByCode = byCode(rows(data, "sample", "industries"));
  const totalRevenue = sumBy(salesPlans, "target_revenue");
  const averageMonthlyRevenue = totalRevenue / Math.max(new Set(salesPlans.map((row) => String(row.period_code ?? ""))).size, 1);
  const topIndustry = useMemo(
    () => groupSumRows(salesPlans, "industry_code", "target_revenue", 5)[0],
    [salesPlans],
  );

  if (loading) return <p>Loading app data...</p>;
  if (error) return <p role="alert">Data load error: {error}</p>;

  async function approve() {
    setRunning(true);
    setRunError(null);
    try {
      const tables = { ...tablesFromAppData(data), sales_plans: salesPlans };
      const response = await runAgentWorkflowEndpoint(
        "/agent/opportunity-portfolio/propose",
        tables,
        approveTable({}, "sales_plans", "executive", ""),
      );
      setAgentResponse(response);
      approval.setTableApproval("sales_plans", "approved", "executive", "");
      window.location.href = "/";
    } catch (err) {
      setRunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  const industryRevenue = labelRows(groupSumRows(salesPlans, "industry_code", "target_revenue", 8), industriesByCode);
  const monthRevenue = monthlyRevenueRows(salesPlans);

  return (
    <div className="grid">
      <HITLStageHeader
        owner="経営層"
        canEdit={["SalesPlanの確認・承認"]}
        canView={["月次・Industry別計画", "Opportunity化された金額との差分"]}
        workflow={{
          step: 1,
          status: approval.statusOf("sales_plans"),
          prerequisite: "経営層が年間売上計画を入力できる状態",
          nextAction: "Theme/Solution候補を生成",
        }}
      />
      <section className="panel sales-plan-review">
        <div className="toolbar">
          <div>
            <h2>SalesPlan BI</h2>
            <p className="muted">
              月別・Industry別の計画配分を確認し、問題がなければ承認してTheme/Solution提案へ進めます。
            </p>
          </div>
        </div>
        <div className="grid cols-3">
          <MetricCard label="SalesPlans" value={salesPlans.length} />
          <MetricCard label="Annual Plan Revenue" value={formatCurrency(totalRevenue)} />
          <MetricCard label="Average Monthly Revenue" value={formatCurrency(averageMonthlyRevenue)} />
          <MetricCard
            label="Top Industry"
            value={topIndustry ? labelFromMap(industriesByCode, topIndustry.label) : "N/A"}
            description={topIndustry ? formatCurrency(topIndustry.value) : undefined}
          />
          <MetricCard
            label="Peak Month"
            value={peakRow(monthRevenue)?.label ?? "N/A"}
            description={peakRow(monthRevenue) ? formatCurrency(peakRow(monthRevenue)?.value ?? 0) : undefined}
          />
          <MetricCard
            label="Monthly Volatility"
            value={`${monthlyVolatility(monthRevenue).toFixed(1)}%`}
            description="月次平均に対する標準偏差"
          />
        </div>
        <div className="grid cols-2">
          <MonthlyRevenueChart rows={monthRevenue} />
          <IndustryShareChart rows={industryRevenue} totalRevenue={totalRevenue} />
        </div>
        <RawDataDisclosure
          title="元データをDataFrameで確認"
          rows={originalPlans}
          columns={[
            { key: "code", label: "Code" },
            { key: "period_code", label: "Period" },
            { key: "industry_code", label: "Industry" },
            { key: "target_revenue", label: "Target Revenue", format: (value) => formatCurrency(Number(value)) },
          ]}
        />
      </section>
      <section className="panel approval-panel">
        <h2>承認</h2>
        <p className="muted">このSalesPlanを承認すると、次工程のTheme/Solution候補が生成されます。</p>
        {running ? (
          <SubmissionProgress
            title="Proposing Theme / Solution"
            body="SalesPlanをもとにTheme/Solution候補を生成しています。完了後に次の承認画面へ進みます。"
          />
        ) : null}
        {runError ? <p role="alert" className="error-text">{runError}</p> : null}
        <AgentAssistSummary response={agentResponse} />
        <div className="toolbar action-toolbar">
          <button disabled={running || salesPlans.length === 0} onClick={approve}>承認する</button>
        </div>
      </section>
    </div>
  );
}

type RevenuePoint = {
  label: string;
  value: number;
};

function monthlyRevenueRows(planRows: ReturnType<typeof rows>): RevenuePoint[] {
  const grouped = new Map<string, number>();
  for (const row of planRows) {
    const period = String(row.period_code ?? "N/A");
    grouped.set(period, (grouped.get(period) ?? 0) + Number(row.target_revenue ?? 0));
  }
  return Array.from(grouped.entries())
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

function MonthlyRevenueChart({ rows }: { rows: RevenuePoint[] }) {
  const chartData: ChartData<"line"> = {
    labels: rows.map((row) => row.label),
    datasets: [
      {
        label: "月次売上計画",
        data: rows.map((row) => row.value),
        borderColor: "#0017c1",
        backgroundColor: "rgb(0 23 193 / 12%)",
        borderWidth: 2,
        fill: true,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.32,
      },
    ],
  };
  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => formatCurrency(Number(context.parsed.y ?? 0)),
        },
      },
    },
    scales: {
      x: { grid: { display: false } },
      y: {
        beginAtZero: true,
        ticks: {
          callback: (value) => formatCurrency(Number(value)),
        },
      },
    },
  };

  return (
    <section className="chart-card" aria-label="Monthly sales plan revenue">
      <h3>Monthly Revenue Plan</h3>
      <div className="chartjs-frame">
        <Line data={chartData} options={options} />
      </div>
    </section>
  );
}

function IndustryShareChart({
  rows,
  totalRevenue,
}: {
  rows: RevenuePoint[];
  totalRevenue: number;
}) {
  const chartData: ChartData<"doughnut"> = {
    labels: rows.map((row) => row.label),
    datasets: [
      {
        data: rows.map((row) => row.value),
        backgroundColor: rows.map((_, index) => chartColor(index)),
        borderColor: "#ffffff",
        borderWidth: 2,
      },
    ],
  };
  const options: ChartOptions<"doughnut"> = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "62%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => {
            const value = Number(context.parsed ?? 0);
            const percentage = ((value / Math.max(totalRevenue, 1)) * 100).toFixed(1);
            return `${context.label}: ${formatCurrency(value)} (${percentage}%)`;
          },
        },
      },
    },
  };

  return (
    <section className="chart-card" aria-label="Industry sales plan share">
      <h3>Industry Share</h3>
      <div className="industry-share">
        <div className="chartjs-donut-frame">
          <Doughnut data={chartData} options={options} />
        </div>
        <div className="industry-legend">
          {rows.map((row, index) => (
            <div className="legend-row" key={row.label}>
              <span className="legend-swatch" style={{ background: chartColor(index) }} />
              <strong>{row.label}</strong>
              <span>{formatCurrency(row.value)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function peakRow(rows: RevenuePoint[]) {
  return rows.reduce<RevenuePoint | null>(
    (peak, row) => (!peak || row.value > peak.value ? row : peak),
    null,
  );
}

function monthlyVolatility(rows: RevenuePoint[]) {
  if (rows.length === 0) {
    return 0;
  }
  const average = rows.reduce((total, row) => total + row.value, 0) / rows.length;
  if (average === 0) {
    return 0;
  }
  const variance = rows.reduce((total, row) => total + (row.value - average) ** 2, 0) / rows.length;
  return (Math.sqrt(variance) / average) * 100;
}
