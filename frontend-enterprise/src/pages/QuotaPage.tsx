import { useMemo, useState } from 'react';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { QuotaBarChart, type QuotaBar } from '../components/charts';
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
} from '../components/ui';
import { notify } from '../components/ui/app-toast';
import { useApi } from '../hooks/useApi';
import { TENANT_ID } from '../api/client';

export type QuotaPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
  /** 嵌入「管理后台」二级 tab 时隐藏自身页头与整页留白。 */
  embedded?: boolean;
};

/** 配额策略行（FR-156）。 */
type QuotaPolicy = {
  scope_type: string; // user | agent | dept | platform
  scope_id: string;
  metric: string; // calls | tokens
  period: string; // day | month
  limit_value: number;
  concurrent_limit: number | null;
};

const SCOPE_LABEL: Record<string, string> = {
  user: '用户',
  agent: 'AI 员工',
  dept: '部门',
  platform: '平台',
};
const METRIC_LABEL: Record<string, string> = { calls: '调用次数', tokens: 'Token' };
const PERIOD_LABEL: Record<string, string> = { day: '每日', month: '每月' };

const Q = `tenant_id=${TENANT_ID}`;

/** 配额管理（FR-156）：四维度（用户/AI员工/部门/平台）日/月上限 + 并发上限，超限硬阻断。 */
export default function QuotaPage({ isAdmin, onLogout, embedded = false }: QuotaPageProps) {
  const policies = useApi<QuotaPolicy[]>(`/api/enterprise/itc/quota/policies?${Q}`);
  const [editorOpen, setEditorOpen] = useState(false);
  const rows = policies.data ?? [];

  // 各维度已用量（后端 counter 端点未实现前为空）
  const bars: QuotaBar[] = useMemo(
    () =>
      rows.map((p) => ({
        label: `${SCOPE_LABEL[p.scope_type] ?? p.scope_type}·${p.scope_id.split('_').slice(-1)[0]}`,
        used: 0,
        limit: p.limit_value,
      })),
    [rows],
  );

  const columns: DataTableColumn<QuotaPolicy>[] = [
    { key: 'scope', title: '维度', width: 100, render: (r) => SCOPE_LABEL[r.scope_type] ?? r.scope_type },
    { key: 'scope_id', title: '对象', dataIndex: 'scope_id', width: 160 },
    { key: 'metric', title: '计量', width: 100, render: (r) => METRIC_LABEL[r.metric] ?? r.metric },
    { key: 'period', title: '周期', width: 90, render: (r) => PERIOD_LABEL[r.period] ?? r.period },
    {
      key: 'limit',
      title: '上限',
      width: 120,
      align: 'right',
      render: (r) => r.limit_value.toLocaleString(),
    },
    {
      key: 'concurrent',
      title: '并发上限',
      width: 100,
      align: 'right',
      render: (r) => (r.concurrent_limit == null ? '—' : r.concurrent_limit),
    },
  ];

  return (
    <div className={embedded ? '' : 'min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]'}>
      {!embedded && (
        <AppHeader
          title="配额与限流"
          description="四维度日/月上限与并发上限，超限硬阻断（FR-156）"
          onLogout={onLogout}
        />
      )}

      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={policies.loading ? '—' : rows.filter((r) => r.scope_type === 'user').length} label="用户配额" />
        <StatCard value={policies.loading ? '—' : rows.filter((r) => r.scope_type === 'agent').length} label="AI 员工配额" />
        <StatCard value={policies.loading ? '—' : rows.filter((r) => r.scope_type === 'dept').length} label="部门配额" />
        <StatCard value={policies.loading ? '—' : rows.filter((r) => r.scope_type === 'platform').length} label="平台配额" />
      </div>

      {/* 用量 / 上限（超 90% 染红） */}
      <div className="mt-[24px] text-[14px] font-semibold text-[#18181a]">各维度用量</div>
      <div className="mt-[10px] rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px]">
        {bars.length > 0 ? (
          <QuotaBarChart data={bars} height={240} />
        ) : (
          <div className="py-[40px] text-center text-[12px] text-[#757f9c]">
            {policies.loading ? '加载中…' : '尚未配置配额策略。配置后各维度用量与上限会在此展示。'}
          </div>
        )}
      </div>

      {/* 策略表 */}
      <div className="mt-[24px] flex items-center justify-between">
        <div className="text-[14px] font-semibold text-[#18181a]">配额策略</div>
        {isAdmin && (
          <UIButton type="button" onClick={() => setEditorOpen(true)}>
            新增策略
          </UIButton>
        )}
      </div>
      <div className="mt-[12px]">
        <DataTable
          columns={columns}
          data={rows}
          rowKey={(r) => `${r.scope_type}:${r.scope_id}:${r.metric}:${r.period}`}
          loading={policies.loading}
          emptyText="暂无配额策略。未配置时不限流，建议至少配置平台维度（D-04 后配额是唯一成本闸门）。"
          aria-label="配额策略"
        />
      </div>

      <div className="mt-[12px] text-[12px] text-[#9aa0ab]">
        达到 80%/90% 预警管理员，100% 按策略硬阻断（FR-155/156）。配额检查在 turn 汇聚点执行（1 行接入）。
      </div>

      {/* 新增策略弹窗（管理员） */}
      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="sm:max-w-[420px]">
          <DialogTitle>新增配额策略</DialogTitle>
          <div className="mt-[14px] flex flex-col gap-[12px]">
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              维度
              <Select defaultValue="platform">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">用户</SelectItem>
                  <SelectItem value="agent">AI 员工</SelectItem>
                  <SelectItem value="dept">部门</SelectItem>
                  <SelectItem value="platform">平台</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              计量
              <Select defaultValue="calls">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="calls">调用次数</SelectItem>
                  <SelectItem value="tokens">Token</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              周期
              <Select defaultValue="month">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="day">每日</SelectItem>
                  <SelectItem value="month">每月</SelectItem>
                </SelectContent>
              </Select>
            </label>
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              上限
              <Input type="number" placeholder="例如 100000" />
            </label>
            <label className="flex flex-col gap-[4px] text-[12px] text-[#464c5e]">
              并发上限（可选）
              <Input type="number" placeholder="留空表示不限制并发" />
            </label>
          </div>
          <DialogFooter>
            <UIButton
              type="button"
              variant="outline"
              onClick={() => setEditorOpen(false)}
            >
              取消
            </UIButton>
            <UIButton
              type="button"
              onClick={() => {
                setEditorOpen(false);
                notify.info('配额策略写入端点待接入（FR-156）');
              }}
            >
              保存
            </UIButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {policies.error && (
        <div className="mt-[12px] text-[12px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={() => void policies.refetch()}>
            点击重试
          </button>
        </div>
      )}
    </div>
  );
}
