import { useMemo } from 'react';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { useApi } from '../hooks/useApi';
import { TENANT_ID } from '../api/client';
import type { AgentProfileRead } from '../types';
import { employeeDisplayNameWithCreator, employeeProfile } from '../employee';

export type OrgChartPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
};

const Q = `tenant_id=${TENANT_ID}&scope=managed&view=summary`;

/** 由岗位名/元数据推断组织层级（FR-148）。原生无层级字段，此处按名称规则推断。 */
function tierOf(a: AgentProfileRead): 'coord' | 'exec' {
  const role = `${(a.metadata?.org_level as string) || ''} ${employeeProfile(a).roleName || ''} ${a.name || ''}`;
  return /军师|协调|幕僚|反调|质检/.test(role) ? 'coord' : 'exec';
}
function isStrategist(a: AgentProfileRead): boolean {
  const role = `${(a.metadata?.org_level as string) || ''} ${employeeProfile(a).roleName || ''}`;
  return /军师|协调|幕僚/.test(role);
}

/** 组织架构（FR-148）：三层组织（决策层/协调层/执行层）+ 军师池。 */
export default function OrgChartPage({ onLogout }: OrgChartPageProps) {
  const agents = useApi<AgentProfileRead[]>(`/api/enterprise/agents?${Q}`);
  const rows = agents.data ?? [];

  const { coordinators, executors } = useMemo(() => {
    const coord: AgentProfileRead[] = [];
    const exec: AgentProfileRead[] = [];
    for (const a of rows) (tierOf(a) === 'coord' ? coord : exec).push(a);
    return { coordinators: coord, executors: exec };
  }, [rows]);

  const strategists = coordinators.filter(isStrategist);

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader
        title="组织架构"
        description="三层 AI 组织：决策层（人）+ 协调层（幕僚组）+ 执行层（FR-148）"
        onLogout={onLogout}
      />

      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={agents.loading ? '—' : coordinators.length} label="协调层（幕僚）" />
        <StatCard value={agents.loading ? '—' : executors.length} label="执行层" />
        <StatCard value={agents.loading ? '—' : strategists.length} label="军师池在岗" />
      </div>

      {/* 三层组织 */}
      <div className="mt-[24px] flex flex-col gap-[16px]">
        <Tier label="决策层" hint="定目标 / 拍板方案 / 派活 / 验收（真实人）">
          <div className="rounded-[12px] border-[0.5px] border-[#e3e7f1] bg-[#f6f6f6] px-[16px] py-[12px] text-[13px] text-[#464c5e]">
            管理员 / 部门负责人 —— 人在【任务台】发布任务
          </div>
        </Tier>

        <Tier label="协调层 · 幕僚组" hint="只出主意不派活；异常处置权归军师（D-06/D-08）">
          {coordinators.length === 0 ? (
            <div className="py-[16px] text-center text-[12px] text-[#757f9c]">
              暂无协调层员工。创建「协调层·军师」后在此展示（军师可配任意数量，D-16）。
            </div>
          ) : (
            <CardGrid agents={coordinators} />
          )}
        </Tier>

        <Tier label="执行层" hint="接任务、执行、交成果">
          {executors.length === 0 ? (
            <div className="py-[16px] text-center text-[12px] text-[#757f9c]">暂无执行层员工。</div>
          ) : (
            <CardGrid agents={executors} />
          )}
        </Tier>
      </div>

      {/* 军师池 */}
      {strategists.length > 0 && (
        <>
          <div className="mt-[24px] text-[14px] font-semibold text-[#18181a]">军师池</div>
          <div className="mt-[10px] text-[12px] text-[#757f9c]">
            系统按「能力标签匹配 ×0.5 + 空闲度 ×0.2 + 历史成功率 ×0.3」择优分配协调型任务（D-17）。
          </div>
          <div className="mt-[10px] grid grid-cols-1 gap-[12px] sm:grid-cols-2 lg:grid-cols-3">
            {strategists.map((a) => (
              <div key={a.id} className="rounded-[14px] border-[0.5px] border-[#e3e7f1] bg-white p-[14px]">
                <div className="text-[14px] font-semibold text-[#18181a]">{employeeDisplayNameWithCreator(a)}</div>
                <div className="mt-[4px] text-[12px] text-[#757f9c]">{employeeProfile(a).roleName || '军师'}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {agents.error && (
        <div className="mt-[12px] text-[12px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={() => void agents.refetch()}>
            点击重试
          </button>
        </div>
      )}
    </div>
  );
}

function Tier({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[18px]">
      <div className="mb-[12px] flex items-baseline gap-[10px]">
        <span className="text-[14px] font-semibold text-[#18181a]">{label}</span>
        <span className="text-[12px] text-[#9aa0ab]">{hint}</span>
      </div>
      {children}
    </div>
  );
}

function CardGrid({ agents }: { agents: AgentProfileRead[] }) {
  return (
    <div className="grid grid-cols-1 gap-[12px] sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((a) => {
        const online = a.status === 'active';
        return (
          <div key={a.id} className="flex items-center gap-[10px] rounded-[12px] border-[0.5px] border-[#e3e7f1] p-[12px]">
            <span
              className="grid size-[34px] shrink-0 place-items-center rounded-[9px] text-[14px] font-semibold text-white"
              style={{ background: 'var(--accent)' }}
            >
              {employeeDisplayNameWithCreator(a).slice(0, 1)}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium text-[#18181a]">
                {employeeDisplayNameWithCreator(a)}
              </div>
              <div className="truncate text-[12px] text-[#757f9c]">{employeeProfile(a).roleName || '—'}</div>
            </div>
            <span className={`flex items-center gap-[4px] text-[11px] ${online ? 'text-[#2cb360]' : 'text-[#9aa0ab]'}`}>
              <i className="size-[6px] rounded-full" style={{ background: online ? '#22c55e' : '#c4c8ce' }} />
              {online ? '在线' : '离线'}
            </span>
          </div>
        );
      })}
    </div>
  );
}
