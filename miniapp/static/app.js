const tg = window.Telegram?.WebApp ?? null;

if (tg) {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation();
    tg.setHeaderColor("#eef6f0");
    tg.setBackgroundColor("#eef6f0");
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
    pendingNextQuestion: null,
    lastQuestionId: null,
    selectedCategory: null,
};

const screens = document.querySelectorAll(".screen");
const navButtons = document.querySelectorAll(".nav-button");
const toast = document.getElementById("toast");
const sessionOverlay = document.getElementById("sessionOverlay");
const detailSheet = document.getElementById("detailSheet");

function pulse(style = "light") {
    try {
        tg?.HapticFeedback?.impactOccurred?.(style);
    } catch (_error) {
        // ignore
    }
}

function syncTelegramBackButton() {
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

async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (tg?.initData) {
        headers.set("X-Telegram-Init-Data", tg.initData);
    }
    headers.set("Content-Type", "application/json");
    const response = await fetch(path, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.detail || "Не удалось выполнить запрос.");
    }
    return payload;
}

function switchScreen(screenId) {
    screens.forEach((screen) => screen.classList.toggle("screen-active", screen.id === `screen-${screenId}`));
    navButtons.forEach((button) => button.classList.toggle("active", button.dataset.screen === screenId));
    pulse("light");
}

function createStatCard(label, value) {
    return `<article class="stat-card"><strong>${value}</strong><span>${label}</span></article>`;
}

function renderBootstrap() {
    const data = state.bootstrap;
    if (!data) {
        return;
    }

    const fullName = [data.user.first_name, data.user.last_name].filter(Boolean).join(" ").trim() || "Охотник";
    document.getElementById("statusLabel").textContent = data.free_mode ? "Open Beta" : "Mini App";
    document.getElementById("heroTitle").textContent = `${data.user.rank.icon} ${fullName}`;
    document.getElementById("heroText").textContent = `Пройдено ${data.user.questions_completed}/257, точность ${data.user.accuracy}%, XP ${data.user.xp_total}.`;
    document.getElementById("heroBadges").innerHTML = `
        <div class="hero-badge"><strong>${data.summary.questions_count}</strong><span>вопросов в базе</span></div>
        <div class="hero-badge"><strong>${data.summary.achievements}</strong><span>достижений открыто</span></div>
        <div class="hero-badge"><strong>${data.summary.starred}</strong><span>избранных вопросов</span></div>
        <div class="hero-badge"><strong>${data.exam.questions}/${data.exam.pass_percent}%</strong><span>экзамен / порог</span></div>
    `;
    document.getElementById("homeStats").innerHTML = `
        ${createStatCard("Звание", `${data.user.rank.icon} ${data.user.rank.name}`)}
        ${createStatCard("Серия дней", `${data.user.streak_days}`)}
        ${createStatCard("Монеты", `${data.user.coins}`)}
        ${createStatCard("Лучший экзамен", `${data.user.best_exam_score}%`)}
    `;
    document.getElementById("quoteText").textContent = data.summary.quote;
    document.getElementById("homeRouteCard").innerHTML = `
        <p class="eyebrow">Маршрут</p>
        <div class="section-head">
            <h2>Текущий ритм подготовки</h2>
            <span>${data.route.completed}/14 дней выполнено</span>
        </div>
        <div class="info-line">Сегодняшний день маршрута: ${data.route.current_day}. Прогресс ${data.route.percent}%.</div>
        ${
            data.route.current_task
                ? `<button class="primary-button" id="homeRouteStart" type="button">Открыть задачу дня</button>`
                : `<div class="info-line">Текущая задача пока не найдена.</div>`
        }
    `;

    document.getElementById("blockGrid").innerHTML = data.blocks
        .map(
            (block) => `
                <button class="block-card" type="button" data-start-mode="trail" data-block-id="${block.id}">
                    <strong>${block.icon} ${block.name}</strong>
                    <span>${block.description}</span>
                </button>
            `,
        )
        .join("");
}

