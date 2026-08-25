"""
Eval harness. Runs every question in eval_set.json through the pipeline
twice — once with the clarification engine on, once off — and reports:

  - Ambiguity detection accuracy (precision/recall vs. expected_ambiguous)
  - "Silent wrong guess" rate: how often the no-clarification baseline
    produces SQL for a question that was actually ambiguous (this is the
    number that makes the case for the clarification engine)

Usage:
    python -m eval.run_eval
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Set UTF-8 encoding for standard output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path if run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline import run_pipeline

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
RESULTS_PATH = Path(__file__).parent / "results.json"


def load_eval_set() -> list[dict]:
    return json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))


def score_ambiguity_detection(cases: list[dict], results: list[dict]) -> dict:
    tp = fp = tn = fn = 0
    for case, result in zip(cases, results):
        expected = case["expected_ambiguous"]
        amb_check = result["with_clarification"].get("ambiguity_check", {})
        predicted = amb_check.get("is_ambiguous", False)
        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif not expected and not predicted:
            tn += 1
        elif expected and not predicted:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (tp + tn) / len(cases) if cases else 0.0

    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "accuracy": round(accuracy, 3),
    }


def score_silent_wrong_guesses(cases: list[dict], results: list[dict]) -> dict:
    """Of the questions that WERE actually ambiguous, how often did the
    baseline (no clarification) generate SQL anyway instead of asking?"""
    ambiguous_cases = [c for c in cases if c["expected_ambiguous"]]
    silent_guesses = 0
    for case, result in zip(cases, results):
        if case["expected_ambiguous"]:
            baseline = result["without_clarification"]
            if baseline.get("final_sql"):
                silent_guesses += 1
    rate = silent_guesses / len(ambiguous_cases) if ambiguous_cases else 0.0
    return {
        "ambiguous_case_count": len(ambiguous_cases),
        "silent_wrong_guesses": silent_guesses,
        "silent_guess_rate": round(rate, 3),
    }


def main():
    cases = load_eval_set()
    results = []
    total = len(cases)

    print(f"\n[EVAL] Running Text-to-SQL Clarification Engine Eval on {total} test cases...\n", flush=True)

    for idx, case in enumerate(cases, 1):
        q_id = case["id"]
        question = case["question"]
        expected = case["expected_ambiguous"]

        with_clar = run_pipeline(question, with_clarification=True)
        without_clar = run_pipeline(question, with_clarification=False)

        pred_amb = with_clar.ambiguity_check.is_ambiguous if with_clar.ambiguity_check else False
        status_tag = "[PASS]" if pred_amb == expected else "[FAIL]"

        results.append({
            "id": q_id,
            "question": question,
            "expected_ambiguous": expected,
            "with_clarification": with_clar.model_dump(),
            "without_clarification": without_clar.model_dump(),
        })

        clar_type = with_clar.ambiguity_check.ambiguity_type.value if with_clar.ambiguity_check else "none"
        print(f"[{idx:02d}/{total:02d}] {status_tag:<6} ID: {q_id:<9} | Expected Ambiguous: {str(expected):<5} | Detected: {str(pred_amb):<5} ({clar_type})", flush=True)
        if with_clar.clarification_asked and with_clar.ambiguity_check and with_clar.ambiguity_check.clarifying_question:
            print(f"         [Clarify] \"{with_clar.ambiguity_check.clarifying_question}\"", flush=True)
        elif not with_clar.clarification_asked and with_clar.final_sql:
            sql_snippet = with_clar.final_sql.replace("\n", " ")[:70]
            print(f"         [SQL] {sql_snippet}...", flush=True)

    ambiguity_scores = score_ambiguity_detection(cases, results)
    silent_guess_scores = score_silent_wrong_guesses(cases, results)

    summary = {
        "ambiguity_detection": ambiguity_scores,
        "silent_wrong_guesses": silent_guess_scores,
    }

    RESULTS_PATH.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY")
    print("=" * 50)
    print(json.dumps(summary, indent=2))
    print(f"\nFull results saved to: {RESULTS_PATH}\n")


if __name__ == "__main__":
    main()
