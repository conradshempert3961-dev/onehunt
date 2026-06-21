from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from huntdriver.data import (
    DISTRICTS,
    DOCUMENT_SECTIONS,
    ESTATE_APPLICATIONS,
    HUNTER_BIDS,
    MONITOR_EVENTS,
    SPECIES,
    TRANSPORT,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="HuntDriver / HUNTTROPHY",
    version="0.1.0",
    description="Отдельное приложение для охотников и охотхозяйств (маркетплейс заявок и торгов).",
)

app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


def _html(path: str) -> HTMLResponse:
    file_path = STATIC_DIR / path
    if not file_path.is_file():
        raise FileNotFoundError(path)
    return HTMLResponse(file_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "product": "huntdriver"}


@app.get("/", response_class=HTMLResponse)
async def hub() -> HTMLResponse:
    return _html("index.html")


@app.get("/hunter", response_class=HTMLResponse)
@app.get("/hunter/", response_class=HTMLResponse)
async def hunter_home() -> HTMLResponse:
    return _html("hunter/index.html")


@app.get("/hunter/request", response_class=HTMLResponse)
async def hunter_request() -> HTMLResponse:
    return _html("hunter/request.html")


@app.get("/hunter/bids", response_class=HTMLResponse)
async def hunter_bids() -> HTMLResponse:
    return _html("hunter/bids.html")


@app.get("/hunter/profile", response_class=HTMLResponse)
async def hunter_profile() -> HTMLResponse:
    return _html("hunter/profile.html")


@app.get("/hunter/estate/{estate_id}", response_class=HTMLResponse)
async def hunter_estate_profile(estate_id: str) -> HTMLResponse:
    return _html("hunter/estate.html")


@app.get("/trophy", response_class=HTMLResponse)
@app.get("/trophy/", response_class=HTMLResponse)
async def trophy_home() -> HTMLResponse:
    return _html("trophy/index.html")


@app.get("/trophy/bids", response_class=HTMLResponse)
async def trophy_bids() -> HTMLResponse:
    return _html("trophy/bids.html")


@app.get("/trophy/monitor", response_class=HTMLResponse)
async def trophy_monitor() -> HTMLResponse:
    return _html("trophy/monitor.html")


@app.get("/trophy/documents", response_class=HTMLResponse)
async def trophy_documents() -> HTMLResponse:
    return _html("trophy/documents.html")


@app.get("/trophy/profile", response_class=HTMLResponse)
async def trophy_profile() -> HTMLResponse:
    return _html("trophy/profile.html")


@app.get("/api/meta")
async def api_meta() -> dict[str, object]:
    return {
        "brands": {
            "hunter": "HuntDriver by ONEHUNT",
            "estate": "HUNTTROPHY",
        },
        "note": "Отдельный продукт, не связан с ONEHUNT Premium (990 ₽).",
    }


@app.get("/api/hunter/bootstrap")
async def hunter_bootstrap() -> dict[str, object]:
    return {
        "districts": DISTRICTS,
        "species": SPECIES,
        "transport": TRANSPORT,
        "active_district": DISTRICTS[0],
    }


@app.get("/api/hunter/bids")
async def hunter_bids_api() -> dict[str, object]:
    return {
        "request": {
            "district": "Мильковский район",
            "species": "Бурый медведь",
            "dates": "12–18 сентября",
            "budget": 1_500_000,
        },
        "offers": HUNTER_BIDS,
        "total": len(HUNTER_BIDS),
    }


@app.get("/api/trophy/bootstrap")
async def trophy_bootstrap() -> dict[str, object]:
    return {
        "estate": {
            "name": "НП Кутх",
            "verified": True,
            "area_ha": 120_450,
            "rating": 4.8,
            "season": "Весна 2025",
            "season_active": True,
        },
        "stats": {
            "open_applications": 12,
            "active_hunters": 28,
            "reports_pending": 7,
        },
    }


@app.get("/api/trophy/applications")
async def trophy_applications() -> dict[str, object]:
    return {"items": ESTATE_APPLICATIONS}


@app.get("/api/trophy/monitor")
async def trophy_monitor_api() -> dict[str, object]:
    return {
        "region": "Камчатский край",
        "ground": {
            "name": "Кутхинское охотничье угодье",
            "area_ha": 120_450,
        },
        "stats": {
            "cameras": {"total": 18, "online": 14},
            "points": {"total": 6, "online": 6},
            "warnings": 2,
        },
        "events": MONITOR_EVENTS,
    }


@app.get("/api/trophy/documents")
async def trophy_documents_api() -> dict[str, object]:
    return {
        "summary": {
            "total": 12,
            "in_review": 3,
            "expiring": 1,
        },
        "sections": DOCUMENT_SECTIONS,
    }
