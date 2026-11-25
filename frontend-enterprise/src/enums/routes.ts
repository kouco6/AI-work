export enum EnterpriseRoute {
  Workspace = '/workspace',
  Chat = '/workspace/chat',
  /** itc 工作台首页（FR-101~108，二次开发新增） */
  Home = '/enterprise/home',
  /** itc 成本与 KPI 看板（FR-151~155，二次开发新增） */
  Cost = '/enterprise/cost',
  /** itc 任务台（FR-196，二次开发新增） */
  Tasks = '/enterprise/tasks',
  /** itc 任务管理（FR-197，二次开发新增） */
  TaskManagement = '/enterprise/task-management',
  /** itc 输出物管理（FR-211~216，二次开发新增） */
  Outputs = '/enterprise/outputs',
  /** itc 数据源管理（FR-178~182，二次开发新增） */
  DataSources = '/enterprise/data-sources',
  /** itc 组织架构 / 三层组织 + 军师池（FR-148，二次开发新增） */
  OrgChart = '/enterprise/org',
  /** itc 共享记忆 L1/L2（FR-201/202，二次开发新增） */
  SharedMemory = '/enterprise/shared-memory',
  Platform = '/enterprise/platform',
  Gallery = '/workspace/gallery',
  Agents = '/enterprise/agents',
  Teams = '/enterprise/teams',
  Dashboard = '/enterprise/dashboard',
  ScheduledTasks = '/enterprise/scheduled-tasks',
  Memories = '/enterprise/memories',
  Feedback = '/enterprise/feedback',
  Channels = '/enterprise/channels',
  Knowledge = '/enterprise/knowledge',
  GeneralSkills = '/enterprise/general-skills',
  Skills = '/enterprise/skills',
  Tools = '/enterprise/tools',
  Accounts = '/enterprise/accounts',
  Models = '/enterprise/models',
  RuntimeSettings = '/enterprise/runtime-settings',
  Admin = '/admin',
}