function renderRouteCard(route, container, compact = false) {
    const days = (route.days || []).slice(0, compact ? 6 : route.days.length);
    container.innerHTML = `
        <p class="eyebrow">Маршрут</p>
        <div class="section-head">
            <h2>${compact ? "Путь на 14 дней" : "Маршрут подготовки"}</h2>
            <span>${route.completed}/14 выполнено</span>
        </div>
        ${
            route.current_task
                ? `<div class="info-line">Сегодня: ${route.current_task.task.icon} ${route.current_task.task.name}</div>
                   <button class="primary-button route-task-launch" type="button">Начать задачу дня</button>`
                : `<div class="info-line">Текущая задача не найдена.</div>`
        }
        <div class="route-grid">
            ${days
                .map(
                    (day) => `
                        <div class="route-day" data-status="${day.status}">
                            <strong>${day.status === "done" ? "✅" : day.status === "today" ? "👉" : "⬜"} День ${day.day}</strong>
                            <span>${day.task.icon} ${day.task.name}</span>
                            <small>${day.task.goal}</small>
                        </div>
                    `,
                )
                .join("")}
        </div>
    `;
}

function renderDaily() {
    const daily = state.daily;
    if (!daily) {
        return;
    }
    const questionCard = document.getElementById("dailyQuestionCard");
    if (!daily.question) {
        questionCard.innerHTML = `<p class="eyebrow">Вопрос дня</p><div class="info-line">Сегодня вопрос дня не найден.</div>`;
    } else if (daily.answered) {
        questionCard.innerHTML = `
            <p class="eyebrow">Вопрос дня</p>
            <div class="section-head"><h2>На сегодня уже закрыто</h2><span>Возвращайтесь завтра</span></div>
            <div class="info-line">${daily.question.text}</div>
        `;
    } else {
        questionCard.innerHTML = `
            <p class="eyebrow">Вопрос дня</p>
            <div class="section-head"><h2>${daily.question.text}</h2><span>+20 XP за правильный ответ</span></div>
            <div class="answer-buttons">
                ${daily.question.options.map((item) => `<button class="answer-pick" data-daily-answer="${item.key}" type="button">${item.label}</button>`).join("")}
            </div>
        `;
    }

    document.getElementById("dailyChallengeCard").innerHTML = `
        <p class="eyebrow">Вызов дня</p>
        <div class="section-head">
            <h2>${daily.challenge.config.icon} ${daily.challenge.config.name}</h2>
            <span>${daily.challenge.completed ? "Выполнен" : "В процессе"}</span>
        </div>
        <div class="info-line">${daily.challenge.config.description}</div>
        <div class="info-line">Награда: +${daily.challenge.config.xp} XP и +${daily.challenge.config.coins} монет.</div>
    `;

    renderRouteCard(daily.route, document.getElementById("routeCard"), true);
}

