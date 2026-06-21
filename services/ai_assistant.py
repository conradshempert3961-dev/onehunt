from __future__ import annotations

import json
import re
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from config import (
    AI_MAX_HISTORY,
    AI_MAX_TOKENS,
    AI_REQUEST_TIMEOUT,
    AI_TEMPERATURE,
    EXAM_PASS_PERCENT,
    OPENAI_API_BASE,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from services.game import (
    count_achievements,
    count_starred,
    get_journal_stats,
    get_route_overview,
    get_route_task,
    get_today_stats,
)

SYSTEM_PROMPT = (
    "Ты ONEHUNT AI — персональный тренер подготовки к охотминимуму в России. "
    "Отвечай на русском, коротко и по делу: 3-5 предложений или короткий список шагов. "
    "Опирайся на переданный контекст прогресса пользователя. "
    "Не выдумывай точные проценты и числа — используй только данные из контекста. "
    "Если данных мало, скажи что сделать сегодня: тренировка, слабый блок, вопрос дня, разбор ошибок. "
    "Не давай юридических гарантий про сдачу экзамена. "
    "Не обсуждай темы вне подготовки к охотминимуму и приложения ONEHUNT."
)


class AIAssistantError(RuntimeError):
    pass


def ai_assistant_configured() -> bool:
    return bool(OPENAI_API_KEY.strip())


def ai_assistant_meta() -> dict[str, Any]:
    configured = ai_assistant_configured()
    provider = "rules"
    if configured:
        base_lower = OPENAI_API_BASE.lower()
        model_lower = OPENAI_MODEL.lower()
        if "deepseek" in base_lower or "deepseek" in model_lower or ":18632" in base_lower:
            provider = "deepseek"
        else:
            provider = "openai_compatible"
    return {
        "configured": configured,
        "provider": provider,
        "model": OPENAI_MODEL if configured else None,
        "endpoint": OPENAI_API_BASE if configured else None,
    }


def build_ai_block_snapshot(journal: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": 1, "icon": "📜", "name": "Правовые основы", "percent": journal["block1"]},
        {"id": 2, "icon": "🔫", "name": "Оружие и безопасность", "percent": journal["block2"]},
        {"id": 3, "icon": "🦌", "name": "Биология и практика", "percent": journal["block3"]},
    ]


async def gather_user_context(user: Any) -> dict[str, Any]:
    journal = await get_journal_stats(user.telegram_id)
    route = await get_route_overview(user.telegram_id)
    route_task = await get_route_task(user.telegram_id)
    today = await get_today_stats(user.telegram_id)
    achievements = await count_achievements(user.telegram_id)
    starred = await count_starred(user.telegram_id)

    blocks = build_ai_block_snapshot(journal)
    weakest = min(blocks, key=lambda item: item["percent"])
    strongest = max(blocks, key=lambda item: item["percent"])
    weak_topics = journal.get("weak_topics") or []
    settings = dict(user.settings or {})

    route_line = (
        f"Сегодня в маршруте день {route['current_day']}: {route_task['task']['icon']} "
        f"{route_task['task']['name']} — {route_task['task']['goal']}."
        if route_task
        else "Маршрут пока не активирован — начать с тренировки на 10-20 вопросов и вопроса дня."
    )
    weak_topics_line = (
        ", ".join(weak_topics[:4])
        if weak_topics
        else "статистики мало — сделать 15-20 обычных вопросов"
    )
    today_line = (
        f"Сегодня дано {today['answers_today']} ответов, вопрос дня "
        f"{'закрыт' if today['daily_answered'] else 'ещё открыт'}, "
        f"исправлено ошибок {today['mistakes_fixed_today']}."
    )

    return {
        "journal": journal,
        "route": route,
        "route_task": route_task,
        "today": today,
        "achievements": achievements,
        "starred": starred,
        "blocks": blocks,
        "weakest": weakest,
        "strongest": strongest,
        "weak_topics": weak_topics,
        "weak_topics_line": weak_topics_line,
        "settings": settings,
        "route_line": route_line,
        "today_line": today_line,
        "user": user,
    }


def build_context_prompt(context: dict[str, Any]) -> str:
    user = context["user"]
    weakest = context["weakest"]
    strongest = context["strongest"]
    settings = context["settings"]
    reminder_state = "включены" if user.daily_reminder else "выключены"
    timer_seconds = int(settings.get("timer_seconds", 0))

    return "\n".join(
        [
            "Контекст пользователя ONEHUNT:",
            f"- Прогресс: {user.questions_completed}/257 вопросов, точность {user.accuracy}%.",
            f"- Лучший результат экзамена: {user.best_exam_score}% (проход {EXAM_PASS_PERCENT}%).",
            f"- XP {user.xp_total}, монеты {user.coins}, серия {user.streak_days} дн.",
            f"- Блоки: «{strongest['icon']} {strongest['name']}» {strongest['percent']}% (сильный), "
            f"«{weakest['icon']} {weakest['name']}» {weakest['percent']}% (слабый).",
            f"- Слабые темы: {context['weak_topics_line']}.",
            f"- Достижений: {context['achievements']}, избранных сложных вопросов: {context['starred']}.",
            f"- {context['route_line']}",
            f"- {context['today_line']}",
            f"- Напоминания {reminder_state}, час {user.reminder_hour}:00.",
            f"- Тренировка: {int(settings.get('questions_per_session', 20))} вопросов, "
            f"таймер {'выкл' if not timer_seconds else f'{timer_seconds} сек'}, "
            f"объяснения {'вкл' if settings.get('show_explanations', True) else 'выкл'}.",
        ]
    )


def normalize_ai_prompt(message: str) -> str:
    return re.sub(r"\s+", " ", message.lower()).strip()


def prompt_has_any(prompt: str, *tokens: str) -> bool:
    return any(token in prompt for token in tokens)


def suggest_quick_replies(message: str) -> list[str]:
    prompt = normalize_ai_prompt(message)
    if prompt_has_any(prompt, "привет", "здравств", "добрый", "hello", "hi", "хай", "здорово"):
        return ["Как пройти курс?", "Составь план на сегодня", "Что подтянуть первым?"]
    if prompt_has_any(
        prompt,
        "курс",
        "пройти",
        "onehunt",
        "охотминим",
        "с чего нач",
        "как пользов",
        "как работ",
        "тропа",
        "нович",
    ):
        return ["Составь план на сегодня", "Что подтянуть первым?", "Готов ли я к экзамену?"]
    if prompt_has_any(prompt, "экзамен", "сдать", "257", "порог", "пройду", "завал"):
        return ["Что подтянуть первым?", "Составь план на сегодня", "Как закрыть слабые темы?"]
    if prompt_has_any(prompt, "ошиб", "слаб", "тема", "просед", "подтянуть", "исправ"):
        return ["Составь план на сегодня", "Как готовиться к экзамену?", "Что у меня с прогрессом?"]
    if prompt_has_any(prompt, "сегодня", "план", "маршрут", "дальше", "начать", "что делать"):
        return ["Какая у меня слабая тема?", "Готов ли я к экзамену?", "Что с напоминаниями?"]
    if prompt_has_any(prompt, "ранг", "xp", "уров", "прогресс", "монет", "серия", "достижен"):
        return ["Что мне подтянуть первым?", "Составь план на сегодня", "Как выйти на экзамен?"]
    if prompt_has_any(prompt, "напомин", "настрой", "таймер", "объяснен"):
        return ["Составь план на сегодня", "Что подтянуть первым?", "Как выйти на экзамен?"]
    if prompt_has_any(prompt, "карточк", "животн", "след", "биолог", "сезон"):
        return ["Какая у меня слабая тема?", "Составь план на сегодня", "Как лучше разобрать ошибки?"]
    return [
        "Что мне подтянуть первым?",
        "Как лучше разобрать ошибки?",
        "Готов ли я к экзамену?",
    ]


def build_rule_based_reply(message: str, context: dict[str, Any]) -> dict[str, Any]:
    user = context["user"]
    weakest = context["weakest"]
    strongest = context["strongest"]
    weak_topics_line = context["weak_topics_line"]
    route_line = context["route_line"]
    today_line = context["today_line"]
    achievements = context["achievements"]
    starred = context["starred"]
    settings = context["settings"]

    prompt = normalize_ai_prompt(message)
    route = context.get("route") or {}
    route_task = context.get("route_task")
    route_day = route.get("current_day") or (route_task or {}).get("day")
    route_percent = route.get("percent", 0)

    if prompt_has_any(prompt, "привет", "здравств", "добрый", "hello", "hi", "хай", "здорово"):
        reply = "\n".join(
            [
                "Привет! Я ONEHUNT AI — ваш тренер по подготовке к охотминимуму.",
                f"Сейчас прогресс {user.questions_completed}/257 вопросов, точность {user.accuracy}%.",
                route_line,
                "Могу подсказать, как пройти курс, что сделать сегодня, где вы проседаете и когда идти на экзамен.",
            ]
        )
    elif prompt_has_any(prompt, "спасиб", "благодар", "thanks", "thx"):
        reply = "\n".join(
            [
                "Пожалуйста! Если нужен следующий шаг — спросите план на сегодня или что подтянуть первым.",
                route_line,
                today_line,
            ]
        )
    elif prompt_has_any(prompt, "что ты умеешь", "что умеешь", "помощ", "help", "чем помож"):
        reply = "\n".join(
            [
                "Я помогаю с подготовкой к охотминимуму в ONEHUNT:",
                "• объясняю, как пройти маршрут и курс;",
                "• составляю план на день по вашему прогрессу;",
                "• подсказываю слабые блоки и темы;",
                "• готовлю к экзамену и разбору ошибок.",
                f"Сейчас главный резерв — «{weakest['icon']} {weakest['name']}» ({weakest['percent']}%).",
            ]
        )
    elif prompt_has_any(
        prompt,
        "курс",
        "пройти",
        "onehunt",
        "охотминим",
        "с чего нач",
        "как пользов",
        "как работ",
        "тропа",
        "нович",
    ):
        today_task = ""
        if route_task:
            task = route_task["task"]
            today_task = (
                f"Сегодня день {route_day}: {task['icon']} {task['name']} — {task['goal']} "
                f"(≈{task['minutes']} мин)."
            )
        reply = "\n".join(
            [
                "Курс ONEHUNT — это 14-дневный маршрут + тренировки по трём блокам (257 вопросов):",
                "1) «Тропы» — проходите вопросы по блокам (право, безопасность, биология);",
                "2) «Стрельбище» — смешанные тренировки и работа над слабыми темами;",
                "3) «Испытания» — пробные экзамены и разбор ошибок.",
                today_task or "Начните с тренировки на 15–20 вопросов и вопроса дня.",
                f"Маршрут пройден на {route_percent}%. После каждого дня — короткий разбор промахов.",
                f"Слабое место сейчас: «{weakest['icon']} {weakest['name']}» — уделите ему время после задания дня.",
            ]
        )
    elif prompt_has_any(prompt, "экзамен", "сдать", "257", "порог", "пройду", "завал"):
        reply = "\n".join(
            [
                f"Лучший результат по экзамену сейчас: {user.best_exam_score}% при проходном пороге {EXAM_PASS_PERCENT}%.",
                f"Сильнее всего у вас идет блок «{strongest['icon']} {strongest['name']}» ({strongest['percent']}%), "
                f"а первым делом стоит дожать «{weakest['icon']} {weakest['name']}» ({weakest['percent']}%).",
                "Быстрый план: 1) короткая тренировка 15-20 вопросов, 2) отдельный проход по слабому блоку, "
                "3) затем пробный экзамен без пауз.",
                route_line,
            ]
        )
    elif prompt_has_any(prompt, "ошиб", "слаб", "тема", "просед", "подтянуть", "исправ"):
        reply = "\n".join(
            [
                f"Сейчас самый слабый блок — «{weakest['icon']} {weakest['name']}» ({weakest['percent']}%).",
                f"Слабые темы по журналу: {weak_topics_line}.",
                "Лучше всего работает короткая серия по слабому блоку, затем один смешанный сет для закрепления "
                "и только потом экзаменационный режим.",
                today_line,
            ]
        )
    elif prompt_has_any(prompt, "сегодня", "план", "маршрут", "дальше", "начать", "что делать"):
        reply = "\n".join(
            [
                "Вот спокойный план на текущий день без перегруза:",
                route_line,
                f"После этого добейте 10-20 вопросов по теме «{weakest['icon']} {weakest['name']}», "
                "потому что она даст самый заметный прирост.",
                f"Финиш — вопрос дня и короткий разбор ошибок. {today_line}",
            ]
        )
    elif prompt_has_any(prompt, "ранг", "xp", "уров", "прогресс", "монет", "серия", "достижен"):
        reply = "\n".join(
            [
                f"Сейчас у вас {user.questions_completed}/257 по прогрессу, точность {user.accuracy}%, "
                f"серия {user.streak_days} дн., XP {user.xp_total}, монеты {user.coins}.",
                f"Открыто достижений: {achievements}, в избранном сложных вопросов: {starred}.",
                f"Сильный блок — «{strongest['icon']} {strongest['name']}», "
                f"а главный резерв роста сейчас в «{weakest['icon']} {weakest['name']}».",
                "Если хотите расти быстрее, держите короткие, но регулярные сессии и не пропускайте разбор ошибок.",
            ]
        )
    elif prompt_has_any(prompt, "напомин", "настрой", "таймер", "объяснен"):
        reminder_state = "включены" if user.daily_reminder else "выключены"
        timer_seconds = int(settings.get("timer_seconds", 0))
        explanations = "включены" if settings.get("show_explanations", True) else "выключены"
        reply = "\n".join(
            [
                f"Напоминания сейчас {reminder_state}, час — {user.reminder_hour}:00.",
                f"В тренировке стоит {int(settings.get('questions_per_session', 20))} вопросов, "
                f"таймер — {timer_seconds if timer_seconds else 'выкл'}, объяснения — {explanations}.",
                "Если нужен спокойный режим, держите 10-20 вопросов и объяснения включенными. "
                "Если нужна боевая подготовка — включайте таймер и идите короткими сетами.",
            ]
        )
    elif prompt_has_any(prompt, "карточк", "животн", "след", "биолог", "сезон"):
        reply = "\n".join(
            [
                "Карточки лучше использовать как короткий добор после вопросов, а не вместо них.",
                f"Сильнее всего они помогут в блоке «{weakest['icon']} {weakest['name']}», "
                f"особенно если там есть пробелы по темам: {weak_topics_line}.",
                "Оптимально: 10-15 вопросов, потом 3-5 карточек по близкой теме и финальный быстрый вопрос.",
            ]
        )
    else:
        reply = "\n".join(
            [
                f"Понял вопрос. Смотрю на ваш прогресс: {user.questions_completed}/257, точность {user.accuracy}%.",
                f"Слабее всего сейчас «{weakest['icon']} {weakest['name']}» ({weakest['percent']}%) — с него обычно и даётся быстрый рост.",
                route_line,
                "Уточните, если нужен план на сегодня, разбор ошибок или подготовка к экзамену.",
            ]
        )

    return {
        "reply": reply,
        "quick_replies": suggest_quick_replies(message)[:3],
        "source": "rules",
    }


def _normalize_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in history[-AI_MAX_HISTORY:]:
        role = str(item.get("role", "")).strip().lower()
        text = str(item.get("text", "")).strip()
        if role not in {"user", "assistant"} or not text:
            continue
        normalized.append({"role": role, "text": text[:400]})
    return normalized


async def _call_openai_chat(messages: list[dict[str, str]]) -> str:
    if not ai_assistant_configured():
        raise AIAssistantError("OpenAI-compatible API is not configured.")

    url = f"{OPENAI_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": AI_TEMPERATURE,
        "max_tokens": AI_MAX_TOKENS,
    }

    timeout = ClientTimeout(total=AI_REQUEST_TIMEOUT)
    async with ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as response:
            raw = await response.text()
            data = json.loads(raw) if raw else {}

    if response.status >= 400:
        detail = data.get("error", {}).get("message") if isinstance(data, dict) else None
        raise AIAssistantError(detail or f"LLM API returned HTTP {response.status}.")

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIAssistantError("LLM API returned an unexpected response.") from exc

    reply = str(content).strip()
    if not reply:
        raise AIAssistantError("LLM API returned an empty reply.")
    return reply


async def generate_ai_reply(
    message: str,
    user: Any,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    context = await gather_user_context(user)
    cleaned_message = message.strip()
    if not cleaned_message:
        raise ValueError("message is required")

    if not ai_assistant_configured():
        result = build_rule_based_reply(cleaned_message, context)
        result["provider"] = "rules"
        return result

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_context_prompt(context)},
    ]
    for item in _normalize_history(history or []):
        messages.append({"role": item["role"], "content": item["text"]})
    messages.append({"role": "user", "content": cleaned_message})

    try:
        reply = await _call_openai_chat(messages)
        return {
            "reply": reply,
            "quick_replies": suggest_quick_replies(cleaned_message)[:3],
            "source": "llm",
            "provider": "openai_compatible",
            "model": OPENAI_MODEL,
        }
    except (AIAssistantError, json.JSONDecodeError):
        result = build_rule_based_reply(cleaned_message, context)
        result["provider"] = "rules"
        result["fallback"] = True
        return result
