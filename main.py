from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_home():
    return {
        "data": "hello world"
    }

@app.get("/tomato")
def read_tomato(request: Request):
    items = {
        "사과", "바나나", "오렌지"
    }
    return templates.TemplateResponse(request, "index.html", {"username": "관리자", "items": items})