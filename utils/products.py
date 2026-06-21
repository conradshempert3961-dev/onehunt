from __future__ import annotations

from typing import Any, Literal

BillingKind = Literal["lifetime", "monthly"]

PRODUCT_ONEHUNT: dict[str, Any] = {
    "id": "onehunt",
    "slug": "hunter",
    "brand": "ONEHUNT",
    "title": "Путь одного охотника",
    "audience": "Охотники и будущие охотники",
    "summary": (
        "Подготовка к охотминимуму, маршрут до первой охоты, "
        "гайд, 12 чек-листов, AI и тренажёр на 257 вопросов."
    ),
    "price_rub": 990,
    "billing": "lifetime",
    "billing_label": "990 ₽ · пожизненный доступ",
    "value_pitch": (
        "Цифровой продукт с гайдом, чек-листами, картой пути, AI-помощником "
        "и полным тренажёром. По содержанию это десятки тысяч рублей консультаций и ошибок."
    ),
    "includes": [
        "257 официальных вопросов и полный экзамен",
        "Маршрут на 14 дней + путь до первой охоты (7 этапов)",
        "Гайд и 12 чек-листов (печать и телефон)",
        "AI-ассистент и карточки охотника",
        "Web-кабинет + Telegram Mini App с общим прогрессом",
    ],
    "cta_label": "Начать подготовку",
    "landing_path": "/promo/hunter.html",
    "web_path": "/",
    "miniapp_path": "/app",
    "telegram_url": "https://t.me/Onehuntbot",
}

PRODUCT_HUNT_TROPHY: dict[str, Any] = {
    "id": "hunt_trophy",
    "slug": "estate",
    "brand": "Hunt Trophy",
    "title": "Операционная система охотхозяйства",
    "audience": "Охотничье хозяйство и егерская служба",
    "summary": (
        "Бронирование выездов, разрешения, гости, отчётность, трофейная книга "
        "и единый кабинет для руководителя хозяйства."
    ),
    "price_rub": 490,
    "billing": "monthly",
    "billing_label": "490 ₽ / месяц",
    "value_pitch": (
        "Заменяет Excel, звонки и разрозненные чаты. Один сервис для заявок, "
        "документов, гостей и контроля угодий — экономия времени егерей и директора."
    ),
    "includes": [
        "Календарь охот и бронирование гостей",
        "Реестр разрешений и контроль документов",
        "Трофейная книга и отчёты для проверок",
        "Кабинет егеря + панель руководителя",
        "Связка с ONEHUNT для подготовки гостей к экзамену",
    ],
    "cta_label": "Запросить демо",
    "landing_path": "/estate/",
    "web_path": "/estate/",
    "miniapp_path": "/estate/app",
    "telegram_url": "https://t.me/Onehuntbot",
    "status": "beta",
}

PRODUCT_CATALOG: list[dict[str, Any]] = [PRODUCT_ONEHUNT, PRODUCT_HUNT_TROPHY]

PRODUCT_BY_ID: dict[str, dict[str, Any]] = {
    item["id"]: item for item in PRODUCT_CATALOG
}
