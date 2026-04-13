from utils.helpers import (
    calculate_accuracy,
    format_duration,
    format_streak_message,
    plural_form,
    truncate_text,
)


def test_truncate_short() -> None:
    assert truncate_text("Привет", 60) == "Привет"


def test_truncate_long() -> None:
    result = truncate_text("А" * 100, 60)
    assert len(result) == 60
    assert result.endswith("...")


def test_accuracy_zero() -> None:
    assert calculate_accuracy(0, 0) == 0.0


def test_accuracy_normal() -> None:
    assert calculate_accuracy(7, 10) == 70.0


def test_accuracy_full() -> None:
    assert calculate_accuracy(10, 10) == 100.0


def test_plural_1() -> None:
    assert plural_form(1, "вопрос", "вопроса", "вопросов") == "вопрос"


def test_plural_2() -> None:
    assert plural_form(2, "вопрос", "вопроса", "вопросов") == "вопроса"


def test_plural_5() -> None:
    assert plural_form(5, "вопрос", "вопроса", "вопросов") == "вопросов"


def test_plural_11() -> None:
    assert plural_form(11, "вопрос", "вопроса", "вопросов") == "вопросов"


def test_plural_21() -> None:
    assert plural_form(21, "вопрос", "вопроса", "вопросов") == "вопрос"


def test_plural_111() -> None:
    assert plural_form(111, "вопрос", "вопроса", "вопросов") == "вопросов"


def test_format_duration_seconds() -> None:
    assert format_duration(45) == "45 сек"


def test_format_duration_minutes() -> None:
    assert format_duration(125) == "2 мин 05 сек"


def test_format_duration_hours() -> None:
    assert format_duration(3725) == "1 ч 02 мин"


def test_streak_zero() -> None:
    assert "Начните" in format_streak_message(0)


def test_streak_small() -> None:
    assert "🔥" in format_streak_message(2)


def test_streak_medium() -> None:
    assert "🔥🔥" in format_streak_message(10)


def test_streak_legend() -> None:
    assert "ЛЕГЕНДА" in format_streak_message(35)
