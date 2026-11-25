# itc AI数字员工平台 · StaffDeck 二开工作副本

> 本目录是 StaffDeck 的**二次开发工作副本**（fork）。上游为
> https://github.com/OpenBMB/StaffDeck （AGPL），基线 commit `fcc28c0`（2026-10-24，分支 `main`）。
>
> 配套文档在隔壁：`E:\AI work\数字员工平台\`（需求 / 蓝图 / 基础层设计）。

## 分支与上游

```sh
git remote -v           # origin = OpenBMB/StaffDeck
git fetch origin        # 跟进上游（RK-05：前端合并冲突是常态工作）
git log -1              # 确认基线
```

**策略**：前端 Fork + 最小改动；后端**无侵入扩展**优先（见下）。自定义代码与上游源码**物理隔离**。

## 新增代码位置（与上游源码隔离）

```
backend/src/
  itc_modules/          # 挂到 StaffDeck ModuleRegistry 的模块
    usage_meter.py      #   用量计量 observer（FR-151/152）
    audit_observer.py   #   审计留存 observer（FR-224）
    memory_shared.py    #   共享记忆 L1/L2 provider（FR-201/202）
  itc_platform/         # 业务库（表模型 / 存储）
    db.py               #   复用 app.db.engine，只建 itc_ 表
    models.py           #   itc_* 新表（SQLModel，由 Alembic 管）
    usage/ cost/ kpi/ audit/ memory/ tasks/ datasource/
  tests_itc/            # itc 独立自测（轻量 venv 即可跑，不依赖 StaffDeck 全环境）
    smoke_usage.py      #   建表 + 落库 + 字段原样
    smoke_observer.py   #   observer 注册进 registry + 事件落库
