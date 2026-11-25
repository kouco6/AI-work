"""补建情报小秘的 2 个 SOP，并把全部资源重绑到情报小秘。"""
from __future__ import annotations
import json, urllib.request

BASE = "http://127.0.0.1:8000"; TENANT = "tenant_demo"
AID = "agent_1cd6836854694c2b"
KB = ["kb_52e73178442b4dc3", "kb_50bc6c18451441b1", "kb_916ace4c0e934aec"]
TOOLS = ["tool_39f1854ce0b34cfe", "tool_8f7a7294f7444f71", "tool_329e04c8e53346ce", "tool_f38f20bd28634ca6"]
GSKILL = ["genskill_4412c9ae07ee43a1"]


def call(method, path, body=None, token=None):
    req = urllib.request.Request(f"{BASE}{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token: req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]


_, login = call("POST", "/api/auth/login", {"tenant_id": TENANT, "username": "admin", "password": "admin"})
token = login["token"]; q = f"?tenant_id={TENANT}"


def sop(skill_id, name, desc):
    card = {"skill_id": skill_id, "name": name, "version": "1.0.0", "business_domain": "情报分析",
            "description": desc, "capability_scope": "general", "trigger_intents": [name], "goal": [desc],
            "nodes": [
                {"node_id": "n1", "type": "collect_info", "name": "采集与筛选",
                 "instruction": "按标签采集行业/竞品/招标信息，筛选有效内容并标注来源链接。", "optional": True},
                {"node_id": "n2", "type": "response", "name": "生成并推送",
                 "instruction": "生成结构化简报（标注来源），按配置推送给指定对象。", "optional": False}],
            "edges": [{"source_node_id": "n1", "next_node_id": "n2"}],
            "start_node_id": "n1", "terminal_node_ids": ["n2"]}
    return call("POST", f"/api/enterprise/skills{q}", {"tenant_id": TENANT, "content": card, "status": "published"}, token)


sops = []
for sid, name, desc in [("daily_brief_generate", "每日简报生成", "每日采集行业动态并生成简报推送"),
                        ("competitor_research", "竞品调研", "调研竞品动态并输出对比摘要")]:
    st, r = sop(sid, name, desc)
    if st == 200 and isinstance(r, dict):
        sops.append(r.get("id") or r.get("skill_id")); print(f"  SOP {name} → {sops[-1]}")
    else:
        print(f"  SOP {name} 失败 {st} {r}")

resources = (
    [{"resource_type": "knowledge_base", "resource_id": i} for i in KB]
    + [{"resource_type": "tool", "resource_id": i} for i in TOOLS]
    + [{"resource_type": "skill", "resource_id": i} for i in sops]
    + [{"resource_type": "general_skill", "resource_id": i} for i in GSKILL]
)
st, r = call("PUT", f"/api/enterprise/agents/{AID}/resources{q}", {"tenant_id": TENANT, "resources": resources}, token)
print(f"  重绑 {len(resources)} 项 → HTTP {st}")
