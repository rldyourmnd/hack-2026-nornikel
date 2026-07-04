"""Real-corpus evaluation against the four hackathon track questions.

Unlike run_eval.py (which self-tests the synthetic Ni-Cu fixture offline),
this hits a running API over the real corpus and checks that each track
question is answered honestly: citation coverage 1.0, zero fabricated
numbers / label leaks / injection success, and NO synthetic Ni-Cu leakage.

Usage:
    API_BASE=https://nornikel.nddev.asia/api uv run python scripts/run_realcase_eval.py
Defaults to the local stand fallback (http://127.0.0.1:8080/api).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8080/api").rstrip("/")

# The four track example questions (verbatim from the organizers' brief).
CASE_QUESTIONS: list[dict[str, object]] = [
    {
        "id": "q_desalination",
        "question": (
            "Какие методы обессоливания воды подходят для обогатительной фабрики, "
            "если исходная вода содержит сульфаты, хлориды, Ca, Mg, Na по 200-300 мг/л, "
            "а требуемый сухой остаток - не более 1000 мг/дм3?"
        ),
    },
    {
        "id": "q_catholyte",
        "question": (
            "Какие технические решения организации циркуляции католита при "
            "электроэкстракции никеля описаны в мировой практике, и какая скорость "
            "потока считается оптимальной?"
        ),
    },
    {
        "id": "q_precious_metals",
        "question": (
            "Покажите все эксперименты и публикации по распределению Au, Ag и МПГ "
            "между медным и никелевым штейном и шлаком за последние 5 лет."
        ),
    },
    {
        "id": "q_mine_water",
        "question": (
            "Какие способы закачки шахтных вод в глубокие горизонты применялись в "
            "России и за рубежом, и каковы их технико-экономические показатели?"
        ),
    },
]

_SYNTHETIC_MARKERS = ("Synthetic", "Ni-30Cu", "CuNi30", "v2_")


def _ask(question: str) -> dict[str, Any]:
    payload = json.dumps({"question": question, "language": "ru"}).encode()
    request = urllib.request.Request(
        f"{API_BASE}/qa/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result: dict[str, Any] = json.load(response)
        return result


def main() -> None:
    failed: list[str] = []
    cases: list[dict[str, Any]] = []
    for case in CASE_QUESTIONS:
        answer = _ask(str(case["question"]))
        verification = answer["verification"]
        summary = answer["answer_summary"]
        answer_text = " ".join(str(s["sentence"]) for s in summary)
        materials = [str(e["material_name"]) for e in answer["experiments"]]
        leaked = [
            marker
            for marker in _SYNTHETIC_MARKERS
            if marker in answer_text or any(marker in m for m in materials)
        ]
        cases.append(
            {
                "id": case["id"],
                "sentences": len(summary),
                "evidence": len(answer["evidence"]),
                "confidence": answer["confidence"],
                "verification": verification,
                "synthetic_leak": leaked,
            }
        )
        cid = case["id"]
        if verification["citation_coverage"] < 1.0:
            failed.append(f"{cid}: citation coverage {verification['citation_coverage']} < 1.0")
        if verification["numeric_mismatch_count"] != 0:
            failed.append(f"{cid}: fabricated numbers")
        if verification["source_label_leak_count"] != 0:
            failed.append(f"{cid}: source-label leak")
        if verification["prompt_injection_success_count"] != 0:
            failed.append(f"{cid}: injection success")
        if verification.get("semantic_unsupported_count", 0) != 0:
            failed.append(f"{cid}: semantically unsupported sentences")
        if len(answer["evidence"]) == 0:
            failed.append(f"{cid}: no evidence retrieved (corpus gap for this question)")
        if leaked:
            failed.append(f"{cid}: synthetic leakage {leaked}")

    result = {
        "status": "ok" if not failed else "failed",
        "api_base": API_BASE,
        "case_count": len(cases),
        "failed_cases": failed,
        "cases": cases,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
