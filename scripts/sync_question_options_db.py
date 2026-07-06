#!/usr/bin/env python3
"""Update stored question options from questions.json (including fixes)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import QUESTIONS_FILE
from database.database import async_session, init_db
from database.models import Question
from scripts.load_questions import normalize_options


async def sync() -> None:
    catalog = json.loads(Path(QUESTIONS_FILE).read_text(encoding="utf-8"))
    by_external_id = {int(item["id"]): item for item in catalog if str(item.get("id", "")).isdigit()}
    await init_db()
    updated = 0
    async with async_session() as session:
        questions = (await session.execute(select(Question))).scalars().all()
        for question in questions:
            source = by_external_id.get(question.external_id or -1)
            if source is None:
                continue
            options = normalize_options(source.get("options"), question_id=str(question.external_id))
            if options and options != dict(question.options or {}):
                question.options = options
                updated += 1
        await session.commit()
    print(f"Updated {updated} questions in database")


if __name__ == "__main__":
    asyncio.run(sync())
