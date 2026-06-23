# FirstByte VDS — куда жать и что дать агенту

Сервер из скрина: **socialspur.ru**, IP **104.128.137.117**, Ubuntu, 1 GB RAM.

**На Mac ничего ставить и запускать не нужно** — весь ONEHUNT работает на VDS. С Mac только открываете сайт в браузере или Telegram.

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
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPqiJsBjAsv4KymedFcUR891X1lgC90DW8yMtjcHJ/p0 cursor-agent
```

4. Сохраните и **привяжите ключ к VPS** (если панель просит выбрать сервер `socialspur.ru`).

После добавления ключа агент сможет деплоить сам. Или одна команда в **VNC-консоли** (шаг 2.3):

```bash
curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/main/scripts/vds_one_click.sh | bash
```

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
curl -fsSL https://raw.githubusercontent.com/conradshempert3961-dev/onehunt/main/scripts/firstbyte_vds_bootstrap.sh | bash -s socialspur.ru
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
- HuntDriver: `https://socialspur.ru/huntdriver/` (после деплоя miniapp)
- HuntDriver Pages: `https://conradshempert3961-dev.github.io/onehunt/` (если VDS ещё не обновлён)

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

## AI на VDS (Groq)

Рекомендуемый вариант — **Groq** (`groq/compound-mini`). Ключ берёте в [console.groq.com](https://console.groq.com).

В `/opt/onehunt/.env`:

```env
OPENAI_API_KEY=gsk_ваш_ключ
OPENAI_API_BASE=https://api.groq.com/openai/v1
OPENAI_MODEL=groq/compound-mini
```

Перезапуск после правки:

```bash
cd /opt/onehunt && docker compose -f docker-compose.prod.yml up -d --build miniapp
```

Без `OPENAI_API_KEY` ассистент отвечает по шаблону (rule-based).
