/**
 * 企业台路由表 —— 从 App.tsx 的硬编码 <Routes> 抽出（仅搬迁，行为不变）。
 *
 * 目的：新增页面只改本文件，不必动 App.tsx 的大段 JSX。
 * 约束（这些**必须**留在 App.tsx，不能进本配置）：
 *  - `<Routes>` 的外层双条件（!isDistillRoute && !showEmployeeEmptyState）
 *  - distill 常驻块、空态块
 *  - 侧栏高亮 startsWith 链
 *  - App()/AuthedApp() 的 auth gate 与 workspace 重定向
 *
 * 顺序敏感：`/enterprise` 重定向与末尾 `*` 兜底必须在数组首尾各就各位。
 */
import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import type { EnterpriseAuthSession } from '../auth';
import { EnterpriseRoute } from '../enums/routes';

import AccountsPage from '../pages/AccountsPage';
import AgentsPage from '../pages/AgentsPage';
import ChannelsPage from '../pages/ChannelsPage';
import DashboardPage from '../pages/dashboard/DashboardPage';
import {
  ScheduledTaskEditPage,
  ScheduledTaskNewPage,
} from '../pages/dashboard/ScheduledTasksTab';
import GeneralSkillsPage, {
  GeneralSkillEditPage,
  GeneralSkillNewPage,
} from '../pages/GeneralSkillsPage';
import KnowledgeManagePage, { KnowledgeAddPage } from '../pages/KnowledgePage';
import ModelsPage from '../pages/ModelsPage';
import OpenPlatformPage from '../pages/OpenPlatformPage';
import PersonaPage from '../pages/PersonaPage';
import RuntimeSettingsPage from '../pages/RuntimeSettingsPage';
import SkillsPage from '../pages/SkillsPage';
import TeamChatPage from '../pages/TeamChatPage';
import TeamDetailPage from '../pages/TeamDetailPage';
import TeamsPage from '../pages/TeamsPage';
import ToolsPage, {
  McpServerEditPage,
  McpServerNewPage,
  ToolEditPage,
  ToolNewPage,
  ToolTestPage,
} from '../pages/ToolsPage';
import WorkbenchHomePage from '../pages/WorkbenchHomePage';
import TaskConsolePage from '../pages/TaskConsolePage';
import TaskManagementPage from '../pages/TaskManagementPage';
import OutputsPage from '../pages/OutputsPage';
import OrgChartPage from '../pages/OrgChartPage';
import SharedMemoryPage from '../pages/SharedMemoryPage';
import KpiDashboardPage from '../pages/KpiDashboardPage';

export type AppRouteCtx = {
  auth: EnterpriseAuthSession;
  isAdmin: boolean;
  onLogout: () => void;
  openCreateAgentModal: () => void;
};

export type AppRoute = {
  path: string;
  element: ReactNode;
};

