import { useNavigate } from 'react-router-dom';

import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { useApi } from '../hooks/useApi';
import { api, TENANT_ID } from '../api/client';
import { EnterpriseRoute } from '../enums/routes';
import {
  employeeDisplayNameWithCreator,
  employeeProfile,
  agentResourceCount,
} from '../employee';
import type { AgentProfileRead } from '../types';

export type WorkbenchHomePageProps = {
  currentUser: { display_name?: string; username: string };
  isAdmin: boolean;
  onLogout: () => void;
};

/** 快捷入口（FR-105）—— 管理员可配置显示项；这里先给默认组。 */
const QUICK_ENTRIES: { key: string; label: string; to: string }[] = [
  { key: 'daily', label: '生成日报', to: EnterpriseRoute.Agents },
  { key: 'intel', label: '情报查询', to: EnterpriseRoute.Agents },
  { key: 'research', label: '竞品调研', to: EnterpriseRoute.Agents },
  { key: 'sched', label: '定时任务', to: EnterpriseRoute.ScheduledTasks },
  { key: 'files', label: '产出文件', to: EnterpriseRoute.Dashboard },
  { key: 'settings', label: '个人设置', to: EnterpriseRoute.Dashboard },
];

export default function WorkbenchHomePage({ currentUser, isAdmin, onLogout }: WorkbenchHomePageProps) {
  const navigate = useNavigate();

  // 我的数字员工（真实数据）
  const agents = useApi<AgentProfileRead[]>(
    `/api/enterprise/agents?tenant_id=${TENANT_ID}&scope=managed&view=summary`,
  );
  // 平台模型（用于 FR-108「平台无可用模型」异常态）
  const models = useApi<unknown[]>(`/api/enterprise/model-configs?tenant_id=${TENANT_ID}`);

  const name = currentUser.display_name || currentUser.username;
  const agentList = agents.data ?? [];
  const noModels = !models.loading && !models.error && (models.data?.length ?? 0) === 0;
  const noAgents = !agents.loading && !agents.error && agentList.length === 0;

  return (
    <div className="min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]">
      <AppHeader
        title={`你好，${name} 👋`}
        description="欢迎回到 itc AI数字员工平台"
        userName={name}
        onLogout={onLogout}
      />

      {/* FR-108 异常态：平台无可用模型 */}
      {noModels && (
        <div className="mt-[16px] rounded-[14px] border-[0.5px] border-[#f5d0d0] bg-[#fce7e7] px-[16px] py-[12px] text-[13px] text-[#d20b0b]">
          系统管理员尚未配置可用模型，请联系管理员开通后再使用。
        </div>
      )}

      {/* 数据看板（FR-104）—— 4 张卡；管理员第 4 张额外看平台额度（D-04） */}
      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={agents.loading ? '—' : agentList.length} label="可用数字员工" />
        <StatCard value="—" label="本月产出文件" />
        <StatCard value="—" label="待处理任务" />
        {isAdmin ? (
          <StatCard value="—" label="平台额度使用率" />
        ) : (
          <StatCard value="平台额度" label="已用 —（D-04 统一计费）" />
        )}
      </div>

      {/* 快捷入口（FR-105） */}
      <div className="mt-[24px] text-[14px] font-semibold text-[#18181a]">
        快捷入口
        <span className="ml-[8px] text-[12px] font-normal text-[#757f9c]">管理员可配置显示项（FR-105）</span>
      </div>
      <div className="mt-[10px] flex flex-wrap gap-[12px]">
        {QUICK_ENTRIES.map((q) => (
          <button
            key={q.key}
            type="button"
            onClick={() => navigate(q.to)}
            className="flex h-[64px] w-[132px] flex-col items-center justify-center gap-[6px] rounded-[14px] border-[0.5px] border-[#e3e7f1] bg-white text-[13px] text-[#464c5e] transition-colors hover:bg-[#f6f6f6]"
          >
            <span className="text-[18px] text-[var(--accent)]">◈</span>
            {q.label}
          </button>
        ))}
      </div>

      {/* 我的数字员工（FR-106） */}
      <div className="mt-[24px] flex items-baseline justify-between">
        <div className="text-[14px] font-semibold text-[#18181a]">我的数字员工</div>
        <button
          type="button"
          onClick={() => navigate(EnterpriseRoute.Agents)}
          className="text-[12px] text-[#757f9c] hover:text-[#18181a]"
        >
          共 {agentList.length} 个 · 查看全部
        </button>
      </div>

      {agents.loading ? (
        <div className="mt-[12px] text-[13px] text-[#757f9c]">加载中…</div>
      ) : agents.error ? (
        <div className="mt-[12px] text-[13px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={() => void agents.refetch()}>
            点击重试
          </button>
        </div>
      ) : noAgents ? (
        <div className="mt-[12px] rounded-[14px] border-[0.5px] border-[#e3e7f1] bg-[#fafbfc] px-[16px] py-[20px] text-center text-[13px] text-[#757f9c]">
          暂无可用数字员工，请联系管理员开通。
        </div>
      ) : (
        <div className="mt-[12px] grid grid-cols-1 gap-[16px] sm:grid-cols-2 lg:grid-cols-3">
          {agentList.slice(0, 6).map((a) => {
            const profile = employeeProfile(a);
            const online = a.status === 'active';
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => navigate(EnterpriseRoute.Agents)}
                className="flex flex-col gap-[10px] rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px] text-left transition-colors hover:bg-[#fafbfc]"
              >
                <div className="flex items-center gap-[10px]">
                  <span
                    className="grid size-[36px] shrink-0 place-items-center rounded-[10px] text-[15px] font-semibold text-white"
                    style={{ background: 'var(--accent)' }}
                  >
                    {employeeDisplayNameWithCreator(a).slice(0, 1)}
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-semibold text-[#18181a]">
                      {a.is_overall ? '开放广场' : employeeDisplayNameWithCreator(a)}
                    </div>
                    <div className="truncate text-[12px] text-[#757f9c]">{profile.roleName || a.description || '数字员工'}</div>
                  </div>
                  <span
                    className={`ml-auto flex items-center gap-[4px] text-[11px] ${online ? 'text-[#2cb360]' : 'text-[#9aa0ab]'}`}
                  >
                    <i className="size-[6px] rounded-full" style={{ background: online ? '#22c55e' : '#c4c8ce' }} />
                    {online ? '在线' : '离线'}
                  </span>
                </div>
                <p className="line-clamp-2 min-h-[34px] text-[12px] leading-[17px] text-[#757f9c]">
                  {a.description || '暂无描述'}
                </p>
                <div className="flex gap-[16px] text-[12px] text-[#464c5e]">
                  <span><b>{agentResourceCount(a, 'knowledge_base')}</b> 资料</span>
                  <span><b>{agentResourceCount(a, 'general_skill')}</b> 技能</span>
                  <span><b>{agentResourceCount(a, 'skill')}</b> SOP</span>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* 双栏动态区（FR-107）：后端未提供前走空态引导（FR-108） */}
      <div className="mt-[24px] grid grid-cols-1 gap-[16px] lg:grid-cols-2">
        <div className="rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px]">
          <div className="mb-[10px] text-[14px] font-semibold text-[#18181a]">最新动态</div>
          <div className="py-[20px] text-center text-[12px] text-[#757f9c]">暂无动态，产生真实任务后将在此展示。</div>
        </div>
        <div className="rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px]">
          <div className="mb-[10px] text-[14px] font-semibold text-[#18181a]">待办任务</div>
          <div className="py-[20px] text-center text-[12px] text-[#757f9c]">暂无待办，需要你处理的审核/确认会出现在这里。</div>
        </div>
      </div>
    </div>
  );
}
