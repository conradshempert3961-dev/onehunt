from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.helpers import clean_option_text


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("question_id", "option_key", "raw", "expected"),
    [
        ("217", "a", "да; -.", "да."),
        ("94", "a", "только самцов;.", "только самцов."),
        ("17", "a", "требует специальной лицензии; о", "требует специальной лицензии"),
        ("159", "c", "осуществление охоты на рябчиков, лысуху, камышницу, серого гуся, белую и тундряную куропатку, на вальдшнепа на утренней тяге в период весенней охоты. -", "осуществление охоты на рябчиков, лысуху, камышницу, серого гуся, белую и тундряную куропатку, на вальдшнепа на утренней тяге в период весенней охоты."),
    ],
)
def test_clean_option_text_fixes_ocr_artifacts(
    question_id: str,
    option_key: str,
    raw: str,
    expected: str,
) -> None:
    assert clean_option_text(raw, question_id=question_id, option_key=option_key) == expected


def test_question_catalog_has_no_semicolon_artifacts() -> None:
    catalog = json.loads((ROOT / "questions.json").read_text(encoding="utf-8"))
    bad: list[str] = []
    for item in catalog:
        question_id = str(item.get("id") or "")
        for option in item.get("options") or []:
            text = str(option.get("text") or "")
            if "; -" in text or ";." in text or text.endswith(";") or ";" in text:
                bad.append(f"{question_id}/{option.get('key')}: {text!r}")
    assert bad == []
