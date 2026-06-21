# HuntDriver / HUNTTROPHY

**Отдельное приложение** — маркетплейс для охотников и охотхозяйств.

Не связано с ONEHUNT Premium (990 ₽, подготовка к охотминимуму) и не использует код miniapp.

## Продукты

| Бренд | Аудитория | Функции |
|-------|-----------|---------|
| **HuntDriver** | Охотники | Карта угодий, заявки, аукцион, профиль, трофеи |
| **HUNTTROPHY** | Охотхозяйства | Заявки, торги, мониторинг, документы, профиль |

## Запуск локально

```bash
cd /workspace
.venv/bin/uvicorn huntdriver.app:app --host 0.0.0.0 --port 8082 --reload
```

- http://127.0.0.1:8082/ — выбор роли
- http://127.0.0.1:8082/hunter/ — HuntDriver
- http://127.0.0.1:8082/trophy/ — HUNTTROPHY

## API (демо)

- `GET /health`
- `GET /api/meta`
- `GET /api/hunter/bootstrap`
- `GET /api/hunter/bids`
- `GET /api/trophy/bootstrap`
- `GET /api/trophy/applications`
- `GET /api/trophy/monitor`
- `GET /api/trophy/documents`

## Деплой

Контейнер `huntdriver` на порту **8082**, nginx:

- `/huntdriver/` → hub
- `/huntdriver/hunter/` → охотник
- `/huntdriver/trophy/` → хозяйство
