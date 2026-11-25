import { useState } from 'react';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { UnderlineTabs, type UnderlineTabItem } from '../components/ui';
import { Button as UIButton } from '../components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
  Input,
} from '../components/ui';
import { notify } from '../components/ui/app-toast';
import { useApi } from '../hooks/useApi';
import { api, TENANT_ID } from '../api/client';

export type DataSourcePageProps = {
  isAdmin: boolean;
  onLogout: () => void;
  /** 嵌入「管理后台」二级 tab 时隐藏自身页头与整页留白。 */
  embedded?: boolean;
};

type DataSource = {
  id: string;
  name: string;
  url: string;
  frequency: string;
  selector: string;
  enabled: boolean;
  status: string;
  lastRun: string;
};

type LogRow = {
  id: string;
  time: string;
  source: string;
  count: number;
  ok: number;
  failed: number;
  reason: string;
};

type TabKey = 'sources' | 'tags' | 'templates' | 'push' | 'logs';

const TABS: UnderlineTabItem<TabKey>[] = [
  { value: 'sources', label: '数据源' },
  { value: 'tags', label: '标签规则' },
  { value: 'templates', label: '简报模板' },
  { value: 'push', label: '推送配置' },
  { value: 'logs', label: '爬取日志' },
];

const Q = `tenant_id=${TENANT_ID}`;
const BLANK = { name: '', url: '', frequency: '', selector: '' };

