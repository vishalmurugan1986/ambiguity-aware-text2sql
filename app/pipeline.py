"""
Core pipeline logic. Two modes:
  - with_clarification=True  -> run ambiguity check first, stop and ask if ambiguous
  - with_clarification=False -> skip straight to SQL generation (baseline for eval comparison)

This split is what lets you measure "accuracy with vs. without the clarification engine"
in the Days 9-10 eval.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from openai import OpenAI

from app.models import AmbiguityCheck, PipelineResult, SQLGeneration
from app.prompts import AMBIGUITY_SYSTEM_PROMPT, SQL_GENERATION_SYSTEM_PROMPT

MODEL = "meta/llama-3.1-70b-instruct"


_last_call_time = 0.0
MIN_CALL_INTERVAL_SEC = 1.6  # Keeps requests under 40 RPM (approx 37.5 req/min)


def get_client() -> OpenAI:
    api_key = os.environ.get("NVIDIA_API_KEY") or DEFAULT_NVIDIA_API_KEY
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )


def _extract_json(text: str) -> dict:
    """Extract JSON from raw model text with fallback patterns."""
    text = text.strip()
    
    # Strip markdown fences
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the outermost { ... }
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        cleaned = text[brace_start : brace_end + 1]
        return json.loads(cleaned)

    raise ValueError(f"Could not parse valid JSON from model response: {text!r}")


def _call_structured(system_prompt: str, user_message: str, max_retries: int = 4) -> dict:
    """Call the model, enforce rate limit (40 RPM), parse JSON, and handle retries."""
    global _last_call_time

    client = get_client()

    for attempt in range(max_retries):
        # Rate limit enforcement
        elapsed = time.time() - _last_call_time
        if elapsed < MIN_CALL_INTERVAL_SEC:
            time.sleep(MIN_CALL_INTERVAL_SEC - elapsed)

        try:
            _last_call_time = time.time()
            response = client.chat.completions.create(
                model=MODEL,
                temperature=0.2,
                top_p=0.7,
                max_tokens=1024,
                stream=False,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            raw_text = (response.choices[0].message.content or "").strip()
            return _extract_json(raw_text)
        except Exception as exc:
            err_str = str(exc)
            # Handle rate limiting (429) or transient network issues
            if ("429" in err_str or "Rate limit" in err_str or "timeout" in err_str.lower()) and attempt < max_retries - 1:
                backoff = (attempt + 1) * 3.0
                time.sleep(backoff)
                continue
            if attempt == max_retries - 1:
                raise


def check_ambiguity(question: str) -> AmbiguityCheck:
    raw = _call_structured(AMBIGUITY_SYSTEM_PROMPT, question)
    return AmbiguityCheck(**raw)


def generate_sql(question: str) -> SQLGeneration:
    raw = _call_structured(SQL_GENERATION_SYSTEM_PROMPT, question)
    return SQLGeneration(**raw)


def run_pipeline(question: str, with_clarification: bool = True) -> PipelineResult:
    """
    with_clarification=True:  detect ambiguity, stop and surface the clarifying
                               question instead of guessing.
    with_clarification=False: baseline â€” go straight to SQL generation, useful
                               as the "off" condition in the eval comparison.
    """
    if not with_clarification:
        try:
            sql_gen = generate_sql(question)
            return PipelineResult(
                question=question,
                ambiguity_check=AmbiguityCheck(is_ambiguous=False, reasoning="clarification disabled"),
                sql_generation=sql_gen,
                clarification_asked=False,
                final_sql=sql_gen.sql,
            )
        except Exception as e:
            return PipelineResult(
                question=question,
                ambiguity_check=AmbiguityCheck(is_ambiguous=False, reasoning="clarification disabled"),
                clarification_asked=False,
                error=str(e),
            )

    try:
        ambiguity_check = check_ambiguity(question)
    except Exception as e:
        return PipelineResult(
            question=question,
            ambiguity_check=AmbiguityCheck(is_ambiguous=False, reasoning="ambiguity check failed"),
            clarification_asked=False,
            error=str(e),
        )

    if ambiguity_check.is_ambiguous:
        return PipelineResult(
            question=question,
            ambiguity_check=ambiguity_check,
            clarification_asked=True,
            final_sql=None,
        )

    try:
        sql_gen = generate_sql(question)
        return PipelineResult(
            question=question,
            ambiguity_check=ambiguity_check,
            sql_generation=sql_gen,
            clarification_asked=False,
            final_sql=sql_gen.sql,
        )
    except Exception as e:
        return PipelineResult(
            question=question,
            ambiguity_check=ambiguity_check,
            clarification_asked=False,
            error=str(e),
        )

