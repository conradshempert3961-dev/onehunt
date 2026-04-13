from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.database import async_session, init_db
from database.models import Question
from utils.constants import BLOCKS
from utils.helpers import normalize_option_key


async def add() -> None:
    await init_db()
    print("Добавление вопроса в ONEHUNT")
    block = int(input("Блок (1/2/3): ").strip())
    question_text = input("Текст вопроса: ").strip()

    options: dict[str, str] = {}
    for raw_key in ("a", "b", "c", "d"):
        value = input(f"{raw_key.upper()}) ").strip()
        if value:
            options[raw_key] = value

    correct = normalize_option_key(input("Правильный ответ (a/b/c/d): ").strip())
    explanation = input("Пояснение (можно пусто): ").strip() or None
    mnemonic = input("Мнемоника (можно пусто): ").strip() or None
    image_url = input("Иллюстрация: URL или путь к файлу (можно пусто): ").strip() or None

    if block not in {1, 2, 3} or not question_text or correct not in options:
        print("Некорректные данные.")
        return

    async with async_session() as session:
        question = Question(
            block=block,
            block_name=BLOCKS[block]["name"],
            question_text=question_text,
            options=options,
            correct_answer=correct,
            explanation=explanation,
            mnemonic=mnemonic,
            difficulty=1,
            image_url=image_url,
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)

    print(f"Вопрос добавлен. ID: {question.id}")


if __name__ == "__main__":
    asyncio.run(add())
