import AppHeader from '../components/AppHeader';
import { StatCard } from '../components/StatCard';
import { UsageLineChart, type UsagePoint } from '../components/charts';
import { useApi } from '../hooks/useApi';
import { TENANT_ID } from '../api/client';

export type CostDashboardPageProps = {
  isAdmin: boolean;
  onLogout: () => void;
  /** 嵌入「管理后台」二级 tab 时隐藏自身页头与整页留白。 */
  embedded?: boolean;
};

type CostSummary = {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost: number;
  unmetered_calls: number;
};

type CostBucketRow = {
  key: string;
  calls: number;
  total_tokens: number;
  cost: number;
  unmetered_calls: number;
};

type DayRow = { label: string; input: number; output: number; total: number; calls: number };

const Q = `tenant_id=${TENANT_ID}`;

/**
 * 成本与 KPI 看板（FR-151~155）。数据来自 itc 平台服务层
 * （`/api/enterprise/itc/cost/*`），即 observer 落库的 ``itc_usage_records``。
 */
export default function CostDashboardPage({ onLogout, embedded = false }: CostDashboardPageProps) {
  const summary = useApi<CostSummary>(`/api/enterprise/itc/cost/summary?${Q}`);
  const byDay = useApi<DayRow[]>(`/api/enterprise/itc/cost/by-day?${Q}`);
  const byModel = useApi<CostBucketRow[]>(`/api/enterprise/itc/cost/by-model?${Q}`);
  const byAgent = useApi<CostBucketRow[]>(`/api/enterprise/itc/cost/by-agent?${Q}`);

  const s = summary.data;
  const loading = summary.loading;
  const empty = !loading && !summary.error && (s?.calls ?? 0) === 0;

  const chartData: UsagePoint[] = (byDay.data ?? []).map((d) => ({
    label: d.label,
    input: d.input,
    output: d.output,
  }));

  return (
    <div className={embedded ? '' : 'min-h-full box-border px-[48px] pt-[32px] pb-[43px] max-[900px]:px-[16px]'}>
      {!embedded && (
        <AppHeader
          title="成本与 KPI"
          description="平台用量与成本统计（数据来自 itc 计量层）"
          onLogout={onLogout}
        />
      )}

      {summary.error && (
        <div className="mt-[16px] text-[13px] text-[#d20b0b]">
          加载失败，
          <button type="button" className="underline" onClick={() => void summary.refetch()}>
            点击重试
          </button>
        </div>
      )}

      {/* 总览卡（FR-151/152/154） */}
      <div className="mt-[20px] flex flex-wrap gap-[16px]">
        <StatCard value={loading ? '—' : (s?.calls ?? 0)} label="调用次数" />
        <StatCard
          value={loading ? '—' : `¥${(s?.cost ?? 0).toFixed(4)}`}
          label="总成本"
        />
        <StatCard value={loading ? '—' : (s?.total_tokens ?? 0).toLocaleString()} label="总 Token" />
        <StatCard
          value={loading ? '—' : (s?.unmetered_calls ?? 0)}
          label="未计量调用"
          tone={(s?.unmetered_calls ?? 0) > 0 ? 'red' : 'default'}
        />
      </div>

      {/* 时间趋势 */}
      <div className="mt-[24px] text-[14px] font-semibold text-[#18181a]">每日用量趋势</div>
      <div className="mt-[10px] rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px]">
        {chartData.length > 0 ? (
          <UsageLineChart data={chartData} height={260} />
        ) : (
          <div className="py-[40px] text-center text-[12px] text-[#757f9c]">
            {loading ? '加载中…' : '暂无用量数据，产生模型调用后将在此展示。'}
          </div>
        )}
      </div>

      {/* 按模型 / 按员工 两栏 */}
      <div className="mt-[24px] grid grid-cols-1 gap-[16px] lg:grid-cols-2">
        {[
          { title: '按模型', rows: byModel.data, loading: byModel.loading },
          { title: '按 AI 员工', rows: byAgent.data, loading: byAgent.loading },
        ].map((block) => (
          <div key={block.title} className="rounded-[16px] border-[0.5px] border-[#e3e7f1] bg-white p-[16px]">
            <div className="mb-[10px] text-[14px] font-semibold text-[#18181a]">{block.title}</div>
            {block.loading ? (
              <div className="py-[20px] text-center text-[12px] text-[#757f9c]">加载中…</div>
            ) : (block.rows?.length ?? 0) === 0 ? (
              <div className="py-[20px] text-center text-[12px] text-[#757f9c]">暂无数据。</div>
            ) : (
              <table className="w-full text-[12px]">
                <thead className="text-[#757f9c]">
                  <tr>
                    <th className="pb-[8px] text-left font-normal">名称</th>
                    <th className="pb-[8px] text-right font-normal">调用</th>
                    <th className="pb-[8px] text-right font-normal">Token</th>
                    <th className="pb-[8px] text-right font-normal">成本</th>
                  </tr>
                </thead>
                <tbody>
                  {block.rows!.map((r) => (
                    <tr key={r.key} className="border-t-[0.5px] border-[#eef0f4]">
                      <td className="py-[8px] text-[#18181a]">{r.key || '(未归属)'}</td>
                      <td className="py-[8px] text-right text-[#464c5e]">{r.calls}</td>
                      <td className="py-[8px] text-right text-[#464c5e]">{r.total_tokens.toLocaleString()}</td>
                      <td className="py-[8px] text-right text-[#18181a]">¥{r.cost.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>

      {empty && (
        <div className="mt-[16px] text-[12px] text-[#757f9c]">
          暂无计量数据。产生模型调用后，用量与成本会在此汇总；未配模型单价时成本按 0 计（见「模型配置」）。
        </div>
      )}
    </div>
  );
}
