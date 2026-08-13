"""End-to-end test: create simulation, verify sales data integration in report."""
import json, time, urllib.request, urllib.error

BASE = "http://8.145.61.207"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if _token:
        req.add_header("Authorization", f"Bearer {_token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read()[:200]}")
        raise

_token = None

# Login
resp = api("POST", "/api/auth/login", {"username": "123@test", "password": "123456"})
_token = resp["data"]["access_token"]
print(f"Login OK (plan={resp['data']['user']['plan_type']})")

# 1. Create project
resp = api("POST", "/api/simulations", {"project_name": "[TEST] iPad Air - sales data verify"})
pid = resp["data"]["id"]
dv = resp["data"]["draft_version"]
print(f"Created #{pid}")

# 2. Step1: Apple iPad Air in 3C电子
resp = api("PUT", f"/api/simulations/{pid}/step1", {
    "draft_version": dv,
    "product_definition": {
        "product_name": "Apple iPad Air", "brand": "Apple",
        "category": "3C电子", "subcategory": "平板电脑", "price_cny": 4399,
        "params": [
            {"name": "屏幕尺寸", "value": "10.9英寸", "weight": 5, "enabled": True},
            {"name": "芯片", "value": "M2", "weight": 5, "enabled": True},
            {"name": "存储", "value": "256GB", "weight": 4, "enabled": True},
        ],
    },
})
dv = resp["data"]["draft_version"]
print(f"Step1 OK v{dv}")

# 3. Step2: market config
resp = api("PUT", f"/api/simulations/{pid}/step2", {
    "draft_version": dv,
    "market_config": {
        "crowd_segments": [
            {"name": "学生", "age_min": 18, "age_max": 25, "ratio": 35},
            {"name": "白领", "age_min": 26, "age_max": 40, "ratio": 45},
            {"name": "轻度用户", "age_min": 41, "age_max": 60, "ratio": 20},
        ],
        "competitors": [
            {"product_name": "小米 Xiaomi Book Air", "brand": "小米", "price_cny": 5299},
            {"product_name": "华为 MateBook X Pro", "brand": "华为", "price_cny": 8999},
        ],
        "strategies": [{"name": "线上标准策略", "intensity": 55}],
    },
})
dv = resp["data"]["draft_version"]
print(f"Step2 OK v{dv}")

# 4. Submit
resp = api("POST", f"/api/simulations/{pid}/submit", {"draft_version": dv})
print(f"Submitted.")

# 4b. Run (push to Redis queue)
resp = api("POST", f"/api/simulations/{pid}/run", {})
print(f"Queued. Polling...", end="", flush=True)

# 5. Poll for completion
for i in range(180):
    time.sleep(5)
    resp = api("GET", f"/api/simulations/{pid}")
    st = resp["data"]["status"]
    c = "." if st in ("queued", "running") else f"[{st}]"
    print(c, end="", flush=True)
    if st in ("completed", "failed", "cancelled"):
        print()
        break
else:
    print(" TIMEOUT")
    exit(1)

if st in ("failed", "cancelled"):
    print(f"Ended: {st} - {resp['data'].get('error_reason', '?')}")
    exit(1)

# 6. Get report
resp = api("GET", f"/api/simulations/{pid}/report")
rd = resp["data"]
rep = rd.get("report", rd)
cd = rep.get("chart_data", {})
ms = cd.get("market_share", [])
cat = cd.get("product_definition", rep.get("product_definition", {}))

print(f"\n=== {cat.get('product_name', '?')} ({cat.get('category', '?')}) ===")
print(f"Purchase Intent: {rep.get('metrics', {}).get('purchase_intent_avg', '?')}")

print("\nMarket Share:")
for row in ms[:6]:
    share = row.get("share") or row.get("value") or 0
    print(f"  {row.get('name', '?')[:30]:<35} {share:>5.1f}%  [{row.get('source', '?')}]")

radar = cd.get("competitor_radar", {})
print("\nRadar Brand Scores:")
for s in radar.get("series", [])[:5]:
    v = s.get("values", [])
    print(f"  {s.get('name', '?')[:25]:<30} brand_score={v[2] if len(v) > 2 else '?'}")

print(f"\nProject #{pid} - test complete")
