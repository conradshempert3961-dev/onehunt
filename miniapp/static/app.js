const APP_MODE = window.ONEHUNT_MODE || "site";
const tg = window.Telegram?.WebApp ?? null;

if (tg) {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation();
    tg.setHeaderColor("#f5f8f6");
    tg.setBackgroundColor("#f5f8f6");
}

const state = {
    bootstrap: null,
    daily: null,
    journal: null,
    progress: null,
    achievements: null,
    history: null,
    cards: null,
    activeSession: null,
    pendingNextQuestion: false,
    lastQuestionId: null,
    selectedCategory: null,
    answerLocked: false,
    aiBusy: false,
    aiHistory: [],
    aiSuggestions: [],
    premiumCheckout: null,
    authMode: "login",
};

const screens = document.querySelectorAll(".screen");
const navButtons = document.querySelectorAll(".tab, .nav-button");
const toast = document.getElementById("toast");
const sessionOverlay = document.getElementById("sessionOverlay");
const detailSheet = document.getElementById("detailSheet");
const aiThread = document.getElementById("aiThread");
const aiPromptGrid = document.getElementById("aiPromptGrid");
const aiForm = document.getElementById("aiForm");
const aiInput = document.getElementById("aiInput");
const aiSendButton = document.getElementById("aiSendButton");
const aiStatus = document.getElementById("aiStatus");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const authTabButtons = document.querySelectorAll("[data-auth-tab]");
const authPanels = document.querySelectorAll("[data-auth-panel]");
const authSwitchLabel = document.getElementById("authSwitchLabel");
const authSwitchAction = document.getElementById("authSwitchAction");
const logoutButton = document.getElementById("logoutButton");
const headerProfileButton = document.getElementById("headerProfileButton");
const bottomNav = document.querySelector(".tabbar, .bottom-nav");
const siteFooter = document.querySelector(".site-footer");
const PREMIUM_BANNER_IMAGE = "/assets/premium-guide.jpg";
const AI_COACH_NAME = "Егерь";
const BRAND_LOGO_IMAGE = "/assets/brand-logo.jpg";
const AI_AVATAR_IMAGE = "/assets/ai-coach-avatar.png?v=20260624";
let sessionTimerInterval = null;

function hasWebSession() {
    return Boolean(state.bootstrap?.user);
}

function currentUser() {
    return state.bootstrap?.user || null;
}

function hasPremiumAccess() {
    return currentUser()?.access_level === "premium" || Boolean(currentUser()?.has_premium);
}

function routeFreeDays() {
    return Number(state.bootstrap?.route?.free_days || 0);
}

function hasRouteAccess(route = state.bootstrap?.route) {
    if (!route) {
        return false;
    }
    return hasPremiumAccess() || Boolean(state.bootstrap?.free_mode) || Number(route.current_day || 0) <= routeFreeDays();
}

function currentAccessBadge() {
    if (hasPremiumAccess()) {
        return { label: "PREMIUM", className: "is-premium", note: "Активен" };
    }
    if (state.bootstrap?.free_mode) {
        return { label: "OPEN BETA", className: "is-beta", note: "Открытый доступ" };
    }
    return { label: "БАЗОВЫЙ", className: "is-basic", note: "Premium — полный маршрут и AI" };
}

function premiumOffer() {
    return state.bootstrap?.premium_offer || {
        title: "Полный путь до первой охоты",
        subtitle: "Гайд + 12 чек-листов",
        price_rub: 990,
        price_stars: 700,
        crypto_enabled: false,
        yoomoney_enabled: false,
        stars_enabled: true,
    };
}

function formatTimerValue(totalSeconds) {
    const safe = Math.max(0, Number(totalSeconds || 0));
    const minutes = Math.floor(safe / 60);
    const seconds = safe % 60;
    if (minutes >= 60) {
        const hours = Math.floor(minutes / 60);
        const restMinutes = minutes % 60;
        return `${hours}:${String(restMinutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function stopSessionTimer() {
    if (sessionTimerInterval) {
        window.clearInterval(sessionTimerInterval);
        sessionTimerInterval = null;
    }
}

function renderSessionTimer(timer) {
    const timerNode = document.querySelector("[data-session-timer]");
    if (!timerNode) {
        return;
    }
    if (!timer) {
        timerNode.remove();
        return;
    }
    timerNode.textContent = `Таймер ${formatTimerValue(timer.left_seconds)} · ${timer.label}`;
    timerNode.classList.toggle("is-danger", timer.left_seconds <= 15);
}

function startSessionTimer(timer) {
    stopSessionTimer();
    if (!timer) {
        return;
    }
    const liveTimer = { ...timer };
    renderSessionTimer(liveTimer);
    sessionTimerInterval = window.setInterval(() => {
        liveTimer.left_seconds = Math.max(0, liveTimer.left_seconds - 1);
        renderSessionTimer(liveTimer);
        if (liveTimer.left_seconds <= 0) {
            stopSessionTimer();
        }
    }, 1000);
}

function closeDetailSheet() {
    detailSheet.classList.add("hidden");
    syncTelegramBackButton();
}

function openExternalLink(url) {
    if (!url) {
        showToast("Ссылка на оплату пока не пришла");
        return;
    }
    const targetUrl = url.startsWith("/") ? `${window.location.origin}${url}` : url;

    if (tg?.openTelegramLink && targetUrl.includes("t.me/")) {
        tg.openTelegramLink(targetUrl);
        return;
    }
    if (tg?.openLink) {
        tg.openLink(targetUrl);
        return;
    }
    window.open(targetUrl, "_blank", "noopener");
}

function pulse(style = "light") {
    try {
        tg?.HapticFeedback?.impactOccurred?.(style);
    } catch (_error) {
        // ignore
    }
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function escapeAttribute(value) {
    return escapeHtml(value).replace(/`/g, "&#96;");
}

function formatRichText(value) {
    return escapeHtml(value).replace(/\n/g, "<br>");
}

function nowLabel() {
    return new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

function sessionModeLabel(mode) {
    const labels = {
        trail: "Тропа знаний",
        training: "Тренировка",
        blitz: "Блиц",
        exam: "Экзамен",
        mistakes: "Разбор ошибок",
        starred: "Избранные вопросы",
        duel: "Дуэль",
        repetition: "Повторение",
        quick: "Быстрый вопрос",
    };
    return labels[mode] || "Практика";
}

function baseAnswerHint(mode) {
    if (mode === "exam") {
        return "Выберите ответ и сразу увидите, где попали или промахнулись. Кнопка перехода уже будет наверху.";
    }
    if (mode === "quick") {
        return "Один точный выстрел: нажмите на вариант и сразу получите разбор.";
    }
    return "Нажмите на вариант прямо под вопросом. После выбора мы подсветим правильный ответ.";
}

function syncTelegramBackButton() {
    if (APP_MODE !== "miniapp") {
        return;
    }
    if (!hasWebSession() && !state.bootstrap?.user) {
        return;
    }
    if (!tg?.BackButton) {
        return;
    }
    const shouldShow = !sessionOverlay.classList.contains("hidden") || !detailSheet.classList.contains("hidden");
    if (shouldShow) {
        tg.BackButton.show();
    } else {
        tg.BackButton.hide();
    }
}

if (tg?.BackButton) {
    tg.BackButton.onClick(() => {
        if (!detailSheet.classList.contains("hidden")) {
            detailSheet.classList.add("hidden");
            syncTelegramBackButton();
            return;
        }
        if (!sessionOverlay.classList.contains("hidden")) {
            closeSessionOverlay();
            hydrate();
        }
    });
}

function showToast(message) {
    toast.textContent = message;
    toast.classList.remove("hidden");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.add("hidden"), 2400);
}

function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isPremiumLocked(error) {
    return Number(error?.status) === 403;
}