backend/env.itc.template # 装配模板（复制为 .env）
```

> **已移除的需求**（本轮）：**配额与限流（FR-156）**、**巡检监控（FR-221~225）**、
> **内容安全（FR-234）** —— 三项 not in scope，相关 itc 代码（`itc_platform/quota`·
> `itc_platform/safety`·`itc_modules/quota_gate`·`itc_modules/content_safety`·`QuotaPage`·
> `QuotaBarChart` + 对应表/端点/测试）已删除。原生功能（聊天流心跳、流程图检查器等）不受影响。

> `launch.py:7` 已把 `backend/` 与 `backend/src/` 注入 `sys.path`；`backend/pyproject.toml` 的
> `packages.find.include` 也已补 `itc_modules*` / `itc_platform*`（双保险）。

## 装配（怎么让 itc 模块生效）

```sh
cd backend
cp env.itc.template .env   # 再按需改
# .env 内已设：STAFFDECK_HARNESS_MODULES=itc_modules.usage_meter:register,...
```

`harness_modules` 的加载逻辑在 `backend/src/staffdeck_harness/modules/registry.py:507-516`。

## 自测（已实测通过）

```sh
cd backend
python -m venv .venv-itc
./.venv-itc/Scripts/python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    "sqlmodel>=0.0.21,<0.0.39" pydantic-settings httpx
./.venv-itc/Scripts/python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .   # 后端全量依赖
./.venv-itc/Scripts/python.exe tests_itc/smoke_usage.py       # 建表 + 落库 + 字段原样
./.venv-itc/Scripts/python.exe tests_itc/smoke_observer.py    # observer 注册 + 事件落库
./.venv-itc/Scripts/python.exe tests_itc/smoke_audit.py       # 审计落库 + 脱敏 + 180 天留存
./.venv-itc/Scripts/python.exe tests_itc/smoke_cost.py        # 成本/KPI：明细计费 + 多维聚合
./.venv-itc/Scripts/python.exe tests_itc/smoke_discovery.py   # 真实装配路径（discover_and_install）
```

**实测结论（2026-11-23，真机非推断）**：

| 验证 | 结果 |
|------|------|
| 8 张 `itc_` 表登记/建出 | ✅ 只建 itc 表，不碰原生表 |
| 非阻塞入队 + 批量落库 | ✅ 2 条 → flush 2 行 |
| usage 缺失原样记 NULL（D-13） | ✅ |
| observer 收 `llm_call_finished` 落库 | ✅ 他类事件被忽略 |
| **真实装配**：`discover_and_install` 按 `harness_modules` 装载 | ✅ 共 **60** 个模块；itc 3 个就位 |
| `event.observer` 槽 | ✅ `observer.trace / observer.feedback / ledger.invocation / usage.meter / audit.observer` —— **追加并存，未顶掉原生** |
| 反向：不配 `harness_modules` | ✅ 共 **57** 个模块，**无 itc 模块** |
| **审计落库 + 脱敏 + 180 天留存**（`smoke_audit`） | ✅ `api_key/token` → `[redacted]`；删 200 天前、留近期 |
| **成本/KPI**（`smoke_cost`） | ✅ 明细计费准确；未计量单列；按模型/员工/用户聚合 |
| 共享 `BatchWriter`（usage/audit 复用） | ✅ 非阻塞入队 + 后台批量 flush |

> ⚠️ 以上为**组件级真机**（脚本驱动）。**整机装配已另行验证**（见下）。

**整机装配验证（2026-11-23，真机）**——起真实后端，`STAFFDECK_HARNESS_MODULES` 指向 itc 模块：

| 证据 | 结果 |
|------|------|
| 后端启动日志 | ✅ `installed staffdeck_harness modules from itc_modules.usage_meter:register` / `audit_observer` / `content_safety` 三条 |
| 运行库建表 | ✅ 后端 DB（`backend/skill_agent_loop.db`，85 张表）含**全部 9 张 `itc_` 表** |
| 全链路 | ✅ 前端 5173 → 代理 → 后端 8000，`admin/admin` 登录返回 token |
| 工作台首页 | ✅ `/enterprise/home` 拉真实 agents；`model-configs=[]` → FR-108 无模型横幅正确显示 |

> 即：**itc 平台服务层模块已真正挂进运行中的 StaffDeck**，不只是脚本驱动。

## 唯一需改的上游源码（共 6 处插入点，均留标记注释）

| # | 文件 | 改动 | 对应 FR |
|---|------|------|---------|
| 2 | `backend/src/staffdeck_harness/security/profile.py:64-85` | 加 `itc_rbac` 分支 | FR-232/266 |
| 3 | `backend/app/api/auth.py` | 新增 `/api/auth/oidc/callback`（老逻辑零改） | FR-262 |
| 4 | `backend/app/db/database.py:22-24` | PG 连接池参数（补 `pool_size` 等） | D-11 |
| 5 | `backend/app/main.py:80` | PG 分支换 advisory lock | D-11 |
| 6 | `frontend-enterprise/src/{App.tsx,styles.css,index.html}` | 路由配置化 + 品牌变量 + 标题 | AD-07 |

**已实际落地的源码改动（截至 2026-11-24）**：

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/main.py` | `include_router(itc_platform.api.router)` — 挂 itc 成本/KPI/数据源/记忆/任务 API | **+2 行** |
| `backend/src/staffdeck_harness/bridge/engine_host.py:196` | v3 trace 的 `EventLog` 接 `event_sink=fanout_event(...)` —— 让引擎事件 fanout 给 observer（原生此处未接，导致 `llm_call_finished` 不达 observer） | **+7 行** |
| `frontend-enterprise/src/App.tsx` | 路由块 259 行 → 5 行（配置化） | 净减 254 行 |

> 其余 itc 功能（计量/审计/成本服务/看板页）**均不改上游源码**——
> 后端走 ModuleRegistry 外部模块 + 独立 `itc_platform` 包，前端走新增文件 + 路由配置表。

## itc 平台 API（`/api/enterprise/itc/*`）

由 `itc_platform/api.py` 提供（`main.py` 挂载），复用 StaffDeck 的 `require_current_tenant` 鉴权：

| 端点 | 用途 | FR |
|------|------|-----|
| `GET /cost/summary` | 成本总览 | FR-151/152/154 |
| `GET /cost/by-day` | 每日用量时间序列（折线图） | FR-154 |
| `GET /cost/by-model` | 按模型 | FR-145 |
| `GET /cost/by-agent` | 按 AI 员工 | FR-152 |
| `GET /cost/by-user` | 按用户排行 | FR-154 |
| `GET /kpi/agents` | AI 员工 KPI：用量 + **准确率/满意度**（原生 message_feedback）+ **响应时长**（原生 harness_runs）+ **S/A/B/C/D 等级** | FR-128/130/153 |
| `GET /model-prices` | 模型单价表 | FR-152 |
| `GET/POST/DELETE /memory/shared` | 共享记忆 L1/L2（仅管理员写） | FR-201/202 |
| `POST /tasks` | 发布任务（按复杂度自动分配） | FR-196 |
| `GET /tasks` · `GET /tasks/strategist-pool` | 任务列表 · 军师池（D-17 择优依据） | FR-196/197 |
| `POST /tasks/{id}/claim · assign · recall · status` | 认领 / 改派 / 收回 / 改状态 | FR-196 |
| `POST /tasks/{id}/execute` | **触发执行**（异步；入队 `enqueue_runtime_job`，立即返回 `{queued:true}`） | FR-196 |
| `GET/POST /outputs` · `/outputs/{id}/share·archive` · `DELETE` | 产出物库（D-10 存平台 + 平台 RBAC + 版本 + 归档 + 分享） | FR-211~216 |

