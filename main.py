from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException
import re
from kiwoom import kiwoom, KiwoomError

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_home(request: Request):
    # 메인 화면 = 주식 시세 조회 (templates/index.html)
    return templates.TemplateResponse(
        request, "index.html", {"configured": kiwoom.configured, "mode": kiwoom.mode}
    )

@app.get("/tomato")
def read_tomato(request: Request):
    items = {
        "사과", "바나나", "오렌지"
    }
    return templates.TemplateResponse(request, "tomato.html", {"username": "관리자", "items": items})

# ---------------- 주식 시세 API (키움 REST API) ----------------

@app.get("/api/stock/{code}")
async def stock_api(code: str, days: int = 60):
    if not re.fullmatch(r"\d{6}", code):
        raise HTTPException(400, "종목코드는 6자리 숫자입니다 (예: 005930)")
    try:
        return await kiwoom.get_stock(code, min(max(days, 5), 600))
    except KiwoomError as e:
        raise HTTPException(502, str(e))
