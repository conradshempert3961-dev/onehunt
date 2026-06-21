# FirstByte VDS — куда жать и что дать агенту

Сервер из скрина: **socialspur.ru**, IP **104.128.137.117**, Ubuntu, 1 GB RAM.

## Шаг 1. DNS (у регистратора домена)

Если домен `socialspur.ru` ваш — добавьте записи:

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | `104.128.137.117` |
| A | `www` | `104.128.137.117` |

Без DNS HTTPS и открытие сайта по домену не заработают (по IP можно временно).

---

## Шаг 2. Панель Virtualizor (vds.first-server.net)

### 2.1. Сброс пароля root

1. **List VPS** (уже открыт) — строка `socialspur.ru`.
2. Справа у статуса **Online** — **синяя шестерёнка** (Manage).
3. В меню найдите **Root Password** / **Change Password** / **Сменить пароль**.
4. Задайте новый пароль, **сохраните** и **скопируйте** (нужен для SSH).

### 2.2. SSH-ключ (чтобы агент мог зайти без пароля)

1. В левом меню: **SSH Keys**.
2. **Add SSH Key** / **Добавить**.
3. Вставьте этот публичный ключ (одна строка):

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHCofkVeLW1ZQ4Wupe7uF8EShex+16bk2QwY6ifrEO5g ubuntu@cursor
```

4. Сохраните и **привяжите ключ к VPS** (если панель просит выбрать сервер `socialspur.ru`).

### 2.3. Консоль (если SSH не открывается)

1. Снова **шестерёнка** у VPS.
2. **VNC** / **Console** / **Консоль** — откроется терминал в браузере.
3. Логин: `root`, пароль из шага 2.1.

### 2.4. Firewall (если есть пункт Firewall)

Откройте входящие: **22** (SSH), **80** (HTTP), **443** (HTTPS).

---

## Шаг 3. Что написать агенту в чат

Минимум:

```
IP: 104.128.137.117
Домен: socialspur.ru
Пароль root: ... (или: SSH ключ добавил)
BOT_TOKEN: ... (из @BotFather, если нужен бот)
```

Пароль лучше сменить после деплоя. Ключ из шага 2.2 — безопаснее, чем пароль в чат.

---

## Шаг 4. Автодеплой одной командой (если заходите сами по SSH)

```bash
ssh root@104.128.137.117
```

На сервере:

```bash
curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/cursor/improve-styling-fix-errors-2866/scripts/firstbyte_vds_bootstrap.sh | bash -s socialspur.ru
```

Или после `git clone`:

```bash
cd /opt/onehunt && bash scripts/firstbyte_vds_bootstrap.sh socialspur.ru
```

Скрипт ставит Docker, Nginx, Certbot, поднимает ONEHUNT (miniapp + postgres + redis), настраивает HTTPS.

---

## Шаг 5. После деплоя

- Сайт: `https://socialspur.ru/`
- Mini App: `https://socialspur.ru/app`
- Промо: `https://socialspur.ru/promo/`
- Estate: `https://socialspur.ru/estate/`

В `.env` на сервере проверьте:

```env
MINIAPP_URL=https://socialspur.ru/app
BOT_TOKEN=...
ADMIN_IDS=6467055041
```

Перезапуск:

```bash
cd /opt/onehunt && docker compose -f docker-compose.prod.yml up -d --build
```

---

## RAM 1 GB

На 1 GB включён swap 2 GB в bootstrap-скрипте. Бот и отдельный лендинг по умолчанию **не** стартуют — только miniapp (внутри него уже web + promo + estate).

## AI на VDS

Локальный DeepSeek proxy на сервере без браузера сложен. Варианты:

- официальный API DeepSeek в `.env`: `OPENAI_API_BASE=https://api.deepseek.com/v1` + ключ;
- или оставить rule-based fallback (без ключа).
