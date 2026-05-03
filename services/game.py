from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import random
from typing import Any

from sqlalchemy import and_, delete, distinct, func, or_, select
from sqlalchemy.exc import IntegrityError

from config import BLOCK_QUESTIONS, EXAM_PASS_PERCENT, EXAM_QUESTIONS
from database.database import async_session
from database.models import (
    AnimalCard,
    AnimalCardQuestion,
    AnimalCardView,
    Answer,
    BroadcastLog,
    CoinPurchase,
    DailyChallenge,
    DailyQuestion,
    DailyQuestionAnswer,
    Duel,
    ExamAttempt,
    HintUsage,
    Payment,
    PromoCode,
    Question,
    ReminderLog,
    SpacedRepetition,
    StarredQuestion,
    User,
    UserAchievement,
    UserSession,
    XPTransaction,
)
from utils.constants import (
    ACHIEVEMENTS,
    ANIMAL_CARDS,
    BLOCKS,
    COIN_RULES,
    DAILY_CHALLENGES,
    FREE_LIMITS,
    HINT_COSTS,
    PREMIUM_PRICES,
    QUOTES,
    RANKS,
    ROUTE_TASKS,
    XP_RULES,
)
from utils.helpers import (
    calculate_accuracy,
    generate_ascii_chart,
    get_next_rank_by_correct,
    get_next_xp_level,
    get_rank_by_correct,
    get_xp_level,
)


@dataclass(slots=True)
class AnswerOutcome:
    is_correct: bool
    xp_added: int
    coins_added: int
    answer_streak: int
    rank_up: dict[str, Any] | None
    achievements: list[dict[str, Any]]
    challenge_completed: dict[str, Any] | None
    route_day_completed: int | None
    mistake_fixed: bool


def utcnow() -> datetime:
    return datetime.utcnow()


def today() -> date:
    return date.today()


def ensure_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    data = {
        "questions_per_session": 20,
        "timer_seconds": 0,
        "show_explanations": True,
    }
    if settings:
        data.update(settings)
    return data


async def seed_reference_data() -> None:
    async with async_session() as session:
        existing_question_ids = set(
            (
                await session.execute(select(Question.id))
            ).scalars().all()
        )
        existing_cards = {
            card.name: card
            for card in (
                await session.execute(select(AnimalCard))
            ).scalars().all()
        }
        for card_data in ANIMAL_CARDS:
            question_ids = list(card_data.get("question_ids", []))
            payload = {k: v for k, v in card_data.items() if k != "question_ids"}
            card = existing_cards.get(str(payload["name"]))
            if card is None:
                card = AnimalCard(**payload)
                session.add(card)
                await session.flush()
                existing_cards[card.name] = card

            existing_links = set(
                (
                    await session.execute(
                        select(AnimalCardQuestion.question_id).where(
                            AnimalCardQuestion.animal_card_id == card.id,
                        )
                    )
                ).scalars().all()
            )

            for question_id in question_ids:
                if question_id not in existing_question_ids or question_id in existing_links:
                    continue
                session.add(
                    AnimalCardQuestion(
                        animal_card_id=card.id,
                        question_id=question_id,
                    )
                )

        await session.commit()


async def get_or_create_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                settings=ensure_settings(None),
            )
            session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.settings = ensure_settings(user.settings)
            user.last_seen_at = utcnow()

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user is None:
                raise
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.settings = ensure_settings(user.settings)
            user.last_seen_at = utcnow()
            await session.commit()
        await session.refresh(user)
        return user


async def get_user(user_id: int) -> User | None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        return result.scalar_one_or_none()


async def update_user(user_id: int, **fields: Any) -> User | None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        for key, value in fields.items():
            setattr(user, key, value)
        user.updated_at = utcnow()
        await session.commit()
        await session.refresh(user)
        return user


async def mark_user_seen(user_id: int) -> None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return
        user.last_seen_at = utcnow()
        await session.commit()


async def get_question_count() -> int:
    async with async_session() as session:
        return int(await session.scalar(select(func.count()).select_from(Question)) or 0)


async def get_question(question_id: int) -> Question | None:
    async with async_session() as session:
        result = await session.execute(select(Question).where(Question.id == question_id))
        return result.scalar_one_or_none()


async def get_random_questions(limit: int, block_id: int | None = None, exclude_ids: list[int] | None = None) -> list[Question]:
    async with async_session() as session:
        query = select(Question)
        if block_id is not None:
            query = query.where(Question.block == block_id)
        if exclude_ids:
            query = query.where(Question.id.not_in(exclude_ids))
        result = await session.execute(query.order_by(func.random()).limit(limit))
        return list(result.scalars().all())


async def get_official_exam_questions(limit: int = EXAM_QUESTIONS, shuffle: bool = True) -> list[Question]:
    async with async_session() as session:
        result = await session.execute(
            select(Question)
            .where(
                Question.source_number.is_not(None),
                Question.source_number >= 1,
                Question.source_number <= EXAM_QUESTIONS,
            )
            .order_by(Question.source_number.asc(), Question.id.asc())
        )
        ordered_questions = list(result.scalars().all())

    unique_questions: list[Question] = []
    seen_source_numbers: set[int] = set()
    for question in ordered_questions:
        source_number = int(question.source_number or 0)
        if source_number in seen_source_numbers:
            continue
        seen_source_numbers.add(source_number)
        unique_questions.append(question)

    if limit < len(unique_questions):
        if shuffle:
            return random.sample(unique_questions, limit)
        return unique_questions[:limit]

    if shuffle:
        random.shuffle(unique_questions)
    return unique_questions


async def get_question_sequence_for_block(block_id: int, limit: int | None = None) -> list[Question]:
    async with async_session() as session:
        query = select(Question).where(Question.block == block_id).order_by(
            func.coalesce(Question.source_number, Question.external_id, Question.id)
        )
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_user_block_progress(user_id: int, block_id: int) -> int:
    async with async_session() as session:
        query = (
            select(func.count(distinct(Answer.question_id)))
            .select_from(Answer)
            .join(Question, Question.id == Answer.question_id)
            .where(
                Answer.user_id == user_id,
                Question.block == block_id,
                Answer.mode == "trail",
            )
        )
        return int(await session.scalar(query) or 0)


async def get_answered_question_ids(user_id: int, mode: str | None = None, block_id: int | None = None) -> set[int]:
    async with async_session() as session:
        query = select(distinct(Answer.question_id)).where(Answer.user_id == user_id)
        if mode is not None:
            query = query.where(Answer.mode == mode)
        if block_id is not None:
            query = query.join(Question, Question.id == Answer.question_id).where(Question.block == block_id)
        result = await session.execute(query)
        return set(result.scalars().all())


async def get_wrong_questions(user_id: int, limit: int = BLOCK_QUESTIONS) -> list[Question]:
    async with async_session() as session:
        wrong_ids = (
            select(Answer.question_id)
            .where(Answer.user_id == user_id, Answer.is_correct.is_(False))
            .distinct()
        )
        result = await session.execute(
            select(Question).where(Question.id.in_(wrong_ids)).order_by(func.random()).limit(limit)
        )
        return list(result.scalars().all())


