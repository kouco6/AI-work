import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CHART_AXIS, CHART_COLORS, CHART_TOOLTIP_STYLE } from './chartTheme';

export type QuotaBar = {
  /** 维度名称，如 "用户 u1" / "军师 · AI-000" */
  label: string;
  /** 已用量 */
  used: number;
  /** 上限 */
  limit: number;
};

export type QuotaBarChartProps = {
  data: QuotaBar[];
  height?: number;
};

/**
 * 配额用量柱状图 —— 供配额管理 / 平台概览复用。
 * 数据来源：itc_quota_counters + itc_quota_policies（FR-156）。
 * 超 90% 的柱染红（--danger 语义），其余染品牌蓝。
 */
export function QuotaBarChart({ data, height = 240 }: QuotaBarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid stroke={CHART_AXIS.stroke} vertical={false} />
        <XAxis dataKey="label" tick={CHART_AXIS.tick} axisLine={{ stroke: CHART_AXIS.stroke }} tickLine={false} />
        <YAxis tick={CHART_AXIS.tick} axisLine={false} tickLine={false} width={48} />
        <Tooltip contentStyle={CHART_TOOLTIP_STYLE} />
        <Bar dataKey="used" name="已用" radius={[4, 4, 0, 0]} maxBarSize={40}>
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={d.limit > 0 && d.used / d.limit >= 0.9 ? 'var(--danger)' : CHART_COLORS.accent}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
