import json
import os
import re
from datetime import datetime

import duckdb
import ollama
import pandas as pd
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
_FEEDBACK_PATH = os.path.join(_HERE, "ai_feedback.md")
_LOG_PATH = os.path.join(_HERE, "chat_log.jsonl")

# The SQL table name the model writes queries against.
TABLE_NAME = "energy"

# Sentinel the model returns when a question cannot be answered from the table.
NO_QUERY = "NO_QUERY"

REFUSAL_MESSAGE = (
    "I can only answer questions about the energy poverty dataset for "
    "Portuguese municipalities and districts (years 2022-2025)."
)

# Column descriptions shown to the model so it picks the right columns.
COLUMN_DESCRIPTIONS = {
    "ano":                      "Year (2022-2025)",
    "distrito":                 "District name, UPPERCASE (e.g. 'PORTO', 'LISBOA')",
    "concelho":                 "Municipality name, UPPERCASE (e.g. 'AVEIRO')",
    "annual_expenditure":       "Annual energy cost per household, in EUR",
    "income":                   "Average household income (rendimento), in EUR",
    "energy_expenditure_ratio": "Energy Expenditure Ratio (EER) in %. HIGHER = worse (bigger share of income spent on energy)",
    "energy_poverty":           "Energy poverty flag: 1 = energy poor, 0 = not poor",
    "median_age":               "Median age, in years",
    "age_weighted_eer":         "Age-weighted EER (EER multiplied by age)",
    "energy_eff_index":         "Energy efficiency index: share of bad energy classes D/E/F. HIGHER = worse efficiency",
}