function renderCards() {
    if (!state.cards) {
        return;
    }
    if (!state.selectedCategory && state.cards.categories.length) {
        state.selectedCategory = state.cards.categories[0].name;
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

    document.getElementById("profileStats").innerHTML = `
        ${createStatCard("Уровень", `${journal.level}`)}
        ${createStatCard("Достижения", `${journal.achievements}`)}
        ${createStatCard("Избранное", `${journal.starred}`)}
        ${createStatCard("Следующий ранг", journal.next_rank ? `${journal.next_rank.icon} ${journal.next_rank.name}` : "Максимум")}
    `;

    document.getElementById("blockProgress").innerHTML = [
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

    if (state.progress?.points) {
        document.getElementById("progressChart").innerHTML = state.progress.points
            .map(
                (point, index) => `
                    <div class="chart-bar">
                        <div class="chart-track"><span class="chart-fill" style="height:${Math.max(point, 8)}%"></span></div>
                        <div class="chart-label">Д${index + 1}</div>
                    </div>
                `,
            )
            .join("");
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
        : `<div class="info-line">Достижения пока ещё не появились.</div>`;

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
        : `<div class="info-line">История экзаменов пока пустая.</div>`;

    document.getElementById("settingQuestions").value = String(bootstrap.user.settings.questions_per_session || 20);
    document.getElementById("settingTimer").value = String(bootstrap.user.settings.timer_seconds || 0);
    document.getElementById("settingExplanations").checked = Boolean(bootstrap.user.settings.show_explanations);
    document.getElementById("settingReminder").checked = Boolean(bootstrap.user.daily_reminder);
    document.getElementById("settingHour").value = bootstrap.user.reminder_hour ?? 9;
}

function renderQuestion(questionState) {
    state.activeSession = questionState;
    state.pendingNextQuestion = null;
    state.lastQuestionId = questionState.question.id;
    sessionOverlay.classList.remove("hidden");
    syncTelegramBackButton();
    pulse("medium");
    document.getElementById("sessionTitle").textContent = questionState.title;
    document.getElementById("sessionMeta").innerHTML = `
        <span class="meta-pill">${questionState.progress.current}/${questionState.progress.total}</span>
        <span class="meta-pill">✅ ${questionState.progress.correct}</span>
        <span class="meta-pill">❌ ${questionState.progress.wrong}</span>
        ${questionState.progress.timer_left !== null ? `<span class="meta-pill">⏱ ${questionState.progress.timer_left} сек</span>` : ""}
    `;
    document.getElementById("questionText").textContent = questionState.question.text;
    document.getElementById("questionOptions").innerHTML = questionState.question.options
        .map(
            (item) => `
                <article class="option-item">
                    <span class="option-key">${item.label}</span>
                    <div><strong>${item.text}</strong><small>${questionState.question.block_name || ""}</small></div>
                </article>
            `,
        )
        .join("");
    document.getElementById("answerButtons").innerHTML = questionState.question.options
        .map((item) => `<button class="answer-pick" data-answer="${item.key}" type="button">${item.label}</button>`)
        .join("");

    const image = document.getElementById("sessionImage");
    if (questionState.question.image_url) {
        image.src = questionState.question.image_url;
        image.classList.remove("hidden");
    } else {
        image.classList.add("hidden");
        image.removeAttribute("src");
    }

    const resultPanel = document.getElementById("resultPanel");
    resultPanel.classList.add("hidden");
    resultPanel.innerHTML = "";
    document.getElementById("starQuestionButton").textContent = "⭐ В избранное";
}

function buildSummaryHtml(summary) {
    if (!summary) {
        return "";
    }
    if (summary.type === "exam") {
        return `<div class="achievement-item"><strong>${summary.passed ? "🏆 Экзамен пройден" : "📘 Экзамен завершён"}</strong><span>${summary.correct_count}/${summary.questions_count} · ${summary.score_percent}% · ${summary.time_spent_minutes} мин</span></div>`;
    }
    if (summary.type === "duel") {
        return `<div class="achievement-item"><strong>${summary.user_won ? "🏆 Вы победили" : "🦌 Михалыч оказался сильнее"}</strong><span>Ваш счёт ${summary.user_score}, Михалыч ${summary.bot_score}, время ${summary.duration}</span></div>`;
    }
    return `<div class="achievement-item"><strong>${summary.timeout ? "⏱ Время вышло" : "🏁 Сессия завершена"}</strong><span>${summary.correct} верно · ${summary.wrong} ошибок · ${summary.accuracy}% · ${summary.duration}</span></div>`;
}

function renderResult(result, hasNext, summary) {
    const resultPanel = document.getElementById("resultPanel");
    resultPanel.className = `result-panel ${result?.is_correct ? "result-correct" : "result-wrong"}`;
    resultPanel.innerHTML = `
        ${
            result
                ? `
                    <h3 class="result-title">${result.is_correct ? "✅ Верно" : "❌ Промах"}</h3>
                    <p class="result-copy">Ваш ответ: ${result.selected_answer.toUpperCase()} · Правильный: ${result.correct_answer.toUpperCase()}</p>
                    <p class="result-copy">+${result.xp_added} XP · +${result.coins_added} монет</p>
                    ${result.explanation ? `<p class="result-copy"><strong>Объяснение:</strong> ${result.explanation}</p>` : ""}
                    ${result.mnemonic ? `<p class="result-copy"><strong>Подсказка:</strong> ${result.mnemonic}</p>` : ""}
                `
                : ""
        }
        ${buildSummaryHtml(summary)}
        <div class="result-actions">
            ${hasNext ? `<button class="primary-button" id="nextQuestionButton" type="button">Следующий вопрос</button>` : `<button class="primary-button" id="finishSessionButton" type="button">Завершить</button>`}
            <button class="ghost-button" id="backToAppButton" type="button">Назад в приложение</button>
        </div>
    `;
    resultPanel.classList.remove("hidden");
    state.pendingNextQuestion = hasNext;
}

function closeSessionOverlay() {
    sessionOverlay.classList.add("hidden");
    state.activeSession = null;
    state.pendingNextQuestion = null;
    syncTelegramBackButton();
}

async function startSession(mode, extra = {}) {
    pulse("light");
    try {
        const data = await api("/api/session/start", { method: "POST", body: JSON.stringify({ mode, ...extra }) });
        renderQuestion(data);
    } catch (error) {
        showToast(error.message);
    }
}

async function answerQuestion(answer) {
    if (!state.activeSession) {
        return;
    }
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
        renderResult(data.result, data.has_next, data.summary);
    } catch (error) {
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
        document.getElementById("cardsList").innerHTML = `<div class="empty-state">Загружаем карточки категории «${category}»...</div>`;
        const payload = await api(`/api/cards/${encodeURIComponent(category)}`);
        document.getElementById("cardsList").innerHTML = payload.items
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
    try {
        const data = await api("/api/route/start-task", { method: "POST", body: JSON.stringify({}) });
        renderQuestion(data);
    } catch (error) {
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

        renderBootstrap();
        renderDaily();
        if (cards) {
            renderCards();
            if (cards.categories.length && !document.getElementById("cardsList").innerHTML.trim()) {
                loadCardsCategory(state.selectedCategory || cards.categories[0].name);
            }
        }
        renderProfile();
        document.getElementById("homeRouteStart")?.addEventListener("click", launchRouteTask);
    } catch (error) {
        showToast(error.message);
        document.getElementById("heroText").textContent = error.message;
    }
}

document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-screen], [data-start-mode], [data-answer], [data-daily-answer], .route-task-launch, [data-category], [data-card-id]");
    if (!target) {
        return;
    }
    if (target.dataset.screen) {
        switchScreen(target.dataset.screen);
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
    if (target.classList.contains("route-task-launch")) {
        launchRouteTask();
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
document.getElementById("sheetBackdrop").addEventListener("click", () => {
    detailSheet.classList.add("hidden");
    syncTelegramBackButton();
});
document.getElementById("closeSheetButton").addEventListener("click", () => {
    detailSheet.classList.add("hidden");
    syncTelegramBackButton();
});
document.getElementById("refreshButton").addEventListener("click", () => {
    pulse("light");
    hydrate();
});
document.getElementById("routeTaskButton").addEventListener("click", launchRouteTask);
document.getElementById("saveSettingsButton").addEventListener("click", saveSettings);
document.getElementById("resetProgressButton").addEventListener("click", resetProgress);
document.getElementById("starQuestionButton").addEventListener("click", toggleStar);

document.addEventListener("click", (event) => {
    if (event.target.id === "nextQuestionButton" && state.pendingNextQuestion) {
        loadNextQuestion();
        return;
    }
    if (event.target.id === "finishSessionButton" || event.target.id === "backToAppButton") {
        closeSessionOverlay();
        hydrate();
    }
});

hydrate();
