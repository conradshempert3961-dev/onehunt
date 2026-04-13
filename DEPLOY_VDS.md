# Деплой ONEHUNT на VDS

Ниже вариант для `Ubuntu 22.04/24.04` с `Docker`, `Docker Compose`, `Nginx` и `Certbot`.

## 1. Что понадобится

- домен для сайта, например `onehunt.ru`
- поддомен для Mini App, например `app.onehunt.ru`
- VDS с публичным IP
- DNS-записи:
  - `A onehunt.ru -> IP_СЕРВЕРА`
  - `A www.onehunt.ru -> IP_СЕРВЕРА`
  - `A app.onehunt.ru -> IP_СЕРВЕРА`

## 2. Установка Docker и Nginx

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx git
sudo systemctl enable --now docker
sudo systemctl enable --now nginx
```

## 3. Загрузка проекта на сервер

```bash
cd /opt
sudo git clone YOUR_REPO_URL onehunt
sudo chown -R $USER:$USER /opt/onehunt
cd /opt/onehunt
```

Если репозиторий не в git, можно просто залить папку через `scp`, `WinSCP` или `SFTP` в `/opt/onehunt`.

## 4. Настройка `.env`

Скопируйте шаблон:

```bash
cp .env.example .env
```

Обязательно проверьте и заполните:

```env
BOT_TOKEN=ВАШ_ТОКЕН
ADMIN_IDS=6467055041
DATABASE_URL=postgresql+asyncpg://onehunt:onehunt@postgres:5432/onehunt
REDIS_URL=redis://redis:6379/0
USE_REDIS_FSM=false
FREE_MODE=true
MINIAPP_URL=https://app.onehunt.ru/
MINIAPP_DEV_USER_ID=6467055041
MINIAPP_PORT=8080
```

## 5. Поднять контейнеры

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Проверить:

```bash
docker compose -f docker-compose.prod.yml ps
```

## 6. Загрузить вопросы в базу

```bash
docker compose -f docker-compose.prod.yml exec bot python scripts/load_questions.py
```

Если нужно пересоздать базу:

```bash
docker compose -f docker-compose.prod.yml exec bot python scripts/reset_db.py
docker compose -f docker-compose.prod.yml exec bot python scripts/load_questions.py
```

## 7. Настроить Nginx

Скопируйте пример конфига:

```bash
sudo cp deploy/nginx/onehunt.conf.example /etc/nginx/sites-available/onehunt
```

Откройте файл и замените:

- `your-domain.ru` на ваш домен
- `app.your-domain.ru` на ваш поддомен Mini App

Включите сайт:

```bash
sudo ln -s /etc/nginx/sites-available/onehunt /etc/nginx/sites-enabled/onehunt
sudo nginx -t
sudo systemctl reload nginx
```

## 8. Подключить HTTPS

```bash
sudo certbot --nginx -d onehunt.ru -d www.onehunt.ru -d app.onehunt.ru
```

После этого:

- сайт будет открываться на `https://onehunt.ru`
- Mini App будет доступен на `https://app.onehunt.ru`

## 9. Проверить Telegram Mini App

После появления HTTPS обязательно проверьте, что в `.env` стоит:

```env
MINIAPP_URL=https://app.onehunt.ru/
```

Потом перезапустите контейнеры:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## 10. Полезные команды

Логи бота:

```bash
docker compose -f docker-compose.prod.yml logs -f bot
```

Логи Mini App:

```bash
docker compose -f docker-compose.prod.yml logs -f miniapp
```

Логи сайта:

```bash
docker compose -f docker-compose.prod.yml logs -f site
```

Перезапуск:

```bash
docker compose -f docker-compose.prod.yml restart
```

Остановка:

```bash
docker compose -f docker-compose.prod.yml down
```

## 11. Что где работает

- `bot` — Telegram-бот в long polling
- `miniapp` — FastAPI на `127.0.0.1:8080`
- `site` — лендинг на `127.0.0.1:8088`
- `postgres` — БД внутри Docker-сети
- `redis` — Redis внутри Docker-сети

## 12. Что важно

- для Mini App Telegram требует именно `HTTPS`
- боту публичный порт не нужен, если он работает через long polling
- если позже подключите внешние вебхуки, платежи или API, можно будет вынести это на отдельный домен или маршрут
