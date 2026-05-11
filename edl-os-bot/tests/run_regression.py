"""Регрессионный прогон 18 вопросов через настоящий Claude Haiku 4.5.

НЕ запускается в pytest (требует ANTHROPIC_API_KEY и кредитов).
Запуск вручную:
    cd edl-os-bot
    ANTHROPIC_API_KEY=sk-... python tests/run_regression.py

Печатает per-case результат и общий pass rate. Цель — ≥ 16/18 = 89%.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core import llm  # noqa: E402

REGRESSION_JSON = Path(__file__).parent / "regression_v3.json"


def check_case(answer: str, case: dict) -> tuple[bool, list[str]]:
    failures: list[str] = []
    lower = answer.lower()

    for term in case.get("must_include_all", []):
        if term.lower() not in lower:
            failures.append(f"missing required: '{term}'")

    any_terms = case.get("must_include_any") or []
    if any_terms and not any(t.lower() in lower for t in any_terms):
        failures.append(f"none of any-terms present: {any_terms}")

    for term in case.get("must_not_include", []):
        if term.lower() in lower:
            failures.append(f"forbidden term present: '{term}'")

    return (len(failures) == 0, failures)


async def run() -> int:
    data = json.loads(REGRESSION_JSON.read_text(encoding="utf-8"))
    cases = data["cases"]
    threshold = data.get("threshold_pass_rate", 0.89)

    passed = 0
    failed_cases: list[tuple[str, list[str]]] = []

    for i, case in enumerate(cases, start=1):
        print(f"[{i:02d}/{len(cases)}] {case['id']} ... ", end="", flush=True)
        try:
            answer, tokens = await llm.reply(
                user_text=case["input"],
                segment=case["segment"],
                stage=case.get("stage", "cold"),
                history=[],
            )
        except Exception as e:
            print(f"ERROR: {e}")
            failed_cases.append((case["id"], [f"exception: {e}"]))
            continue

        ok, failures = check_case(answer, case)
        if ok:
            print(f"PASS ({tokens} tokens)")
            passed += 1
        else:
            print(f"FAIL ({tokens} tokens)")
            for f in failures:
                print(f"    · {f}")
            failed_cases.append((case["id"], failures))

    rate = passed / len(cases)
    print()
    print(f"Pass: {passed}/{len(cases)} ({rate:.0%}). Threshold: {threshold:.0%}.")
    if rate < threshold:
        print("\nFAILED CASES:")
        for cid, fs in failed_cases:
            print(f"  {cid}: {fs}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
