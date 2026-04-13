from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, inspect, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.database import async_session, engine, init_db
from database.models import Answer, Question, StarredQuestion, User


async def check() -> None:
    await init_db()

    async with async_session() as session:
        dialect = session.bind.dialect.name
        version_query = "select sqlite_version()" if dialect == "sqlite" else "select version()"
        version = (await session.execute(text(version_query))).scalar()

        users = await session.scalar(select(func.count()).select_from(User))
        questions = await session.scalar(select(func.count()).select_from(Question))
        answers = await session.scalar(select(func.count()).select_from(Answer))
        starred = await session.scalar(select(func.count()).select_from(StarredQuestion))

        async with engine.begin() as connection:
            tables = await connection.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())

    print("=" * 50)
    print("ONEHUNT - диагностика БД")
    print("=" * 50)
    print(f"Диалект: {dialect}")
    print(f"Версия: {version}")
    print(f"Таблицы: {', '.join(sorted(tables))}")
    print(f"Users: {users or 0}")
    print(f"Questions: {questions or 0}")
    print(f"Answers: {answers or 0}")
    print(f"Starred: {starred or 0}")


if __name__ == "__main__":
    asyncio.run(check())
