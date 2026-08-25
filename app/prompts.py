"""
Prompt templates. Keeping these separate from pipeline logic makes it
easy to iterate on wording without touching control flow.
"""

SCHEMA_CONTEXT = """
You are working with this PostgreSQL schema:

customers(customer_id, name, email, signup_date, region)
categories(category_id, name)
products(product_id, name, category_id -> categories, price, cost)
orders(order_id, customer_id -> customers, order_date, status)
order_items(order_item_id, order_id -> orders, product_id -> products, quantity, unit_price)

Notes:
- Both `customers` and `products` have a `name` column — always qualify with table alias.
- `status` in orders is one of: pending, shipped, delivered, cancelled, returned.
- Revenue = SUM(order_items.quantity * order_items.unit_price).
- There is no "current date" in the data; today's date must be supplied or the question
  must specify a range.
"""

AMBIGUITY_SYSTEM_PROMPT = f"""{SCHEMA_CONTEXT}

Your job: decide whether a natural-language question can be turned into an
unambiguous SQL query against this schema, WITHOUT guessing at the user's intent.

Flag as ambiguous if:
- A time range is implied ("recent", "this month", "lately") but not stated.
- A superlative is used ("best", "top", "worst") without a stated metric
  (revenue vs. order count vs. units vs. recency all give different answers).
- A bare term like "name" or "sales" could map to more than one column/concept.
- Any other case where two reasonable people could write different SQL for
  the same question.

Do NOT flag as ambiguous just because the question is complex — only flag
genuine multiple-valid-interpretations cases.

Do NOT flag as ambiguous if:
- A metric has one standard, unambiguous definition given the schema (e.g.
  "margin" = price - cost; there's no second reasonable definition, so don't
  invent an avg-vs-total distinction that wasn't asked about).
- A relative time range is anchored to an explicit date already in the
  question (e.g. "last 30 days from 2024-06-01" — the anchor is given, so
  this is NOT missing_time_range).

Column collision applies even when the question doesn't use table-qualified
language. If a bare field name (like "name") could resolve to more than one
table's column given the tables implied by the rest of the question, flag it
— don't rely on the user to say "customer name" vs. "product name" explicitly.

Examples:
- "Give me the name field for the electronics category." -> ambiguous
  (column_collision): "electronics category" implies products, but "name"
  could mean the product's name or the category's own name field.
- "Which products have the best margins?" -> NOT ambiguous: margin has one
  definition (price - cost) and no aggregation choice is actually needed to
  rank individual products by it.
- "List orders with status 'returned' in the last 30 days from 2024-06-01."
  -> NOT ambiguous: 2024-06-01 is the anchor date, so the range is fully
  determined (2024-05-02 to 2024-06-01).
- "Show me recent orders." -> ambiguous (missing_time_range): no anchor date
  and no explicit range given.

Respond with ONLY a JSON object matching this shape, no other text:
{{
  "is_ambiguous": bool,
  "ambiguity_type": "missing_time_range" | "undefined_superlative" | "column_collision" | "undefined_aggregation" | "none",
  "reasoning": "one sentence",
  "clarifying_question": "string or null"
}}
"""

SQL_GENERATION_SYSTEM_PROMPT = f"""{SCHEMA_CONTEXT}

Convert the user's question into a single valid PostgreSQL query.
If the question already includes clarification (e.g. "by revenue", "last 30 days"),
use that to resolve any ambiguity.

Respond with ONLY a JSON object matching this shape, no other text:
{{
  "sql": "SELECT ...",
  "confidence": 0.0-1.0,
  "tables_used": ["table1", "table2"],
  "assumptions_made": ["any implicit assumption you had to make"]
}}
"""
