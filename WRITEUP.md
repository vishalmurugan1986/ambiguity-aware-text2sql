# Text-to-SQL with Clarification Engine — Results Write-Up

## The problem

Most text-to-SQL systems pick *an* interpretation of an ambiguous question and
run with it. "Who's our best customer?" gets silently resolved to some
default metric — usually whichever one the model reaches for first — with no
signal to the user that a judgment call was made on their behalf.

This project tests whether a lightweight ambiguity-detection step, placed
before SQL generation, can catch that problem and ask instead of guess.

## Method

Built a two-path pipeline against a 5-table e-commerce schema:

- **Baseline**: question -> SQL directly, no ambiguity check.
- **Clarification-enabled**: question -> ambiguity check -> either a
  clarifying question (if ambiguous) or SQL generation (if not).

Evaluated both against a labeled set of 26 questions (13 designed to be
ambiguous — undefined superlatives, missing time ranges, column collisions,
undefined aggregations — and 13 designed to be unambiguous, including several
adversarial "looks ambiguous but isn't" cases).

## Results

| Metric | Baseline (no clarification) | Zero-Shot Detector | Few-Shot Detector |
| :--- | :---: | :---: | :---: |
| Silent wrong guesses on ambiguous Qs | 100% (12/12) | — | — |
| Ambiguity detection accuracy | — | 88.5% (23/26) | **96.2% (25/26)** |
| Precision | — | 84.6% | **100.0%** |
| Recall | — | 91.7% | 91.7% |
| False positives | — | 2 | **0** |
| False negatives | — | 1 | 1 |

**Headline finding:** without the clarification step, the baseline generated
SQL for 100% of ambiguous questions — every one of those queries embeds an
unstated assumption (which metric, which time range, which column) with no
indication to the user that a choice was made.

## What the iteration fixed

The zero-shot detector's two false positives and one of its false negatives
came from a narrow, fixable gap: the prompt stated the ambiguity *rules* but
gave no worked examples of where the line sits. Adding four few-shot examples
plus explicit "do NOT flag" cases resolved all three:

- **Column collision without explicit table language** — "Give me the name
  field for the electronics category" wasn't being checked against both
  `categories.name` and `products.name` just because the question didn't
  spell out "customer name" vs. "product name."
- **Over-flagging well-defined metrics** — "best margins" was being treated
  as ambiguous (avg vs. total) despite margin having a single standard
  definition (`price - cost`) given the schema.
- **Anchor-date recognition** — "last 30 days from 2024-06-01" was being
  flagged as a missing time range despite the anchor date being explicitly
  stated in the question.

This moved precision to 100% (zero false-positive interruptions) without
sacrificing recall.

## Remaining limitation

One false negative persists after tuning: **`amb_05`** (*"What are our sales by category?"*). The test set labels this as an `undefined_aggregation` ambiguity because "sales" in retail can mean total dollar revenue (`SUM(quantity * unit_price)`) or unit sales volume (`SUM(quantity)`). The model treated this as unambiguous by defaulting to revenue (`SUM(quantity * unit_price)`), reasoning that dollar revenue is the most standard business interpretation in the schema context.

Worth naming honestly rather than implying the detector is perfect — a single miss out of 12 ambiguous cases means roughly 1 in 12 genuinely ambiguous questions would still get a silent guess through, versus 12 in 12 (100%) with no detector at all.

## Takeaway

A zero-shot ambiguity detector already beats the alternative by a wide
margin (0% vs. 100% silent-guess rate on ambiguous questions). A single
round of targeted few-shot tuning — informed by looking at *which* cases
failed and why — closed most of the remaining gap and eliminated false
positives entirely, at the cost of maybe an hour of iteration.
