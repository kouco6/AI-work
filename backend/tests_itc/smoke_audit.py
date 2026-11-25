"""itc 审计留存 · 真机自测（独立 SQLite）。

运行::

    backend/.venv-itc/Scripts/python.exe backend/tests_itc/smoke_audit.py

验证：
1. ``write_audit`` 入队 → ``flush_now`` 落库到 ``itc_audit_logs``；
2. **脱敏**：payload 里的 api_key/token 等被替换为 [redacted]；
3. **留存**：``purge_old(180)`` 删掉 200 天前的旧记录，保留近期记录。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(BACKEND / "src")]

from sqlmodel import Session, create_engine, select  # noqa: E402

from itc_platform.models import AuditLog  # noqa: E402


def main() -> int:
    engine = create_engine("sqlite://")

    import itc_platform.db as db
    import itc_platform.audit.store as audit

    db.get_engine = lambda: engine  # type: ignore[assignment]
    audit.get_engine = lambda: engine  # type: ignore[assignment]

    # 1) 入队 + 脱敏 + 落库
    audit.write_audit(
        tenant_id="tenant_demo",
        session_id="s1",
        event_type="llm_call_started",
        payload={"model": "qwen", "api_key": "sk-secret-xxx", "token": "abc", "prompt_len": 42},
    )
    written = audit.flush_now()
    print(f"1) flush 落库 {written} 行")
    assert written == 1, f"预期 1 行，实际 {written}"

    with Session(engine) as s:
        row = s.exec(select(AuditLog)).one()
    print("2) 脱敏后 payload:", row.payload_json)
    assert row.payload_json["api_key"] == "[redacted]", "api_key 未脱敏"
    assert row.payload_json["token"] == "[redacted]", "token 未脱敏"
    assert row.payload_json["model"] == "qwen" and row.payload_json["prompt_len"] == 42
    assert row.action == "llm_call_started" and row.tenant_id == "tenant_demo"

    # 3) 留存：塞一条 200 天前的旧记录 + 一条今天的
    old = AuditLog(
        tenant_id="tenant_demo", action="old_event",
        created_at=datetime.now(timezone.utc) - timedelta(days=200),
    )
    recent = AuditLog(
        tenant_id="tenant_demo", action="recent_event",
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    with Session(engine) as s:
        s.add(old); s.add(recent); s.commit()
        before = len(s.exec(select(AuditLog)).all())
    removed = audit.purge_old(180, engine=engine)
    with Session(engine) as s:
        after_ids = {r.action for r in s.exec(select(AuditLog)).all()}
    print(f"3) 清理前 {before} 行；purge_old(180) 删除 {removed} 行；剩余动作={sorted(after_ids)}")
    assert removed == 1, f"预期删 1 条旧记录，实际 {removed}"
    assert "old_event" not in after_ids, "旧记录未被清理"
    assert "recent_event" in after_ids and "llm_call_started" in after_ids, "近期记录被误删"

    print("\n✅ 审计通过：落库 / 脱敏 / 180 天留存清理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
