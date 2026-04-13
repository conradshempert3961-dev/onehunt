from __future__ import annotations

import hashlib
import random
import string
from datetime import date, datetime

from utils.constants import RANKS, XP_LEVELS


def generate_session_id(user_id: int) -> str:
    raw = f"{user_id}_{datetime.utcnow().isoformat()}_{random.randint(1000, 9999)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def truncate_text(text: str, max_length: int = 60) -> str:
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return text[: max_length - 3].rstrip() + "..."


def calculate_accuracy(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(correct / total * 100, 1)


def plural_form(number: int, one: str, two: str, many: str) -> str:
    remainder_100 = number % 100
    remainder_10 = number % 10
    if 11 <= remainder_100 <= 14:
        return many
    if remainder_10 == 1:
        return one
    if 2 <= remainder_10 <= 4:
        return two
    return many


def format_duration(total_seconds: int) -> str:
    if total_seconds < 60:
        return f"{total_seconds} сек"

    minutes, seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{minutes} мин {seconds:02d} сек"

    hours, minutes = divmod(minutes, 60)
    return f"{hours} ч {minutes:02d} мин"


def format_streak_message(streak: int) -> str:
    if streak <= 0:
        return "Начните сегодня и соберите первую серию."

    day_word = plural_form(streak, "день", "дня", "дней")
    if streak < 3:
        return f"🔥 {streak} {day_word} подряд. Продолжайте!"
    if streak < 7:
        return f"🔥 {streak} {day_word} подряд! Отличный темп!"
    if streak < 30:
        return f"🔥🔥 {streak} {day_word}! Вы в форме."
    return f"🔥🔥🔥 {streak} {day_word}! ЛЕГЕНДА!"


def progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "░" * length
    filled = int(length * current / total)
    return "█" * filled + "░" * (length - filled)


def derive_block(question_number: int | None, total_questions: int = 257) -> int:
    if not question_number or question_number <= 0:
        return 1
    if question_number <= 98:
        return 1
    if question_number <= 172:
        return 2
    return 3


def normalize_option_key(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned in {"a", "b", "c", "d"}:
        return cleaned
    translit = {
        "а": "a",
        "б": "b",
        "в": "c",
        "г": "d",
    }
    return translit.get(cleaned, cleaned)


def random_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def get_rank_by_correct(correct_answers: int) -> dict[str, int | str]:
    current_rank = RANKS[0]
    for rank in RANKS:
        if correct_answers >= int(rank["min_correct"]):
            current_rank = rank
    return current_rank


def get_next_rank_by_correct(correct_answers: int) -> dict[str, int | str] | None:
    for rank in RANKS:
        if correct_answers < int(rank["min_correct"]):
            return rank
    return None


def get_xp_level(xp_total: int) -> tuple[int, str]:
    level = XP_LEVELS[0]
    for entry in XP_LEVELS:
        if xp_total >= entry[1]:
            level = entry
    return level[0], level[2]


def get_next_xp_level(xp_total: int) -> tuple[int, int, str] | None:
    for level, threshold, title in XP_LEVELS:
        if xp_total < threshold:
            return level, threshold, title
    return None


def generate_ascii_chart(daily_accuracy: list[int], height: int = 6) -> str:
    if not daily_accuracy:
        return "Нет данных за период."

    max_val = 100
    min_val = 50
    range_val = max_val - min_val
    chart: list[str] = []

    for row in range(height, -1, -1):
        threshold = min_val + (row / max(height, 1)) * range_val
        line = f"{int(threshold):3d} ┤"
        for index, value in enumerate(daily_accuracy):
            if value >= threshold:
                if index > 0 and daily_accuracy[index - 1] < threshold:
                    line += "╱"
                else:
                    line += "─"
            else:
                line += " "
        chart.append(line)

    chart.append("    └" + "─" * len(daily_accuracy))
    return "\n".join(chart)


def day_bounds(value: datetime) -> tuple[datetime, datetime]:
    start = value.replace(hour=0, minute=0, second=0, microsecond=0)
    end = value.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def today_iso() -> str:
    return date.today().isoformat()
