"""GA4에서 방문 현황 숫자를 받아 _site/stats.json으로 저장합니다(관리자 페이지 eduplan.kr/stats, 강남 · 대치 두 사이트).

GitHub Actions(deploy.yml)가 1시간마다 실행해 GitHub Pages로 배포합니다(커밋 없음). 11/18 eduplan-site에서 이 저장소로 옮김.
학종파이터 stats와 같은 방식(11/17 사용자): 숫자는 STATS_PASSWORD로 암호화해서만 저장하고, 페이지에서 비밀번호로 풉니다.
비밀값이 없으면 '연결 전'(not_connected) · '비밀번호 없음'(no_password) 상태만 남깁니다.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# 사이트 목록(11/17 사용자: 강남 · 대치를 한 페이지에서). 속성 ID는 숫자(GA 관리 › 속성 세부정보). 비밀값이 아님
SITES = [
    ("gangnam", "강남에듀플랜", "eduplan.kr", os.environ.get("GA_PROPERTY_ID", "").strip()),
    ("daechi", "대치마스터교육", "gongboomaster.com", os.environ.get("GA_PROPERTY_ID_DAECHI", "").strip()),
]
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "_site", "stats.json")
KST = timezone(timedelta(hours=9))
# 숫자에서 뺄 국가(ISO 국가 코드). 중국발 봇 · 스팸 접속 제외(사용자 11/17). GA4 자체 보고서에는 그대로 남음
EXCLUDE_COUNTRIES = ["CN"]


def _old_status():
    try:
        return json.load(open(OUT, encoding="utf-8")).get("status")
    except Exception:
        return None


def write(payload):
    """숫자가 담긴 결과는 STATS_PASSWORD로 암호화해서만 저장. 숫자 없는 상태는 이전과 같으면 다시 쓰지 않음(쓸데없는 커밋 · 배포 방지)."""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if payload.get("status") == "ok":
        pw = os.environ.get("STATS_PASSWORD", "")
        if not pw:
            payload = {"status": "no_password", "updated_at": payload.get("updated_at")}
        else:
            import base64
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            it = 250000
            salt, iv = os.urandom(16), os.urandom(12)
            key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=it).derive(pw.encode("utf-8"))
            ct = AESGCM(key).encrypt(iv, json.dumps(payload, ensure_ascii=False).encode("utf-8"), None)
            b64 = lambda b: base64.b64encode(b).decode("ascii")
            payload = {"status": "locked", "enc": "aes-256-gcm/pbkdf2-sha256", "iter": it,
                       "salt": b64(salt), "iv": b64(iv), "ct": b64(ct),
                       "updated_at": payload.get("updated_at")}
    if payload["status"] != "locked" and payload["status"] == _old_status() and payload["status"] != "error":
        print("상태가 그대로라 stats.json을 다시 쓰지 않습니다:", payload["status"])
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")


def fetch_site(client, pid):
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Filter, FilterExpression, FilterExpressionList, Metric, OrderBy, RunReportRequest,
    )
    prop = f"properties/{pid}"
    cur = DateRange(start_date="27daysAgo", end_date="today", name="cur")
    prev = DateRange(start_date="55daysAgo", end_date="28daysAgo", name="prev")

    def run(dims, mets, ranges=(cur,), order=None, limit=50, path_prefix=None):
        req = RunReportRequest(
            property=prop,
            dimensions=[Dimension(name=d) for d in dims],
            metrics=[Metric(name=m) for m in mets],
            date_ranges=list(ranges),
            limit=limit,
        )
        if order:
            req.order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order), desc=True)]
        # 제외할 국가(11/17 사용자: 중국 접속은 기록 제외). 모든 숫자에 같이 적용
        conds = [FilterExpression(not_expression=FilterExpression(filter=Filter(
            field_name="countryId", in_list_filter=Filter.InListFilter(values=EXCLUDE_COUNTRIES))))]
        if path_prefix:
            conds.append(FilterExpression(filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(match_type=Filter.StringFilter.MatchType.BEGINS_WITH, value=path_prefix))))
        req.dimension_filter = FilterExpression(and_group=FilterExpressionList(expressions=conds))
        res = client.run_report(req)
        dh = [h.name for h in res.dimension_headers]
        mh = [h.name for h in res.metric_headers]
        rows = []
        for r in res.rows:
            row = {dh[i]: v.value for i, v in enumerate(r.dimension_values)}
            for i, v in enumerate(r.metric_values):
                row[mh[i]] = float(v.value) if v.value not in ("", None) else 0.0
            rows.append(row)
        return rows

    def by_range(rows):
        out = {"cur": {}, "prev": {}}
        for r in rows:
            out[r.pop("dateRange", "cur")] = r
        return out

    total_mets = ["activeUsers", "newUsers", "sessions", "screenPageViews",
                  "engagementRate", "averageSessionDuration"]
    # 날짜 범위가 둘이면 GA4가 dateRange 열을 자동으로 붙여 줌
    totals = by_range(run([], total_mets, ranges=(cur, prev)))
    # 상담 신청 페이지(/consult, /consult.html)를 본 사람 수
    consult = by_range(run([], ["activeUsers"], ranges=(cur, prev), path_prefix="/consult"))
    events = {"cur": {}, "prev": {}}
    for r in run(["eventName"], ["eventCount"], ranges=(cur, prev), limit=200):
        events[r.get("dateRange", "cur")][r["eventName"]] = r["eventCount"]
    d = {
        "totals": totals,
        "consult_users": {"cur": consult["cur"].get("activeUsers", 0), "prev": consult["prev"].get("activeUsers", 0)},
        "events": events,
        "daily": run(["date"], ["activeUsers"], limit=60),
        "pages": run(["pagePath"], ["screenPageViews", "activeUsers"], order="screenPageViews", limit=40),
        "channels": run(["sessionSourceMedium"], ["sessions"], order="sessions", limit=10),
        "devices": run(["deviceCategory"], ["activeUsers"], order="activeUsers", limit=5),
        "regions": run(["region"], ["activeUsers"], order="activeUsers", limit=10),
    }
    d["daily"].sort(key=lambda r: r["date"])
    return d


def main():
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    key = os.environ.get("GA_SA_KEY", "").strip()
    sites = [s for s in SITES if s[3]]
    if not key or not sites:
        write({"status": "not_connected", "updated_at": now})
        print("연결 전 상태로 둡니다. 없는 값:", "GA_SA_KEY" if not key else "속성 ID(GA_PROPERTY_ID · GA_PROPERTY_ID_DAECHI)")
        return

    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        json.loads(key), scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    client = BetaAnalyticsDataClient(credentials=creds)
    out = []
    for skey, name, host, pid in SITES:
        site = {"key": skey, "name": name, "host": host}
        if not pid:
            site.update(status="not_connected")
        elif not pid.isdigit():
            site.update(status="error", message="속성 ID는 숫자여야 해요(G-로 시작하는 측정 ID가 아니라 GA 관리 › 속성 세부정보의 속성 ID). 지금 값 앞부분: " + pid[:2])
        else:
            try:
                site.update(status="ok", **fetch_site(client, pid))
            except Exception as e:  # 한 사이트가 실패해도 다른 사이트 숫자는 보여 줌
                site.update(status="error", message=str(e)[:300])
                print(name, "불러오기 실패:", e, file=sys.stderr)
        out.append(site)
    if not any(x["status"] == "ok" for x in out):
        write({"status": "error", "message": " / ".join(f'{x["name"]}: {x.get("message", x["status"])}' for x in out)[:600], "updated_at": now})
        return
    write({
        "status": "ok",
        "updated_at": now,
        "period": {"cur": [(datetime.now(KST) - timedelta(days=27)).strftime("%Y-%m-%d"), datetime.now(KST).strftime("%Y-%m-%d")]},
        "sites": out,
    })
    print("저장 완료:", OUT, [(x["name"], x["status"]) for x in out])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 실패해도 사이트 배포는 막지 않음
        write({"status": "error", "message": str(e)[:300],
               "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M")})
        print("GA4 불러오기 실패:", e, file=sys.stderr)
