import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CHART_AXIS, CHART_COLORS, CHART_TOOLTIP_STYLE } from './chartTheme';

export type UsagePoint = {
  /** X 轴标签，如 "11-01" 或 "09:00" */
  label: string;
  /** 输入 token */
  input?: number | null;
  /** 输出 token */
  output?: number | null;
};

export type UsageLineChartProps = {
  data: UsagePoint[];
  height?: number;
};

/**
 * 用量折线图 —— 供工作台首页 / 成本与 KPI 看板复用。
 * 数据来源：itc_usage_records（FR-151/152）。
 */
export function UsageLineChart({ data, height = 240 }: UsageLineChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid stroke={CHART_AXIS.stroke} vertical={false} />
        <XAxis dataKey="label" tick={CHART_AXIS.tick} axisLine={{ stroke: CHART_AXIS.stroke }} tickLine={false} />
        <YAxis tick={CHART_AXIS.tick} axisLine={false} tickLine={false} width={48} />
        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
        <Line
          type="monotone"
          dataKey="input"
          name="输入 Token"
          stroke={CHART_COLORS.accent}
          strokeWidth={2}
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="output"
          name="输出 Token"
          stroke={CHART_COLORS.chart3}
          strokeWidth={2}
          dot={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
