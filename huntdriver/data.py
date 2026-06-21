"""Mock data for HuntDriver / HUNTTROPHY demo."""

from __future__ import annotations

from typing import Any

DISTRICTS: list[dict[str, Any]] = [
    {
        "id": "milkovo",
        "name": "Мильковский район",
        "region": "Камчатский край",
        "species": "Бурый медведь",
        "species_icon": "bear",
        "licenses": 7,
    },
    {
        "id": "elizovo",
        "name": "Елизовский район",
        "region": "Камчатский край",
        "species": "Бурый медведь",
        "species_icon": "bear",
        "licenses": 4,
    },
]

SPECIES: list[dict[str, str]] = [
    {"id": "bear", "label": "Медведь"},
    {"id": "ram", "label": "Баран"},
    {"id": "moose", "label": "Лось"},
]

TRANSPORT: list[dict[str, str]] = [
    {"id": "mi8", "label": "Ми-8"},
    {"id": "robinson", "label": "Robinson"},
    {"id": "suv", "label": "Внедорожник"},
    {"id": "boat", "label": "Лодка"},
    {"id": "snowmobile", "label": "Снегоход"},
    {"id": "atv", "label": "Квадроцикл"},
    {"id": "horses", "label": "Кони"},
]

HUNTER_BIDS: list[dict[str, Any]] = [
    {
        "id": "ursus",
        "name": "УРСУС",
        "price": 1_420_000,
        "transport": "Ми-8 + внедорожник",
        "rating": 4.9,
        "best_price": True,
    },
    {
        "id": "khrebtovaya",
        "name": "Хребтовая",
        "price": 1_250_000,
        "transport": "Внедорожник + лодка",
        "rating": 4.7,
        "best_price": False,
    },
    {
        "id": "dolina",
        "name": "Долина",
        "price": 1_560_000,
        "transport": "Robinson + квадроцикл",
        "rating": 4.8,
        "best_price": False,
    },
]

ESTATE_APPLICATIONS: list[dict[str, Any]] = [
    {
        "id": "app-1",
        "species": "Бурый медведь",
        "district": "Мильковский район",
        "dates": "12–18 сентября",
        "budget": 750_000,
        "status": "new",
        "hot": False,
        "transport": ["Ми-8", "лодка"],
    },
    {
        "id": "app-2",
        "species": "Снежный баран",
        "district": "Улаганский район",
        "dates": "5–12 октября",
        "budget": 1_200_000,
        "status": "hot",
        "hot": True,
        "transport": ["Robinson", "кони"],
    },
    {
        "id": "app-3",
        "species": "Камчатский лось",
        "district": "Елизовский район",
        "dates": "20–27 сентября",
        "budget": 580_000,
        "status": "new",
        "hot": False,
        "transport": ["внедорожник"],
    },
]

MONITOR_EVENTS: list[dict[str, str]] = [
    {
        "id": "ev-1",
        "type": "tracks",
        "title": "Следы медведя · 2 часа назад",
        "detail": "Сектор B-12 · Координаты: 56.3212, 160.4321",
    },
    {
        "id": "ev-2",
        "type": "warning",
        "title": "Проверить сектор B-12",
        "detail": "Нет данных с фотоловушки №7 более 24 часов",
    },
    {
        "id": "ev-3",
        "type": "camera",
        "title": "Фотоловушка №4 активна",
        "detail": "Передано 32 фото · 15 минут назад",
    },
]

DOCUMENT_SECTIONS: list[dict[str, Any]] = [
    {
        "id": "licenses",
        "title": "Лицензии и разрешения",
        "detail": "Охотничьи лицензии, квоты, разрешения на добычу",
        "count": 4,
        "status": "ok",
        "status_label": "Актуально",
    },
    {
        "id": "contracts",
        "title": "Договоры и аренда",
        "detail": "Договоры аренды угодий, допсоглашения",
        "count": 3,
        "status": "warn",
        "status_label": "Нужно обновить",
    },
    {
        "id": "reports",
        "title": "Отчёты в Минприроды",
        "detail": "Сезонные отчёты, формы учёта добычи",
        "count": 2,
        "status": "pending",
        "status_label": "На проверке",
    },
    {
        "id": "zmu",
        "title": "Зимний маршрутный учёт (ЗМУ)",
        "detail": "Маршруты, протоколы, фотоотчёты",
        "count": 3,
        "status": "ok",
        "status_label": "Актуально",
    },
]