function maybeOpenPremiumFromError(error, fallbackMessage = "Эта функция доступна в PREMIUM") {
    if (!isPremiumLocked(error)) {
        return false;
    }
    renderPremiumSheet();
    showToast(error.message || fallbackMessage);
    return true;
}

function premiumCheckoutStatusText(checkout) {
    if (!checkout) {
        return APP_MODE === "miniapp"
            ? "Оплата привязывается к вашему профилю ONEHUNT внутри Telegram. После успешного платежа статус сразу станет PREMIUM."
            : "Оплата привязывается к вашему web-аккаунту ONEHUNT. После успешного платежа статус сразу станет PREMIUM.";
    }
    if (checkout.provider === "telegram_stars") {
        return `Счет #${checkout.payment_id} создан в Telegram Stars. Если окно оплаты уже закрыли, можно открыть его снова или проверить статус ниже.`;
    }
    if (checkout.provider === "yoomoney") {
        return checkout.detail || `Счет #${checkout.payment_id} создан в YooMoney. Оплатите его картой или кошельком, затем вернитесь и нажмите проверку.`;
    }
    return `Счет #${checkout.payment_id} создан через Crypto Bot. После оплаты вернитесь сюда и нажмите проверку.`;
}

function premiumPrimaryActionLabel(offer) {
    if (hasPremiumAccess()) {
        return "PREMIUM уже активен";
    }
    if (APP_MODE === "miniapp" && offer.stars_enabled) {
        return `Оплатить ${offer.price_stars} ⭐ в Telegram`;
    }
    return `Оплатить ${offer.price_rub} ₽ через YooMoney`;
}

function renderPremiumSheet() {
    const offer = premiumOffer();
    const access = currentAccessBadge();
    const checkout = state.premiumCheckout;
    const premiumActive = hasPremiumAccess();
    const canPayStars = Boolean(offer.stars_enabled && !premiumActive);
    const canPayCrypto = Boolean(offer.crypto_enabled && !premiumActive);
    const canPayYooMoney = Boolean(offer.yoomoney_enabled && !premiumActive);
    const primaryProvider = APP_MODE === "miniapp" && canPayStars ? "stars" : (canPayYooMoney ? "yoomoney" : "stars");
    const openLabel =
        checkout?.provider === "telegram_stars"
            ? "Открыть Stars-счет"
            : checkout?.provider === "yoomoney"
              ? "Открыть страницу YooMoney"
              : "Открыть счет";

    document.getElementById("sheetContent").innerHTML = `
        <div class="premium-sheet">
            <div class="premium-sheet-head">
                <div>
                    <p class="eyebrow">Премиум-доступ</p>
                    <h2>PREMIUM</h2>
                    <p class="info-line">${offer.price_rub} ₽ · пожизненный доступ</p>
                </div>
                <span class="access-pill ${access.className}">${access.label}</span>
            </div>
            <div class="premium-benefits">
                <article class="premium-benefit-card">
                    <strong>Полный доступ</strong>
                    <span>Маршрут, экзамен, карточки, AI и все режимы.</span>
                </article>
                <article class="premium-benefit-card">
                    <strong>Материалы</strong>
                    <span>Гайд и чек-листы для подготовки.</span>
                </article>
            </div>
            <div class="premium-checkout-box">
                <strong>${access.note}</strong>
                <span>${premiumCheckoutStatusText(checkout)}</span>
            </div>
            <div class="premium-actions">
                <button class="primary-button" type="button" data-premium-action="${primaryProvider}" ${(primaryProvider === "stars" && !canPayStars) || (primaryProvider === "yoomoney" && !canPayYooMoney) ? "disabled" : ""}>${premiumPrimaryActionLabel(offer)}</button>
                ${canPayYooMoney && primaryProvider !== "yoomoney" ? `<button class="ghost-button premium-alt-button" type="button" data-premium-action="yoomoney">Оплатить ${offer.price_rub} ₽ через YooMoney</button>` : ""}
                ${canPayStars && primaryProvider !== "stars" ? `<button class="ghost-button premium-alt-button" type="button" data-premium-action="stars">Оплатить ${offer.price_stars} ⭐ в Telegram</button>` : ""}
                <button class="ghost-button premium-alt-button" type="button" data-premium-action="crypto" ${canPayCrypto ? "" : "disabled"}>Оплатить ${offer.price_rub} ₽ через Crypto Bot</button>
                ${checkout?.payment_id && !premiumActive ? `<button class="ghost-button" type="button" data-premium-action="open">${openLabel}</button>` : ""}
                ${checkout?.payment_id && !premiumActive ? `<button class="ghost-button" type="button" data-premium-action="check">Проверить оплату</button>` : ""}
            </div>
        </div>
    `;
    detailSheet.classList.remove("hidden");
    syncTelegramBackButton();
}

function openPremiumCheckout(checkout = state.premiumCheckout) {
    if (!checkout) {
        showToast("Сначала создайте счет");
        return;
    }
    if (checkout.provider === "telegram_stars" && checkout.invoice_link) {
        if (tg?.openInvoice) {
            tg.openInvoice(checkout.invoice_link, async (status) => {
                if (status === "paid") {
                    await pollPremiumStatus("stars", checkout.payment_id, 5, 1200);
                    return;
                }
                if (status === "cancelled" || status === "failed") {
                    showToast("Оплата не завершена");
                    return;
                }
                showToast("Счет открыт. После оплаты вернитесь в ONEHUNT.");
            });
            return;
        }
        openExternalLink(checkout.invoice_link);
        return;
    }
    openExternalLink(checkout.pay_url || checkout.invoice_link);
}

async function pollPremiumStatus(provider, paymentId, attempts = 4, delayMs = 1200) {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
        const payload = await api(`/api/premium/${provider}/status/${paymentId}`);
        state.premiumCheckout = { ...state.premiumCheckout, ...payload };
        if (payload.activated) {
            pulse("success");
            await hydrate();
            renderPremiumSheet();
            showToast("PREMIUM активирован");
            return payload;
        }
        if (attempt < attempts - 1) {
            await sleep(delayMs);
        }
    }
    renderPremiumSheet();
    showToast("Платеж пока еще не подтвержден");
    return null;
}

async function createPremiumInvoice(provider = "crypto") {
    if (hasPremiumAccess()) {
        renderPremiumSheet();
        return;
    }

    try {
        const pathByProvider = {
            telegram_stars: "/api/premium/stars/invoice",
            yoomoney: "/api/premium/yoomoney/invoice",
            crypto: "/api/premium/crypto/invoice",
        };
        const path = pathByProvider[provider] || pathByProvider.crypto;
        const payload = await api(path, {
            method: "POST",
            body: JSON.stringify({}),
        });
        state.premiumCheckout = payload;
        renderPremiumSheet();
        openPremiumCheckout(payload);
    } catch (error) {
        showToast(error.message);
    }
}

async function checkPremiumInvoice() {
    if (!state.premiumCheckout?.payment_id) {
        showToast("Сначала создайте счет");
        return;
    }

    try {
        const providerMap = {
            telegram_stars: "stars",
            yoomoney: "yoomoney",
            crypto_bot: "crypto",
        };
        await pollPremiumStatus(
            providerMap[state.premiumCheckout.provider] || "crypto",
            state.premiumCheckout.payment_id,
        );
    } catch (error) {
        showToast(error.message);
    }
}

async function api(path, options = {}) {
    window.wolfLoader?.start();
    try {
        const headers = new Headers(options.headers || {});
        if (tg?.initData) {
            headers.set("X-Telegram-Init-Data", tg.initData);
        }
        headers.set("Content-Type", "application/json");
        const response = await fetch(path, { credentials: "same-origin", ...options, headers });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            let detail = payload.detail;
            if (Array.isArray(detail)) {
                detail = detail.map((item) => item.msg || item.message || JSON.stringify(item)).join("; ");
            }
            const message =
                (typeof detail === "string" && detail) ||
                payload.message ||
                response.statusText ||
                `HTTP ${response.status}`;
            const error = new Error(message);
            error.status = response.status;
            error.payload = payload;
            throw error;
        }
        return payload;
    } finally {
        window.wolfLoader?.stop();
    }
}

