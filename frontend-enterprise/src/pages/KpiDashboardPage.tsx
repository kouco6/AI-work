import { useMemo, useState } from 'react';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { notify } from '../components/ui/app-toast';
import { useApi } from '../hooks/useApi';
import { TENANT_ID } from '../api/client';

export type KpiDashboardPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
};

/** 员工 KPI 行（FR-128/130/153）。 */
type KpiRow = {
  agent_id: string;
  name: string;
  calls: number;
  total_tokens: number;
  cost: number;
  unmetered_calls: number;
  unmetered_ratio: number;
  accuracy: number | null;
  satisfaction: number | null;
  up: number;
  down: number;
  avg_duration_ms: number | null;
  runs: number;
  score: number;
  grade: string; // S/A/B/C/D
};

const Q = `tenant_id=${TENANT_ID}`;
const GRADE_TONE: Record<string, string> = {
  S: 'bg-[#138a55] text-white',
  A: 'bg-[#2cb360] text-white',
  B: 'bg-[#e8f0ff] text-[var(--accent)]',
  C: 'bg-[#fdf2e3] text-[#b45309]',
  D: 'bg-[#fce7e7] text-[#d20b0b]',
};

function Grade({ g }: { g: string }) {
  return <span className={`rounded-full px-[8px] py-[1px] text-[12px] font-semibold ${GRADE_TONE[g] ?? 'bg-[#f0f1f4]'}`}>{g}</span>;
}

/**
 * 绩效考核 / 报表 / 预警（FR-128/130/132）。
 * 数据来自 itc KPI 层（用量 ← itc_usage_records；准确率/满意度 ← 原生 message_feedback；
 * 响应时长 ← 原生 harness_runs）+ **S/A/B/C/D 等级**。
 */
export default function KpiDashboardPage({ onLogout }: KpiDashboardPageProps) {
  const kpi = useApi<KpiRow[]>(`/api/enterprise/itc/kpi/agents?${Q}`);
  const rows = kpi.data ?? [];
  const [onlyAlert, setOnlyAlert] = useState(false);

  const alerted = rows.filter((r) => r.grade === 'D' && r.calls > 0);
  const shown = onlyAlert ? alerted : rows;

  const columns: DataTableColumn<KpiRow>[] = [
    { key: 'name', title: '员工', width: 160, render: (r) => <span className="text-[#18181a]">{r.name}</span> },
    { key: 'grade', title: 'KPI 等级', width: 90, render: (r) => <Grade g={r.grade} /> },
    { key: 'score', title: '综合分', width: 80, align: 'right', render: (r) => r.score.toFixed(3) },
    { key: 'calls', title: '完成量', width: 80, align: 'right', dataIndex: 'calls' },
    {
      key: 'accuracy',
      title: '准确率',
      width: 90,
      align: 'right',
      render: (r) => (r.accuracy == null ? '—' : `${(r.accuracy * 100).toFixed(0)}%`),
    },
    {
      key: 'satisfaction',
      title: '满意度',
      width: 90,
      align: 'right',
      render: (r) => (r.satisfaction == null ? '—' : `${r.satisfaction.toFixed(1)}/5`),
    },
    {
      key: 'duration',
      title: '响应时长',
      width: 100,
      align: 'right',
      render: (r) => (r.avg_duration_ms == null ? '—' : `${(r.avg_duration_ms / 1000).toFixed(1)}s`),
    },
    { key: 'cost', title: '成本', width: 100, align: 'right', render: (r) => `¥${r.cost.toFixed(4)}` },
  ];

  function exportCsv() {
    if (shown.length === 0) {
      notify.error('无可导出的数据');
      return;
    }
    const header = '员工,等级,综合分,完成量,准确率,满意度,响应时长(ms),成本\n';
    const body = shown
      .map((r) =>
        [r.name, r.grade, r.score, r.calls, r.accuracy ?? '', r.satisfaction ?? '', r.avg_duration_ms ?? '', r.cost].join(','),
      )
      .join('\n');
    const blob = new Blob([`﻿${header}${body}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'kpi-report.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  const gradeCount = useMemo(() => {
    const c: Record<string, number> = { S: 0, A: 0, B: 0, C: 0, D: 0 };
    rows.forEach((r) => {
      if (r.calls > 0) c[r.grade] = (c[r.grade] ?? 0) + 1;
    });
    return c;
  }, [rows]);

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader title="绩效考核" description="AI 员工 KPI / 绩效报表 / 绩效预警（FR-128/130/132）" onLogout={onLogout} />

      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={rows.filter((r) => r.calls > 0).length} label="有业绩员工" />
        <StatCard value={gradeCount.S + gradeCount.A} label="优秀（S/A）" tone="green" />
        <StatCard value={gradeCount.D} label="待改进（D）" tone={gradeCount.D > 0 ? 'red' : 'default'} />
        <StatCard value={rows.reduce((s, r) => s + r.calls, 0)} label="总完成量" />
      </div>

      {/* 绩效预警（FR-132）：连续低分/末位 */}
      {alerted.length > 0 && (
        <div className="mt-[18px] rounded-[14px] border-[0.5px] border-[#f5d0d0] bg-[#fce7e7] px-[16px] py-[12px] text-[13px] text-[#d20b0b]">
          绩效预警：{alerted.map((r) => r.name).join('、')} 等级为 D，建议管理员优化其 Prompt / 筛选取规则或调整岗位。
        </div>
      )}

      <div className="mt-[20px] flex items-center justify-between">
        <label className="flex items-center gap-[6px] text-[13px] text-[#464c5e]">
          <input type="checkbox" checked={onlyAlert} onChange={(e) => setOnlyAlert(e.target.checked)} />
          仅看预警
        </label>
        <button
          type="button"
          onClick={exportCsv}
          className="flex h-[32px] items-center rounded-[10px] border-[0.5px] border-[#e3e7f1] bg-white px-[14px] text-[13px] text-[#464c5e] hover:bg-[#f6f6f6]"
        >
          导出绩效报表
        </button>
      </div>

      <div className="mt-[12px]">
        <DataTable
          columns={columns}
          data={shown}
          rowKey={(r) => r.agent_id}
          loading={kpi.loading}
          emptyText="暂无 KPI 数据。产生模型调用与用户反馈后在此展示。"
          aria-label="绩效考核"
        />
      </div>

      <div className="mt-[12px] text-[12px] text-[#9aa0ab]">
        综合分 = 完成量(归一) × 0.5 + 准确率 × 0.5；等级阈值 S≥0.9 / A≥0.8 / B≥0.65 / C≥0.5 / D&lt;0.5。
        准确率与满意度来自用户点赞/点踩反馈（无反馈显示 —）；响应时长来自执行记录。
        {kpi.error && (
          <>
            {' '}
            <button type="button" className="underline" onClick={() => void kpi.refetch()}>
              加载失败，点击重试
            </button>
          </>
        )}
      </div>
    </div>
  );
}
