import json, urllib.request, urllib.error
BASE="http://127.0.0.1:8000"; T="tenant_demo"; AID="agent_1cd6836854694c2b"
def call(m,p,b=None,tok=None):
    r=urllib.request.Request(f"{BASE}{p}",data=json.dumps(b,ensure_ascii=False).encode() if b is not None else None,method=m)
    r.add_header("Content-Type","application/json; charset=utf-8")
    if tok: r.add_header("Authorization",f"Bearer {tok}")
    try:
        with urllib.request.urlopen(r,timeout=30) as x: return x.status, json.loads(x.read().decode())
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8","replace")[:300]
_,l=call("POST","/api/auth/login",{"tenant_id":T,"username":"admin","password":"admin"}); tok=l["token"]
st,r=call("POST",f"/api/enterprise/scheduled-tasks?tenant_id={T}",{
  "tenant_id":T,"agent_id":AID,"title":"每日行业简报",
  "prompt":"采集今日行业新闻、竞品动态与公开招标信息，筛选有效内容，生成《行业动态日报》并推送到企划部群。标注来源链接，无关内容不推。",
  "schedule_type":"daily","schedule":{"time":"08:00","weekdays":[1,2,3,4,5]},"timezone":"Asia/Shanghai",
  "status":"active","description":"工作日早8点自动生成并推送行业动态日报"},tok)
print("定时任务:",st, r.get("id") if isinstance(r,dict) else r)
