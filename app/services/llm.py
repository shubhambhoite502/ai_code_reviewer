from typing import List, Dict
from openai import OpenAI
import os
import json
from ..config import OPENAI_API_KEY, OPENAI_MODEL
from ..utils.logger import logger

import json
from typing import List, Dict

# Explicitly pass API key to avoid environment issues
client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = OPENAI_MODEL


SYSTEM = (
    "You are a senior code reviewer. Review diffs for correctness, readability, performance, "
    "security, and maintainability. Be concise, concrete, and actionable. "
    "Point to risky patterns and offer better alternatives. Always return valid JSON."
)

# Fallback if model not set in config
MODEL = OPENAI_MODEL or os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def review_diff_chunks(chunks: List[str]) -> Dict:
    logger.info("Sending %d chunks to LLM (model=%s)", len(chunks), MODEL)

    all_must_do, all_good_to_have, all_security = [], [], []

    # --- Step 1: Per-chunk review ---
    for idx, chunk in enumerate(chunks, 1):
        prompt = f"""
You are reviewing code diffs.

Rules for reporting:
1. Only report a **missing import or undefined service/function** if it is clearly not defined or imported anywhere in this diff. 
   - Do NOT assume something is missing just because it isn’t visible here (it might exist in unchanged lines).
2. Review ONLY what is visible in this diff.
3. Categorize findings as:
   - **must_do**: Critical issues that will break code, cause runtime errors, security vulnerabilities, or introduce serious bugs.
   - **good_to_have**: Improvements related to readability, maintainability, performance optimizations, or best practices.
   - **security**: Specific issues related to security flaws or vulnerabilities.
4. Keep suggestions concrete and actionable.

DIFF CHUNK START
{chunk}
DIFF CHUNK END

Return only valid JSON in this format:
{{
    "must_do": ["..."],
    "good_to_have": ["..."],
    "security": ["..."]
}}
"""

        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            content = resp.choices[0].message.content.strip()

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("Chunk %d: Invalid JSON. Raw content: %s", idx, content)
                parsed = {"must_do": [content], "good_to_have": [], "security": []}

            all_must_do.extend(parsed.get("must_do", []))
            all_good_to_have.extend(parsed.get("good_to_have", []))
            all_security.extend(parsed.get("security", []))

        except Exception as e:
            logger.error("Error reviewing chunk %d: %s", idx, str(e))
            all_must_do.append(f"⚠️ Error reviewing chunk {idx}: {str(e)}")

    # --- Step 2: Consolidate ---
    final_prompt = f"""
You will receive categorized findings across multiple diff chunks.
Create a consolidated summary while preserving categories.

Rules:
- Group findings into 'must_do', 'good_to_have', and 'security'.
- Avoid duplicates, merge similar comments.
- Provide a short 'summary' describing the overall review quality.

MUST DO:
{all_must_do}

GOOD TO HAVE:
{all_good_to_have}

SECURITY:
{all_security}

Return only JSON in this format:
{{
    "summary": "...",
    "must_do": [...],
    "good_to_have": [...],
    "security": [...]
}}
"""

    try:
        resp2 = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0.2,
        )
        consolidated_raw = resp2.choices[0].message.content.strip()

        try:
            consolidated = json.loads(consolidated_raw)
        except json.JSONDecodeError:
            logger.warning("Final consolidation not JSON. Using fallback.")
            consolidated = {
                "summary": consolidated_raw,
                "must_do": list(set(all_must_do)),
                "good_to_have": list(set(all_good_to_have)),
                "security": list(set(all_security)),
            }

    except Exception as e:
        logger.error("Error consolidating review: %s", str(e))
        consolidated = {
            "summary": "⚠️ Error generating consolidated summary.",
            "must_do": list(set(all_must_do)),
            "good_to_have": list(set(all_good_to_have)),
            "security": list(set(all_security)),
        }

    # --- Step 3: Final return ---
    return {
        "title": "🤖 AI Code Review",
        "summary": consolidated.get("summary", "Automated review across all diff chunks."),
        "must_do": consolidated.get("must_do", list(set(all_must_do))),
        "good_to_have": consolidated.get("good_to_have", list(set(all_good_to_have))),
        "security": consolidated.get("security", list(set(all_security))),
        "final_thoughts": "Treat this as assistance, not a replacement for human review.",
    }