async def get_starred_questions(user_id: int, limit: int = BLOCK_QUESTIONS) -> list[Question]:
    async with async_session() as session:
        starred_ids = select(StarredQuestion.question_id).where(StarredQuestion.user_id == user_id)
        result = await session.execute(
            select(Question).where(Question.id.in_(starred_ids)).order_by(func.random()).limit(limit)
        )
        return list(result.scalars().all())


async def get_due_repetition_questions(user_id: int, limit: int = BLOCK_QUESTIONS) -> list[Question]:
    async with async_session() as session:
        due_ids = select(SpacedRepetition.question_id).where(
            SpacedRepetition.user_id == user_id,
            SpacedRepetition.next_review_at <= utcnow(),
        )
        result = await session.execute(
            select(Question).where(Question.id.in_(due_ids)).order_by(func.random()).limit(limit)
        )
        return list(result.scalars().all())


async def is_starred(user_id: int, question_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(StarredQuestion).where(
                StarredQuestion.user_id == user_id,
                StarredQuestion.question_id == question_id,
            )
        )
        return result.scalar_one_or_none() is not None


async def toggle_star(user_id: int, question_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(StarredQuestion).where(
                StarredQuestion.user_id == user_id,
                StarredQuestion.question_id == question_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()
            return False

        session.add(StarredQuestion(user_id=user_id, question_id=question_id))
        await session.commit()
        return True


async def count_starred(user_id: int) -> int:
    async with async_session() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(StarredQuestion).where(StarredQuestion.user_id == user_id)
            )
            or 0
        )


async def count_achievements(user_id: int) -> int:
    async with async_session() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(UserAchievement).where(UserAchievement.user_id == user_id)
            )
            or 0
        )


async def get_unlocked_achievement_codes(user_id: int) -> set[str]:
    async with async_session() as session:
        result = await session.execute(
            select(UserAchievement.achievement_code).where(UserAchievement.user_id == user_id)
        )
        return set(result.scalars().all())


async def count_distinct_correct_questions(user_id: int) -> int:
    async with async_session() as session:
        query = (
            select(func.count(distinct(Answer.question_id)))
            .where(Answer.user_id == user_id, Answer.is_correct.is_(True))
        )
        return int(await session.scalar(query) or 0)


async def count_fast_answers(user_id: int, max_seconds: int = 10) -> int:
    async with async_session() as session:
        query = select(func.count()).where(
            Answer.user_id == user_id,
            Answer.is_correct.is_(True),
            Answer.time_spent_seconds.is_not(None),
            Answer.time_spent_seconds <= max_seconds,
        )
        return int(await session.scalar(query) or 0)


async def count_duel_wins(user_id: int) -> int:
    async with async_session() as session:
        query = select(func.count()).where(Duel.user_id == user_id, Duel.user_won.is_(True))
        return int(await session.scalar(query) or 0)


async def count_viewed_cards(user_id: int) -> int:
    async with async_session() as session:
        query = select(func.count()).where(AnimalCardView.user_id == user_id)
        return int(await session.scalar(query) or 0)


async def count_completed_challenges_streak(user_id: int) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(DailyChallenge.challenge_date)
            .where(DailyChallenge.user_id == user_id, DailyChallenge.completed.is_(True))
            .order_by(DailyChallenge.challenge_date.desc())
        )
        dates = list(result.scalars().all())

    streak = 0
    cursor = today()
    for value in dates:
        if value == cursor:
            streak += 1
            cursor -= timedelta(days=1)
        elif value < cursor:
            break
    return streak


async def get_block_accuracy(user_id: int, block_id: int) -> float:
    async with async_session() as session:
        query_total = (
            select(func.count())
            .select_from(Answer)
            .join(Question, Question.id == Answer.question_id)
            .where(Answer.user_id == user_id, Question.block == block_id)
        )
        query_correct = (
            select(func.count())
            .select_from(Answer)
            .join(Question, Question.id == Answer.question_id)
            .where(Answer.user_id == user_id, Question.block == block_id, Answer.is_correct.is_(True))
        )
        total = int(await session.scalar(query_total) or 0)
        correct = int(await session.scalar(query_correct) or 0)
    return calculate_accuracy(correct, total)


async def get_weak_topics(user_id: int, limit: int = 3) -> list[str]:
    parts: list[str] = []
    for block_id, block in BLOCKS.items():
        percent = await get_block_accuracy(user_id, block_id)
        parts.append(f"{block['icon']} {block['name']}: {percent}%")
    return parts[:limit]


async def update_question_global_stats(session: Any, question_id: int) -> None:
    question = (
        await session.execute(select(Question).where(Question.id == question_id))
    ).scalar_one_or_none()
    if question is None:
        return
    total = int(
        await session.scalar(select(func.count()).select_from(Answer).where(Answer.question_id == question_id))
        or 0
    )
    correct = int(
        await session.scalar(
            select(func.count()).select_from(Answer).where(
                Answer.question_id == question_id, Answer.is_correct.is_(True)
            )
        )
        or 0
    )
    question.times_answered = total
    question.times_correct = correct
    question.global_accuracy = calculate_accuracy(correct, total)


def get_xp_for_answer(mode: str, is_correct: bool, is_first_time: bool, time_spent: int | None) -> int:
    if not is_correct:
        return 0
    if mode == "daily_question":
        return XP_RULES["daily_question_correct"]
    if mode == "blitz":
        return XP_RULES["blitz_correct"]
    if mode == "exam":
        return XP_RULES["exam_correct"]
    if mode == "repetition":
        return XP_RULES["repetition_correct"]
    if time_spent is not None and time_spent < 15 and mode == "training":
        return XP_RULES["fast_correct"]
    if is_first_time:
        return XP_RULES["first_time_correct"]
    if mode == "training":
        return XP_RULES["training_correct"]
    return XP_RULES["trail_correct"]


def get_coin_for_answer(mode: str, is_correct: bool) -> int:
    if not is_correct:
        return 0
    if mode == "daily_question":
        return COIN_RULES["daily_question_correct"]
    return COIN_RULES["correct"]


def get_rank_up_payload(previous_correct: int, current_correct: int) -> dict[str, Any] | None:
    old_rank = get_rank_by_correct(previous_correct)
    new_rank = get_rank_by_correct(current_correct)
    if old_rank["code"] == new_rank["code"]:
        return None
    return {"old": old_rank, "new": new_rank}


def achievement_matches(achievement: dict[str, Any], stats: dict[str, Any]) -> bool:
    metric = achievement["metric"]
    value = stats.get(metric, 0)
    target = achievement["target"]
    comparison = achievement.get("comparison", "gte")
    if comparison == "lte":
        return bool(value) and value <= target
    return value >= target


