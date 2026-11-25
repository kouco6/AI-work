"""itc 新增数据表模型（SQLModel）。

与《基础层设计.md》§三 schema 对齐。**由 Alembic 管理** migration（新表独立，
不改 StaffDeck 老迁移层）。

> 说明：这里用 SQLModel ``table=True``，导入即登记进 ``SQLModel.metadata``——
> 既能被 Alembic autogenerate 看到，也能被 ``create_all`` 建出（M1 过渡期两者皆可）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, JSON, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UsageRecord(SQLModel, table=True):
    """用量计量（FR-151/152）。D-13：usage 原样记录，缺失记 NULL，不归一化。"""

    __tablename__ = "itc_usage_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True, max_length=64)
    user_id: Optional[str] = Field(default=None, index=True, max_length=64)
    agent_id: Optional[str] = Field(default=None, index=True, max_length=64)
    session_id: Optional[str] = Field(default=None, index=True, max_length=64)
    model_name: Optional[str] = Field(default=None, max_length=128)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    source_type: Optional[str] = Field(default=None, max_length=32)  # 对话/定时/任务台/手动
    span_id: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))


class ModelPrice(SQLModel, table=True):
    """模型单价表（FR-152 成本归属配套）。

    每百万 token 的单价；按 model_name 匹配（可空 = 兜底默认价）。
    """

    __tablename__ = "itc_model_prices"

    model_name: str = Field(primary_key=True, max_length=128)
    currency: str = Field(default="CNY", max_length=8)
    input_per_million: float = Field(default=0.0)
    output_per_million: float = Field(default=0.0)
    cached_input_per_million: float = Field(default=0.0)


class AuditLog(SQLModel, table=True):
    """审计日志（FR-224，≥180 天）。"""

    __tablename__ = "itc_audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[str] = Field(default=None, index=True, max_length=64)
    actor: Optional[str] = Field(default=None, max_length=64)
    action: Optional[str] = Field(default=None, max_length=64)
    target: Optional[str] = Field(default=None, max_length=128)
    payload_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    ip: Optional[str] = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))


class DataSource(SQLModel, table=True):
    """数据源配置（FR-178）。需求标注为「完全新增」——原生无数据源/爬虫模块。

    配置爬取频率/规则/内容选择器，支持连通性测试（FR-178）。
    """

    __tablename__ = "itc_data_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True, max_length=64)
    name: str = Field(max_length=200)
    url: str = Field(sa_column=Column(Text))
    frequency: str = Field(default="每日", max_length=64)  # 爬取频率
    selector: str = Field(default="", max_length=512)       # 内容选择器
    tags: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # 标签规则（FR-179）
    enabled: bool = Field(default=True)
    status: str = Field(default="正常", max_length=32)      # 正常 / 异常
    last_run: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))


class CrawlLog(SQLModel, table=True):
    """爬取日志（FR-182）。时间 / 数据源 / 条数 / 成功 / 失败 / 失败原因。"""

    __tablename__ = "itc_crawl_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True, max_length=64)
    source_id: Optional[int] = Field(default=None, index=True)
    source_name: str = Field(default="", max_length=200)
    count: int = Field(default=0)
    ok: int = Field(default=0)
    failed: int = Field(default=0)
    reason: str = Field(default="", max_length=512)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))


class SharedMemory(SQLModel, table=True):
    """共享记忆层（FR-201 四层记忆的 L1 全局 / L2 岗位）。

    与原生 ``memories`` 表**完全独立**（原生表一行不改）。scope 决定作用域：
    * ``global`` —— L1：全员共享，仅管理员可写
    * ``role``   —— L2：岗位/员工共享，``owner`` = 岗位 key 或 agent_id

    ``key`` 用于去重（同 scope+owner+key 覆盖），对齐原生记忆的 keyed upsert 语义。
    """

    __tablename__ = "itc_shared_memories"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True, max_length=64)
    scope: str = Field(index=True, max_length=16)          # global | role
    owner: Optional[str] = Field(default=None, index=True, max_length=128)  # L2=岗位key/agent_id；L1=None
    kind: str = Field(default="fact", max_length=32)
    key: Optional[str] = Field(default=None, max_length=128)
    content: str = Field(sa_column=Column(Text))
    importance: float = Field(default=0.5)
    metadata_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))


class Role(SQLModel, table=True):
    """角色（FR-232/266）。"""

    __tablename__ = "itc_roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, max_length=64)
    name: str = Field(max_length=64)


class Permission(SQLModel, table=True):
    __tablename__ = "itc_permissions"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, max_length=128)
    name: str = Field(max_length=64)


class RoleBinding(SQLModel, table=True):
    """用户 → 角色 → 作用域 绑定（支持部门级）。"""

    __tablename__ = "itc_role_bindings"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True, max_length=64)
    role_id: int = Field(foreign_key="itc_roles.id")
    scope_type: Optional[str] = Field(default=None, max_length=16)  # global/dept
    scope_id: Optional[str] = Field(default=None, max_length=64)


class ItcTask(SQLModel, table=True):
    """任务台任务池（FR-196 / FR-197）。

    人只写目标并发布；系统按**复杂度**路由：
      * ``coordinated``（协调型，需多岗位）→ 从**军师池择优**（D-17 加权）分配给一位军师
      * ``execution``（执行型，单一岗位）→ 进入执行层**自主认领**

    状态机：``pending``（待分配/待认领）→ ``assigned``（已分配）→ ``running`` → ``done`` / ``failed`` / ``cancelled``。
    ``assign_detail`` 存 D-17 三项分项得分，供界面「为什么是这位军师」核对与改派。
    """

    __tablename__ = "itc_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True, max_length=64)
    title: str = Field(max_length=500)
    description: str = Field(default="", sa_column=Column(Text))
    kind: str = Field(default="execution", max_length=16)  # coordinated | execution
    status: str = Field(default="pending", index=True, max_length=16)
    assignee_agent_id: Optional[str] = Field(default=None, index=True, max_length=64)
    assign_detail: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_by: Optional[str] = Field(default=None, max_length=64)
    source: str = Field(default="任务台", max_length=32)  # 任务台 | 手动 | …
    session_id: Optional[str] = Field(default=None, max_length=64)
    token_used: int = Field(default=0)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True)))
