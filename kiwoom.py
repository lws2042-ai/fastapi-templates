"""키움증권 REST API 클라이언트 (토큰 발급 + 종목 기본정보 + 일봉 차트).

공식 명세: https://github.com/Kiwoom-Securities/Kiwoom-REST-API
- au10001  POST /oauth2/token      접근토큰 발급
- ka10001  POST /api/dostk/stkinfo 주식 기본정보
- ka10081  POST /api/dostk/chart   주식 일봉차트

.env 에 KIWOOM_APP_KEY / KIWOOM_SECRET_KEY 가 없으면 샘플 데이터(demo)를 돌려준다.
"""

import os
import random
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URLS = {
    "real": "https://api.kiwoom.com",
    "mock": "https://mockapi.kiwoom.com",  # 모의투자
}


class KiwoomError(Exception):
    pass


def to_num(value) -> float:
    """키움은 숫자를 '+70100', '-1.25' 같은 문자열로 준다."""
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0


class KiwoomClient:
    def __init__(self):
        self.app_key = os.getenv("KIWOOM_APP_KEY", "")
        self.secret_key = os.getenv("KIWOOM_SECRET_KEY", "")
        mode = os.getenv("KIWOOM_MODE", "mock")
        self.base_url = BASE_URLS.get(mode, BASE_URLS["mock"])
        self.mode = mode
        self._token: str | None = None
        self._token_expires: datetime | None = None

    @property
    def configured(self) -> bool:
        return bool(self.app_key and self.secret_key)

    # ---------- 인증 ----------
    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and self._token_expires and datetime.now() < self._token_expires - timedelta(minutes=5):
            return self._token

        res = await client.post(
            f"{self.base_url}/oauth2/token",
            headers={"Content-Type": "application/json;charset=UTF-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.secret_key,
            },
        )
        data = res.json()
        if not data.get("token"):
            raise KiwoomError(f"토큰 발급 실패: {data.get('return_msg', data)}")

        self._token = data["token"]
        try:
            self._token_expires = datetime.strptime(data["expires_dt"], "%Y%m%d%H%M%S")
        except (KeyError, ValueError):
            self._token_expires = datetime.now() + timedelta(hours=1)
        return self._token

    async def _call(self, api_id: str, path: str, body: dict, retry: bool = True) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            token = await self._get_token(client)
            res = await client.post(
                f"{self.base_url}{path}",
                headers={
                    "Content-Type": "application/json;charset=UTF-8",
                    "api-id": api_id,
                    "authorization": f"Bearer {token}",
                },
                json=body,
            )
        data = res.json()
        code = data.get("return_code")
        # 키움은 오류도 HTTP 200 으로 내려주고 return_code 로만 알려준다. 8005 = 토큰 만료
        if str(code) == "8005" and retry:
            self._token = None
            return await self._call(api_id, path, body, retry=False)
        if code not in (None, 0, "0"):
            raise KiwoomError(f"[{api_id}] {data.get('return_msg')} (code={code})")
        return data

    # ---------- 시세 ----------
    async def get_stock(self, code: str, days: int = 60) -> dict:
        if not self.configured:
            return demo_stock(code, days)

        info = await self._call("ka10001", "/api/dostk/stkinfo", {"stk_cd": code})
        chart = await self._call(
            "ka10081",
            "/api/dostk/chart",
            {"stk_cd": code, "base_dt": datetime.now().strftime("%Y%m%d"), "upd_stkpc_tp": "1"},
        )
        rows = chart.get("stk_dt_pole_chart_qry", [])[:days]
        return {
            "source": f"kiwoom-{self.mode}",
            "code": code,
            "name": info.get("stk_nm", code),
            "price": abs(to_num(info.get("cur_prc"))),
            "change": to_num(info.get("pred_pre")),
            "rate": to_num(info.get("flu_rt")),
            "volume": to_num(info.get("trde_qty")),
            "high": abs(to_num(info.get("high_pric"))),
            "low": abs(to_num(info.get("low_pric"))),
            "open": abs(to_num(info.get("open_pric"))),
            "per": info.get("per", ""),
            "pbr": info.get("pbr", ""),
            "chart": [
                {
                    "date": r.get("dt"),
                    "open": abs(to_num(r.get("open_pric"))),
                    "high": abs(to_num(r.get("high_pric"))),
                    "low": abs(to_num(r.get("low_pric"))),
                    "close": abs(to_num(r.get("cur_prc"))),
                    "volume": to_num(r.get("trde_qty")),
                }
                for r in reversed(rows)  # 키움은 최신순 → 오래된 순으로 뒤집기
            ],
        }


# ---------- API 키 없을 때 쓰는 샘플 데이터 ----------
DEMO_NAMES = {"005930": "삼성전자", "000660": "SK하이닉스", "035420": "NAVER", "035720": "카카오"}


def demo_stock(code: str, days: int) -> dict:
    rnd = random.Random(code)
    price = rnd.randint(20, 300) * 1000
    chart = []
    day = datetime.now() - timedelta(days=days * 1.5)
    while len(chart) < days:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue
        open_ = price
        price = max(1000, round(price * (1 + rnd.uniform(-0.03, 0.03)), -2))
        chart.append({
            "date": day.strftime("%Y%m%d"),
            "open": open_,
            "high": max(open_, price) * 1.01,
            "low": min(open_, price) * 0.99,
            "close": price,
            "volume": rnd.randint(100_000, 5_000_000),
        })
    last, prev = chart[-1], chart[-2]
    change = last["close"] - prev["close"]
    return {
        "source": "demo",
        "code": code,
        "name": DEMO_NAMES.get(code, f"샘플종목 {code}"),
        "price": last["close"],
        "change": change,
        "rate": round(change / prev["close"] * 100, 2),
        "volume": last["volume"],
        "high": round(last["high"]),
        "low": round(last["low"]),
        "open": last["open"],
        "per": "-",
        "pbr": "-",
        "chart": chart,
    }


kiwoom = KiwoomClient()