function scrollAppToTop() {
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
}

function switchScreen(screenId) {
    if (!hasWebSession()) {
        return;
    }
    screens.forEach((screen) => screen.classList.toggle("screen-active", screen.id === `screen-${screenId}`));
    navButtons.forEach((button) => button.classList.toggle("active", button.dataset.screen === screenId));
    window.requestAnimationFrame(scrollAppToTop);
    if (screenId === "ai") {
        window.setTimeout(() => aiInput?.focus(), 120);
    }
    pulse("light");
}

function setAuthMode(mode = "login") {
    if (APP_MODE !== "site") {
        return;
    }

    state.authMode = mode === "register" ? "register" : "login";

    authTabButtons.forEach((button) => {
        button.classList.toggle("is-active", button.dataset.authTab === state.authMode);
    });

    authPanels.forEach((panel) => {
        const isActive = panel.dataset.authPanel === state.authMode;
        panel.classList.toggle("is-active", isActive);
        panel.classList.toggle("hidden", !isActive);
    });

    if (authSwitchLabel) {
        authSwitchLabel.textContent = state.authMode === "login" ? "Нет аккаунта?" : "Уже есть аккаунт?";
    }

    if (authSwitchAction) {
        authSwitchAction.dataset.authSwitch = state.authMode === "login" ? "register" : "login";
        authSwitchAction.textContent = state.authMode === "login" ? "Зарегистрироваться" : "Войти";
    }
}

function createStatCard(label, value) {
    return `<article class="metric-chip"><strong>${value}</strong><span>${label}</span></article>`;
}

function createMetricPill(label, value) {
    return `<div class="metric-pill"><strong>${value}</strong><span>${label}</span></div>`;
}

function createAiPromptButton(label) {
    return `<button class="ai-prompt-chip" type="button" data-ai-prompt="${escapeAttribute(label)}">${escapeHtml(label)}</button>`;
}

function buildAiWelcomeMessage() {
    if (!state.bootstrap || !state.journal) {
        return "Спросите про маршрут, ошибки или экзамен.";
    }

    const user = state.bootstrap.user;
    const blocks = [
        { icon: "📜", name: "Правовые основы", percent: state.journal.block1 },
        { icon: "🔫", name: "Оружие и безопасность", percent: state.journal.block2 },
        { icon: "🦌", name: "Биология и практика", percent: state.journal.block3 },
    ];
    const weakest = [...blocks].sort((left, right) => left.percent - right.percent)[0];
    const routeTask = state.bootstrap.route?.current_task?.task;

    return [
        `${user.questions_completed}/257 · точность ${user.accuracy}%.`,
        `Слабее всего: «${weakest.icon} ${weakest.name}» (${weakest.percent}%).`,
        routeTask ? `Сегодня: ${routeTask.icon} ${routeTask.name}.` : null,
    ]
        .filter(Boolean)
        .join("\n");
}

function buildAiHistoryPayload() {
    return state.aiHistory
        .filter((item) => item.role === "user" || item.role === "assistant")
        .slice(-8)
        .map((item) => ({ role: item.role, text: String(item.text || "").slice(0, 400) }));
}

function getAiStatusText(isBusy = false) {
    if (isBusy) {
        return "Думаю…";
    }

    const ai = state.bootstrap?.ai;
    if (ai?.configured) {
        return ai.provider === "groq" ? "Groq AI" : "AI";
    }

    return "Онлайн";
}

function applyAiMeta() {
    if (!aiStatus) {
        return;
    }
    aiStatus.textContent = getAiStatusText(state.aiBusy);
}

function buildDefaultAiPrompts() {
    return [
        "Что мне подтянуть первым?",
        "Составь план на сегодня",
        "Как лучше разобрать ошибки?",
        "Готов ли я к экзамену?",
    ];
}

function renderAiPrompts(prompts = []) {
    state.aiSuggestions = prompts;
    aiPromptGrid.innerHTML = prompts.map((prompt) => createAiPromptButton(prompt)).join("");
}

function renderAiThread() {
    if (!state.aiHistory.length) {
        aiThread.innerHTML = '<div class="empty-state">Задайте вопрос — разберём прогресс и ошибки.</div>';
        return;
    }

    aiThread.innerHTML = state.aiHistory
        .map((item) => {
            const isUser = item.role === "user";
            return `
                <article class="ai-message ${isUser ? "is-user" : "is-assistant"}">
                    ${isUser ? "" : `<span class="ai-avatar"><img src="${AI_AVATAR_IMAGE}" alt="${AI_COACH_NAME}"></span>`}
                    <div class="ai-bubble-wrap">
                        <div class="ai-bubble ${isUser ? "is-user" : "is-assistant"}">${formatRichText(item.text)}</div>
                        <div class="ai-meta">${isUser ? "Вы" : AI_COACH_NAME} · ${escapeHtml(item.time)}</div>
                    </div>
                </article>
            `;
        })
        .join("");
    aiThread.scrollTop = aiThread.scrollHeight;
}

function pushAiMessage(role, text) {
    state.aiHistory.push({ role, text, time: nowLabel() });
    renderAiThread();
}

function ensureAiBootstrapped(force = false) {
    if (!force && state.aiHistory.length) {
        if (!state.aiSuggestions.length) {
            renderAiPrompts(!hasPremiumAccess() && !state.bootstrap?.free_mode ? [] : buildDefaultAiPrompts());
        }
        return;
    }

    if (!hasPremiumAccess() && !state.bootstrap?.free_mode) {
        state.aiHistory = [
            {
                role: "assistant",
                text: "AI-ассистент входит в PREMIUM. После оплаты он откроет персональные подсказки по ошибкам, маршруту и экзамену.",
                time: nowLabel(),
            },
        ];
        renderAiPrompts([]);
        renderAiThread();
        applyAiMeta();
        return;
    }

    state.aiHistory = [
        {
            role: "assistant",
            text: buildAiWelcomeMessage(),
            time: nowLabel(),
        },
    ];
    renderAiPrompts(buildDefaultAiPrompts());
    renderAiThread();
    applyAiMeta();
}

function setAiBusy(isBusy) {
    state.aiBusy = isBusy;
    aiSendButton.disabled = isBusy;
    aiInput.disabled = isBusy;
    applyAiMeta();
}

function autosizeAiInput() {
    aiInput.style.height = "0px";
    aiInput.style.height = `${Math.min(aiInput.scrollHeight, 148)}px`;
}

async function submitAiMessage(rawMessage) {
    const message = String(rawMessage || "").trim();
    if (!message || state.aiBusy) {
        return;
    }

    if (!hasPremiumAccess() && !state.bootstrap?.free_mode) {
        renderPremiumSheet();
        showToast("AI-ассистент доступен только в PREMIUM");
        return;
    }

    pushAiMessage("user", message);
    renderAiPrompts([]);
    aiInput.value = "";
    autosizeAiInput();
    setAiBusy(true);
    pulse("light");

    try {
        const payload = await api("/api/ai/chat", {
            method: "POST",
            body: JSON.stringify({
                message,
                history: buildAiHistoryPayload(),
            }),
        });
        pushAiMessage("assistant", payload.reply || "Пока не удалось собрать ответ. Попробуйте уточнить вопрос.");
        renderAiPrompts(payload.quick_replies || buildDefaultAiPrompts());
        if (payload.fallback) {
            const reason = payload.error || "Groq AI недоступен с сервера";
            showToast(`${reason} — ответ по шаблону.`);
        }
        pulse("success");
    } catch (error) {
        if (maybeOpenPremiumFromError(error, "AI-ассистент доступен только в PREMIUM")) {
            state.aiHistory.pop();
            renderAiThread();
            setAiBusy(false);
            return;
        }
        pushAiMessage("assistant", `Не удалось получить ответ: ${error.message}`);
        renderAiPrompts(buildDefaultAiPrompts());
        showToast(error.message);
    } finally {
        setAiBusy(false);
    }
}

