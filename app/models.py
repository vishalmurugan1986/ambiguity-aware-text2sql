"""
Structured output models. This is the pattern you'll reuse across
projects 1, 3, and 4 — force the LLM into a schema instead of parsing
free text.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AmbiguityType(str, Enum):
    MISSING_TIME_RANGE = "missing_time_range"
    UNDEFINED_SUPERLATIVE = "undefined_superlative"     # "best", "top" without a metric
    COLUMN_COLLISION = "column_collision"                # e.g. "name" on multiple tables
    UNDEFINED_AGGREGATION = "undefined_aggregation"      # "sales" -> revenue or units?
    NONE = "none"


class AmbiguityCheck(BaseModel):
    """Output of the ambiguity-detection step."""
    is_ambiguous: bool
    ambiguity_type: AmbiguityType = AmbiguityType.NONE
    reasoning: str = Field(description="Why this is/isn't ambiguous, one sentence")
    clarifying_question: Optional[str] = Field(
        default=None,
        description="Only set if is_ambiguous is True"
    )


class SQLGeneration(BaseModel):
    """Output of the text-to-SQL step."""
    sql: str
    confidence: float = Field(ge=0.0, le=1.0)
    tables_used: list[str]
    assumptions_made: list[str] = Field(
        default_factory=list,
        description="Any implicit assumptions the model made (e.g. 'assumed best = revenue')"
    )


class PipelineResult(BaseModel):
    """Final result returned to the caller — what the eval harness scores against."""
    question: str
    ambiguity_check: AmbiguityCheck
    sql_generation: Optional[SQLGeneration] = None
    clarification_asked: bool
    final_sql: Optional[str] = None
    error: Optional[str] = None
