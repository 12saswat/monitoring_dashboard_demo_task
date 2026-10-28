from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()

@router.get("/", include_in_schema=False)
def index_redirect():
    return RedirectResponse(url="/dashboard")

@router.get("/dashboard", response_class=HTMLResponse)
def render_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"app_title": "FastAPI API Sentinel"}
    )