function renderBootstrap() {
    const data = state.bootstrap;
    if (!data) {
        return;
    }
    document.body.dataset.accessLevel = hasPremiumAccess() ? "premium" : (data.free_mode ? "beta" : "basic");
    const offer = premiumOffer();
    const access = currentAccessBadge();
    const routeLocked = !hasRouteAccess(data.route);
    const freeRouteDays = routeFreeDays();

    const fullName = [data.user.first_name, data.user.last_name].filter(Boolean).join(" ").trim() || "Охотник";
    const displayName = fullName.replace(/^ONEHUNT\s+/i, "").trim() || fullName;
    const heroName = displayName.length > 16 ? (data.user.first_name || displayName.split(" ")[0]) : displayName;
    const routeTask = data.route?.current_task?.task;
    const progressPct = Math.min(100, Math.round((data.user.questions_completed / 257) * 100));
    document.getElementById("homeGreeting")?.replaceChildren(
        document.createTextNode(data.user.questions_completed ? `Привет, ${heroName}` : "Добро пожаловать"),
    );
    document.getElementById("homeHeading")?.replaceChildren(document.createTextNode("Подготовка к экзамену"));
    document.getElementById("homeSummary") &&
        (document.getElementById("homeSummary").textContent = `${data.user.rank.icon} ${data.user.rank.name} · ${data.user.questions_completed}/257 · точность ${data.user.accuracy}%`);

    const progressRing = document.getElementById("homeProgressRing");
    const progressValue = document.getElementById("homeProgressValue");
    if (progressRing) {
        progressRing.style.setProperty("--progress", String(progressPct));
    }
    if (progressValue) {
        progressValue.textContent = `${progressPct}%`;
    }

    document.getElementById("headerStreak")?.replaceChildren(
        document.createTextNode(`🔥 ${data.user.streak_days}`),
    );
    document.getElementById("headerCoins")?.replaceChildren(
        document.createTextNode(`🪙 ${data.user.coins}`),
    );

    if (headerProfileButton) {
        headerProfileButton.textContent = displayName || "Профиль";
    }
    document.getElementById("statusLabel")?.replaceChildren(document.createTextNode(data.free_mode ? "Бета" : "ONEHUNT"));
    const heroTitle = document.getElementById("heroTitle");
    const heroText = document.getElementById("heroText");
    if (heroTitle) {
        heroTitle.textContent = "Подготовка";
    }
    if (heroText) {
        heroText.textContent = `${heroName} · ${data.user.rank.icon} ${data.user.rank.name} · ${data.user.questions_completed}/257 · ${data.user.accuracy}%`;
    }

    const continueButton = document.getElementById("homeContinueButton");
    if (continueButton) {
        if (routeTask && !routeLocked) {
            continueButton.textContent = `Продолжить: ${routeTask.icon} ${routeTask.name}`;
        } else if (routeLocked) {
            continueButton.textContent = "Открыть PREMIUM";
        } else {
            continueButton.textContent = "Начать тренировку";
        }
    }

    const heroBadges = document.getElementById("heroBadges");
    if (heroBadges) {
        heroBadges.innerHTML = `
        ${createMetricPill("Ранг", `${data.user.rank.icon} ${data.user.rank.name}`)}
        ${createMetricPill("Маршрут", `${data.route.percent}%`)}
        ${createMetricPill("Серия", `${data.user.streak_days} дн.`)}
        ${createMetricPill("Экзамен", `${data.exam.pass_percent}%`)}
    `;
    }
    document.getElementById("homeStats").innerHTML = `
        ${createStatCard("Пройдено", `${data.user.questions_completed}/257`)}
        ${createStatCard("Точность", `${data.user.accuracy}%`)}
        ${createStatCard("XP", `${data.user.xp_total}`)}
        ${createStatCard("Монеты", `${data.user.coins}`)}
    `;
    const quoteEyebrow = document.getElementById("quoteEyebrow");
    const quoteText = document.getElementById("quoteText");
    if (quoteEyebrow) {
        quoteEyebrow.textContent = routeTask ? "Сегодняшний фокус" : "Что такое ONEHUNT";
    }
    if (quoteText) {
        quoteText.textContent = routeTask
            ? `Сегодня в фокусе: ${routeTask.icon} ${routeTask.name}. ${routeTask.goal}.`
            : "ONEHUNT помогает спокойно подготовиться к охотминимуму: внутри 257 официальных вопросов, 14-дневный путь, тренировки, экзамен, разбор ошибок и AI-помощник.";
    }
    document.getElementById("homeRouteCard").innerHTML = `
        <div class="panel-head">
            <h2>Маршрут · день ${data.route.current_day}</h2>
            <span>${data.route.completed}/14</span>
        </div>
        <p class="panel-lead">${
            routeLocked
                ? `День ${data.route.current_day} · нужен PREMIUM`
                : hasPremiumAccess()
                  ? `День ${data.route.current_day}/14 · ${data.route.percent}%`
                  : `День ${data.route.current_day}/${freeRouteDays}`
        }</p>
        ${
            data.route.current_task
                ? `<button class="btn btn-primary btn-block" id="homeRouteStart" type="button">${routeLocked ? "Открыть PREMIUM" : hasPremiumAccess() ? "Открыть задачу дня" : "Открыть бесплатный день"}</button>`
                : `<p class="panel-lead">Текущая задача пока не найдена.</p>`
        }
    `;

    const guideBanner = document.getElementById("guideBannerButton");
    if (guideBanner) {
        const bannerTitle = hasPremiumAccess() ? "PREMIUM активен" : "PREMIUM";
        const bannerSubtitle = hasPremiumAccess()
            ? access.note
            : `${offer.price_rub} ₽ · пожизненный доступ`;
        guideBanner.querySelector(".offer-banner-title").textContent = bannerTitle;
        guideBanner.querySelector(".offer-banner-subtitle").textContent = bannerSubtitle;
        const bannerMeta = guideBanner.querySelector(".offer-banner-meta");
        if (bannerMeta) {
            bannerMeta.textContent = "";
            bannerMeta.classList.add("hidden");
        }
        guideBanner.querySelector(".offer-banner-image").src = PREMIUM_BANNER_IMAGE;
    }

    const routeTaskButton = document.getElementById("routeTaskButton");
    if (routeTaskButton) {
        const titleNode = routeTaskButton.querySelector(".mode-row-body strong") || routeTaskButton.querySelector("strong");
        const copyNode = routeTaskButton.querySelector(".mode-row-body span") || routeTaskButton.querySelector("span:not(.mode-row-icon):not(.mode-row-chevron)");
        if (titleNode) {
            titleNode.textContent = routeLocked ? "Маршрут дня · PREMIUM" : hasPremiumAccess() ? "Маршрут дня" : `День ${data.route.current_day} · бесплатно`;
        }
        if (copyNode) {
            copyNode.textContent = routeLocked
                ? `После ${freeRouteDays}-го дня нужен PREMIUM`
                : hasPremiumAccess()
                  ? "Открыть текущий шаг подготовки"
                  : `Открыть день ${data.route.current_day} из ${freeRouteDays}`;
        }
    }

    document.getElementById("blockGrid").innerHTML = data.blocks
        .map(
            (block) => `
                <button class="block-row" type="button" data-start-mode="trail" data-block-id="${block.id}">
                    <strong>${block.icon} ${block.name}</strong>
                    <span>${block.description}</span>
                </button>
            `,
        )
        .join("");
}