> **派活→执行闭环已通**（**异步 + 自动触发**，实测）：
> 发布任务 → 协调型分给军师 / 执行型被认领 → **认领/分配即自动异步执行**（不阻塞 HTTP）→
> 后台线程复用 `AgentLoop(db).handle_turn_stream` 跑一轮 → 结果写回任务、状态置 `done`。
> 执行走 StaffDeck 的后台任务队列（与定时任务同款：独立 Session + 绑定身份 + channel=web）。
> 前端任务台/任务管理**轮询**（4–5s）看状态变化。

## 记忆 L1/L2 共享层（FR-201）

**做法（无侵入，满足 D-15）**：新增独立表 `itc_shared_memories` + 一个 **`runtime.memory` provider**
（`itc_modules/memory_shared.py`），在 recall 时把共享层合并到**原生 per-user 记忆之后**
（优先级 L3/L4 > L2 岗位 > L1 全局）。**原生 `app/memory/service.py`、`MemoryRecord` 表、API 一行不改**。
capture/list/clear 一律透传原生；卸载该模块即完全退回原生行为。

装配：`.env` 里 `STAFFDECK_HARNESS_DISABLED_MODULES=memory.default`（禁用内置）+ 安装本 provider。

> **D-15 验证**：上游记忆测试 `tests/test_memory_service.py` **10/11 通过**。
> 唯一失败项 `test_memory_job_reads_canonical_history_through_its_own_turn` 经**纯净源码复现**——
> 是 StaffDeck **自身缺陷**（同事务消息 `created_at` 微秒并列 + `ORDER BY created_at DESC` 排序不确定），
> **与本次改动无关**（`git status` 对 `app/memory/`、`models.py` 无输出）。

> 实际改动以《基础层设计.md》为准；此处为登记表，便于 `git diff` 对照与上游 merge。

## 前端基础层 + 品牌化（已落地）

**新增文件**（与上游源码隔离在 `src/` 内独立目录）：

```
src/hooks/useApi.ts                 # 数据请求 hook（复用 api/client.ts 的 api.get，防竞态/可轮询）
src/components/charts/              # 图表层（recharts，颜色吃 styles.css 变量）
  chartTheme.ts  UsageLineChart.tsx  index.ts
src/routes/config.tsx               # 企业台路由表（从 App.tsx 抽出）
src/pages/WorkbenchHomePage.tsx     # 工作台首页（FR-101~108，二次开发整页新增）
src/pages/CostDashboardPage.tsx     # 成本与 KPI 看板（FR-151~155）
src/pages/TaskConsolePage.tsx       # 任务台（FR-196 / D-16 / D-17）
src/pages/TaskManagementPage.tsx    # 任务管理（FR-197）
src/pages/OutputsPage.tsx           # 输出物管理（FR-211~216）
src/pages/DataSourcePage.tsx        # 数据源管理（FR-178~182）
src/pages/OrgChartPage.tsx          # 组织架构 / 三层组织 + 军师池（FR-148）
src/pages/SharedMemoryPage.tsx      # 共享记忆 L1/L2（FR-201/202）
src/pages/KpiDashboardPage.tsx      # 绩效考核 / KPI（FR-128/130/132）
src/lib/orgLevels.ts                # 组织层级选项（FR-122/D-16，新建+编辑共用）
src/assets/icons/nav-*.svg          # 侧栏图标（home/cost/task/outputs/quota/datasource/org/shared-memory）
```

**数字员工组织层级（FR-122 / D-16）**——原生新建弹窗只有 4 字段、**没有组织层级**，本项目在
**入职流程首位**新增层级选择（三选一）：
- **执行层** —— 干活的专业 AI，接任务、执行、交成果
- **协调层 · 军师** —— 领协调型任务、拆解、组队（可配任意数量）
- **协调层 · 反调官** —— 持续检验产出、退回修改