async def build_achievement_stats(user_id: int) -> dict[str, Any]:
    user = await get_user(user_id)
    if user is None:
        return {}

    block1 = await get_block_accuracy(user_id, 1)
    block2 = await get_block_accuracy(user_id, 2)
    block3 = await get_block_accuracy(user_id, 3)

    async with async_session() as session:
        total_answers = int(
            await session.scalar(select(func.count()).select_from(Answer).where(Answer.user_id == user_id))
            or 0
        )
        mastered_topics = 3 if all(percent >= 100 for percent in (block1, block2, block3)) else 0
        first_exam = (
            await session.execute(
                select(ExamAttempt).where(ExamAttempt.user_id == user_id).order_by(ExamAttempt.started_at.asc()).limit(1)
            )
        ).scalar_one_or_none()
        passed_exam = int(
            await session.scalar(
                select(func.count()).select_from(ExamAttempt).where(
                    ExamAttempt.user_id == user_id,
                    ExamAttempt.passed.is_(True),
                )
            )
            or 0
        )
        failed_exam = int(
            await session.scalar(
                select(func.count()).select_from(ExamAttempt).where(
                    ExamAttempt.user_id == user_id,
                    ExamAttempt.passed.is_(False),
                )
            )
            or 0
        )
        training_duration = (
            await session.execute(
                select(UserSession.duration_seconds)
                .where(UserSession.user_id == user_id, UserSession.mode == "training")
                .order_by(UserSession.ended_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        exam_duration = (
            await session.execute(
                select(ExamAttempt.time_spent_minutes)
                .where(ExamAttempt.user_id == user_id, ExamAttempt.passed.is_(True))
                .order_by(ExamAttempt.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        doublet_blocks = int(
            await session.scalar(
                select(func.count(distinct(Question.block)))
                .select_from(Answer)
                .join(Question, Question.id == Answer.question_id)
                .where(
                    Answer.user_id == user_id,
                    func.date(Answer.created_at) == today(),
                    Answer.mode == "trail",
                )
            )
            or 0
        )

    current_hour = datetime.now().hour
    return {
        "total_answers": total_answers,
        "correct_total": user.correct_answers,
        "questions_completed": user.questions_completed,
        "max_streak": user.streak_answers_best,
        "day_streak": user.streak_days,
        "fast_answers": await count_fast_answers(user_id, 10),
        "blocks_today": doublet_blocks,
        "block1_percent": block1,
        "block2_percent": block2,
        "block3_percent": block3,
        "all_blocks": 100 if all(percent >= 100 for percent in (block1, block2, block3)) else mastered_topics,
        "exam_first_pass": 1 if first_exam and first_exam.passed else 0,
        "exam_time": int(exam_duration or 0),
        "training_time": int((training_duration or 0) / 60) if training_duration else 0,
        "mistakes_fixed": await count_fixed_mistakes(user_id),
        "failed_then_passed": 1 if failed_exam and passed_exam else 0,
        "topic_mastered_3x": 1 if mastered_topics >= 3 else 0,
        "challenges_streak": await count_completed_challenges_streak(user_id),
        "duel_wins": await count_duel_wins(user_id),
        "cards_viewed": await count_viewed_cards(user_id),
        "studied_after_23": 1 if current_hour >= 23 or current_hour < 1 else 0,
        "studied_before_6": 1 if current_hour < 6 else 0,
    }


async def award_xp(session: Any, user: User, amount: int, reason: str) -> None:
    if amount <= 0:
        return
    user.xp_total += amount
    user.xp_level = get_xp_level(user.xp_total)[0]
    session.add(XPTransaction(user_id=user.telegram_id, amount=amount, reason=reason))


async def award_coins(user: User, amount: int) -> None:
    if amount <= 0:
        return
    user.coins += amount


async def update_user_progress_fields(session: Any, user: User) -> None:
    correct_distinct = int(
        await session.scalar(
            select(func.count(distinct(Answer.question_id))).where(
                Answer.user_id == user.telegram_id,
                Answer.is_correct.is_(True),
            )
        )
        or 0
    )
    user.correct_answers = correct_distinct
    user.questions_completed = correct_distinct
    total_answers = int(
        await session.scalar(
            select(func.count()).select_from(Answer).where(Answer.user_id == user.telegram_id)
        )
        or 0
    )
    wrong_answers = int(
        await session.scalar(
            select(func.count()).select_from(Answer).where(
                Answer.user_id == user.telegram_id, Answer.is_correct.is_(False)
            )
        )
        or 0
    )
    user.total_answers = total_answers
    user.wrong_answers = wrong_answers
    user.accuracy = calculate_accuracy(correct_distinct, total_answers)
    user.rank_code = str(get_rank_by_correct(correct_distinct)["code"])


async def count_fixed_mistakes(user_id: int, for_day: date | None = None) -> int:
    async with async_session() as session:
        if for_day is None:
            wrong_ids = (
                await session.execute(
                    select(distinct(Answer.question_id)).where(
                        Answer.user_id == user_id,
                        Answer.is_correct.is_(False),
                    )
                )
            ).scalars().all()
            if not wrong_ids:
                return 0
            fixed = 0
            for question_id in wrong_ids:
                got_right = await session.scalar(
                    select(func.count()).select_from(Answer).where(
                        Answer.user_id == user_id,
                        Answer.question_id == question_id,
                        Answer.is_correct.is_(True),
                    )
                )
                if got_right:
                    fixed += 1
            return fixed

        day_start = datetime.combine(for_day, time.min)
        day_end = datetime.combine(for_day, time.max)
        corrected_today = (
            await session.execute(
                select(distinct(Answer.question_id)).where(
                    Answer.user_id == user_id,
                    Answer.is_correct.is_(True),
                    Answer.created_at >= day_start,
                    Answer.created_at <= day_end,
                )
            )
        ).scalars().all()
        if not corrected_today:
            return 0
        fixed = 0
        for question_id in corrected_today:
            had_wrong = await session.scalar(
                select(func.count()).select_from(Answer).where(
                    Answer.user_id == user_id,
                    Answer.question_id == question_id,
                    Answer.is_correct.is_(False),
                    Answer.created_at <= day_end,
                )
            )
            if had_wrong:
                fixed += 1
        return fixed


async def check_and_unlock_achievements(session: Any, user: User) -> list[dict[str, Any]]:
    stats = await build_achievement_stats(user.telegram_id)
    unlocked = {
        value
        for value in (
            await session.execute(
                select(UserAchievement.achievement_code).where(UserAchievement.user_id == user.telegram_id)
            )
        ).scalars().all()
    }
    new_items: list[dict[str, Any]] = []
    for achievement in ACHIEVEMENTS:
        if achievement["code"] in unlocked:
            continue
        if not achievement_matches(achievement, stats):
            continue
        session.add(
            UserAchievement(
                user_id=user.telegram_id,
                achievement_code=achievement["code"],
            )
        )
        await award_xp(session, user, int(achievement["xp"]), f"achievement:{achievement['code']}")
        await award_coins(user, int(achievement["coins"]))
        new_items.append(achievement)
    return new_items


async def update_spaced_repetition(session: Any, user_id: int, question_id: int, is_correct: bool) -> None:
    result = await session.execute(
        select(SpacedRepetition).where(
            SpacedRepetition.user_id == user_id,
            SpacedRepetition.question_id == question_id,
        )
    )
    item = result.scalar_one_or_none()
    now = utcnow()
    if item is None:
        item = SpacedRepetition(
            user_id=user_id,
            question_id=question_id,
            correct_streak=1 if is_correct else 0,
            next_review_at=now + timedelta(days=1 if is_correct else 0),
            last_reviewed_at=now,
        )
        if not is_correct:
            item.next_review_at = now + timedelta(hours=4)
        session.add(item)
        return

    item.last_reviewed_at = now
    if not is_correct:
        item.correct_streak = 0
        item.next_review_at = now + timedelta(hours=4)
        return

    item.correct_streak += 1
    intervals = {1: 1, 2: 3, 3: 7, 4: 14}
    days = intervals.get(item.correct_streak, 30)
    item.next_review_at = now + timedelta(days=days)


async def get_or_create_daily_question() -> DailyQuestion:
    current_day = today()
    async with async_session() as session:
        existing = (
            await session.execute(select(DailyQuestion).where(DailyQuestion.question_date == current_day))
        ).scalar_one_or_none()
        if existing:
            return existing

        used_ids = (
            await session.execute(select(DailyQuestion.question_id).order_by(DailyQuestion.question_date.asc()))
        ).scalars().all()
        query = select(Question)
        if used_ids:
            query = query.where(Question.id.not_in(list(used_ids)))
        available = await session.execute(query.order_by(func.random()).limit(1))
        question = available.scalar_one_or_none()
        if question is None:
            await session.execute(delete(DailyQuestion))
            await session.commit()
            question = (await session.execute(select(Question).order_by(func.random()).limit(1))).scalar_one()

        daily_question = DailyQuestion(question_id=question.id, question_date=current_day)
        session.add(daily_question)
        await session.commit()
        await session.refresh(daily_question)
        return daily_question


async def get_daily_question_question() -> Question | None:
    daily_question = await get_or_create_daily_question()
    return await get_question(daily_question.question_id)


async def get_daily_question_answer(user_id: int) -> DailyQuestionAnswer | None:
    async with async_session() as session:
        result = await session.execute(
            select(DailyQuestionAnswer).where(
                DailyQuestionAnswer.user_id == user_id,
                DailyQuestionAnswer.question_date == today(),
            )
        )
        return result.scalar_one_or_none()


async def get_or_create_daily_challenge(user_id: int) -> DailyChallenge:
    current_day = today()
    weekday = current_day.weekday()
    async with async_session() as session:
        existing = (
            await session.execute(
                select(DailyChallenge).where(
                    DailyChallenge.user_id == user_id,
                    DailyChallenge.challenge_date == current_day,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        challenge = DailyChallenge(
            user_id=user_id,
            challenge_date=current_day,
            challenge_type=DAILY_CHALLENGES[weekday]["type"],
        )
        session.add(challenge)
        await session.commit()
        await session.refresh(challenge)
        return challenge


async def get_today_stats(user_id: int) -> dict[str, Any]:
    day_start = datetime.combine(today(), time.min)
    async with async_session() as session:
        answers_today = int(
            await session.scalar(
                select(func.count()).select_from(Answer).where(
                    Answer.user_id == user_id,
                    Answer.created_at >= day_start,
                )
            )
            or 0
        )
        fixed_today = await count_fixed_mistakes(user_id, for_day=today())
        starred_today = int(
            await session.scalar(
                select(func.count()).select_from(Answer).where(
                    Answer.user_id == user_id,
                    Answer.mode == "starred",
                    Answer.created_at >= day_start,
                )
            )
            or 0
        )
        blitz_correct = int(
            await session.scalar(
                select(func.count()).select_from(Answer).where(
                    Answer.user_id == user_id,
                    Answer.mode == "blitz",
                    Answer.is_correct.is_(True),
                    Answer.created_at >= day_start,
                )
            )
            or 0
        )
        training_session = (
            await session.execute(
                select(UserSession)
                .where(
                    UserSession.user_id == user_id,
                    UserSession.mode == "training",
                    UserSession.started_at >= day_start,
                )
                .order_by(UserSession.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        duel_won = bool(
            await session.scalar(
                select(func.count()).select_from(Duel).where(
                    Duel.user_id == user_id,
                    Duel.user_won.is_(True),
                    Duel.played_at >= day_start,
                )
            )
        )
        daily_answer = bool(
            await session.scalar(
                select(func.count()).select_from(DailyQuestionAnswer).where(
                    DailyQuestionAnswer.user_id == user_id,
                    DailyQuestionAnswer.question_date == today(),
                )
            )
        )
        exams_today = int(
            await session.scalar(
                select(func.count()).select_from(ExamAttempt).where(
                    ExamAttempt.user_id == user_id,
                    ExamAttempt.started_at >= day_start,
                )
            )
            or 0
        )
    user = await get_user(user_id)
    return {
        "answers_today": answers_today,
        "current_streak": user.streak_answers if user else 0,
        "mistakes_fixed_today": fixed_today,
        "starred_done_today": starred_today,
        "blitz_correct_today": blitz_correct,
        "training_duration_minutes": int((training_session.duration_seconds or 0) / 60) if training_session else 0,
        "duel_won_today": duel_won,
        "daily_answered": daily_answer,
        "exam_completed": exams_today,
    }


async def check_daily_challenge(session: Any, user: User) -> dict[str, Any] | None:
    challenge = (
        await session.execute(
            select(DailyChallenge).where(
                DailyChallenge.user_id == user.telegram_id,
                DailyChallenge.challenge_date == today(),
            )
        )
    ).scalar_one_or_none()
    if challenge is None:
        challenge = DailyChallenge(
            user_id=user.telegram_id,
            challenge_date=today(),
            challenge_type=DAILY_CHALLENGES[today().weekday()]["type"],
        )
        session.add(challenge)
        await session.flush()

    if challenge.completed:
        return None

    stats = await get_today_stats(user.telegram_id)
    ctype = challenge.challenge_type
    completed = False
    if ctype == "streak_5":
        completed = stats["current_streak"] >= 5
    elif ctype == "blitz_10":
        completed = stats["blitz_correct_today"] >= 10
    elif ctype == "fix_5":
        completed = stats["mistakes_fixed_today"] >= 5
    elif ctype == "starred_3":
        completed = stats["starred_done_today"] >= 3
    elif ctype == "duel":
        completed = stats["duel_won_today"]
    elif ctype == "marathon_30":
        completed = stats["answers_today"] >= 30
    elif ctype == "easy_1":
        completed = stats["daily_answered"]

    if not completed:
        return None

    challenge.completed = True
    challenge.completed_at = utcnow()
    cfg = DAILY_CHALLENGES[today().weekday()]
    await award_xp(session, user, int(cfg["xp"]), "challenge_completed")
    await award_coins(user, int(cfg["coins"]))
    return cfg


async def get_route_day(user: User) -> int | None:
    if user.route_started_at is None:
        return None
    days_since_start = (today() - user.route_started_at).days
    return min(days_since_start + 1, 14)


async def evaluate_route_progress(session: Any, user: User) -> int | None:
    route_day = await get_route_day(user)
    if route_day is None or route_day not in ROUTE_TASKS:
        return None
    completed_map = dict(user.route_day_completed or {})
    if completed_map.get(str(route_day)):
        return None

    task = ROUTE_TASKS[route_day]
    stats = await get_today_stats(user.telegram_id)
    complete = False
    if task["mode"] == "trail":
        complete = stats["answers_today"] >= 20
    elif task["mode"] == "training":
        complete = stats["training_duration_minutes"] >= 1 or stats["answers_today"] >= 20
    elif task["mode"] == "blitz":
        complete = stats["blitz_correct_today"] >= 15
    elif task["mode"] == "exam":
        complete = stats["exam_completed"] >= 1
    elif task["mode"] == "mistakes":
        complete = stats["mistakes_fixed_today"] >= 5

    if not complete:
        return None

    completed_map[str(route_day)] = True
    user.route_day_completed = completed_map
    await award_xp(session, user, XP_RULES["daily_task"], "daily_task")
    await award_coins(user, 15)
    return route_day


async def save_answer(
    user_id: int,
    question_id: int,
    selected_answer: str,
    mode: str,
    time_spent_seconds: int | None = None,
    hint_used: str | None = None,
) -> AnswerOutcome:
    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        question = (
            await session.execute(select(Question).where(Question.id == question_id))
        ).scalar_one_or_none()
        if user is None or question is None:
            raise ValueError("User or question not found.")

        previous_correct_total = user.correct_answers
        previous_correct_answer = bool(
            await session.scalar(
                select(func.count()).select_from(Answer).where(
                    Answer.user_id == user_id,
                    Answer.question_id == question_id,
                    Answer.is_correct.is_(True),
                )
            )
        )
        is_correct = selected_answer == question.correct_answer
        mistake_fixed = False
        if is_correct and not previous_correct_answer:
            previous_wrong = bool(
                await session.scalar(
                    select(func.count()).select_from(Answer).where(
                        Answer.user_id == user_id,
                        Answer.question_id == question_id,
                        Answer.is_correct.is_(False),
                    )
                )
            )
            mistake_fixed = previous_wrong

        session.add(
            Answer(
                user_id=user_id,
                question_id=question_id,
                mode=mode,
                selected_answer=selected_answer,
                is_correct=is_correct,
                time_spent_seconds=time_spent_seconds,
                hint_used=hint_used,
            )
        )

        user.last_seen_at = utcnow()
        if user.last_activity_date != today():
            if user.last_activity_date == today() - timedelta(days=1):
                user.streak_days += 1
            else:
                user.streak_days = 1
            user.streak_best = max(user.streak_best, user.streak_days)
            user.last_activity_date = today()
        if is_correct:
            user.streak_answers += 1
            user.streak_answers_best = max(user.streak_answers_best, user.streak_answers)
        else:
            user.streak_answers = 0

        xp_added = get_xp_for_answer(mode, is_correct, not previous_correct_answer, time_spent_seconds)
        if mistake_fixed:
            xp_added = max(xp_added, XP_RULES["mistake_fixed"])
        if user.streak_answers in {5, 10, 20, 50} and is_correct:
            xp_added += XP_RULES[f"streak_{user.streak_answers}"]
        coins_added = get_coin_for_answer(mode, is_correct)

        await award_xp(session, user, xp_added, f"answer:{mode}")
        await award_coins(user, coins_added)
        await update_spaced_repetition(session, user_id, question_id, is_correct)
        await update_user_progress_fields(session, user)
        await update_question_global_stats(session, question_id)
        rank_up = get_rank_up_payload(previous_correct_total, user.correct_answers)
        if rank_up:
            await award_xp(session, user, 50, f"rank:{rank_up['new']['code']}")
            await award_coins(user, COIN_RULES["new_rank"])

        challenge_completed = await check_daily_challenge(session, user)
        route_day_completed = await evaluate_route_progress(session, user)
        achievements = await check_and_unlock_achievements(session, user)

        user.updated_at = utcnow()
        await session.commit()
        return AnswerOutcome(
            is_correct=is_correct,
            xp_added=xp_added,
            coins_added=coins_added,
            answer_streak=user.streak_answers,
            rank_up=rank_up,
            achievements=achievements,
            challenge_completed=challenge_completed,
            route_day_completed=route_day_completed,
            mistake_fixed=mistake_fixed,
        )


async def answer_daily_question(user_id: int, selected_answer: str) -> dict[str, Any]:
    daily_question = await get_or_create_daily_question()
    question = await get_question(daily_question.question_id)
    if question is None:
        raise ValueError("Daily question not found.")

    async with async_session() as session:
        existing = (
            await session.execute(
                select(DailyQuestionAnswer).where(
                    DailyQuestionAnswer.user_id == user_id,
                    DailyQuestionAnswer.question_date == daily_question.question_date,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return {"already_answered": True, "question": question}

        user = (
            await session.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise ValueError("User not found.")

        is_correct = selected_answer == question.correct_answer
        session.add(
            DailyQuestionAnswer(
                user_id=user_id,
                question_date=daily_question.question_date,
                selected_answer=selected_answer,
                is_correct=is_correct,
            )
        )
        daily_question.total_answers += 1
        if is_correct:
            daily_question.correct_answers += 1
        daily_question.correct_percent = calculate_accuracy(
            daily_question.correct_answers,
            daily_question.total_answers,
        )

        user.last_seen_at = utcnow()
        if is_correct:
            user.daily_question_streak += 1
            user.daily_question_streak_best = max(
                user.daily_question_streak_best,
                user.daily_question_streak,
            )
            await award_xp(session, user, XP_RULES["daily_question_correct"], "daily_question")
            await award_coins(user, COIN_RULES["daily_question_correct"])
        else:
            user.daily_question_streak = 0

        await session.commit()

        wrong_counter = Counter()
        rows = (
            await session.execute(
                select(DailyQuestionAnswer.selected_answer)
                .where(DailyQuestionAnswer.question_date == daily_question.question_date)
            )
        ).scalars().all()
        for value in rows:
            if value != question.correct_answer:
                wrong_counter[value] += 1
        most_wrong = wrong_counter.most_common(1)
        return {
            "already_answered": False,
            "question": question,
            "is_correct": is_correct,
            "correct_percent": daily_question.correct_percent,
            "most_wrong": most_wrong[0] if most_wrong else None,
            "daily_streak": user.daily_question_streak,
        }


async def finish_exam_attempt(
    user_id: int,
    answers_detail: list[dict[str, Any]],
    started_at: datetime,
    completed_at: datetime,
) -> dict[str, Any]:
    correct_count = sum(1 for item in answers_detail if item["is_correct"])
    wrong_count = len(answers_detail) - correct_count
    score_percent = calculate_accuracy(correct_count, len(answers_detail))
    passed = score_percent >= EXAM_PASS_PERCENT

    block_stats: dict[int, dict[str, int]] = {
        1: {"total": 0, "correct": 0},
        2: {"total": 0, "correct": 0},
        3: {"total": 0, "correct": 0},
    }
    for item in answers_detail:
        block_stats[item["block"]]["total"] += 1
        if item["is_correct"]:
            block_stats[item["block"]]["correct"] += 1

    time_spent_minutes = max(int((completed_at - started_at).total_seconds() / 60), 1)
    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise ValueError("User not found.")

        xp_reason = "exam_pass_90" if score_percent >= 90 else "exam_pass_80" if score_percent >= 80 else "exam_pass_75" if passed else "exam_completed"
        xp_bonus = XP_RULES[xp_reason]
        await award_xp(session, user, xp_bonus, xp_reason)
        if passed:
            await award_coins(user, COIN_RULES["exam_passed"])

        user.exams_taken += 1
        if passed:
            user.exams_passed += 1
        user.best_exam_score = max(user.best_exam_score, score_percent)

        attempt = ExamAttempt(
            user_id=user_id,
            questions_count=len(answers_detail),
            correct_count=correct_count,
            wrong_count=wrong_count,
            score_percent=score_percent,
            passed=passed,
            block1_total=block_stats[1]["total"],
            block1_correct=block_stats[1]["correct"],
            block1_percent=calculate_accuracy(block_stats[1]["correct"], block_stats[1]["total"]),
            block2_total=block_stats[2]["total"],
            block2_correct=block_stats[2]["correct"],
            block2_percent=calculate_accuracy(block_stats[2]["correct"], block_stats[2]["total"]),
            block3_total=block_stats[3]["total"],
            block3_correct=block_stats[3]["correct"],
            block3_percent=calculate_accuracy(block_stats[3]["correct"], block_stats[3]["total"]),
            time_limit_minutes=90,
            time_spent_minutes=time_spent_minutes,
            answers_detail=answers_detail,
            started_at=started_at,
            completed_at=completed_at,
        )
        session.add(attempt)
        await update_user_progress_fields(session, user)
        achievements = await check_and_unlock_achievements(session, user)
        await session.commit()
        return {
            "passed": passed,
            "score_percent": score_percent,
            "xp_bonus": xp_bonus,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "block_stats": block_stats,
            "time_spent_minutes": time_spent_minutes,
            "achievements": achievements,
        }


async def record_user_session(
    user_id: int,
    mode: str,
    questions_count: int,
    correct_count: int,
    max_streak: int,
    started_at: datetime,
    ended_at: datetime,
) -> None:
    async with async_session() as session:
        session.add(
            UserSession(
                user_id=user_id,
                mode=mode,
                questions_count=questions_count,
                correct_count=correct_count,
                max_streak=max_streak,
                duration_seconds=max(int((ended_at - started_at).total_seconds()), 1),
                started_at=started_at,
                ended_at=ended_at,
            )
        )
        await session.commit()


async def record_duel(user_id: int, user_score: int, bot_score: int, answers_detail: list[dict[str, Any]]) -> dict[str, Any]:
    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise ValueError("User not found.")

        user_won = user_score >= bot_score
        session.add(
            Duel(
                user_id=user_id,
                user_score=user_score,
                bot_score=bot_score,
                user_won=user_won,
                questions_count=len(answers_detail),
                answers_detail=answers_detail,
            )
        )
        if user_won:
            user.duel_wins += 1
            await award_xp(session, user, XP_RULES["duel_win"], "duel_win")
            await award_coins(user, COIN_RULES["duel_win"])
        else:
            await award_xp(session, user, XP_RULES["duel_loss"], "duel_loss")

        achievements = await check_and_unlock_achievements(session, user)
        await session.commit()
        return {"user_won": user_won, "achievements": achievements}


async def get_cards_catalog(user_id: int) -> dict[str, Any]:
    async with async_session() as session:
        total_cards = int(await session.scalar(select(func.count()).select_from(AnimalCard)) or 0)
        viewed_cards = int(
            await session.scalar(select(func.count()).select_from(AnimalCardView).where(AnimalCardView.user_id == user_id))
            or 0
        )
        result = await session.execute(
            select(AnimalCard.category, func.count()).group_by(AnimalCard.category).order_by(AnimalCard.category.asc())
        )
        categories = [{"name": name, "count": count} for name, count in result.fetchall()]
    return {
        "total": total_cards,
        "viewed": viewed_cards,
        "percent": calculate_accuracy(viewed_cards, total_cards),
        "categories": categories,
    }


async def get_cards_by_category(category: str) -> list[AnimalCard]:
    async with async_session() as session:
        result = await session.execute(select(AnimalCard).where(AnimalCard.category == category).order_by(AnimalCard.name.asc()))
        return list(result.scalars().all())


async def get_card_details(user_id: int, card_id: int) -> dict[str, Any] | None:
    async with async_session() as session:
        card = (
            await session.execute(select(AnimalCard).where(AnimalCard.id == card_id))
        ).scalar_one_or_none()
        if card is None:
            return None
        existing_view = (
            await session.execute(
                select(AnimalCardView).where(
                    AnimalCardView.user_id == user_id,
                    AnimalCardView.card_id == card_id,
                )
            )
        ).scalar_one_or_none()
        if existing_view is None:
            session.add(AnimalCardView(user_id=user_id, card_id=card_id))
            await session.flush()
        question_ids = (
            await session.execute(
                select(AnimalCardQuestion.question_id).where(AnimalCardQuestion.animal_card_id == card_id)
            )
        ).scalars().all()
        correct = int(
            await session.scalar(
                select(func.count(distinct(Answer.question_id))).where(
                    Answer.user_id == user_id,
                    Answer.question_id.in_(list(question_ids) or [-1]),
                    Answer.is_correct.is_(True),
                )
            )
            or 0
        )
        question_count = len(set(question_ids))
        await session.commit()
        return {
            "card": card,
            "question_count": question_count,
            "correct_count": correct,
            "percent": calculate_accuracy(correct, question_count),
        }


async def get_journal_stats(user_id: int) -> dict[str, Any]:
    user = await get_user(user_id)
    if user is None:
        raise ValueError("User not found.")
    block1 = await get_block_accuracy(user_id, 1)
    block2 = await get_block_accuracy(user_id, 2)
    block3 = await get_block_accuracy(user_id, 3)
    achievement_count = await count_achievements(user_id)
    starred_count = await count_starred(user_id)
    rank = get_rank_by_correct(user.correct_answers)
    next_rank = get_next_rank_by_correct(user.correct_answers)
    current_level, level_name = get_xp_level(user.xp_total)
    next_level = get_next_xp_level(user.xp_total)
    return {
        "user": user,
        "rank": rank,
        "next_rank": next_rank,
        "level": current_level,
        "level_name": level_name,
        "next_level": next_level,
        "achievements": achievement_count,
        "starred": starred_count,
        "block1": block1,
        "block2": block2,
        "block3": block3,
        "weak_topics": await get_weak_topics(user_id),
    }


async def get_exam_history(user_id: int) -> list[ExamAttempt]:
    async with async_session() as session:
        result = await session.execute(
            select(ExamAttempt)
            .where(ExamAttempt.user_id == user_id)
            .order_by(ExamAttempt.started_at.desc())
            .limit(10)
        )
        return list(result.scalars().all())


async def get_progress_chart(user_id: int, days: int = 14) -> dict[str, Any]:
    points: list[int] = []
    totals: list[int] = []
    async with async_session() as session:
        for offset in range(days - 1, -1, -1):
            day = today() - timedelta(days=offset)
            day_start = datetime.combine(day, time.min)
            day_end = datetime.combine(day, time.max)
            total = int(
                await session.scalar(
                    select(func.count()).select_from(Answer).where(
                        Answer.user_id == user_id,
                        Answer.created_at >= day_start,
                        Answer.created_at <= day_end,
                    )
                )
                or 0
            )
            totals.append(total)
            correct = int(
                await session.scalar(
                    select(func.count()).select_from(Answer).where(
                        Answer.user_id == user_id,
                        Answer.is_correct.is_(True),
                        Answer.created_at >= day_start,
                        Answer.created_at <= day_end,
                    )
                )
                or 0
            )
            points.append(int(calculate_accuracy(correct, total)) if total else 50)
    has_activity = any(total > 0 for total in totals)
    diff = points[-1] - points[0] if len(points) > 1 else 0
    return {
        "points": points if has_activity else [],
        "chart": generate_ascii_chart(points),
        "diff": diff,
        "estimate_days": max(1, int((80 - points[-1]) / max(diff, 1))) if has_activity and points[-1] < 80 else 0,
        "has_activity": has_activity,
    }


async def get_achievement_overview(user_id: int) -> dict[str, Any]:
    unlocked_codes = await get_unlocked_achievement_codes(user_id)
    stats = await build_achievement_stats(user_id)
    items: list[dict[str, Any]] = []
    nearest: list[dict[str, Any]] = []
    for achievement in ACHIEVEMENTS:
        unlocked = achievement["code"] in unlocked_codes
        metric_value = stats.get(achievement["metric"], 0)
        target = achievement["target"]
        percent = 100.0 if unlocked else calculate_accuracy(min(int(metric_value), int(target)), int(target))
        payload = {**achievement, "unlocked": unlocked, "current": metric_value, "percent": percent}
        items.append(payload)
        if not unlocked:
            nearest.append(payload)
    nearest.sort(key=lambda item: item["percent"], reverse=True)
    return {
        "items": items,
        "unlocked": len(unlocked_codes),
        "nearest": nearest[:3],
    }


async def get_route_overview(user_id: int) -> dict[str, Any]:
    user = await get_user(user_id)
    if user is None:
        raise ValueError("User not found.")
    if user.route_started_at is None:
        user = await update_user(user_id, route_started_at=today(), route_day_completed=user.route_day_completed)
    current_day = await get_route_day(user)
    completed_map = user.route_day_completed or {}
    completed = sum(1 for value in completed_map.values() if value)
    days: list[dict[str, Any]] = []
    for day_number, task in ROUTE_TASKS.items():
        status = "future"
        if str(day_number) in completed_map:
            status = "done"
        elif current_day == day_number:
            status = "today"
        days.append({"day": day_number, "task": task, "status": status})
    return {
        "current_day": current_day,
        "completed": completed,
        "percent": calculate_accuracy(completed, len(ROUTE_TASKS)),
        "days": days,
    }


async def get_route_task(user_id: int, day_number: int | None = None) -> dict[str, Any] | None:
    user = await get_user(user_id)
    if user is None:
        return None
    route_day = day_number or await get_route_day(user)
    if route_day is None or route_day not in ROUTE_TASKS:
        return None
    return {"day": route_day, "task": ROUTE_TASKS[route_day]}


async def create_promo_code(code: str, discount_percent: int, max_uses: int, days_valid: int | None, created_by: int | None) -> PromoCode:
    async with async_session() as session:
        promo = PromoCode(
            code=code.upper(),
            discount_percent=discount_percent,
            max_uses=max_uses,
            valid_until=(utcnow() + timedelta(days=days_valid)) if days_valid else None,
            created_by=created_by,
        )
        session.add(promo)
        await session.commit()
        await session.refresh(promo)
        return promo


async def list_promo_codes() -> list[PromoCode]:
    async with async_session() as session:
        result = await session.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
        return list(result.scalars().all())


async def apply_promo_code(user_id: int, code: str) -> dict[str, Any]:
    async with async_session() as session:
        promo = (
            await session.execute(select(PromoCode).where(PromoCode.code == code.upper()))
        ).scalar_one_or_none()
        user = (
            await session.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise ValueError("User not found.")
        if promo is None:
            return {"ok": False, "error": "Промокод не найден."}
        if promo.valid_until and promo.valid_until < utcnow():
            return {"ok": False, "error": "Промокод истёк."}
        if promo.used_count >= promo.max_uses:
            return {"ok": False, "error": "Лимит активаций исчерпан."}
        if user.promo_code_used:
            return {"ok": False, "error": "Вы уже использовали промокод."}

        user.promo_code_used = promo.code
        promo.used_count += 1
        if promo.discount_percent >= 100:
            user.access_level = "premium"
            user.premium_activated_at = utcnow()
            await session.commit()
            return {"ok": True, "activated": True, "discount_percent": promo.discount_percent}

        await session.commit()
        discounted = round(PREMIUM_PRICES["rub"] * (100 - promo.discount_percent) / 100)
        return {"ok": True, "activated": False, "discount_percent": promo.discount_percent, "discounted_price": discounted}


async def grant_premium(user_id: int) -> User | None:
    return await update_user(user_id, access_level="premium", premium_activated_at=utcnow())


async def revoke_premium(user_id: int) -> User | None:
    return await update_user(user_id, access_level="free")


async def create_payment(user_id: int, amount: int, currency: str, provider: str, provider_payment_id: str, status: str = "pending", product: str = "premium", promo_code: str | None = None) -> Payment:
    async with async_session() as session:
        payment = Payment(
            user_id=user_id,
            amount=amount,
            currency=currency,
            provider=provider,
            provider_payment_id=provider_payment_id,
            status=status,
            product=product,
            promo_code=promo_code,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment


async def get_payment_record(payment_id: int, user_id: int | None = None) -> Payment | None:
    async with async_session() as session:
        query = select(Payment).where(Payment.id == payment_id)
        if user_id is not None:
            query = query.where(Payment.user_id == user_id)
        payment = (await session.execute(query)).scalar_one_or_none()
        return payment


async def get_payment_by_provider_payment_id(provider_payment_id: str) -> Payment | None:
    async with async_session() as session:
        payment = (
            await session.execute(select(Payment).where(Payment.provider_payment_id == provider_payment_id))
        ).scalar_one_or_none()
        return payment


async def bind_payment_provider_payment_id(payment_id: int, provider_payment_id: str) -> Payment | None:
    async with async_session() as session:
        payment = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
        if payment is None:
            return None
        payment.provider_payment_id = provider_payment_id
        await session.commit()
        await session.refresh(payment)
        return payment


async def update_payment_status(payment_id: int, status: str) -> Payment | None:
    async with async_session() as session:
        payment = (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
        if payment is None:
            return None
        payment.status = status
        if status == "completed" and payment.completed_at is None:
            payment.completed_at = utcnow()
        await session.commit()
        await session.refresh(payment)
        return payment


async def complete_payment(provider_payment_id: str) -> Payment | None:
    async with async_session() as session:
        payment = (
            await session.execute(select(Payment).where(Payment.provider_payment_id == provider_payment_id))
        ).scalar_one_or_none()
        if payment is None:
            return None
        if payment.status == "completed":
            return payment
        payment.status = "completed"
        payment.completed_at = utcnow()
        user = (
            await session.execute(select(User).where(User.telegram_id == payment.user_id))
        ).scalar_one_or_none()
        if user:
            user.access_level = "premium"
            user.premium_activated_at = utcnow()
        await session.commit()
        await session.refresh(payment)
        return payment


async def get_admin_dashboard() -> dict[str, Any]:
    async with async_session() as session:
        total_users = int(await session.scalar(select(func.count()).select_from(User)) or 0)
        premium_users = int(
            await session.scalar(select(func.count()).select_from(User).where(User.access_level == "premium"))
            or 0
        )
        dau = int(
            await session.scalar(
                select(func.count()).select_from(User).where(User.last_seen_at >= utcnow() - timedelta(days=1))
            )
            or 0
        )
        wau = int(
            await session.scalar(
                select(func.count()).select_from(User).where(User.last_seen_at >= utcnow() - timedelta(days=7))
            )
            or 0
        )
        revenue_total = int(
            await session.scalar(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "completed")
            )
            or 0
        )
        revenue_30d = int(
            await session.scalar(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == "completed",
                    Payment.created_at >= utcnow() - timedelta(days=30),
                )
            )
            or 0
        )
        avg_exam = float(await session.scalar(select(func.coalesce(func.avg(ExamAttempt.score_percent), 0.0))) or 0.0)
        exams_passed = int(await session.scalar(select(func.count()).select_from(ExamAttempt).where(ExamAttempt.passed.is_(True))) or 0)
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "premium_percent": calculate_accuracy(premium_users, total_users),
        "dau": dau,
        "wau": wau,
        "revenue_total": revenue_total,
        "revenue_30d": revenue_30d,
        "avg_exam": round(avg_exam, 1),
        "exams_passed": exams_passed,
    }


async def get_user_card(user_id: int) -> dict[str, Any] | None:
    user = await get_user(user_id)
    if user is None:
        return None
    paid = 0
    paid_date = None
    async with async_session() as session:
        payment = (
            await session.execute(
                select(Payment)
                .where(Payment.user_id == user_id, Payment.status == "completed")
                .order_by(Payment.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if payment:
            paid = payment.amount
            paid_date = payment.completed_at or payment.created_at
    stats = await get_journal_stats(user_id)
    return {"user": user, "stats": stats, "payment_amount": paid, "payment_date": paid_date}


async def reset_user_progress(user_id: int) -> bool:
    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == user_id))
        ).scalar_one_or_none()
        if user is None:
            return False

        for model in (
            Answer,
            ExamAttempt,
            UserAchievement,
            Duel,
            DailyChallenge,
            SpacedRepetition,
            StarredQuestion,
            DailyQuestionAnswer,
            HintUsage,
            CoinPurchase,
            XPTransaction,
            AnimalCardView,
            ReminderLog,
            UserSession,
        ):
            await session.execute(delete(model).where(model.user_id == user_id))

        user.questions_completed = 0
        user.total_answers = 0
        user.correct_answers = 0
        user.wrong_answers = 0
        user.accuracy = 0.0
        user.xp_total = 0
        user.xp_level = 1
        user.coins = 0
        user.rank_code = "egg"
        user.streak_days = 0
        user.streak_best = 0
        user.streak_answers = 0
        user.streak_answers_best = 0
        user.daily_question_streak = 0
        user.daily_question_streak_best = 0
        user.last_activity_date = None
        user.exams_taken = 0
        user.exams_passed = 0
        user.best_exam_score = 0.0
        user.duel_wins = 0
        user.route_started_at = None
        user.route_day_completed = {}
        user.updated_at = utcnow()
        await session.commit()
        return True


async def get_active_users(days: int = 90, premium_only: bool = False) -> list[User]:
    async with async_session() as session:
        query = select(User).where(User.last_seen_at >= utcnow() - timedelta(days=days))
        if premium_only:
            query = query.where(User.access_level == "premium")
        result = await session.execute(query.order_by(User.last_seen_at.desc()))
        return list(result.scalars().all())


async def log_broadcast(broadcast_type: str, text_preview: str, sent_count: int, failed_count: int, blocked_count: int, initiated_by: int | None) -> None:
    async with async_session() as session:
        session.add(
            BroadcastLog(
                broadcast_type=broadcast_type,
                text_preview=text_preview[:200],
                sent_count=sent_count,
                failed_count=failed_count,
                blocked_count=blocked_count,
                initiated_by=initiated_by,
            )
        )
        await session.commit()


async def get_questions_stats() -> list[dict[str, Any]]:
    async with async_session() as session:
        result = await session.execute(
            select(Question).order_by(Question.global_accuracy.asc(), Question.times_answered.desc()).limit(20)
        )
        items = []
        for question in result.scalars().all():
            items.append(
                {
                    "id": question.id,
                    "accuracy": question.global_accuracy,
                    "text": question.question_text,
                    "times_answered": question.times_answered,
                }
            )
        return items


async def should_send_reminder(user_id: int, reminder_type: str) -> bool:
    cooldowns = {
        "streak_warning": timedelta(hours=20),
        "gentle_reminder": timedelta(hours=44),
        "progress_reminder": timedelta(hours=68),
        "week_away": timedelta(days=6),
        "two_weeks_away": timedelta(days=13),
        "month_away": None,
        "repetition": timedelta(hours=6),
    }
    async with async_session() as session:
        last_log = (
            await session.execute(
                select(ReminderLog)
                .where(ReminderLog.user_id == user_id, ReminderLog.reminder_type == reminder_type)
                .order_by(ReminderLog.sent_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if last_log is None:
        return True
    cooldown = cooldowns.get(reminder_type)
    if cooldown is None:
        return False
    return utcnow() - last_log.sent_at > cooldown


async def log_reminder(user_id: int, reminder_type: str) -> None:
    async with async_session() as session:
        session.add(ReminderLog(user_id=user_id, reminder_type=reminder_type))
        await session.commit()


def random_quote() -> str:
    return QUOTES[hash(today().isoformat()) % len(QUOTES)]
