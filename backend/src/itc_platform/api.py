"""itc 成本 / KPI / 记忆 / 任务 / 数据源 API（FR-145/151/152/153/154/155/156）。

挂载：``app/main.py`` 中 ``app.include_router(itc_platform...)`` 一行。
鉴权：复用 StaffDeck 的 ``require_current_tenant``（JWT），与既有企业路由一致。
数据：读 ``itc_usage_records``（由 observer 落库）。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.db.models import User
from app.security.auth import require_current_tenant

from itc_platform.cost import service as cost_service
from itc_platform.db import itc_tables
from itc_platform.kpi import service as kpi_service
from itc_platform.models import ModelPrice

router = APIRouter(prefix="/api/enterprise/itc", tags=["enterprise:itc"])


def _ensure_itc_schema() -> None:
    """兜底建 itc 表（幂等；正常由 init_db 的 create_all 完成）。"""
    try:
        from sqlmodel import SQLModel

        from app.db import engine
        from itc_platform import models as _models  # noqa: F401  确保模型已登记

        SQLModel.metadata.create_all(engine, tables=itc_tables())
    except Exception:
        # 建表失败不应阻断只读查询（表已存在时亦会进入此分支）
        pass


@router.get("/cost/summary")
def cost_summary(
    tenant_id: str = Query(...),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """成本总览（FR-151/152/154）。"""
    _ensure_itc_schema()
    return cost_service.summary(
        cost_service._parse_dt(since), cost_service._parse_dt(until)
    )


@router.get("/cost/by-model")
def cost_by_model(
    tenant_id: str = Query(...),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """按模型维度（FR-145 模型使用统计）。"""
    _ensure_itc_schema()
    return cost_service.by_model(cost_service._parse_dt(since), cost_service._parse_dt(until))


@router.get("/cost/by-agent")
def cost_by_agent(
    tenant_id: str = Query(...),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """按 AI 员工维度（FR-152 用量归属）。"""
    _ensure_itc_schema()
    return cost_service.by_agent(cost_service._parse_dt(since), cost_service._parse_dt(until))


@router.get("/cost/by-user")
def cost_by_user(
    tenant_id: str = Query(...),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """按用户维度（FR-154 用量排行）。"""
    _ensure_itc_schema()
    return cost_service.by_user(cost_service._parse_dt(since), cost_service._parse_dt(until))


@router.get("/cost/by-day")
def cost_by_day(
    tenant_id: str = Query(...),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """按天聚合（时间序列，供折线图）。"""
    _ensure_itc_schema()
    return cost_service.by_day(cost_service._parse_dt(since), cost_service._parse_dt(until))


@router.get("/kpi/agents")
def kpi_agents(
    tenant_id: str = Query(...),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """AI 员工 KPI（FR-153，含未计量占比）。"""
    _ensure_itc_schema()
    return kpi_service.agent_kpi(cost_service._parse_dt(since), cost_service._parse_dt(until))


@router.get("/model-prices")
def list_model_prices(
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
    db: Session = Depends(get_session),
) -> list[dict]:
    """模型单价表（成本计算依据）。"""
    _ensure_itc_schema()
    from itc_platform.db import get_engine

    with Session(get_engine()) as session:
        rows = session.exec(select(ModelPrice)).all()
    return [
        {
            "model_name": r.model_name,
            "currency": r.currency,
            "input_per_million": r.input_per_million,
            "output_per_million": r.output_per_million,
            "cached_input_per_million": r.cached_input_per_million,
        }
        for r in rows
    ]


# ── 模型「一键获取列表」（FR-147）────────────────────────────

@router.post("/models/list")
def fetch_model_list(
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """用 Base URL + API Key 调 ``GET {base_url}/models`` 拉取可用模型清单（FR-147）。

    兼容 OpenAI 风格 ``{"data":[{"id":...}]}`` 与 ``{"models":[...]}`` 两种返回结构。
    原生模型配置仅有连通性测试、**不拉取清单**（源码核实），故本端点为新增。
    """
    from fastapi import HTTPException
    import httpx

    base_url = str(body.get("base_url") or "").strip().rstrip("/")
    api_key = str(body.get("api_key") or "").strip()
    if not base_url:
        raise HTTPException(status_code=400, detail="缺少 Base URL")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    url = f"{base_url}/models"
    try:
        resp = httpx.get(url, headers=headers, timeout=15.0)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"拉取模型列表失败：{exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="模型服务返回的不是合法 JSON") from exc

    models: list[str] = []
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            models = [str(item.get("id")) for item in data if isinstance(item, dict) and item.get("id")]
        elif isinstance(payload.get("models"), list):
            models = [str(m) for m in payload["models"]]
    return {"models": models}


# ── 任务台（FR-196 / FR-197）─────────────────────────────────

@router.post("/tasks")
def publish_task(
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """发布任务并按复杂度自动分配（D-16）。协调型→军师池择优；执行型→待执行层认领。"""
    from itc_platform.tasks import service as tasks

    return tasks.publish_task(
        tenant_id=tenant_id,
        title=str(body.get("title") or "").strip(),
        description=str(body.get("description") or ""),
        created_by=current_user.id,
        source=str(body.get("source") or "任务台"),
    )


@router.get("/tasks")
def list_tasks(
    tenant_id: str = Query(...),
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """统一任务列表（FR-197）。"""
    from itc_platform.tasks import service as tasks

    return tasks.list_tasks(tenant_id, status=status)


@router.get("/tasks/strategist-pool")
def strategist_pool(
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """军师池 + 各军师负载（任务台展示 D-17 择优依据）。"""
    from itc_platform.tasks import service as tasks

    return tasks.strategist_pool(tenant_id)


@router.post("/tasks/{task_id}/claim")
def claim_task(
    task_id: int,
    tenant_id: str = Query(...),
    agent_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """执行层自主认领（FR-196）。"""
    from itc_platform.tasks import service as tasks

    return {"claimed": tasks.claim_task(tenant_id=tenant_id, task_id=task_id, agent_id=agent_id)}


@router.post("/tasks/{task_id}/assign")
def assign_task(
    task_id: int,
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """人工指定/改派员工（D-16 人干预权）。"""
    from itc_platform.tasks import service as tasks

    return {
        "updated": tasks.assign_task(
            tenant_id=tenant_id, task_id=task_id,
            agent_id=str(body.get("agent_id") or ""), by=current_user.username,
        )
    }


@router.post("/tasks/{task_id}/recall")
def recall_task(
    task_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """收回任务（回到待分配）。"""
    from itc_platform.tasks import service as tasks

    return {"updated": tasks.recall_task(tenant_id=tenant_id, task_id=task_id)}


@router.post("/tasks/{task_id}/status")
def update_task_status(
    task_id: int,
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """更新任务状态（running/done/failed/cancelled）。"""
    from itc_platform.tasks import service as tasks

    return {
        "updated": tasks.update_status(
            tenant_id=tenant_id, task_id=task_id, status=str(body.get("status") or "")
        )
    }


@router.post("/tasks/{task_id}/execute")
def execute_task(
    task_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """触发任务执行：让承接员工真跑一轮（FR-196 派活→执行）。"""
    from itc_platform.tasks import service as tasks

    return tasks.execute_task(tenant_id=tenant_id, task_id=task_id)


@router.post("/tasks/{task_id}/escalate")
def escalate_task(
    task_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """军师异常处置（FR-194 / D-08）：手动/自动触发——改派重跑或转人工接管。"""
    from itc_platform.tasks import service as tasks

    return {"escalated": tasks.escalate_to_strategist(tenant_id=tenant_id, task_id=task_id)}


# ── 部门管理（FR-232/266）────────────────────────────────────

@router.get("/depts/user-map")
def dept_user_map(
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """用户 id → 部门名 映射（供人员列表展示部门列）。"""
    _ensure_itc_schema()
    from itc_platform.depts import service as depts

    return depts.user_dept_map(tenant_id)


@router.post("/depts/assign-user")
def assign_user_dept(
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """把某用户归到某部门（仅管理员）。"""
    _require_admin(current_user)
    _ensure_itc_schema()
    from itc_platform.depts import service as depts

    return {"ok": depts.set_user_dept(
        tenant_id, str(body.get("user_id") or ""),
        int(body["dept_id"]) if body.get("dept_id") is not None else None,
    )}


@router.get("/depts")
def list_depts(
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """部门列表（含成员数与成员 id）。"""
    _ensure_itc_schema()
    from itc_platform.depts import service as depts

    return depts.list_depts(tenant_id)


@router.post("/depts")
def create_dept(
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """新增部门（仅管理员）。"""
    _require_admin(current_user)
    _ensure_itc_schema()
    from itc_platform.depts import service as depts

    return {"id": depts.create_dept(
        tenant_id=tenant_id, name=str(body.get("name") or "").strip(),
        parent_id=body.get("parent_id"), leader_user_id=body.get("leader_user_id"),
    )}


@router.put("/depts/{dept_id}/members")
def set_dept_members(
    dept_id: int,
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """设置部门成员（仅管理员或该部门负责人）。"""
    from app.security.permissions import is_admin_user

    from itc_platform.depts import service as depts

    if not is_admin_user(current_user) and not depts.is_dept_leader(tenant_id, dept_id, current_user.id):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="仅管理员或部门负责人可维护成员")
    _ensure_itc_schema()
    ids = body.get("user_ids") if isinstance(body.get("user_ids"), list) else []
    return {"count": depts.set_members(tenant_id=tenant_id, dept_id=dept_id, user_ids=ids)}


@router.get("/depts/{dept_id}/stats")
def dept_stats(
    dept_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """部门统计（成员数 + 用量/成本）。"""
    _ensure_itc_schema()
    from itc_platform.depts import service as depts

    return depts.dept_stats(tenant_id, dept_id)


@router.delete("/depts/{dept_id}")
def delete_dept(
    dept_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """删除部门（仅管理员）。"""
    _require_admin(current_user)
    _ensure_itc_schema()
    from itc_platform.depts import service as depts

    return {"deleted": depts.delete_dept(tenant_id=tenant_id, dept_id=dept_id)}


# ── 产出物管理（FR-211~216，D-10 存平台 + 平台 RBAC）────────────

@router.get("/outputs")
def list_outputs(
    tenant_id: str = Query(...),
    view: str = Query("mine"),
    agent_id: Optional[str] = Query(None),
    q: str = Query(""),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """列出产出物（视图 + RBAC 过滤）。"""
    from app.security.permissions import is_admin_user

    from itc_platform.artifacts import service as arts

    return arts.list_artifacts(
        tenant_id, user_id=current_user.id, is_admin=is_admin_user(current_user),
        view=view, agent_id=agent_id, query=q,
    )


@router.post("/outputs")
def register_output(
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """登记一份产出物（产出 AI 写回，或手动补录）。"""
    from itc_platform.artifacts import service as arts

    aid = arts.register_artifact(
        tenant_id=tenant_id,
        name=str(body.get("name") or "").strip(),
        produced_by=current_user.id,
        file_type=str(body.get("file_type") or ""),
        agent_id=body.get("agent_id"),
        agent_name=str(body.get("agent_name") or ""),
        source=str(body.get("source") or "对话"),
        task_id=body.get("task_id"),
        session_id=body.get("session_id"),
        size=int(body.get("size") or 0),
        storage_path=str(body.get("storage_path") or ""),
        source_url=str(body.get("source_url") or ""),
        parent_id=body.get("parent_id"),
    )
    return {"id": aid}


@router.post("/outputs/{artifact_id}/share")
def share_output(
    artifact_id: int,
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """改分享范围（FR-212）。"""
    from itc_platform.artifacts import service as arts

    return {"updated": arts.share_artifact(
        tenant_id=tenant_id, artifact_id=artifact_id,
        visibility=str(body.get("visibility") or "private"),
        shared_with=body.get("shared_with") if isinstance(body.get("shared_with"), list) else None,
    )}


@router.post("/outputs/{artifact_id}/archive")
def archive_output(
    artifact_id: int,
    body: dict = Body(default={}),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """归档 / 取消归档（FR-215）。"""
    from itc_platform.artifacts import service as arts

    return {"updated": arts.archive_artifact(
        tenant_id=tenant_id, artifact_id=artifact_id, archived=bool(body.get("archived", True)),
    )}


@router.delete("/outputs/{artifact_id}")
def delete_output(
    artifact_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """删除产出物记录。"""
    from itc_platform.artifacts import service as arts

    return {"deleted": arts.delete_artifact(tenant_id=tenant_id, artifact_id=artifact_id)}


# ── 数据源管理（FR-178~182）──────────────────────────────────

def _require_admin(current_user: User) -> None:
    from app.security.permissions import is_admin_user

    if not is_admin_user(current_user):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="仅管理员可维护数据源")


@router.get("/data-sources")
def list_data_sources(
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """列出数据源（FR-178）。"""
    _ensure_itc_schema()
    from itc_platform.datasource import store as ds

    return ds.list_sources(tenant_id)


@router.post("/data-sources")
def create_data_source(
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """新增数据源（仅管理员，FR-178）。"""
    _require_admin(current_user)
    _ensure_itc_schema()
    from itc_platform.datasource import store as ds

    sid = ds.create_source(
        tenant_id=tenant_id,
        name=str(body.get("name") or "").strip(),
        url=str(body.get("url") or "").strip(),
        frequency=str(body.get("frequency") or "每日"),
        selector=str(body.get("selector") or ""),
        tags=body.get("tags") if isinstance(body.get("tags"), dict) else None,
    )
    return {"id": sid}


@router.put("/data-sources/{source_id}")
def update_data_source(
    source_id: int,
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """编辑数据源（仅管理员）。"""
    _require_admin(current_user)
    _ensure_itc_schema()
    from itc_platform.datasource import store as ds

    return {"updated": ds.update_source(tenant_id=tenant_id, source_id=source_id, patch=body)}


@router.delete("/data-sources/{source_id}")
def delete_data_source(
    source_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """删除数据源（仅管理员）。"""
    _require_admin(current_user)
    _ensure_itc_schema()
    from itc_platform.datasource import store as ds

    return {"deleted": ds.delete_source(tenant_id=tenant_id, source_id=source_id)}


@router.get("/crawl-logs")
def list_crawl_logs(
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """爬取日志（FR-182）。"""
    _ensure_itc_schema()
    from itc_platform.datasource import store as ds

    return ds.list_logs(tenant_id)


# ── 共享记忆 L1/L2（FR-201/202）──────────────────────────────

@router.get("/memory/shared")
def list_shared_memories(
    tenant_id: str = Query(...),
    agent_id: Optional[str] = Query(None),
    current_user: User = Depends(require_current_tenant),
) -> list[dict]:
    """列出适用的共享记忆（L2 岗位 + L1 全局）。"""
    _ensure_itc_schema()
    from itc_platform.memory import store as mem

    return mem.list_shared(tenant_id=tenant_id, agent_id=agent_id)


@router.post("/memory/shared")
def upsert_shared_memory(
    body: dict = Body(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """新增/更新共享记忆（FR-202：仅管理员写 L1/L2）。"""
    from app.security.permissions import is_admin_user

    if not is_admin_user(current_user):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="仅管理员可维护共享记忆")
    _ensure_itc_schema()
    from itc_platform.memory import store as mem

    mid = mem.upsert_shared(
        tenant_id=tenant_id,
        scope=str(body.get("scope") or mem.SCOPE_GLOBAL),
        owner=body.get("owner"),
        kind=str(body.get("kind") or "fact"),
        key=body.get("key"),
        content=str(body.get("content") or ""),
        importance=float(body.get("importance") or 0.5),
        metadata=body.get("metadata"),
    )
    return {"id": mid}


@router.delete("/memory/shared/{memory_id}")
def delete_shared_memory(
    memory_id: int,
    tenant_id: str = Query(...),
    current_user: User = Depends(require_current_tenant),
) -> dict:
    """删除共享记忆（仅管理员）。"""
    from app.security.permissions import is_admin_user

    if not is_admin_user(current_user):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="仅管理员可维护共享记忆")
    _ensure_itc_schema()
    from itc_platform.memory import store as mem

    return {"deleted": mem.delete_shared(tenant_id=tenant_id, memory_id=memory_id)}
