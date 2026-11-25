/**
 * 组织层级选项（FR-122 / D-16，itc 二次开发新增）。
 * 新建数字员工与编辑档案共用。层级决定该员工能被分配什么任务类型（协调型 / 执行型）。
 */

export type OrgLevelValue = 'executor' | 'strategist' | 'qa';

export type OrgLevelOption = {
  value: OrgLevelValue;
  label: string;
  title: string;
  desc: string;
  eg: string;
};

export const ORG_LEVELS: OrgLevelOption[] = [
  {
    value: 'executor',
    label: '执行层',
    title: '干活的专业 AI',
    desc: '接收任务、投入执行、交出成果。不组织别人，不派活。',
    eg: '例：情报小秘、爬虫专员、内容编辑、推送专员',
  },
  {
    value: 'strategist',
    label: '协调层 · 军师',
    title: '领任务、组队、推进',
    desc: '从系统分配中领协调型任务，拆解后拉执行层组队。不派发新任务。',
    eg: '例：军师·林、军师·周（可配多个，无数量上限）',
  },
  {
    value: 'qa',
    label: '协调层 · 反调官',
    title: '持续检验与挑错',
    desc: '检验各阶段产出、标注问题点、退回修改。不执行生产任务。',
    eg: '例：反调官 AI-002',
  },
];

export const ORG_LEVEL_HINTS: Record<string, string> = {
  executor: '执行层员工从任务池自主认领执行型任务；每个执行层员工可绑定自己的知识库、技能、SOP 与工具。',
  strategist:
    '军师是岗位类型，可配任意数量；系统按「能力×0.5 + 空闲×0.2 + 成功率×0.3」从军师池择优分配协调型任务（D-17）。',
  qa: '反调官归协调层（参谋性质），持续检验产出、标注问题点；不执行生产任务。',
};

/** 层级 → 中文名（用于卡片/标签展示）。 */
export function orgLevelLabel(value?: string): string {
  return ORG_LEVELS.find((l) => l.value === value)?.label || '';
}

/** 由岗位名推断层级（原生无 org_level 时的兜底）。 */
export function inferOrgLevel(roleText: string): OrgLevelValue {
  return /军师|协调|幕僚/.test(roleText)
    ? 'strategist'
    : /反调|质检|QA/i.test(roleText)
      ? 'qa'
      : 'executor';
}
