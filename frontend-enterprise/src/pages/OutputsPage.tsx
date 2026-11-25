import { useState } from 'react';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { UnderlineTabs, type UnderlineTabItem } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { TENANT_ID } from '../api/client';

export type OutputsPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
};

/** 输出物（FR-211~216）。产出物存平台存储（D-10），权限走平台 RBAC（FR-212）。 */
export type OutputItem = {
  id: string;
  name: string;
  type: string; // PPT / Excel / Word / PDF / 图片
  agentId: string;
  agentName: string;
  createdAt: string;
  version: string;
  size: number;
  source: string; // 触发方式：定时 / 对话 / 任务台
  archived?: boolean;
  visibility?: string;
};

type ViewKey = 'mine' | 'platform' | 'by-agent' | 'versions';

const VIEWS: UnderlineTabItem<ViewKey>[] = [
  { value: 'mine', label: '个人产出' },
  { value: 'platform', label: '平台产出' },
  { value: 'by-agent', label: '按员工' },
  { value: 'versions', label: '版本与归档' },
];

const Q = `tenant_id=${TENANT_ID}`;

/** 可见范围（FR-212）。 */
const VIS_LABEL: Record<string, string> = {
  private: '仅本人',
  user: '指定用户',
  dept: '本部门',
  all: '全员',
};

const COLUMNS: DataTableColumn<OutputItem>[] = [
  { key: 'name', title: '文件', width: 280, render: (r) => <span className="text-[#18181a]">{r.name}</span> },
  { key: 'type', title: '类型', dataIndex: 'type', width: 80 },
  { key: 'agent', title: '产出 AI', width: 140, render: (r) => r.agentName || r.agentId || '—' },
  { key: 'source', title: '触发方式', dataIndex: 'source', width: 90 },
  { key: 'version', title: '版本', dataIndex: 'version', width: 80 },
  {
    key: 'size',
    title: '大小',
    width: 90,
    align: 'right',
    render: (r) => (r.size ? `${(r.size / 1024).toFixed(1)} KB` : '—'),
  },
  { key: 'createdAt', title: '生成时间', width: 160, render: (r) => r.createdAt || '—' },
];

/**
 * 输出物管理（FR-211~216）：个人产出 / 平台产出 / 按员工 / 版本与归档。
 * 产出物统一存平台文件库，按「年份/月份/类型」分目录（FR-211）；元数据含
 * 产出 AI / 生成时间 / 触发方式 / 版本 / 来源（FR-213）。
 */
export default function OutputsPage({ onLogout }: OutputsPageProps) {
  const [view, setView] = useState<ViewKey>('mine');
  const [selected, setSelected] = useState<OutputItem | null>(null);
  const outputs = useApi<OutputItem[]>(`/api/enterprise/itc/outputs?${Q}&view=${view}`);
  const rows = outputs.data ?? [];
  const now = new Date();
  const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const monthCount = rows.filter((r) => (r.createdAt || '').startsWith(ym)).length;
  const totalSize = rows.reduce((s, r) => s + (r.size || 0), 0);
  const archivedCount = rows.filter((r) => r.archived).length;

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader title="输出物" description="平台产出物统一管理（FR-211~216）" onLogout={onLogout} />

      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={outputs.loading ? '—' : rows.length} label="本视图文件数" />
        <StatCard value={outputs.loading ? '—' : monthCount} label="本月产出" />
        <StatCard
          value={outputs.loading ? '—' : totalSize >= 1024 * 1024 ? `${(totalSize / 1024 / 1024).toFixed(1)} MB` : `${(totalSize / 1024).toFixed(0)} KB`}
          label="占用空间"
        />
        <StatCard value={outputs.loading ? '—' : archivedCount} label="已归档" />
      </div>

      <div className="mt-[20px]">
        <UnderlineTabs items={VIEWS} value={view} onChange={setView} aria-label="输出物视图" />
      </div>

      <div className="mt-[16px] grid grid-cols-1 gap-[16px] lg:grid-cols-[1fr_280px]">
        <DataTable
          columns={COLUMNS}
          data={rows}
          rowKey={(r) => r.id}
          loading={outputs.loading}
          emptyText="暂无输出物。数字员工产出文件后，会按视图归类在此展示。"
          aria-label="输出物"
          onRowClick={(r) => setSelected(r)}
        />

        {/* 元数据面板（FR-213） */}
        <div className="rounded-[14px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px]">
          <div className="text-[13px] font-semibold text-[#18181a]">文件元数据</div>
          {selected ? (
            <dl className="mt-[10px] flex flex-col gap-[8px] text-[12px]">
              <MetaRow k="文件" v={selected.name} />
              <MetaRow k="产出 AI" v={selected.agentName || selected.agentId} />
              <MetaRow k="生成时间" v={selected.createdAt} />
              <MetaRow k="触发方式" v={selected.source} />
              <MetaRow k="版本" v={selected.version} />
              <MetaRow k="可见范围" v={VIS_LABEL[selected.visibility || 'private']} />
            </dl>
          ) : (
            <div className="mt-[10px] text-[12px] text-[#757f9c]">选择一份文件查看元数据。</div>
          )}
          <div className="mt-[14px] text-[12px] text-[#9aa0ab]">
            产出物存平台存储（D-10），权限走平台 RBAC：默认仅产出者本人可见，可分享给用户/部门/全员（FR-212）。
          </div>
        </div>
      </div>

      {outputs.error && (
        <div className="mt-[12px] text-[12px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={() => void outputs.refetch()}>
            点击重试
          </button>
        </div>
      )}
    </div>
  );
}

function MetaRow({ k, v }: { k: string; v?: string }) {
  return (
    <div className="flex justify-between gap-[8px]">
      <dt className="shrink-0 text-[#757f9c]">{k}</dt>
      <dd className="min-w-0 truncate text-right text-[#18181a]">{v || '—'}</dd>
    </div>
  );
}
