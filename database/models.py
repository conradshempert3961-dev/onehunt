from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.database import Base
from utils.constants import DEFAULT_SETTINGS


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    questions_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_answers: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    wrong_answers: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)

    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    xp_level: Mapped[int] = mapped_column(Integer, default=1)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    rank_code: Mapped[str] = mapped_column(String(20), default="egg")

    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    streak_best: Mapped[int] = mapped_column(Integer, default=0)
    streak_answers: Mapped[int] = mapped_column(Integer, default=0)
    streak_answers_best: Mapped[int] = mapped_column(Integer, default=0)
    daily_question_streak: Mapped[int] = mapped_column(Integer, default=0)
    daily_question_streak_best: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    exams_taken: Mapped[int] = mapped_column(Integer, default=0)
    exams_passed: Mapped[int] = mapped_column(Integer, default=0)
    best_exam_score: Mapped[float] = mapped_column(Float, default=0.0)
    duel_wins: Mapped[int] = mapped_column(Integer, default=0)

    settings: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_SETTINGS))
    daily_reminder: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_hour: Mapped[int] = mapped_column(Integer, default=9)
    all_notifications_off: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_snoozed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    theme: Mapped[str] = mapped_column(String(20), default="forest")
    badge: Mapped[str | None] = mapped_column(String(20), nullable=True)

    access_level: Mapped[str] = mapped_column(String(10), default="free", index=True)
    premium_activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    promo_code_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    free_questions_used: Mapped[int] = mapped_column(Integer, default=0)
    free_trainings_used: Mapped[int] = mapped_column(Integer, default=0)

    route_started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    route_day_completed: Mapped[dict] = mapped_column(JSON, default=dict)
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_users_last_seen", "last_seen_at"),
        Index("ix_users_last_activity", "last_activity_date"),
        Index("ix_users_streak_days", "streak_days"),
    )

    @property
    def xp(self) -> int:
        return self.xp_total


class WebAccount(Base):
    __tablename__ = "web_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class WebSession(Base):
    __tablename__ = "web_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_web_sessions_expires_at", "expires_at"),
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    source_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    block: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    block_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(10), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mnemonic: Mapped[str | None] = mapped_column(Text, nullable=True)
    fun_fact: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    times_answered: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    global_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_questions_block_difficulty", "block", "difficulty"),
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    selected_answer: Mapped[str] = mapped_column(String(10), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hint_used: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_answers_user_question", "user_id", "question_id"),
        Index("ix_answers_user_correct", "user_id", "is_correct"),
        Index("ix_answers_user_mode", "user_id", "mode"),
        Index("ix_answers_created_at", "created_at"),
    )


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    questions_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    score_percent: Mapped[float] = mapped_column(Float, default=0.0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    block1_total: Mapped[int] = mapped_column(Integer, default=0)
    block1_correct: Mapped[int] = mapped_column(Integer, default=0)
    block1_percent: Mapped[float] = mapped_column(Float, default=0.0)
    block2_total: Mapped[int] = mapped_column(Integer, default=0)
    block2_correct: Mapped[int] = mapped_column(Integer, default=0)
    block2_percent: Mapped[float] = mapped_column(Float, default=0.0)
    block3_total: Mapped[int] = mapped_column(Integer, default=0)
    block3_correct: Mapped[int] = mapped_column(Integer, default=0)
    block3_percent: Mapped[float] = mapped_column(Float, default=0.0)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_spent_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answers_detail: Mapped[list[dict]] = mapped_column(JSON, default=list)
    flagged_questions: Mapped[list[int]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    achievement_code: Mapped[str] = mapped_column(String(50), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_code", name="uq_user_achievement"),
    )


class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_score: Mapped[int] = mapped_column(Integer, default=0)
    bot_score: Mapped[int] = mapped_column(Integer, default=0)
    user_won: Mapped[bool] = mapped_column(Boolean, default=False)
    questions_count: Mapped[int] = mapped_column(Integer, default=10)
    answers_detail: Mapped[list[dict]] = mapped_column(JSON, default=list)
    played_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    challenge_date: Mapped[date] = mapped_column(Date, nullable=False)
    challenge_type: Mapped[str] = mapped_column(String(30), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "challenge_date", name="uq_daily_challenge"),
    )


class SpacedRepetition(Base):
    __tablename__ = "spaced_repetition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    correct_streak: Mapped[int] = mapped_column(Integer, default=0)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_repetition_user_question"),
        Index("ix_repetition_due", "user_id", "next_review_at"),
    )


class StarredQuestion(Base):
    __tablename__ = "starred_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    starred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "question_id", name="uq_starred_user_question"),
    )


class DailyQuestion(Base):
    __tablename__ = "daily_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    question_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    total_answers: Mapped[int] = mapped_column(Integer, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    correct_percent: Mapped[float] = mapped_column(Float, default=0.0)


class DailyQuestionAnswer(Base):
    __tablename__ = "daily_question_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    question_date: Mapped[date] = mapped_column(Date, nullable=False)
    selected_answer: Mapped[str] = mapped_column(String(10), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "question_date", name="uq_daily_question_answer"),
        Index("ix_daily_question_answer_date", "question_date"),
    )


class HintUsage(Base):
    __tablename__ = "hint_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    hint_type: Mapped[str] = mapped_column(String(20), nullable=False)
    coins_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CoinPurchase(Base):
    __tablename__ = "coin_purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)
    item_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    coins_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    product: Mapped[str] = mapped_column(String(50), default="premium")
    promo_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_payments_status", "status"),
        Index("ix_payments_provider_payment_id", "provider_payment_id"),
    )


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, default=100)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnimalCard(Base):
    __tablename__ = "animal_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    latin_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    order_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    weight: Mapped[str | None] = mapped_column(String(50), nullable=True)
    body_length: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lifespan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    habitat: Mapped[str | None] = mapped_column(Text, nullable=True)
    hunting_season: Mapped[str | None] = mapped_column(Text, nullable=True)
    special_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    track_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    track_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AnimalCardQuestion(Base):
    __tablename__ = "animal_card_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    animal_card_id: Mapped[int] = mapped_column(Integer, ForeignKey("animal_cards.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("animal_card_id", "question_id", name="uq_card_question"),
    )


class AnimalCardView(Base):
    __tablename__ = "animal_card_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("animal_cards.id"), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_user_card_view"),
    )


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_reminders_user_type", "user_id", "reminder_type"),
    )


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_type: Mapped[str] = mapped_column(String(30), nullable=False)
    text_preview: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    initiated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    questions_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    max_streak: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
