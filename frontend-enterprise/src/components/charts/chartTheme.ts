/**
 * 图表层共享主题 —— 颜色取自 styles.css 的 CSS 变量，保证与全站风格一致。
 * 新增图表一律从此处取色，不要在组件里写死色值。
 */

/** 语义色（对应 styles.css 的 --chart-1..5 / --accent 等） */
export const CHART_COLORS = {
  accent: 'var(--chart-1)',
  chart2: 'var(--chart-2)',
  chart3: 'var(--chart-3)',
  chart4: 'var(--chart-4)',
  chart5: 'var(--chart-5)',
} as const;

/** 数据系列默认色序 */
export const CHART_SERIES = [
  CHART_COLORS.accent,
  CHART_COLORS.chart2,
  CHART_COLORS.chart3,
  CHART_COLORS.chart4,
  CHART_COLORS.chart5,
] as const;

/** 轴与网格（对齐企业台文字色 #18181a / #757f9c、描边 #e3e7f1） */
export const CHART_AXIS = {
  stroke: '#e3e7f1',
  tick: { fontSize: 11, fill: '#757f9c' },
} as const;

export const CHART_TOOLTIP_STYLE: React.CSSProperties = {
  borderRadius: 10,
  border: '0.5px solid #e3e7f1',
  boxShadow: '0 10px 30px rgba(37, 32, 24, 0.055)',
  fontSize: 12,
  color: '#18181a',
};
