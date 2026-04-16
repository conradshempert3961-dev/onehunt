# ONEHUNT

Telegram-бот для подготовки к охотничьему минимуму по вашему ТЗ: 257 официальных вопросов, 3 блока, 9+ режимов подготовки, маршрут на 14 дней, геймификация, Premium, карточки животных, админ-инструменты и напоминания.

## Что реализовано

- `bot.py` - основной aiogram-бот с FSM, платежами через Telegram Stars, маршрутом и напоминаниями.
- `database/` - асинхронное подключение и расширенная ORM-схема.
- `services/game.py` - логика ответов, XP, достижений, маршрута, дуэлей, промокодов и аналитики.
- `miniapp/` - Telegram Mini App на FastAPI + статический webview-интерфейс.
- `miniapp_server.py` - локальный запуск Mini App.
- `scripts/load_questions.py` - загрузка `questions.json` в БД.
- `scripts/check_db.py` - быстрая диагностика базы.
- `scripts/export_stats.py` - экспорт CSV со статистикой.
- `scripts/reset_db.py` - полное пересоздание таблиц.
- `scripts/add_question.py` - ручное добавление вопроса.
- `tests/test_helpers.py` - базовые юнит-тесты утилит.

## Режимы и функции

- Тропа знаний по 3 блокам с последовательным прогрессом.
- Стрельбище, слабые темы, таймер.
- Блиц, Испытание `257 вопросов / 90 минут / порог 75%`.
- Промахи, избранные вопросы, интервальное повторение.
- Быстрый вопрос и Вопрос дня.
- Маршрут на 14 дней и Вызов дня.
- Журнал, история испытаний, график прогресса, достижения.
- Карточки животных.
- Premium, промокоды, Telegram Stars, админ-панель и рассылки.
- Планировщик напоминаний.

## Быстрый старт локально

1. Создайте `.env` на основе `.env.example`.
2. Установите зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. При необходимости пересоздайте БД:

```bash
python scripts/reset_db.py
```

4. Загрузите вопросы:

```bash
python scripts/load_questions.py
```

5. Запустите бота:

```bash
python bot.py
```

6. Запустите Mini App:

```bash
python miniapp_server.py
```

После этого локальная web-часть будет доступна на `http://127.0.0.1:8080/`.

По умолчанию загрузчик берёт `questions.json` из корня проекта. Если нужен PostgreSQL/Redis, просто заполните `DATABASE_URL`, `REDIS_URL` и включите `USE_REDIS_FSM=true`.

## Mini App

- `MINIAPP_URL` — адрес Mini App, который бот использует для кнопки входа.
- `MINIAPP_DEV_USER_ID` — локальный dev-пользователь для теста в браузере вне Telegram.
- `MINIAPP_PORT` — порт локального FastAPI-сервера.
- `TELEGRAM_PROXY` — SOCKS5/HTTP прокси для бота, если VDS не может достучаться до `api.telegram.org`.
- Бот умеет открывать Mini App кнопкой из меню и из стартового экрана.

## Docker

1. Скопируйте `.env.example` в `.env` и заполните `BOT_TOKEN`.
2. Запустите сервисы:

```bash
docker compose up -d --build
```

3. Загрузите вопросы:

```bash
docker compose exec bot python scripts/load_questions.py
```

## Команды

- `/start`
- `/help`
- `/admin`
- `/user TELEGRAM_ID`
- `/grant_premium TELEGRAM_ID`
- `/revoke_premium TELEGRAM_ID`
- `/promo_create CODE DISCOUNT MAX_USES [DAYS]`
- `/promo_list`
- `/questions_stats`
- `/broadcast`
- `/broadcast_premium`

## Что настроить отдельно

- `BOT_TOKEN` обязателен.
- Для Telegram Stars заполните `TELEGRAM_STARS_PROVIDER_TOKEN`.
- Для банковских платежей в коде уже есть каркас, но реальные реквизиты/вебхуки ЮKassa нужно подключить в `.env`.
