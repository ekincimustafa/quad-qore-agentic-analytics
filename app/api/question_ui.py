"""Local, same-origin presentation; opening the page never calls a model."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from plotly.offline import get_plotlyjs

STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
def question_page(request: Request) -> HTMLResponse:
    preview = getattr(request.app.state, "offline_preview", False)
    notice = (
        "OFFLINE ÖNİZLEME · Sabit planlar kullanılır; canlı model çağrısı yapılmaz."
        if preview else "Yerel analiz · Sorunuz yapılandırılmış modelle planlanır."
    )
    return HTMLResponse(
        (STATIC_ROOT / "question.html").read_text(encoding="utf-8").replace("__MODE_NOTICE__", notice),
        headers={
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; font-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store",
        },
    )


@router.get("/ui-assets/plotly.js")
def plotly_script() -> Response:
    return Response(get_plotlyjs(), media_type="application/javascript", headers={"Cache-Control": "public, max-age=86400"})
