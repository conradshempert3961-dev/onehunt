#!/usr/bin/env python3
"""Fix OCR/import artifacts in questions.json option texts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.helpers import clean_option_text, normalize_option_key


def sanitize_catalog(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for item in data:
        question_id = str(item.get("id") or item.get("sourceNumber") or "")
        for option in item.get("options") or []:
            if not isinstance(option, dict):
                continue
            key = normalize_option_key(str(option.get("key") or option.get("label") or ""))
            raw = str(option.get("text") or "")
            cleaned = clean_option_text(raw, question_id=question_id, option_key=key)
            if cleaned != raw:
                option["text"] = cleaned
                changed += 1
        correct = item.get("correctAnswer")
        if isinstance(correct, str) and correct.strip():
            cleaned_correct = clean_option_text(correct, question_id=question_id, option_key="")
            correct_key = normalize_option_key(str(item.get("correctOption") or ""))
            if correct_key:
                for option in item.get("options") or []:
                    if normalize_option_key(str(option.get("key") or "")) == correct_key:
                        option["text"] = cleaned_correct
                        break
            if cleaned_correct != correct.strip():
                item["correctAnswer"] = cleaned_correct
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "questions.json")
    count = sanitize_catalog(target)
    print(f"Sanitized {count} option texts in {target}")