def _load_feedback() -> str:
    try:
        with open(_FEEDBACK_PATH, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _log_interaction(question: str, sql: str | None, result_text: str | None, error: str | None, explanation: str, model: str) -> None:
    """Append an interaction record to the chat log (JSONL format)."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "question": question,
        "sql_generated": sql,
        "success": error is None,
        "error": error,
        "result_text": result_text[:500] if result_text and len(result_text) > 500 else result_text,
        "explanation": explanation[:200] if explanation and len(explanation) > 200 else explanation,
    }
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Warning: failed to log interaction: {e}")


@st.cache_data
def get_installed_models() -> list[str]:
    try:
        return [m["model"] for m in ollama.list()["models"]]
    except Exception:
        return []


def build_schema_prompt(df: pd.DataFrame) -> str:
    col_info = "\n".join(
        f"  - {col} ({df[col].dtype}): {COLUMN_DESCRIPTIONS.get(col, col)}"
        for col in df.columns
        if col in COLUMN_DESCRIPTIONS
    )
    feedback = _load_feedback()
    feedback_section = f"\n\nGUIDANCE & EXAMPLES (follow these strictly):\n{feedback}" if feedback else ""
    return (
        f"You are a text-to-SQL engine for a DuckDB table named `{TABLE_NAME}`.\n"
        f"Each row is one municipality (concelho) in one year. There are {len(df)} rows.\n\n"
        f"COLUMNS:\n{col_info}\n\n"
        f"Available years: {sorted(int(y) for y in df['ano'].unique())}\n"
        "District (distrito) and municipality (concelho) names are UPPERCASE.\n\n"
        "RULES:\n"
        f"1. If the question can be answered from this table, output ONLY one valid DuckDB SQL query "
        f"against `{TABLE_NAME}`. No prose, no markdown fences.\n"
        f"2. If the question is NOT about this data (general knowledge, the assistant itself, unrelated "
        f"topics), output ONLY this exact word: {NO_QUERY}\n"
        "3. When the user asks about a DISTRICT ('distrito'), aggregate municipalities with AVG and GROUP BY distrito.\n"
        "4. Use UPPERCASE string literals for distrito/concelho comparisons.\n"
        "5. 'pior'/'worst'/'maior'/'highest' for poverty, EER or efficiency means ORDER BY ... DESC. "
        "'melhor'/'best'/'menor'/'lowest' means ORDER BY ... ASC.\n"
        "6. Always add ORDER BY and LIMIT so the answer is small and focused.\n"
        "7. If the user does not mention a year, aggregate across all years (do not invent a year).\n\n"
        "EXAMPLE:\n"
        "Q: Qual o distrito com pior pobreza energética?\n"
        f"A: SELECT distrito, AVG(energy_expenditure_ratio) AS avg_eer FROM {TABLE_NAME} "
        "GROUP BY distrito ORDER BY avg_eer DESC LIMIT 1;"
        f"{feedback_section}"
    )


def _extract_sql(raw: str) -> str | None:
    """Pull a clean SQL statement out of the model's raw response.

    Returns None if the model declined to answer (NO_QUERY) or produced no query.
    """
    text = raw.strip()

    if NO_QUERY in text.upper():
        return None

    # Prefer content inside a ```sql ... ``` (or plain ```) fenced block.
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    # Keep from the first SELECT/WITH onward (drops any leading chatter).
    match = re.search(r"\b(SELECT|WITH)\b", text, re.IGNORECASE)
    if not match:
        return None
    text = text[match.start():]

    # Keep only the first statement.
    if ";" in text:
        text = text.split(";")[0]

    return text.strip()


def suggest_guidance_updates(model: str) -> str:
    """Analyze chat log and suggest new GOOD/BAD guidance lines for ai_feedback.md.

    Returns the suggested text (without modifying the file), or empty string if no log exists.
    """
    if not os.path.exists(_LOG_PATH):
        return ""

    try:
        with open(_LOG_PATH, encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
    except Exception:
        return ""

    if not records:
        return ""

    feedback = _load_feedback()

    error_cases = [r for r in records if r["error"] is not None]
    refusal_cases = [r for r in records if r["sql_generated"] is None and r["error"] is None]
    success_cases = [r for r in records if r["success"] and r["sql_generated"] is not None]

    log_summary = f"""
Recent chat interactions:
- Total interactions: {len(records)}
- Successful SQL queries: {len(success_cases)}
- Refusals (out of scope): {len(refusal_cases)}
- SQL errors: {len(error_cases)}

Recent error cases (if any):
"""
    for r in error_cases[-3:]:
        log_summary += f"\n  Q: {r['question']}\n  Error: {r['error']}\n"

    log_summary += f"\nRecent refusal cases (if any):"
    for r in refusal_cases[-3:]:
        log_summary += f"\n  Q: {r['question']}\n"

    prompt = f"""You are helping improve the guidance for a text-to-SQL assistant for an energy poverty dataset.

Current guidance in ai_feedback.md:
{feedback}

---

Recent chat log summary:
{log_summary}

---

Based on the recent chat interactions, suggest 2-3 NEW lines to add to the ai_feedback.md file.
These could be:
1. New GOOD examples (Q -> SQL pairs) from recent successful queries that aren't covered yet.
2. New BAD examples (questions to refuse) if you spot patterns in refusals or errors.
3. New glossary entries if users asked about columns using wording not yet mapped.

Format your response EXACTLY as you would add it to the file:

## New suggestions

Q: [question in Portuguese]
SQL: [DuckDB SQL query]
Reason: [why this is important]

OR

Q: [question]
Reason: [why this should be refused]

Do NOT repeat existing examples. Be concise."""

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )["message"]["content"]

    return response


def query_ollama(history: list[dict], model: str, df: pd.DataFrame) -> tuple[str, str | None, str | None]:
    last_question = history[-1]["content"]

    # Step 1: generate SQL (or NO_QUERY if the question is off-topic)
    raw_sql = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": build_schema_prompt(df)},
            {"role": "user", "content": last_question},
        ],
    )["message"]["content"]
    sql = _extract_sql(raw_sql)

    if sql is None:
        _log_interaction(last_question, None, None, None, REFUSAL_MESSAGE, model)
        return REFUSAL_MESSAGE, None, None

    # Step 2: execute against the dataframe via DuckDB
    try:
        con = duckdb.connect(database=":memory:")
        con.register(TABLE_NAME, df)
        result_df = con.execute(sql).fetchdf()
        result_text = result_df.to_string(index=False)
    except Exception as e:
        error_msg = f"The generated query failed to run: {e}"
        _log_interaction(last_question, sql, None, str(e), error_msg, model)
        return f"_(The generated query failed to run: {e})_", sql, None

    # Step 3: explain the result in natural language
    explanation = ollama.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful data analyst. The user asked a question about an energy poverty dataset. "
                    "A SQL query was run and returned the result below. Explain the result clearly and concisely, "
                    "in the same language the user used. Do not mention SQL, queries, or tables."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {last_question}\n\nResult:\n{result_text}",
            },
        ],
    )["message"]["content"]

    _log_interaction(last_question, sql, result_text, None, explanation, model)
    return explanation, sql, result_text
