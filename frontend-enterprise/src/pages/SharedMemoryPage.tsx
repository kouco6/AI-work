import { useState } from 'react';

import AppHeader from '../components/AppHeader';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { UnderlineTabs, type UnderlineTabItem } from '../components/ui';
import { Button as UIButton } from '../components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
} from '../components/ui';
import { notify } from '../components/ui/app-toast';
import { useApi } from '../hooks/useApi';
import { api, TENANT_ID } from '../api/client';

export type SharedMemoryPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
};

/** 共享记忆行（FR-201/202）。scope=global(L1) / role(L2 岗位)。 */
type SharedMemory = {
  id: string;
  kind: string;
  content: string;
  importance: number;
  metadata: { scope?: string; owner?: string; [k: string]: unknown };
  updated_at: string;
};

type TabKey = 'global' | 'role';

const TABS: UnderlineTabItem<TabKey>[] = [
  { value: 'global', label: '全局规则（L1）' },
  { value: 'role', label: '岗位经验（L2）' },
];

const Q = `tenant_id=${TENANT_ID}`;

const COLUMNS: DataTableColumn<SharedMemory>[] = [
  { key: 'kind', title: '类型', dataIndex: 'kind', width: 90 },
  { key: 'content', title: '内容', width: 480, render: (r) => <span className="text-[#18181a]">{r.content}</span> },
  { key: 'owner', title: '归属', width: 140, render: (r) => r.metadata?.owner || '全员' },
  {
    key: 'importance',
    title: '重要性',
    width: 90,
    align: 'right',
    render: (r) => (r.importance ?? 0.5).toFixed(2),
  },
  { key: 'updated', title: '更新时间', width: 170, render: (r) => r.updated_at || '—' },
];

/**
 * 共享记忆管理（FR-201/202）：L1 全局规则 / L2 岗位经验，仅管理员可维护。
 * 记忆优先级 L4 会话 > L3 用户 > L2 岗位 > L1 全局（需求 §4.3），
 * 检索时由 memory_shared provider 合并到原生 per-user 记忆之后。
 */
export default function SharedMemoryPage({ isAdmin, onLogout }: SharedMemoryPageProps) {
  const [tab, setTab] = useState<TabKey>('global');
  const [editorOpen, setEditorOpen] = useState(false);
  const [form, setForm] = useState({ kind: 'fact', content: '', key: '', owner: '', importance: '0.5' });
  const [saving, setSaving] = useState(false);

  const memories = useApi<SharedMemory[]>(`/api/enterprise/itc/memory/shared?${Q}`);
  const rows = (memories.data ?? []).filter((m) => (m.metadata?.scope || 'global') === tab);

  async function save() {
    if (!form.content.trim()) {
      notify.error('请填写记忆内容');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/api/enterprise/itc/memory/shared?${Q}`, {
        scope: tab,
        owner: tab === 'role' ? form.owner || null : null,
        kind: form.kind,
        key: form.key || null,
        content: form.content,
        importance: Number(form.importance) || 0.5,
      });
      notify.success('已保存');
      setEditorOpen(false);
      setForm({ kind: 'fact', content: '', key: '', owner: '', importance: '0.5' });
      await memories.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '保存失败（仅管理员可写）');
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    try {
      await api.delete(`/api/enterprise/itc/memory/shared/${encodeURIComponent(id.replace(/^shared-/, ''))}?${Q}`);
      notify.success('已删除');
      await memories.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '删除失败');
    }
  }

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader
        title="共享记忆"
        description="L1 全局规则 / L2 岗位经验（FR-201/202），仅管理员可维护"
        onLogout={onLogout}
      />

      <div className="mt-[20px]">
        <UnderlineTabs items={TABS} value={tab} onChange={setTab} aria-label="共享记忆" />
      </div>

      <div className="mt-[12px] flex items-center justify-between">
        <div className="text-[12px] text-[#757f9c]">
          {tab === 'global'
            ? '全局规则：所有用户共享，仅管理员可编辑（L1）。'
            : '岗位经验：按岗位/员工共享，自动沉淀 + 管理员审核（L2）。'}
        </div>
        {isAdmin && (
          <UIButton type="button" onClick={() => setEditorOpen(true)}>
            新增记忆
          </UIButton>
        )}
      </div>

      <div className="mt-[12px]">
        <DataTable
          columns={[
            ...COLUMNS,
            {
              key: 'actions',
              title: '操作',
              width: 90,
              render: (r) =>
                isAdmin ? (
                  <button
                    type="button"
                    className="text-[12px] text-[#d20b0b] hover:underline"
                    onClick={() => void remove(r.id)}
                  >
                    删除
                  </button>
                ) : (
                  '—'
                ),
            },
          ]}
          data={rows}
          rowKey={(r) => r.id}
          loading={memories.loading}
          emptyText={
            tab === 'global'
              ? '暂无全局规则。添加全体共享的公司规则/通用模板后在此展示。'
              : '暂无岗位经验。岗位自动沉淀或管理员添加后在此展示。'
          }
          aria-label="共享记忆"
        />
      </div>

      {memories.error && (
        <div className="mt-[12px] text-[12px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={() => void memories.refetch()}>
            点击重试
          </button>
        </div>
      )}

      {/* 新增记忆弹窗 */}
      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogTitle>{tab === 'global' ? '新增全局规则（L1）' : '新增岗位经验（L2）'}</DialogTitle>
          <div className="mt-[14px] flex flex-col gap-[12px]">
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              类型
              <Select value={form.kind} onValueChange={(v) => setForm((f) => ({ ...f, kind: v }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fact">事实</SelectItem>
                  <SelectItem value="rule">规则</SelectItem>
                  <SelectItem value="template">模板</SelectItem>
                  <SelectItem value="case">案例</SelectItem>
                </SelectContent>
              </Select>
            </label>
            {tab === 'role' && (
              <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
                归属岗位/员工 ID
                <Input
                  value={form.owner}
                  placeholder="例如 AI-001"
                  onChange={(e) => setForm((f) => ({ ...f, owner: e.target.value }))}
                />
              </label>
            )}
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              去重键（可选）
              <Input
                value={form.key}
                placeholder="同键覆盖，留空则按内容生成"
                onChange={(e) => setForm((f) => ({ ...f, key: e.target.value }))}
              />
            </label>
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              内容
              <Textarea
                value={form.content}
                rows={4}
                placeholder="记忆正文"
                onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
              />
            </label>
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              重要性（0–1）
              <Input
                type="number"
                min={0}
                max={1}
                step={0.1}
                value={form.importance}
                onChange={(e) => setForm((f) => ({ ...f, importance: e.target.value }))}
              />
            </label>
          </div>
          <DialogFooter>
            <UIButton type="button" variant="outline" onClick={() => setEditorOpen(false)}>
              取消
            </UIButton>
            <UIButton type="button" disabled={saving} onClick={() => void save()}>
              {saving ? '保存中…' : '保存'}
            </UIButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