层级存入员工 `metadata.org_level`（无侵入，不改后端表）；**新建弹窗**（`App.tsx`）为三张可点选层级卡 +
联动提示；**编辑档案**（`EmployeeProfileEditor.tsx`）为下拉；**员工卡**（`EmployeeCard.tsx`）显示层级标签；
**我的数字员工**页（`AgentsPage.tsx`）新增 **全部 / 协调层 / 执行层 / 在线 / 下线** 筛选 tab（照原型 `pg-agents`），
按 `metadata.org_level` 分流（缺省按岗位/名称 `inferOrgLevel` 推断）。

**前端页面清单（itc 二次开发）**：

| 页面 | 路由 | 位置 | FR |
|------|------|------|-----|
| 工作台首页 | `/enterprise/home` | 侧栏置顶 | FR-101~108 |
| 任务台 | `/enterprise/tasks` | 侧栏主导航 | FR-196 |
| 任务管理 | `/enterprise/task-management` | 侧栏主导航 | FR-197 |
| 输出物 | `/enterprise/outputs` | 侧栏主导航 | FR-211~216 |
| **数据源** | 并入**渠道接入**页的顶层 tab | 侧栏主导航 | FR-178~182 |
| 组织架构 | `/enterprise/org` | （URL 可达） | FR-148 |
| 共享记忆 | `/enterprise/shared-memory` | （URL 可达） | FR-201/202 |

> **管理后台已去掉**：`/admin` 还原为原生空壳页；侧栏「管理后台」项按原生规则
> （`FRAMEWORK_MANAGEMENT_INCLUDED=false`）自动隐藏。**数据源并入「渠道接入」**作为一个顶层 tab
> （渠道接入 / 数据源），不再单独占侧栏，也不再走管理后台。
>
> 侧栏最终结构：`工作台首页`（置顶）+ `PRIMARY_NAV`（开放广场平台 / 我的数字员工 / 我的团队 /
> **任务台 / 任务管理 / 输出物** / 渠道接入）+ `SYSTEM_NAV`（账号管理 / 模型配置 /
> 运行设置；管理后台按原生规则隐藏）。
>
> ⚠️ **孤立文件**（本轮去除管理后台后无入口，保留备用）：`CostDashboardPage.tsx`（成本/KPI 后端已就绪）、
>
> 新增页面统一照抄 `ModelsPage` 的「`AppHeader` + `StatCard` + `DataTable` + `Dialog` + `UnderlineTabs`」骨架，
> 复用 `useApi` / `DataTable` / `StatCard` / `UsageLineChart`，**不新造设计**。
> 后端未提供的端点一律**乐观空态**（「暂无数据…功能接入后在此展示」+ 独立「点击重试」），不整页崩溃。
> **FR-147**（平台模型「⚡获取列表」）为 `ModelsPage` 弹窗内**原生页扩展**，配套后端 `POST /api/enterprise/itc/models/list`。

**工作台首页（FR-101~108）**：路由 `/enterprise/home`（置顶 + 落地到 `/enterprise`）。
4 统计卡（`StatCard`）+ 快捷入口 + 我的数字员工（真实数据 `useApi(['/api/enterprise/agents'])`）
+ 动态/待办两栏。**FR-108 异常态**：平台无模型 / 无员工 / 空态 均优雅降级，
各卡片独立「加载失败，点击重试」。侧栏「工作台首页」置顶为 `primaryNavItems` 首项。

**品牌化**：`styles.css` 的 `--accent/--primary/--ring/--chart-1` → itc 蓝 `#1a71ff`；
`index.html` 标题、**官方 itc logo**（`src/assets/itc-logo.png`，替换掉纯文字「itc」）、登录页/引导页文案。
- **logo 来源**：`【其他】logo ITC-icon (2).png`（4666×3011，透明背景）；已裁边 → `src/assets/itc-logo.png`。
- **favicon**：`public/favicon.ico` / `favicon.png` / `itc-icon-192.png` / `itc-icon-512.png`（方形、居中、透明底），`apple-touch-icon` 指向 itc 图标。
- 装饰性 teal（头像 tone-teal / 文档青色）**保留**——那是色阶体系，非品牌标识。

**StaffDeck → 系统 品牌清理**（`StaffDeck`/`StaffDeck` → `系统`，全系统用户可见文案）：