function renderRouteCard(route, container, compact = false) {
    const routeLocked = !hasRouteAccess(route);
    const freeDays = Number(route.free_days || routeFreeDays());
    const days = (route.days || []).slice(0, compact ? 6 : route.days.length);
    const statusLabel = (day) => {
        if (day.locked) {
            return { icon: "🔒", copy: "PREMIUM" };
        }
        if (day.status === "done") {
            return { icon: "✓", copy: "Пройдено" };
        }
        if (day.status === "today") {
            return { icon: "●", copy: "Текущий шаг" };
        }
        return { icon: "○", copy: "Еще не открыт" };
    };
    container.innerHTML = `
        <div class="panel-head">
            <h2>${compact ? "Маршрут 14 дней" : "Маршрут подготовки"}</h2>
            <span>${route.completed}/14</span>
        </div>
        ${
            route.current_task
                ? `<p class="panel-lead">${
                      routeLocked
                          ? `День ${route.current_day} · нужен PREMIUM`
                          : hasPremiumAccess()
                            ? `${route.current_task.task.icon} ${route.current_task.task.name}`
                            : `День ${route.current_day}/${freeDays}`
                  }</p>
                   <button class="btn btn-primary btn-block route-task-launch" type="button">${routeLocked ? "Открыть PREMIUM" : hasPremiumAccess() ? "Начать задачу дня" : "Начать бесплатный день"}</button>`
                : `<p class="panel-lead">Текущая задача не найдена.</p>`
        }
        <div class="route-timeline">
            ${days
                .map(
                    (day) => {
                        const status = statusLabel(day);
                        return `
                        <div class="route-step" data-status="${day.status}" data-locked="${day.locked ? "true" : "false"}">
                            <strong><span>${status.icon} День ${day.day}</span><em>${status.copy}</em></strong>
                            <span>${day.task.icon} ${day.task.name}</span>
                            <small>${day.task.goal}</small>
                        </div>
                    `;
                    },
                )
                .join("")}
        </div>
    `;
}

function setAuthenticatedUi(authenticated) {
    const authScreen = document.getElementById("screen-auth");
    authScreen?.classList.toggle("screen-active", !authenticated);
    authScreen?.classList.toggle("hidden", authenticated);
    bottomNav?.classList.toggle("hidden", !authenticated);
    siteFooter?.classList.toggle("hidden", !authenticated || APP_MODE === "miniapp");
    logoutButton?.classList.toggle("hidden", !authenticated || APP_MODE !== "site");
    headerProfileButton?.classList.toggle("hidden", !authenticated);

    screens.forEach((screen) => {
        if (screen.id === "screen-auth") {
            return;
        }
        screen.classList.toggle("hidden", !authenticated);
    });

    if (!authenticated) {
        navButtons.forEach((button) => button.classList.remove("active"));
        setAuthMode(state.authMode || "login");
        return;
    }

    const activeNav = [...navButtons].find((button) => button.classList.contains("active"))?.dataset.screen || "home";
    switchScreen(activeNav);
}

async function restoreSession() {
    if (APP_MODE !== "site") {
        return null;
    }
    const payload = await api("/api/auth/session");
    return payload.user || null;
}

async function login(email, password) {
    return api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
    });
}

async function register(name, email, password) {
    return api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ display_name: name, email, password }),
    });
}

