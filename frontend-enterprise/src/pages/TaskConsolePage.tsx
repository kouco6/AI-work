import { useState } from 'react';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { notify } from '../components/ui/app-toast';
import { useApi } from '../hooks/useApi';
import { api, TENANT_ID } from '../api/client';
import type { AgentProfileRead } from '../types';
import { employeeDisplayNameWithCreator } from '../employee';

export type TaskConsolePageProps = {
  isAdmin: boolean;
  onLogout: () => void;
};

type Candidate = { agent_id: string; name: string; capability: number; idleness: number; success: number; score: number };
type TaskRow = {
  id: string;
  title: string;
  kind: string;
  status: string;
  assignee: string | null;
  assign_detail: { source?: string; candidates?: Candidate[]; note?: string } | null;
};

const Q = `tenant_id=${TENANT_ID}`;
const STATUS_LABEL: Record<string, string> = {
  pending: '待分配', assigned: '已分配', running: '进行中', done: '已完成', failed: '已失败', cancelled: '已取消',
};

/** 任务台（FR-196 / D-16 / D-17）：人写目标发布 → 系统按复杂度自动分配。 */
export default function TaskConsolePage({ onLogout }: TaskConsolePageProps) {
  const [goal, setGoal] = useState('');
  const [publishing, setPublishing] = useState(false);
  const [last, setLast] = useState<TaskRow | null>(null);
  const [executingId, setExecutingId] = useState<string | null>(null);
  const tasks = useApi<TaskRow[]>(`/api/enterprise/itc/tasks?${Q}`, [], { pollMs: 4000 });
  const agents = useApi<AgentProfileRead[]>(`/api/enterprise/agents?${Q.replace('itc/tasks?tenant_id=tenant_demo', 'enterprise/agents')}&scope=managed&view=summary`);
  const rows = tasks.data ?? [];
  const nameOf = (id: string | null) => {
    if (!id) return '—';
    const a = (agents.data ?? []).find((x) => x.id === id);
    return a ? employeeDisplayNameWithCreator(a) : id;
  };

  async function publish() {
    const title = goal.trim();
    if (!title) {
      notify.error('请先填写目标');
      return;
    }
    setPublishing(true);
    try {
      const created = await api.post<TaskRow>(`/api/enterprise/itc/tasks?${Q}`, { title });
      setLast(created);
      setGoal('');
      notify.success(created.kind === 'coordinated' ? '已发布，系统请军师接单' : '已发布，进入执行层认领');
      await tasks.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '发布失败');
    } finally {
      setPublishing(false);
    }
  }

  const columns: DataTableColumn<TaskRow>[] = [
    { key: 'title', title: '任务', width: 260, render: (r) => <span className="text-[#18181a]">{r.title}</span> },
    { key: 'kind', title: '类型', width: 90, render: (r) => (r.kind === 'coordinated' ? '协调型' : '执行型') },
    { key: 'status', title: '状态', width: 90, render: (r) => STATUS_LABEL[r.status] ?? r.status },
    { key: 'assignee', title: '承接', width: 140, render: (r) => nameOf(r.assignee) },
    {
      key: 'actions',
      title: '操作',
      width: 90,
      render: (r) =>
        r.assignee && r.status !== 'done' && r.status !== 'running' ? (
          <button
            type="button"
            disabled={executingId === r.id}
            onClick={() => void runTask(r.id)}
            className="text-[12px] text-[var(--accent)] hover:underline disabled:opacity-50"
          >
            {executingId === r.id ? '执行中…' : '触发执行'}
          </button>
        ) : (
          '—'
        ),
    },
  ];

  async function runTask(id: string) {
    setExecutingId(id);
    try {
      const res = await api.post<{ queued?: boolean; error?: string }>(
        `/api/enterprise/itc/tasks/${encodeURIComponent(id)}/execute?${Q}`,
        {},
      );
      if (res?.queued) notify.success('已触发执行，员工正在处理…');
      else notify.error(res?.error || '触发失败');
      await tasks.refetch();
    } catch (e) {
      notify.error(e instanceof Error ? e.message : '执行失败');
    } finally {
      setExecutingId(null);
    }
  }

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader
        title="任务台"
        description="写目标并发布，系统按任务复杂度自动分配（D-16）。人保留干预权。"
        onLogout={onLogout}
      />

      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={rows.filter((r) => r.status === 'pending').length} label="待分配" />
        <StatCard value={rows.filter((r) => r.status === 'assigned').length} label="已分配" />
        <StatCard value={rows.filter((r) => r.status === 'running').length} label="进行中" />
        <StatCard value={rows.length} label="任务总数" />
      </div>

      {/* 发布区 */}
      <div className="mt-[20px] rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[20px]">
        <div className="text-[14px] font-semibold text-[#18181a]">要做什么？</div>
        <div className="mt-[4px] text-[12px] text-[#757f9c]">
          你只负责写目标。发布后：协调型任务（含协作/跨部门等）由系统从军师池择优；执行型任务进入执行层自主认领。
        </div>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={3}
          placeholder="例如：整理本周三个竞品的价格变动并输出对比表（含「协作」触发协调型）"
          className="mt-[12px] w-full resize-none rounded-[10px] border-[0.5px] border-[#e3e7f1] px-[14px] py-[10px] text-[13px] text-[#18181a] outline-none focus:border-[var(--accent)]"
        />
        <div className="mt-[12px] flex justify-end">
          <button
            type="button"
            disabled={publishing}
            onClick={() => void publish()}
            className="flex h-[36px] items-center justify-center rounded-[10px] bg-[var(--accent)] px-[24px] text-[14px] text-white transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {publishing ? '发布中…' : '发布任务'}
          </button>
        </div>
      </div>

      {/* 最近一次分配结果（D-17 可解释性） */}
      {last && (
        <div className="mt-[20px] rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[20px]">
          <div className="flex items-center gap-[8px]">
            <span className="rounded-full bg-[var(--accent-soft)] px-[10px] py-[2px] text-[12px] text-[var(--accent)]">
              {last.kind === 'coordinated' ? '协调型' : '执行型'}
            </span>
            <span className="min-w-0 truncate text-[13px] text-[#464c5e]">{last.title}</span>
            <span className="ml-auto text-[12px] text-[#757f9c]">{STATUS_LABEL[last.status] ?? last.status}</span>
          </div>

          {last.kind === 'execution' ? (
            <div className="mt-[12px] text-[13px] text-[#757f9c]">
              已进入执行层自主认领。可由执行员工按能力标签领活，或由你
              <span className="mx-[4px] text-[#18181a]">在任务列表直接改派</span>。
            </div>
          ) : last.assign_detail?.candidates?.length ? (
            <div className="mt-[14px]">
              <div className="mb-[8px] text-[13px] text-[#464c5e]">
                系统从军师池择优（D-17：展示三项分项得分）：
              </div>
              <table className="w-full text-[12px]">
                <thead className="text-[#757f9c]">
                  <tr>
                    <th className="pb-[8px] text-left font-normal">军师</th>
                    <th className="pb-[8px] text-right font-normal">能力匹配 ×0.5</th>
                    <th className="pb-[8px] text-right font-normal">空闲度 ×0.2</th>
                    <th className="pb-[8px] text-right font-normal">成功率 ×0.3</th>
                    <th className="pb-[8px] text-right font-normal">综合得分</th>
                  </tr>
                </thead>
                <tbody>
                  {last.assign_detail.candidates.map((c, i) => (
                    <tr key={c.agent_id} className={`border-t-[0.5px] border-[#eef0f4] ${i === 0 ? 'bg-[#f5f9ff]' : ''}`}>
                      <td className="py-[8px] text-[#18181a]">
                        {i === 0 && <span className="mr-[6px] text-[var(--accent)]">★</span>}
                        {nameOf(c.agent_id)}
                      </td>
                      <td className="py-[8px] text-right text-[#464c5e]">{(c.capability * 100).toFixed(0)}%</td>
                      <td className="py-[8px] text-right text-[#464c5e]">{(c.idleness * 100).toFixed(0)}%</td>
                      <td className="py-[8px] text-right text-[#464c5e]">{(c.success * 100).toFixed(0)}%</td>
                      <td className="py-[8px] text-right font-semibold text-[#18181a]">{c.score.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mt-[8px] text-[12px] text-[#757f9c]">
                综合得分 = 能力匹配度 × 0.5 + 空闲度 × 0.2 + 历史成功率 × 0.3。军师之间不竞标（D-17）。
              </div>
            </div>
          ) : (
            <div className="mt-[12px] text-[13px] text-[#757f9c]">
              军师池暂无在岗军师（需先创建「协调层·军师」员工）。任务暂存待分配。
            </div>
          )}
        </div>
      )}

      {/* 任务列表 */}
      <div className="mt-[24px] text-[14px] font-semibold text-[#18181a]">最近任务</div>
      <div className="mt-[12px]">
        <DataTable
          columns={columns}
          data={rows.slice(0, 10)}
          rowKey={(r) => r.id}
          loading={tasks.loading}
          emptyText="暂无任务。在上方写目标并发布后在此展示。"
          aria-label="任务台任务"
        />
      </div>

      {tasks.error && (
        <div className="mt-[12px] text-[12px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={() => void tasks.refetch()}>
            点击重试
          </button>
        </div>
      )}
    </div>
  );
}
