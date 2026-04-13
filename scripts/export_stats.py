from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import EXPORT_DIR
from database.database import async_session, init_db
from database.models import Answer, Question, User
from utils.helpers import calculate_accuracy


async def export() -> None:
    output_dir = Path(EXPORT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    await init_db()

    async with async_session() as session:
        users = (
            await session.execute(select(User).order_by(User.xp_total.desc(), User.created_at.asc()))
        ).scalars().all()
        users_file = output_dir / "export_users.csv"
        with users_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "telegram_id",
                    "username",
                    "first_name",
                    "xp",
                    "rank_code",
                    "access_level",
                    "total_answers",
                    "correct_answers",
                    "accuracy_percent",
                    "exams_taken",
                    "exams_passed",
                    "best_exam_score",
                    "streak_days",
                    "best_day_streak",
                    "best_answer_streak",
                ]
            )
            for user in users:
                writer.writerow(
                    [
                        user.telegram_id,
                        user.username or "",
                        user.first_name or "",
                        user.xp_total,
                        user.rank_code,
                        user.access_level,
                        user.total_answers,
                        user.correct_answers,
                        calculate_accuracy(user.correct_answers, user.total_answers),
                        user.exams_taken,
                        user.exams_passed,
                        user.best_exam_score,
                        user.streak_days,
                        user.streak_best,
                        user.streak_answers_best,
                    ]
                )

        answers = (
            await session.execute(select(Answer).order_by(Answer.created_at.desc()).limit(10000))
        ).scalars().all()
        answers_file = output_dir / "export_answers.csv"
        with answers_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["id", "user_id", "question_id", "selected_answer", "is_correct", "mode", "created_at"])
            for answer in answers:
                writer.writerow(
                    [
                        answer.id,
                        answer.user_id,
                        answer.question_id,
                        answer.selected_answer,
                        answer.is_correct,
                        answer.mode,
                        answer.created_at.isoformat(),
                    ]
                )

        blocks_file = output_dir / "export_blocks.csv"
        with blocks_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["block", "questions", "answers", "correct_answers", "accuracy_percent"])
            for block_id in (1, 2, 3):
                total_questions = await session.scalar(
                    select(func.count()).select_from(Question).where(Question.block == block_id)
                )
                total_answers = await session.scalar(
                    select(func.count()).select_from(Answer).where(
                        Answer.question_id.in_(select(Question.id).where(Question.block == block_id))
                    )
                )
                correct_answers = await session.scalar(
                    select(func.count()).select_from(Answer).where(
                        Answer.is_correct.is_(True),
                        Answer.question_id.in_(select(Question.id).where(Question.block == block_id)),
                    )
                )
                writer.writerow(
                    [
                        block_id,
                        total_questions or 0,
                        total_answers or 0,
                        correct_answers or 0,
                        calculate_accuracy(int(correct_answers or 0), int(total_answers or 0)),
                    ]
                )

    print(f"CSV-файлы сохранены в {output_dir}")


if __name__ == "__main__":
    asyncio.run(export())
