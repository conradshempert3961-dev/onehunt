from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_catalog(name: str) -> list[dict]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_question_catalog_normalizes_to_257_unique_source_numbers() -> None:
    catalog = load_catalog("questions.json")

    seen: dict[int, dict] = {}
    duplicate_source_numbers: list[int] = []
    for item in catalog:
        source_number = int(item["sourceNumber"])
        if source_number in seen:
            duplicate_source_numbers.append(source_number)
            continue
        seen[source_number] = item

    assert duplicate_source_numbers == [118]
    assert len(seen) == 257
    assert list(sorted(seen)) == list(range(1, 258))


def test_question_catalog_answers_match_available_options() -> None:
    catalog = load_catalog("questions.json")

    for item in catalog:
        options = {option["key"] for option in item["options"]}
        assert item["correctOption"] in options, f"Question {item['id']} has invalid correctOption"

