import { useMemo, useState } from 'react';

import AppHeader from '../components/AppHeader';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { notify } from '../components/ui/app-toast';
import { useApi } from '../hooks/useApi';
import { api, TENANT_ID } from '../api/client';
import { employeeDisplayNameWithCreator } from '../employee';
import type { AgentProfileRead } from '../types';

export type TaskManagementPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
};

/** 统一任务行（FR-197）。来源跨 对话/定时/任务台/手动 三处，由后端统一查询层聚合。 */
type UnifiedTask = {
  id: string;
  source: string;        // 对话 / 定时 / 任务台 / 手动
  title: string;
  participants: string[];
  status: string;
  token: number;
  durationMs: number;
  producedAt: string;
};

/** itc 任务池原始行（/api/enterprise/itc/tasks）。 */
type TaskRowRaw = {
  id: string;
  title: string;
  kind: string;
  status: string;
  assignee: string | null;
  source: string;
  token: number;
  createdAt: string;
};

const STATUS_LABEL: Record<string, string> = {
  pending: '待分配',
  assigned: '已分配',
  running: '进行中',
  done: '已完成',
  failed: '已失败',
  cancelled: '已取消',
};

const SOURCE_FILTERS = ['全部', '对话', '定时', '任务台', '手动'] as const;
const STATUS_FILTERS = ['全部', '待分配', '已分配', '进行中', '已完成', '已失败'] as const;

/** 任务管理（FR-197）：统一任务视图 + 筛选 + 导出。 */
export default function TaskManagementPage({ onLogout }: TaskManagementPageProps) {
  const [source, setSource] = useState<string>('全部');
  const [status, setStatus] = useState<string>('全部');

  // 统一任务视图：由 itc 任务池提供（FR-197）；其余来源（对话/定时）后续并入
  const tasks = useApi<TaskRowRaw[]>(`/api/enterprise/itc/tasks?tenant_id=${TENANT_ID}`, [], { pollMs: 5000 });
  const agents = useApi<AgentProfileRead[]>(`/api/enterprise/agents?tenant_id=${TENANT_ID}&scope=managed&view=summary`);
  const nameOf = (id: string | null) => {
    if (!id) return '—';
    const a = (agents.data ?? []).find((x) => x.id === id);
    return a ? employeeDisplayNameWithCreator(a) : id;
  };
  const rows: UnifiedTask[] = (tasks.data ?? []).map((t: TaskRowRaw) => ({
    id: t.id,
    source: t.source || '任务台',
    title: t.title,
    participants: t.assignee ? [nameOf(t.assignee)] : [],
    status: t.status,
    token: t.token,
    durationMs: 0,
    producedAt: t.createdAt,
  }));

  const filtered = useMemo(
    () =>
      rows.filter(
        (t) => (source === '全部' || t.source === source) && (status === '全部' || STATUS_LABEL[t.status] === status),
      ),
    [rows, source, status],
  );

  const columns: DataTableColumn<UnifiedTask>[] = [
    { key: 'title', title: '任务', dataIndex: 'title', width: 260 },
    { key: 'source', title: '来源', dataIndex: 'source', width: 90 },
    {
      key: 'participants',
      title: '参与员工',
      width: 160,
      render: (r) => (r.participants?.length ? r.participants.join('、') : '—'),
    },
    {
      key: 'status',
      title: '状态',
      width: 100,
      render: (r) => (
        <span className={r.status === 'failed' ? 'text-[#d20b0b]' : r.status === 'done' ? 'text-[#2cb360]' : ''}>
          {STATUS_LABEL[r.status] ?? r.status}
        </span>
      ),
    },
    {
      key: 'token',
      title: 'Token',
      width: 100,
      align: 'right',
      render: (r) => (r.token ? r.token.toLocaleString() : '—'),
    },
    {
      key: 'duration',
      title: '耗时',
      width: 100,
      align: 'right',
      render: (r) => (r.durationMs ? `${(r.durationMs / 1000).toFixed(1)}s` : '—'),
    },
  ];

  function exportCsv() {
    if (filtered.length === 0) {
      notify.error('无可导出的任务');
      return;
    }
    const header = '任务,来源,参与员工,状态,Token,耗时(ms)\n';
    const body = filtered
      .map((r) => [r.title, r.source, (r.participants ?? []).join('|'), STATUS_LABEL[r.status] ?? r.status, r.token ?? '', r.durationMs ?? ''].join(','))
      .join('\n');
    const blob = new Blob([`﻿${header}${body}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tasks.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader title="任务管理" description="统一任务视图（FR-197）" onLogout={onLogout} />

      <div className="mt-[20px] flex flex-wrap items-center gap-[12px]">
        <FilterGroup label="来源" value={source} options={SOURCE_FILTERS} onChange={setSource} />
        <FilterGroup label="状态" value={status} options={STATUS_FILTERS} onChange={setStatus} />
        <button
          type="button"
          onClick={exportCsv}
          className="ml-auto flex h-[32px] items-center rounded-[10px] border-[0.5px] border-[#e3e7f1] bg-white px-[14px] text-[13px] text-[#464c5e] hover:bg-[#f6f6f6]"
        >
          导出 CSV
        </button>
      </div>

      <div className="mt-[16px]">
        <DataTable
          columns={columns}
          data={filtered}
          rowKey={(r) => r.id}
          loading={tasks.loading}
          emptyText="暂无任务。统一查询层接入后，对话/定时/任务台来源的任务会汇总在此。"
          aria-label="任务管理"
        />
      </div>

      <div className="mt-[12px] text-[12px] text-[#9aa0ab]">
        数据来自统一查询层（三源联合查询 + 字段标准化，不建新表双写 —— 见《基础层设计.md》）。
        {tasks.error && (
          <>
            {' '}
            <button type="button" className="underline" onClick={() => void tasks.refetch()}>
              加载失败，点击重试
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function FilterGroup({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-[8px]">
      <span className="text-[12px] text-[#757f9c]">{label}</span>
      <div className="flex gap-[4px]">
        {options.map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => onChange(o)}
            className={`rounded-[8px] px-[10px] py-[4px] text-[12px] transition-colors ${
              value === o ? 'bg-[var(--accent)] text-white' : 'bg-[#f6f6f6] text-[#464c5e] hover:bg-[#eceef1]'
            }`}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}
