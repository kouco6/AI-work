"""按需求《AI-001-情报小秘-档案卡》把情报小秘建出来（走 API）。

创建 + 绑定：
* 员工「情报小秘」（执行层 / 企划部）
* 3 个知识库：行业动态库 / 竞品信息库 / 公开招标信息库
* 4 个工具：网页抓取 / 文档生成 / 企微推送 / 行业资讯搜索
* 2 个 SOP：每日简报生成 / 竞品调研
* 1 个通用技能：情报摘要生成
* 全部资源绑给情报小秘

用法（后端在跑）: backend/.venv-itc/Scripts/python.exe tests_itc/seed_intel_agent.py
"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"
TENANT = "tenant_demo"


def call(method: str, path: str, body=None, token=None):
    url = f"{BASE}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def main() -> int:
    st, login = call("POST", "/api/auth/login", {"tenant_id": TENANT, "username": "admin", "password": "admin"})
    if st != 200:
        print("登录失败", st, login); return 1
    token = login["token"]
    q = f"?tenant_id={TENANT}"

    # 工具端点（mock / 本地）
    MOCK = "http://localhost:5173/api/mock"

    defs = {
        "kb": [
            ("行业动态库", "行业新闻 / 政策 / 市场动态采集库"),
            ("竞品信息库", "竞品动态 / 价格 / 产品信息库"),
            ("公开招标信息库", "公开招标与采购公告库"),
        ],
        "tools": [
            {"name": "intel.web_crawl", "display_name": "网页抓取", "description": "抓取公开网页正文（遵守 robots，标注来源）",
             "method": "POST", "url": f"{MOCK}/intel/web-crawl",
             "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
            {"name": "intel.doc_generate", "display_name": "文档生成", "description": "生成 PPT/Excel 简报文档",
             "method": "POST", "url": f"{MOCK}/intel/brief-generate",
             "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "items": {"type": "array"}}, "required": ["title"]}},
            {"name": "intel.push", "display_name": "企微/邮件推送", "description": "把简报推送到企微群 / 邮箱",
             "method": "POST", "url": f"{MOCK}/intel/push",
             "input_schema": {"type": "object", "properties": {"target": {"type": "string"}, "content": {"type": "string"}}, "required": ["target", "content"]}},
            {"name": "intel.news_search", "display_name": "行业资讯搜索", "description": "按关键词搜索行业资讯（外部搜索引擎）",
             "method": "POST", "url": f"{MOCK}/intel/news-search",
             "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        ],
    }

    created = {"kb": [], "tool": [], "sop": [], "general_skill": []}

    # 1) 知识库
    for name, desc in defs["kb"]:
        st, r = call("POST", f"/api/enterprise/knowledge-bases{q}", {"tenant_id": TENANT, "name": name, "description": desc, "capability_scope": "general"}, token)
        if st == 200 and isinstance(r, dict):
            created["kb"].append(r.get("id") or r.get("knowledge_base_id"))
            print(f"  KB {name} → {created['kb'][-1]}")
        else:
            print(f"  KB {name} 失败 {st} {r}")

    # 2) 工具
    for t in defs["tools"]:
        st, r = call("POST", f"/api/enterprise/tools{q}", {"tenant_id": TENANT, "tool_type": "http", "bucket": "情报工具", "capability_scope": "general", **t}, token)
        if st == 200 and isinstance(r, dict):
            created["tool"].append(r.get("id"))
            print(f"  工具 {t['display_name']} → {r.get('id')}")
        else:
            print(f"  工具 {t['name']} 失败 {st} {r}")

    # 3) SOP（简化：单节点 collect_info → response）
    def sop(skill_id, name, desc, domain):
        card = {
            "skill_id": skill_id, "name": name, "version": "1.0.0", "business_domain": domain,
            "description": desc, "capability_scope": "general",
            "trigger_intents": [name],
            "goal": [desc],
            "nodes": [
                {"node_id": "n1", "type": "collect_info", "name": "采集与筛选",
                 "instruction": "按标签采集行业/竞品/招标信息，筛选有效内容并标注来源链接。", "optional": True},
                {"node_id": "n2", "type": "response", "name": "生成并推送",
                 "instruction": "生成结构化简报（标注来源），按配置推送给指定对象。", "optional": False},
            ],
            "edges": [{"source_node_id": "n1", "next_node_id": "n2"}],
            "start_node_id": "n1", "terminal_node_ids": ["n2"],
        }
        return call("POST", f"/api/enterprise/skills{q}", {"tenant_id": TENANT, "content": card, "status": "published"}, token)

    for sid, name, desc in [
        ("daily_brief_generate", "每日简报生成", "每日采集行业动态并生成简报推送"),
        ("competitor_research", "竞品调研", "调研竞品动态并输出对比摘要"),
    ]:
        st, r = call("POST", f"/api/enterprise/skills{q}", None) if False else sop(sid, name, desc, "情报分析")
        if st == 200 and isinstance(r, dict):
            created["sop"].append(r.get("id") or r.get("skill_id"))
            print(f"  SOP {name} → {created['sop'][-1]}")
        else:
            print(f"  SOP {name} 失败 {st} {r}")

    # 4) 通用技能（情报摘要生成）
    st, r = call("POST", f"/api/enterprise/general-skills/import{q}", {
        "tenant_id": TENANT, "slug": "intel-summary", "name": "情报摘要生成",
        "description": "把采集到的新闻/竞品/招标信息压缩成结构化摘要，保留来源链接。",
        "markdown": "# 情报摘要生成\n\n## 用途\n把采集到的行业新闻、竞品动态、招标信息压缩成结构化摘要，保留来源链接。\n\n## 输出\n标题 / 摘要 / 标签 / 来源链接。",
        "status": "published", "capability_scope": "general",
    }, token)
    if st == 200 and isinstance(r, dict):
        created["general_skill"].append(r.get("id") or r.get("slug"))
        print(f"  通用技能 情报摘要生成 → {created['general_skill'][-1]}")
    else:
        print(f"  通用技能失败 {st} {r}")

    # 5) 建员工「情报小秘」（执行层）
    meta = {
        "role_name": "情报专员", "org_level": "executor", "avatar_text": "情", "avatar_tone": "knowledge",
        "avatar_kind": "preset", "avatar_preset": "knowledge",
        "expertise_tags": ["行业情报", "竞品跟踪", "招标信息", "简报生成"],
        "work_styles": ["严谨", "高效", "信息敏感", "言简意赅"],
        "system_prompt_summary": "企划部情报专员，每日收集行业动态、竞品信息、公开招标情报，生成简报推送。",
        "owner_username": "admin", "created_by": "admin",
    }
    st, agent = call("POST", f"/api/enterprise/agents{q}", {
        "tenant_id": TENANT, "name": "情报小秘", "source_mode": "blank",
        "description": "每日自动收集行业动态、竞品信息与公开招标情报，生成简报并推送。支持手动发起情报查询。",
        "persona_prompt": "你是企划部的情报小秘，情报分析岗。专业、简洁、不啰嗦，直接给结论和关键信息，重要内容标红。只回答情报相关问题，不处理审批报销等行政流程。",
        "metadata": meta, "harness_max_actions": 32,
    }, token)
    if st != 200 or not isinstance(agent, dict):
        print("建员工失败", st, agent); return 1
    aid = agent["id"]
    print(f"  ✅ 情报小秘 → {aid}")

    # 6) 绑定全部资源
    resources = (
        [{"resource_type": "knowledge_base", "resource_id": i} for i in created["kb"] if i]
        + [{"resource_type": "tool", "resource_id": i} for i in created["tool"] if i]
        + [{"resource_type": "skill", "resource_id": i} for i in created["sop"] if i]
        + [{"resource_type": "general_skill", "resource_id": i} for i in created["general_skill"] if i]
    )
    st, r = call("PUT", f"/api/enterprise/agents/{aid}/resources{q}", {"tenant_id": TENANT, "resources": resources}, token)
    print(f"  绑定 {len(resources)} 项资源 → HTTP {st}")
    return 0 if st == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