export function buildAppRoutes({
  auth,
  isAdmin,
  onLogout,
  openCreateAgentModal,
}: AppRouteCtx): AppRoute[] {
  const user = auth.user;
  return [
    { path: '/enterprise', element: <Navigate to="/enterprise/home" replace /> },
    // itc 工作台首页（FR-101~108，二次开发整页新增）
    {
      path: '/enterprise/home',
      element: <WorkbenchHomePage currentUser={user} isAdmin={isAdmin} onLogout={onLogout} />,
    },
    // 注：成本/KPI、配额、数据源已并入「管理后台」二级 tab（/admin），不再单独占路由。
    // itc 任务台（FR-196，二次开发整页新增）
    {
      path: '/enterprise/tasks',
      element: <TaskConsolePage isAdmin={isAdmin} onLogout={onLogout} />,
    },
    // itc 任务管理（FR-197，二次开发整页新增）
    {
      path: '/enterprise/task-management',
      element: <TaskManagementPage isAdmin={isAdmin} onLogout={onLogout} />,
    },
    // itc 输出物管理（FR-211~216，二次开发整页新增）
    {
      path: '/enterprise/outputs',
      element: <OutputsPage isAdmin={isAdmin} onLogout={onLogout} />,
    },
    // itc 组织架构（FR-148，二次开发整页新增；原型中折进「我的团队」，此处保留 URL 可达）
    {
      path: '/enterprise/org',
      element: <OrgChartPage isAdmin={isAdmin} onLogout={onLogout} />,
    },
    // itc 绩效考核 / KPI（FR-128/130/132，二次开发整页新增）
    {
      path: '/enterprise/kpi',
      element: <KpiDashboardPage isAdmin={isAdmin} onLogout={onLogout} />,
    },
    // itc 部门权限已并入「组织管理」(/enterprise/accounts)
    { path: '/enterprise/depts', element: <Navigate to="/enterprise/accounts" replace /> },
    // itc 共享记忆 L1/L2（FR-201/202，二次开发整页新增；原型中折进「记忆」，此处保留 URL 可达）
    {
      path: '/enterprise/shared-memory',
      element: <SharedMemoryPage isAdmin={isAdmin} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/platform',
      element: <OpenPlatformPage currentUser={user} isAdmin={isAdmin} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/platform/:kind',
      element: <OpenPlatformPage currentUser={user} isAdmin={isAdmin} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/dashboard',
      element: <DashboardPage currentUser={user} isAdmin={isAdmin} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/agents',
      element: (
        <AgentsPage
          currentUser={user}
          isAdmin={isAdmin}
          onCreateAgent={openCreateAgentModal}
          onLogout={onLogout}
        />
      ),
    },
    {
      path: '/enterprise/teams',
      element: <TeamsPage currentUser={user} isAdmin={isAdmin} onLogout={onLogout} />,
    },
    { path: '/enterprise/teams/:teamId/chat', element: <TeamChatPage /> },
    {
      path: '/enterprise/teams/:teamId',
      element: <TeamDetailPage currentUser={user} isAdmin={isAdmin} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/memories',
      element: (
        <DashboardPage currentUser={user} isAdmin={isAdmin} profileTab="memories" onLogout={onLogout} />
      ),
    },
    {
      path: '/enterprise/knowledge',
      element: <KnowledgeManagePage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/knowledge/new',
      element: <KnowledgeAddPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/feedback',
      element: (
        <DashboardPage currentUser={user} isAdmin={isAdmin} profileTab="logs" onLogout={onLogout} />
      ),
    },
    {
      path: '/enterprise/channels',
      element: <ChannelsPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/scheduled-tasks',
      element: (
        <DashboardPage currentUser={user} isAdmin={isAdmin} profileTab="scheduled" onLogout={onLogout} />
      ),
    },
    {
      path: '/enterprise/scheduled-tasks/new',
      element: <ScheduledTaskNewPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/scheduled-tasks/:taskId/edit',
      element: <ScheduledTaskEditPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/skills',
      element: <SkillsPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/general-skills',
      element: <GeneralSkillsPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/general-skills/new',
      element: <GeneralSkillNewPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/general-skills/:slug/edit',
      element: <GeneralSkillEditPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/accounts',
      element: isAdmin ? (
        <AccountsPage currentUser={user} onLogout={onLogout} />
      ) : (
        <Navigate to={EnterpriseRoute.Gallery} replace />
      ),
    },
    {
      path: '/enterprise/models',
      element: isAdmin ? (
        <ModelsPage currentUser={user} onLogout={onLogout} />
      ) : (
        <Navigate to={EnterpriseRoute.Gallery} replace />
      ),
    },
    {
      path: '/enterprise/runtime-settings',
      element: isAdmin ? (
        <RuntimeSettingsPage currentUser={user} />
      ) : (
        <Navigate to={EnterpriseRoute.Gallery} replace />
      ),
    },
    { path: '/enterprise/tools', element: <ToolsPage currentUser={user} onLogout={onLogout} /> },
    {
      path: '/enterprise/tools/new',
      element: <ToolNewPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/tools/mcp/new',
      element: <McpServerNewPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/tools/mcp/:serverId/edit',
      element: <McpServerEditPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/tools/:toolId/edit',
      element: <ToolEditPage currentUser={user} onLogout={onLogout} />,
    },
    {
      path: '/enterprise/tools/:toolId/test',
      element: <ToolTestPage currentUser={user} onLogout={onLogout} />,
    },
    { path: '/enterprise/persona', element: <PersonaPage /> },
    { path: '*', element: <Navigate to="/enterprise/dashboard" replace /> },
  ];
}
