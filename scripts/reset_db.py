from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.database import Base, engine
from database import models  # noqa: F401


async def reset() -> None:
    print("ВНИМАНИЕ: это удалит все таблицы и данные.")
    confirmation = input("Введите RESET для подтверждения: ").strip()
    if confirmation != "RESET":
        print("Отменено.")
        return

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    print("База данных пересоздана.")


if __name__ == "__main__":
    asyncio.run(reset())