async function logout() {
    await api("/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
    state.bootstrap = null;
    state.daily = null;
    state.journal = null;
    state.progress = null;
    state.achievements = null;
    state.history = null;
    state.cards = null;
    state.aiHistory = [];
    setAuthenticatedUi(false);
    showToast("Вы вышли из аккаунта");
}

function renderDaily() {
    const daily = state.daily;
    if (!daily) {
        return;
    }

    const questionCard = document.getElementById("dailyQuestionCard");
    if (!daily.question) {
        questionCard.innerHTML = `<div class="panel-head"><h2>Вопрос дня</h2></div><p class="panel-lead">Сегодня вопрос дня не найден.</p>`;
    } else if (daily.answered) {
        questionCard.innerHTML = `
            <div class="panel-head"><h2>✓ Вопрос дня закрыт</h2><span>Завтра новый</span></div>
            <p class="panel-lead">${daily.question.text}</p>
        `;
    } else {
        questionCard.innerHTML = `
            <div class="panel-head"><h2>Вопрос дня</h2><span>1 ответ</span></div>
            <p class="quiz-question">${daily.question.text}</p>
            <div class="daily-answer-list">
                ${daily.question.options
                    .map(
                        (item) => `
                            <button class="daily-answer-card" data-daily-answer="${item.key}" type="button">
                                <span class="daily-answer-key">${item.label}</span>
                                <strong>${item.text}</strong>
                            </button>`,
                    )
                    .join("")}
            </div>
        `;
    }

    document.getElementById("dailyChallengeCard").innerHTML = `
        <div class="panel-head">
            <h2>${daily.challenge.config.icon} ${daily.challenge.config.name}</h2>
            <span>${daily.challenge.completed ? "Готово" : daily.challenge.attempts ? "В процессе" : "Новый"}</span>
        </div>
        <p class="panel-lead">${daily.challenge.config.description}</p>
        <p class="panel-lead">+${daily.challenge.config.xp} XP · +${daily.challenge.config.coins} 🪙</p>
    `;

    renderRouteCard(daily.route, document.getElementById("routeCard"), true);
}
function renderCards() {
    if (!state.cards) {
        if (!hasPremiumAccess() && !state.bootstrap?.free_mode) {
            document.getElementById("cardsSummary").textContent = "PREMIUM";
            document.getElementById("cardCategories").innerHTML = "";
            document.getElementById("cardsList").innerHTML =
                '<button class="ghost-button" type="button" data-premium-entry="cards">Открыть PREMIUM</button>';
        }
        return;
    }
    if (!state.selectedCategory || !state.cards.categories.some((item) => item.name === state.selectedCategory)) {
        state.selectedCategory = state.cards.categories[0]?.name || null;
    }

    document.getElementById("cardsSummary").textContent = `Изучено ${state.cards.viewed}/${state.cards.total} карточек (${state.cards.percent}%).`;
    document.getElementById("cardCategories").innerHTML = state.cards.categories
        .map(
            (item) => `
                <button class="category-chip ${state.selectedCategory === item.name ? "is-active" : ""}" type="button" data-category="${item.name}">
                    <strong>${item.name}</strong>
                    <span>${item.count} карточек</span>
                </button>
            `,
        )
        .join("");
}

function renderProfile() {
    const bootstrap = state.bootstrap;
    const journal = state.journal;
    if (!bootstrap || !journal) {
        return;
    }

    const access = currentAccessBadge();
    const fullName = [bootstrap.user.first_name, bootstrap.user.last_name].filter(Boolean).join(" ").trim() || "ONEHUNT";
    const username = bootstrap.user.username ? `@${bootstrap.user.username}` : "профиль ONEHUNT";

    document.getElementById("profileIdentityCard").innerHTML = `
        <div class="profile-banner-inner">
            <div class="profile-identity-copy">
                <h2>${escapeHtml(fullName)}</h2>
                <p class="panel-lead">${escapeHtml(username)} · ${bootstrap.user.rank.icon} ${escapeHtml(bootstrap.user.rank.name)}</p>
            </div>
            <div class="profile-identity-side">
                <span class="access-pill ${access.className}">${access.label}</span>
            </div>
        </div>
    `;

    document.getElementById("profileStats").innerHTML = `
        ${createStatCard("Уровень", `${journal.level}`)}
        ${createStatCard("Достижения", `${journal.achievements}`)}
        ${createStatCard("Избранное", `${journal.starred}`)}
        ${createStatCard("Следующий ранг", journal.next_rank ? `${journal.next_rank.icon} ${journal.next_rank.name}` : "Максимум")}
    `;

    const blockProgress = document.getElementById("blockProgress");
    if (blockProgress) {
        blockProgress.innerHTML = [
            { label: "📜 Право", value: journal.block1 },
            { label: "🔫 Безопасность", value: journal.block2 },
            { label: "🦌 Природа", value: journal.block3 },
        ]
            .map(
                (item) => `
                <div class="achievement-item">
                    <strong>${item.label}</strong>
                    <span>${item.value}%</span>
                    <div class="achievement-progress"><span style="width:${Math.max(4, item.value)}%"></span></div>
                </div>
            `,
            )
            .join("");
    }

    if (state.progress?.points?.length) {
        const chartEl = document.getElementById("progressChart");
        chartEl.classList.remove("is-empty");
        chartEl.innerHTML = state.progress.points
            .map(
                (point, index) => `
                    <div class="chart-bar">
                        <div class="chart-track"><span class="chart-fill" style="height:${Math.max(point, 8)}%"></span></div>
                        <div class="chart-label">Д${index + 1}</div>
                    </div>
                `,
            )
            .join("");
    } else {
        const chartEl = document.getElementById("progressChart");
        chartEl.classList.add("is-empty");
        if (!hasPremiumAccess() && !bootstrap.free_mode) {
            chartEl.innerHTML = '<div class="empty-state">Нужен PREMIUM.</div>';
        } else {
            chartEl.innerHTML = '<div class="empty-state">Нет данных за 14 дней.</div>';
        }
    }

    const nearest = state.achievements?.nearest || [];
    document.getElementById("achievementsList").innerHTML = nearest.length
        ? nearest
              .map(
                  (item) => `
                      <article class="achievement-item">
                          <strong>${item.name}</strong>
                          <span>${item.description}</span>
                          <div class="achievement-progress"><span style="width:${Math.max(4, item.percent)}%"></span></div>
                          <small>${item.current}/${item.target} (${item.percent}%)</small>
                      </article>
                  `,
              )
              .join("")
        : `<div class="info-line">Пока нет достижений.</div>`;

    const history = state.history?.items || [];
    document.getElementById("historyList").innerHTML = history.length
        ? history
              .map(
                  (item, index) => `
                      <article class="history-item">
                          <strong>#${index + 1} — ${item.score_percent}% ${item.passed ? "✅" : "❌"}</strong>
                          <span>${new Date(item.started_at).toLocaleDateString("ru-RU")} · ${item.time_spent_minutes || 0} мин · ${item.correct_count}/${item.correct_count + item.wrong_count}</span>
                      </article>
                  `,
              )
              .join("")
        : `<div class="info-line">История пуста.</div>`;

    document.getElementById("settingQuestions").value = String(bootstrap.user.settings.questions_per_session || 20);
    document.getElementById("settingTimer").value = String(bootstrap.user.settings.timer_seconds || 0);
    document.getElementById("settingExplanations").checked = Boolean(bootstrap.user.settings.show_explanations);
    document.getElementById("settingReminder").checked = Boolean(bootstrap.user.daily_reminder);
    document.getElementById("settingHour").value = bootstrap.user.reminder_hour ?? 9;
}

function updateAnswerHint(message, tone = "neutral") {
    const hint = document.getElementById("answerHint");
    hint.textContent = message;
    hint.classList.remove("is-success", "is-error");
    if (tone === "success") {
        hint.classList.add("is-success");
    } else if (tone === "error") {
        hint.classList.add("is-error");
    }
}

function setQuestionOptionsEnabled(enabled) {
    document.querySelectorAll("#questionOptions .option-item").forEach((button) => {
        button.disabled = !enabled;
    });
}

function applyAnswerFeedback(result) {
    const options = document.querySelectorAll("#questionOptions .option-item");
    options.forEach((button) => {
        const answer = button.dataset.answer;
        button.classList.remove("is-pending");
        button.classList.add("is-muted");

        if (answer === result.correct_answer) {
            button.classList.add("is-correct");
            button.classList.remove("is-muted");
        }

        if (answer === result.selected_answer) {
            button.classList.add("is-selected");
            button.classList.remove("is-muted");
            if (!result.is_correct) {
                button.classList.add("is-wrong");
            }
        }
    });

    if (result.is_correct) {
        updateAnswerHint(
            `Верно. +${result.xp_added} XP и +${result.coins_added} монет. Дальше можно идти сразу, кнопка уже наверху.`,
            "success",
        );
    } else {
        updateAnswerHint(
            `Промах. Правильный вариант: ${result.correct_answer.toUpperCase()}. Сверху уже есть кнопка перехода к следующему вопросу.`,
            "error",
        );
    }
}

function renderQuestion(questionState) {
    state.activeSession = questionState;
    state.pendingNextQuestion = false;
    state.lastQuestionId = questionState.question.id;
    state.answerLocked = false;

    sessionOverlay.classList.remove("hidden");
    syncTelegramBackButton();
    pulse("medium");

    document.getElementById("sessionTitle").textContent = questionState.title;
    document.getElementById("questionCaption").textContent = sessionModeLabel(questionState.mode);
    const progressPct = questionState.progress.total
        ? Math.round((questionState.progress.current / questionState.progress.total) * 100)
        : 0;
    document.getElementById("quizProgressFill")?.style.setProperty("width", `${progressPct}%`);
    document.getElementById("sessionMeta").innerHTML = `
        <span class="meta-pill">${questionState.progress.current}/${questionState.progress.total}</span>
        <span class="meta-pill">✅ ${questionState.progress.correct}</span>
        <span class="meta-pill">❌ ${questionState.progress.wrong}</span>
        ${
            questionState.progress.timer
                ? `<span class="meta-pill" data-session-timer>Таймер ${formatTimerValue(questionState.progress.timer.left_seconds)} · ${questionState.progress.timer.label}</span>`
                : ""
        }
    `;
    document.getElementById("questionText").textContent = questionState.question.text;
    document.getElementById("questionOptions").innerHTML = questionState.question.options
        .map(
            (item) => `
                <button class="option-item" type="button" data-answer="${item.key}">
                    <span class="option-key">${item.label}</span>
                    <div class="option-body">
                        <strong>${item.text}</strong>
                        <small class="option-meta">${questionState.question.block_name || "ONEHUNT"}</small>
                    </div>
                </button>
            `,
        )
        .join("");

    const image = document.getElementById("sessionImage");
    if (questionState.question.image_url) {
        image.src = questionState.question.image_url;
        image.classList.remove("hidden");
    } else {
        image.classList.add("hidden");
        image.removeAttribute("src");
    }

    document.getElementById("starQuestionButton").textContent = "⭐ В избранное";
    updateAnswerHint(baseAnswerHint(questionState.mode));

    const resultPanel = document.getElementById("resultPanel");
    resultPanel.className = "quiz-result hidden";
    resultPanel.innerHTML = "";
    setQuestionOptionsEnabled(true);
    startSessionTimer(questionState.progress.timer || null);
}

function buildSummaryHtml(summary) {
    if (!summary) {
        return "";
    }
    if (summary.type === "exam") {
        return `<div class="achievement-item"><strong>${summary.passed ? "🏆 Экзамен пройден" : "📘 Экзамен завершен"}</strong><span>${summary.correct_count}/${summary.questions_count} · ${summary.score_percent}% · ${summary.time_spent_minutes} мин</span></div>`;
    }
    if (summary.type === "duel") {
        return `<div class="achievement-item"><strong>${summary.user_won ? "🏆 Вы победили" : "🦌 Михалыч оказался сильнее"}</strong><span>Ваш счет ${summary.user_score}, Михалыч ${summary.bot_score}, время ${summary.duration}</span></div>`;
    }
    return `<div class="achievement-item"><strong>${summary.timeout ? "⏱ Время вышло" : "🏁 Сессия завершена"}</strong><span>${summary.correct} верно · ${summary.wrong} ошибок · ${summary.accuracy}% · ${summary.duration}</span></div>`;
}

function renderResult(result, hasNext, summary) {
    stopSessionTimer();
    const resultPanel = document.getElementById("resultPanel");
    const modeClass = result ? (result.is_correct ? "result-correct" : "result-wrong") : "result-neutral";
    resultPanel.className = `quiz-result ${modeClass}`;
    resultPanel.innerHTML = `
        <div class="result-actions">
            ${hasNext ? `<button class="btn btn-primary" id="nextQuestionButton" type="button">Следующий вопрос</button>` : `<button class="btn btn-primary" id="finishSessionButton" type="button">Завершить</button>`}
            <button class="btn btn-ghost" id="backToAppButton" type="button">В приложение</button>
        </div>
        <div class="result-scroll">
            ${
                result
                    ? `
                        <h3 class="result-title">${result.is_correct ? "✓ Верно" : "✗ Промах"}</h3>
                        <p class="result-copy">Ваш: ${result.selected_answer.toUpperCase()} · Верный: ${result.correct_answer.toUpperCase()}</p>
                        <p class="result-copy">+${result.xp_added} XP · +${result.coins_added} 🪙</p>
                        ${result.explanation ? `<p class="result-copy"><strong>Почему:</strong> ${result.explanation}</p>` : ""}
                        ${result.mnemonic ? `<p class="result-copy"><strong>Подсказка:</strong> ${result.mnemonic}</p>` : ""}
                    `
                    : ""
            }
            ${buildSummaryHtml(summary)}
        </div>
    `;
    resultPanel.classList.remove("hidden");
    resultPanel.scrollTop = 0;
    state.pendingNextQuestion = hasNext;
}

function closeSessionOverlay() {
    sessionOverlay.classList.add("hidden");
    state.activeSession = null;
    state.pendingNextQuestion = false;
    state.answerLocked = false;
    stopSessionTimer();
    syncTelegramBackButton();
}

async function startSession(mode, extra = {}) {
    pulse("light");
    try {
        const data = await api("/api/session/start", { method: "POST", body: JSON.stringify({ mode, ...extra }) });
        renderQuestion(data);
    } catch (error) {
        if (maybeOpenPremiumFromError(error)) {
            return;
        }
        showToast(error.message);
    }
}

async function answerQuestion(answer) {
    if (!state.activeSession || state.answerLocked) {
        return;
    }

    state.answerLocked = true;
    const selectedButton = document.querySelector(`#questionOptions .option-item[data-answer="${answer}"]`);
    selectedButton?.classList.add("is-pending");
    setQuestionOptionsEnabled(false);
    updateAnswerHint("Проверяем ответ...", "neutral");
    pulse("medium");

    try {
        const data = await api("/api/session/answer", {
            method: "POST",
            body: JSON.stringify({
                session_id: state.activeSession.session_id,
                question_id: state.lastQuestionId,
                answer,
            }),
        });

        if (data.result) {
            applyAnswerFeedback(data.result);
        }
        renderResult(data.result, Boolean(data.has_next), data.summary);
    } catch (error) {
        state.answerLocked = false;
        selectedButton?.classList.remove("is-pending");
        setQuestionOptionsEnabled(true);
        if (error.status === 409) {
            updateAnswerHint("Вопрос уже сменился. Обновляем экран...", "error");
            showToast(error.message || "Вопрос сменился, обновляем экран");
            await loadNextQuestion().catch(() => hydrate());
            return;
        }
        if (error.status === 404) {
            updateAnswerHint("Не нашли текущий вопрос. Подгружаем следующий...", "error");
            showToast(error.message || "Вопрос не найден, обновляем сессию");
            await loadNextQuestion().catch(() => hydrate());
            return;
        }
        updateAnswerHint("Не удалось проверить ответ. Попробуйте еще раз.", "error");
        showToast(error.message);
    }
}

async function loadNextQuestion() {
    if (!state.activeSession) {
        return;
    }
    pulse("light");
    try {
        const data = await api("/api/session/next", {
            method: "POST",
            body: JSON.stringify({ session_id: state.activeSession.session_id }),
        });
        renderQuestion(data);
    } catch (error) {
        showToast(error.message);
    }
}
async function loadCardsCategory(category) {
    try {
        state.selectedCategory = category;
        renderCards();
        document.getElementById("cardsList").innerHTML = `<div class="empty-state">Загружаем карточки категории «${escapeHtml(category)}»...</div>`;
        const payload = await api(`/api/cards/${encodeURIComponent(category)}`);
        document.getElementById("cardsList").innerHTML =
            payload.items
                .map(
                    (item) => `
                        <button class="card-tile" type="button" data-card-id="${item.id}">
                            <strong>${item.name}</strong>
                            <span>${item.latin_name || "Без латинского названия"}</span>
                        </button>
                    `,
                )
                .join("") || `<div class="empty-state">В этой категории пока нет карточек.</div>`;
    } catch (error) {
        if (maybeOpenPremiumFromError(error, "Карточки доступны только в PREMIUM")) {
            return;
        }
        showToast(error.message);
    }
}

async function openCardDetails(cardId) {
    try {
        const payload = await api(`/api/card/${cardId}`);
        document.getElementById("sheetContent").innerHTML = `
            <p class="eyebrow">Карточка</p>
            <div class="section-head"><h2>${payload.card.name}</h2><span>${payload.card.latin_name || payload.card.category}</span></div>
            <div class="info-line">Категория: ${payload.card.category}</div>
            <div class="info-line">Семейство: ${payload.card.family_name || "—"}</div>
            <div class="info-line">Вес: ${payload.card.weight || "—"}</div>
            <div class="info-line">Среда: ${payload.card.habitat || "—"}</div>
            <div class="info-line">Охота: ${payload.card.hunting_season || "—"}</div>
            <div class="info-line">След: ${payload.card.track_description || "—"}</div>
            <div class="info-line">Вопросов по теме: ${payload.question_count}</div>
            <div class="info-line">Правильно: ${payload.correct_count} (${payload.percent}%)</div>
        `;
        detailSheet.classList.remove("hidden");
        syncTelegramBackButton();
        pulse("light");
    } catch (error) {
        if (maybeOpenPremiumFromError(error, "Карточки доступны только в PREMIUM")) {
            return;
        }
        showToast(error.message);
    }
}

async function saveSettings() {
    try {
        await api("/api/settings", {
            method: "POST",
            body: JSON.stringify({
                questions_per_session: Number(document.getElementById("settingQuestions").value),
                timer_seconds: Number(document.getElementById("settingTimer").value),
                show_explanations: document.getElementById("settingExplanations").checked,
                daily_reminder: document.getElementById("settingReminder").checked,
                reminder_hour: Number(document.getElementById("settingHour").value || 9),
            }),
        });
        pulse("success");
        showToast("Настройки сохранены");
        await hydrate();
    } catch (error) {
        showToast(error.message);
    }
}

async function resetProgress() {
    if (!window.confirm("Сбросить прогресс?")) {
        return;
    }
    try {
        await api("/api/reset-progress", { method: "POST", body: JSON.stringify({}) });
        pulse("rigid");
        showToast("Прогресс сброшен");
        await hydrate();
    } catch (error) {
        showToast(error.message);
    }
}

async function submitDailyAnswer(answer) {
    try {
        const payload = await api("/api/daily/answer", { method: "POST", body: JSON.stringify({ answer }) });
        pulse(payload.result?.is_correct ? "success" : "light");
        showToast(payload.result?.is_correct ? "Верно" : "Промах");
        await hydrate();
    } catch (error) {
        showToast(error.message);
    }
}

async function launchRouteTask() {
    if (!hasRouteAccess(state.bootstrap?.route)) {
        renderPremiumSheet();
        showToast(`Первые ${routeFreeDays()} дня маршрута бесплатны, дальше нужен PREMIUM`);
        return;
    }
    try {
        const data = await api("/api/route/start-task", { method: "POST", body: JSON.stringify({}) });
        renderQuestion(data);
    } catch (error) {
        if (maybeOpenPremiumFromError(error, `Первые ${routeFreeDays()} дня маршрута бесплатны, дальше нужен PREMIUM`)) {
            return;
        }
        showToast(error.message);
    }
}

async function toggleStar() {
    if (!state.lastQuestionId) {
        return;
    }
    try {
        const payload = await api("/api/star/toggle", {
            method: "POST",
            body: JSON.stringify({ question_id: state.lastQuestionId }),
        });
        document.getElementById("starQuestionButton").textContent = payload.starred ? "⭐ Убрать" : "⭐ В избранное";
        pulse("light");
        showToast(payload.starred ? "Добавлено в избранное" : "Убрано из избранного");
    } catch (error) {
        showToast(error.message);
    }
}

async function hydrate() {
    try {
        const [bootstrap, daily, journal, progress, achievements, history, cards] = await Promise.all([
            api("/api/bootstrap"),
            api("/api/daily"),
            api("/api/journal"),
            api("/api/progress").catch(() => null),
            api("/api/achievements"),
            api("/api/history"),
            api("/api/cards").catch(() => null),
        ]);

        state.bootstrap = bootstrap;
        state.daily = daily;
        state.journal = journal;
        state.progress = progress;
        state.achievements = achievements;
        state.history = history;
        state.cards = cards;
        setAuthenticatedUi(true);

        renderBootstrap();
        renderDaily();
        renderCards();
        if (cards && cards.categories.length && !document.getElementById("cardsList").innerHTML.trim()) {
            loadCardsCategory(state.selectedCategory || cards.categories[0].name);
        }
        renderProfile();
        ensureAiBootstrapped(state.aiHistory.length === 0);
        applyAiMeta();
    } catch (error) {
        setAuthenticatedUi(false);
        if (error.status === 401) {
            return;
        }
        showToast(error.message);
        const heroText = document.getElementById("heroText");
        if (heroText) {
            heroText.textContent = error.message;
        }
    }
}

document.addEventListener("click", (event) => {
    const target = event.target.closest(
        "[data-auth-tab], [data-auth-switch], [data-screen], [data-start-mode], [data-answer], [data-daily-answer], .route-task-launch, [data-category], [data-card-id], [data-ai-prompt], [data-premium-entry], #homeRouteStart",
    );
    if (!target) {
        return;
    }

    if (target.dataset.authTab) {
        setAuthMode(target.dataset.authTab);
        return;
    }
    if (target.dataset.authSwitch) {
        setAuthMode(target.dataset.authSwitch);
        return;
    }
    if (target.dataset.screen) {
        switchScreen(target.dataset.screen);
        return;
    }
    if (target.dataset.aiPrompt) {
        submitAiMessage(target.dataset.aiPrompt);
        return;
    }
    if (target.id === "homeRouteStart" || target.classList.contains("route-task-launch")) {
        launchRouteTask();
        return;
    }
    if (target.dataset.premiumEntry) {
        renderPremiumSheet();
        return;
    }
    if (target.dataset.startMode) {
        startSession(target.dataset.startMode, {
            block_id: target.dataset.blockId ? Number(target.dataset.blockId) : null,
            weak: target.dataset.weak === "true",
            timed: target.dataset.timed === "true",
        });
        return;
    }
    if (target.dataset.answer) {
        answerQuestion(target.dataset.answer);
        return;
    }
    if (target.dataset.dailyAnswer) {
        submitDailyAnswer(target.dataset.dailyAnswer);
        return;
    }
    if (target.dataset.category) {
        loadCardsCategory(target.dataset.category);
        return;
    }
    if (target.dataset.cardId) {
        openCardDetails(target.dataset.cardId);
    }
});

document.getElementById("closeSessionButton").addEventListener("click", closeSessionOverlay);
document.getElementById("sheetBackdrop").addEventListener("click", closeDetailSheet);
document.getElementById("closeSheetButton").addEventListener("click", closeDetailSheet);
document.getElementById("routeTaskButton")?.addEventListener("click", launchRouteTask);
document.getElementById("guideBannerButton")?.addEventListener("click", () => {
    pulse("medium");
    renderPremiumSheet();
});
document.getElementById("homeContinueButton")?.addEventListener("click", () => {
    const route = state.bootstrap?.route;
    if (route?.current_task && hasRouteAccess(route)) {
        launchRouteTask();
        return;
    }
    if (route && !hasRouteAccess(route)) {
        renderPremiumSheet();
        return;
    }
    startSession("training");
});
document.getElementById("saveSettingsButton").addEventListener("click", saveSettings);
document.getElementById("resetProgressButton").addEventListener("click", resetProgress);
document.getElementById("starQuestionButton").addEventListener("click", toggleStar);
headerProfileButton?.addEventListener("click", () => switchScreen("profile"));
logoutButton?.addEventListener("click", () => logout().catch((error) => showToast(error.message)));

loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await login(
            document.getElementById("loginEmail").value,
            document.getElementById("loginPassword").value,
        );
        pulse("success");
        showToast("Вход выполнен");
        await hydrate();
    } catch (error) {
        showToast(error.message);
    }
});

registerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
        await register(
            document.getElementById("registerName").value,
            document.getElementById("registerEmail").value,
            document.getElementById("registerPassword").value,
        );
        pulse("success");
        showToast("Аккаунт создан");
        await hydrate();
    } catch (error) {
        showToast(error.message);
    }
});

aiForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitAiMessage(aiInput.value);
});

aiInput.addEventListener("input", autosizeAiInput);
aiInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        aiForm.requestSubmit();
    }
});

document.addEventListener("click", (event) => {
    if (event.target.id === "nextQuestionButton" && state.pendingNextQuestion) {
        loadNextQuestion();
        return;
    }
    if (event.target.id === "finishSessionButton" || event.target.id === "backToAppButton") {
        closeSessionOverlay();
        hydrate().finally(() => window.requestAnimationFrame(scrollAppToTop));
        return;
    }
    if (event.target.closest("[data-premium-action='stars']")) {
        createPremiumInvoice("telegram_stars");
        return;
    }
    if (event.target.closest("[data-premium-action='yoomoney']")) {
        createPremiumInvoice("yoomoney");
        return;
    }
    if (event.target.closest("[data-premium-action='crypto']")) {
        createPremiumInvoice("crypto");
        return;
    }
    if (event.target.closest("[data-premium-action='open']")) {
        openPremiumCheckout();
        return;
    }
    if (event.target.closest("[data-premium-action='check']")) {
        checkPremiumInvoice();
    }
});

autosizeAiInput();
setAuthMode(state.authMode);
window.wolfLoader?.start();
if (APP_MODE === "miniapp") {
    hydrate()
        .catch(() => {
            setAuthenticatedUi(false);
            const heroText = document.getElementById("heroText");
            if (heroText) {
                heroText.textContent = "Откройте ONEHUNT из Telegram, чтобы Mini App получил ваш профиль автоматически.";
            }
        })
        .finally(() => {
            window.wolfLoader?.reset();
            window.requestAnimationFrame(scrollAppToTop);
        });
} else {
    restoreSession()
        .then((user) => {
            if (!user) {
                setAuthenticatedUi(false);
                return;
            }
            return hydrate();
        })
        .catch(() => {
            setAuthenticatedUi(false);
        })
        .finally(() => {
            window.wolfLoader?.reset();
            window.requestAnimationFrame(scrollAppToTop);
        });
}