/** 数据源管理（FR-178~182）：数据源 / 标签规则 / 简报模板 / 推送配置 / 爬取日志。 */
export default function DataSourcePage({ isAdmin, onLogout, embedded = false }: DataSourcePageProps) {
  const [tab, setTab] = useState<TabKey>('sources');
  const [editorOpen, setEditorOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(BLANK);
  const sources = useApi<DataSource[]>(`/api/enterprise/itc/data-sources?${Q}`);
  const logs = useApi<LogRow[]>(`/api/enterprise/itc/crawl-logs?${Q}`);
  const sourceRows = sources.data ?? [];

  async function save() {
    if (!form.name.trim() || !form.url.trim()) {
      notify.error('请填写名称与地址');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/api/enterprise/itc/data-sources?${Q}`, form);
      notify.success('已新增数据源');
      setEditorOpen(false);
      setForm(BLANK);
      await sources.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '新增失败（仅管理员可写）');
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    try {
      await api.delete(`/api/enterprise/itc/data-sources/${encodeURIComponent(id)}?${Q}`);
      notify.success('已删除');
      await sources.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '删除失败');
    }
  }

  const sourceColumns: DataTableColumn<DataSource>[] = [
    { key: 'name', title: '名称', width: 180, render: (r) => <span className="text-[#18181a]">{r.name}</span> },
    { key: 'url', title: '地址', dataIndex: 'url', width: 300 },
    { key: 'frequency', title: '爬取频率', dataIndex: 'frequency', width: 110 },
    {
      key: 'status',
      title: '状态',
      width: 80,
      render: (r) => <span className={r.status === '异常' ? 'text-[#d20b0b]' : 'text-[#2cb360]'}>{r.status}</span>,
    },
    { key: 'lastRun', title: '最近爬取', width: 150, render: (r) => r.lastRun || '—' },
    {
      key: 'actions',
      title: '操作',
      width: 80,
      render: (r) =>
        isAdmin ? (
          <button type="button" className="text-[12px] text-[#d20b0b] hover:underline" onClick={() => void remove(r.id)}>
            删除
          </button>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <div className={embedded ? '' : 'min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]'}>
      {!embedded && (
        <AppHeader
          title="数据源管理"
          description="公开/内部数据源、标签规则、简报模板与推送配置（FR-178~182）"
          onLogout={onLogout}
        />
      )}

      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={sources.loading ? '—' : sourceRows.length} label="数据源" />
        <StatCard value={sourceRows.filter((r) => r.status === '异常').length} label="异常数据源" tone={sourceRows.some((r) => r.status === '异常') ? 'red' : 'default'} />
        <StatCard value={sources.loading ? '—' : (logs.data?.length ?? 0)} label="爬取记录" />
      </div>

      <div className="mt-[20px]">
        <UnderlineTabs items={TABS} value={tab} onChange={setTab} aria-label="数据源" />
      </div>

      <div className="mt-[16px]">
        {tab === 'sources' && (
          <Section
            title="数据源"
            action={isAdmin ? <UIButton type="button" onClick={() => { setForm(BLANK); setEditorOpen(true); }}>新增数据源</UIButton> : null}
            loading={sources.loading}
            error={sources.error}
            onRetry={() => void sources.refetch()}
          >
            <DataTable
              columns={sourceColumns}
              data={sourceRows}
              rowKey={(r) => r.id}
              loading={sources.loading}
              emptyText="暂无数据源。添加公开/内部数据源并配置爬取规则后在此展示（FR-178）。"
              aria-label="数据源"
            />
          </Section>
        )}

        {tab === 'tags' && (
          <Placeholder text="暂无标签规则。配置关键词标签与匹配规则（精确/模糊/排除）后在此展示（FR-179）。" />
        )}
        {tab === 'templates' && (
          <Placeholder text="暂无简报模板。上传 PPT/Excel/Word 模板并配置生成规则/命名规范/存储路径后在此展示（FR-180）。" />
        )}
        {tab === 'push' && (
          <Placeholder text="暂无推送配置。配置推送对象（群/用户/邮箱）、时间与方式后在此展示（FR-181）。" />
        )}
        {tab === 'logs' && (
          <Section title="爬取日志" loading={logs.loading} error={logs.error} onRetry={() => void logs.refetch()}>
            <DataTable
              columns={[
                { key: 'time', title: '时间', dataIndex: 'time', width: 160 },
                { key: 'source', title: '数据源', dataIndex: 'source', width: 200 },
                { key: 'count', title: '条数', dataIndex: 'count', width: 80, align: 'right' },
                { key: 'ok', title: '成功', dataIndex: 'ok', width: 80, align: 'right' },
                { key: 'failed', title: '失败', width: 80, align: 'right', render: (r) => <span className={r.failed ? 'text-[#d20b0b]' : ''}>{r.failed}</span> },
                { key: 'reason', title: '失败原因', dataIndex: 'reason', width: 260 },
              ]}
              data={logs.data ?? []}
              rowKey={(r) => r.id}
              loading={logs.loading}
              emptyText="暂无爬取日志（FR-182）。"
              aria-label="爬取日志"
            />
          </Section>
        )}
      </div>

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="sm:max-w-[460px]">
          <DialogTitle>新增数据源</DialogTitle>
          <div className="mt-[14px] flex flex-col gap-[12px]">
            <Field label="名称"><Input value={form.name} placeholder="例如 中国安防展览网" onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></Field>
            <Field label="地址"><Input value={form.url} placeholder="https://..." onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} /></Field>
            <Field label="爬取频率"><Input value={form.frequency} placeholder="例如 每日 08:00" onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value }))} /></Field>
            <Field label="内容选择器"><Input value={form.selector} placeholder="CSS 选择器（可选）" onChange={(e) => setForm((f) => ({ ...f, selector: e.target.value }))} /></Field>
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

function Placeholder({ text }: { text: string }) {
  return (
    <div className="rounded-[14px] border-[0.5px] border-[#e3e7f1] bg-white py-[48px] text-center text-[12px] text-[#757f9c]">
      {text}
    </div>
  );
}

function Section({
  title,
  action,
  loading,
  error,
  onRetry,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-[12px] flex items-center justify-between">
        <div className="text-[14px] font-semibold text-[#18181a]">{title}</div>
        {action}
      </div>
      {error ? (
        <div className="text-[12px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={onRetry}>
            点击重试
          </button>
        </div>
      ) : loading ? (
        <div className="py-[20px] text-center text-[12px] text-[#757f9c]">加载中…</div>
      ) : (
        children
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
      {label}
      {children}
    </label>
  );
}
