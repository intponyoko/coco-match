const CHART_COLORS = [
  "#0017c1",
  "#006ab6",
  "#008b8b",
  "#8f6c00",
  "#d18b00",
  "#8b5cf6",
  "#c2410c",
  "#15803d",
];

export function chartColor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length];
}
