from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import QUESTIONS_FILE
from database.database import async_session, init_db
from database.models import Question
from utils.constants import BLOCKS
from utils.helpers import derive_block, normalize_option_key


def normalize_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def normalize_options(raw_options: object) -> dict[str, str]:
    if isinstance(raw_options, dict):
        return {
            normalize_option_key(str(key)): str(value).strip()
            for key, value in raw_options.items()
            if str(value).strip()
        }

    if isinstance(raw_options, list):
        normalized: dict[str, str] = {}
        for index, item in enumerate(raw_options):
            fallback_key = ("a", "b", "c", "d")[index]
            if isinstance(item, dict):
                key = normalize_option_key(str(item.get("key") or item.get("label") or fallback_key))
                text = str(item.get("text") or item.get("value") or "").strip()
            else:
                key = fallback_key
                text = str(item).strip()
            if text:
                normalized[key] = text
        return normalized

    return {}


def normalize_correct_answer(item: dict[str, object], options: dict[str, str]) -> str:
    candidates = [
        item.get("answer"),
        item.get("correctOption"),
        item.get("correct_answer"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        normalized = normalize_option_key(str(candidate))
        if normalized in options:
            return normalized
    return ""


def resolve_block(item: dict[str, object], external_id: int | None, source_number: int | None) -> int:
    raw_block = normalize_int(item.get("block"))
    if raw_block in {1, 2, 3}:
        return raw_block
    return derive_block(source_number or external_id)


def normalize_image(item: dict[str, object]) -> str | None:
    for key in ("image_url", "image", "picture", "illustration", "photo"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return None


async def load() -> None:
    questions_path = Path(QUESTIONS_FILE)
    print("=" * 50)
    print("ONEHUNT - загрузка вопросов")
    print("=" * 50)
    print(f"Источник: {questions_path}")

    if not questions_path.exists():
        print("Файл не найден.")
        return

    with questions_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("questions.json должен содержать массив вопросов.")

    await init_db()

    loaded = 0
    skipped = 0
    errors = 0

    async with async_session() as session:
        existing_external_ids = set(
            (
                await session.execute(select(Question.external_id).where(Question.external_id.is_not(None)))
            ).scalars().all()
        )
        existing_source_numbers = set(
            (
                await session.execute(select(Question.source_number).where(Question.source_number.is_not(None)))
            ).scalars().all()
        )
        for item in data:
            if not isinstance(item, dict):
                errors += 1
                continue

            external_id = normalize_int(item.get("id"))
            source_number = normalize_int(item.get("sourceNumber"))

            if external_id is not None and external_id in existing_external_ids:
                skipped += 1
                continue
            if source_number is not None and source_number in existing_source_numbers:
                skipped += 1
                continue

            question_text = str(item.get("question") or item.get("question_text") or "").strip()
            options = normalize_options(item.get("options"))
            correct_answer = normalize_correct_answer(item, options)
            block = resolve_block(item, external_id, source_number)

            if not question_text or not options or correct_answer not in options:
                errors += 1
                continue

            question = Question(
                external_id=external_id,
                source_number=source_number,
                block=block,
                block_name=BLOCKS[block]["name"],
                question_text=question_text,
                options=options,
                correct_answer=correct_answer,
                explanation=str(item.get("explanation") or "").strip() or None,
                mnemonic=str(item.get("mnemonic") or "").strip() or None,
                difficulty=normalize_int(item.get("difficulty")) or 1,
                image_url=normalize_image(item),
            )
            session.add(question)
            if external_id is not None:
                existing_external_ids.add(external_id)
            if source_number is not None:
                existing_source_numbers.add(source_number)
            loaded += 1

            if loaded % 50 == 0:
                await session.commit()
                print(f"Загружено: {loaded}")

        await session.commit()

    print(f"Готово. Загружено: {loaded}, пропущено: {skipped}, ошибок: {errors}")


if __name__ == "__main__":
    asyncio.run(load())