| 范围 | 处理 |
|------|------|
| **前端文案**（9 文件） | `StaffDeck` → `系统`：UpdateReminder / MCPAppView / RuntimeSettingsPage / ToolsPage / TutorialPage / LoginPage 等；`en.json` 21 条（键→系统、英文值→System） |
| **后端文案**（~18 文件） | 沙盒错误、渠道绑定提示、UI 配置提示、健康接口 `app` 名、种子/prompt（`evolution`/`scheduled_tasks`）、开放 API 提示、MCP clientInfo、工具错误消息等 |
| **保留（功能性，不改）** | 目录名 `StaffDeck`（`paths.py`）、HTTP 头 `X-StaffDeck-*`、`STAFFDECK_*` 环境变量、PowerShell 函数名、GitHub 更新源 URL、代码标识符（`StaffdeckIcon`/`staffdeck_*`/`staffdeckDisplayText`）、英文 docstring |

> 验证：`/api/health` → `{"app":"系统"}`；前端构建通过；后端全部 `py_compile` 通过。

> ⚠️ **`styles.css` 有两个 `:root`**：块一（第 8 行）+ **块二（第 ~5168 行「SD1 visual alignment」）**。
> 块二在后、同优先级 → **覆盖块一**。品牌色必须改**块二**（或两处都改），否则不生效。
>
> 🗑️ **移除的 StaffDeck 素材**（位图，带 StaffDeck logo/teal，无法改色）：
> `login-preview.png`（登录页配图）、`onboarding-gallery.png` / `onboarding-profile.png`（引导页左半）。
> 对应地把登录页配图块、引导页左列图片块一并删除，`LoginPage.test.tsx` 的图片断言同步移除。

**路由配置化**：`App.tsx` 的 259 行 `<Routes>` 块 → 5 行 `buildAppRoutes(ctx).map(...)`。
新增页面只改 `src/routes/config.tsx`。**保留在 App.tsx** 的：distill 常驻块、空态块、
侧栏高亮链、`App()/AuthedApp()` 的 auth gate 与 workspace 重定向。

**验证（2026-11-23，真机）**：`npx tsc -b` ✅ · `npm run build` ✅(3.79s) ·
`npm run i18n:check` ✅(3967 条) · `npm run config:check` ✅

## 未决 / 待真机确认

见《基础层设计.md》附录「仍需真机确认的细节」（5 条）——如 `accept()` 返回字段名、
`client.ts` 是否导出 `request()`、`llm_call_finished` payload 精确键名等。

## 构建（Linux 目标）

```sh
node --version            # ≥22.19
python3 prepare.py        # 构建前端 + harness-engine + backend venv
# 或容器：docker compose up --build -d
```

## 本地起服务（Windows 开发，看真实界面）

```sh
# 1) 后端（需 harness-engine 产物 + python SDK）
#    引擎未源码构建时，可直接用官方安装包的预构建引擎：
#    tar xzf <StaffDeck-setup 旁>/harness-engine.tar.gz -C harness-engine-dist
cd backend
HARNESS_V3_ROOT="E:/AI work/itc-staffdeck/harness-engine-dist" \
  ./.venv-itc/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2) 前端（代理到 8000）
cd frontend-enterprise && npm run dev      # http://127.0.0.1:5173
```

**登录**：`admin` / `admin`（另有演示号 `demo` / `demo`）。

> ⚠️ **Windows tar 解压不会还原 pnpm 的 node_modules 符号链接**（需管理员权限），引擎会缺包。
> **修复（Windows 免管理员）**：用 **junction**（`fs.symlinkSync(target, link, 'junction')`，
> 不需管理员）把 hoisted 层的包链到各 workspace 的 `node_modules`：
> 逐包把 `node_modules/.pnpm/node_modules/<pkg>` 链到 `apps/*/node_modules/<pkg>` 与
> `packages/*/*/node_modules/<pkg>`（含 `@scope/*`）。
> 修复后引擎可运行：`node harness-engine-dist/apps/cli/lib/bin.js --version` → **`0.1.2-alpha.2`** ✅。

**日志**：dev 模式（`main.py` 直启）**不配控制台日志**（日志配置在 `launch.py`）。
需看应用日志（如 module discovery）时，用 `python -c "import logging; logging.basicConfig(level=logging.INFO, force=True); import uvicorn; uvicorn.run('app.main:app', port=8000)"`。

**Windows 侧进程模型**：uvicorn 在 Windows 上用 **spawn** 起 worker（另起一个 python 进程），故 `wmic` 会看到两个 `app.main` 进程——正常。
