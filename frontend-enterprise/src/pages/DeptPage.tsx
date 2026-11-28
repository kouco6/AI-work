import { useState } from 'react';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { Button as UIButton } from '../components/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogTitle, Input } from '../components/ui';
import { notify } from '../components/ui/app-toast';
import { useApi } from '../hooks/useApi';
import { api, TENANT_ID } from '../api/client';

export type DeptPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
};

/** 部门行（FR-266）。 */
type DeptRow = {
  id: string;
  name: string;
  parentId: number | null;
  leaderUserId: string | null;
  memberCount: number;
  members: string[];
};

type DeptStats = { deptId: string; name: string; memberCount: number; calls: number; totalTokens: number; cost: number };

const Q = `tenant_id=${TENANT_ID}`;

/** 部门权限管理（FR-232/266）：部门 + 成员 + 负责人 + 部门统计。 */
export default function DeptPage({ isAdmin, onLogout }: DeptPageProps) {
  const depts = useApi<DeptRow[]>(`/api/enterprise/itc/depts?${Q}`);
  const [editorOpen, setEditorOpen] = useState(false);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<DeptRow | null>(null);
  const [stats, setStats] = useState<DeptStats | null>(null);
  const rows = depts.data ?? [];

  async function addDept() {
    if (!name.trim()) {
      notify.error('请填写部门名称');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/api/enterprise/itc/depts?${Q}`, { name: name.trim() });
      notify.success('已新增部门');
      setEditorOpen(false);
      setName('');
      await depts.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '新增失败');
    } finally {
      setSaving(false);
    }
  }

  async function loadStats(d: DeptRow) {
    setSelected(d);
    setStats(null);
    try {
      const s = await api.get<DeptStats>(`/api/enterprise/itc/depts/${d.id}/stats?${Q}`);
      setStats(s);
    } catch {
      setStats(null);
    }
  }

  async function remove(d: DeptRow) {
    try {
      await api.delete(`/api/enterprise/itc/depts/${d.id}?${Q}`);
      notify.success('已删除');
      if (selected?.id === d.id) {
        setSelected(null);
        setStats(null);
      }
      await depts.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '删除失败');
    }
  }

  const columns: DataTableColumn<DeptRow>[] = [
    { key: 'name', title: '部门', width: 200, render: (r) => <span className="text-[#18181a]">{r.name}</span> },
    { key: 'members', title: '成员数', width: 100, align: 'right', render: (r) => r.memberCount },
    { key: 'leader', title: '负责人', width: 160, render: (r) => r.leaderUserId || '—' },
    {
      key: 'actions',
      title: '操作',
      width: 140,
      render: (r) => (
        <div className="flex gap-[10px]">
          <button type="button" className="text-[12px] text-[var(--accent)] hover:underline" onClick={() => void loadStats(r)}>
            统计
          </button>
          {isAdmin && (
            <button type="button" className="text-[12px] text-[#d20b0b] hover:underline" onClick={() => void remove(r)}>
              删除
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader title="部门权限" description="部门 / 成员 / 负责人 / 部门统计（FR-232/266）" onLogout={onLogout} />

      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={depts.loading ? '—' : rows.length} label="部门数" />
        <StatCard value={rows.reduce((s, r) => s + r.memberCount, 0)} label="成员总数" />
      </div>

      <div className="mt-[20px] flex items-center justify-between">
        <div className="text-[14px] font-semibold text-[#18181a]">部门列表</div>
        {isAdmin && (
          <UIButton type="button" onClick={() => setEditorOpen(true)}>
            新增部门
          </UIButton>
        )}
      </div>

      <div className="mt-[12px] grid grid-cols-1 gap-[16px] lg:grid-cols-[1fr_300px]">
        <DataTable
          columns={columns}
          data={rows}
          rowKey={(r) => r.id}
          loading={depts.loading}
          emptyText="暂无部门。新增部门后在此展示（FR-266）。"
          aria-label="部门"
          onRowClick={(r) => void loadStats(r)}
        />

        <div className="rounded-[14px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px]">
          <div className="text-[13px] font-semibold text-[#18181a]">部门统计</div>
          {selected ? (
            stats ? (
              <dl className="mt-[10px] flex flex-col gap-[8px] text-[12px]">
                <Row k="部门" v={stats.name} />
                <Row k="成员数" v={String(stats.memberCount)} />
                <Row k="调用次数" v={String(stats.calls)} />
                <Row k="Token" v={stats.totalTokens.toLocaleString()} />
                <Row k="成本" v={`¥${stats.cost.toFixed(4)}`} />
              </dl>
            ) : (
              <div className="mt-[10px] text-[12px] text-[#757f9c]">加载中…</div>
            )
          ) : (
            <div className="mt-[10px] text-[12px] text-[#757f9c]">选择左侧部门查看统计。</div>
          )}
          <div className="mt-[14px] text-[12px] text-[#9aa0ab]">
            部门权限（FR-232）：管理员管全平台；部门负责人管本部门。用户归属存 itc_dept_members（非侵入，不改原生用户表）。
          </div>
        </div>
      </div>

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogTitle>新增部门</DialogTitle>
          <div className="mt-[14px]">
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              部门名称
              <Input value={name} placeholder="例如 企划部" onChange={(e) => setName(e.target.value)} />
            </label>
          </div>
          <DialogFooter>
            <UIButton type="button" variant="outline" onClick={() => setEditorOpen(false)}>
              取消
            </UIButton>
            <UIButton type="button" disabled={saving} onClick={() => void addDept()}>
              {saving ? '保存中…' : '保存'}
            </UIButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-[8px]">
      <dt className="shrink-0 text-[#757f9c]">{k}</dt>
      <dd className="min-w-0 truncate text-right text-[#18181a]">{v}</dd>
    </div>
  );
}
