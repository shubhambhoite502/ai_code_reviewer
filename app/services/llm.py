from typing import List, Dict
from openai import OpenAI
import os
import json
from ..config import OPENAI_API_KEY, OPENAI_MODEL,GOOGLE_API_KEY
from ..utils.logger import logger
import google.generativeai as genai
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
SYSTEM_PROMPT = "You are a senior QA engineer helping generate high-quality software test cases."

# Fallback if model not set in config
MODEL = OPENAI_MODEL or os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def review_diff_chunks(chunks: List[str]) -> Dict:
    logger.info("Sending %d chunks to LLM (model=%s)", len(chunks), MODEL)

    all_must_do, all_good_to_have, all_security = [], [], []

    # --- Step 1: Per-chunk review ---
    for idx, chunk in enumerate(chunks, 1):
        prompt = f"""
            You are reviewing a code diff.  

            Rules for reviewing:
            1. Only report a **missing import or undefined service/function** if it is clearly absent in this diff.
            2. Review ONLY visible lines in this diff (do not assume context from outside).
            3. Categorize findings as:
               - **must_do**: Critical issues (runtime errors, bugs, security vulnerabilities).
               - **good_to_have**: Improvements (readability, maintainability, performance).
               - **security**: Security-specific issues.
            4. When possible, reference the issue with line numbers from the diff, e.g., `"Line 42: Possible null pointer"`.
            5. Keep feedback actionable and concise.

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
You are consolidating categorized findings from multiple diff chunks.  

Rules:
- Group findings into 'must_do', 'good_to_have', and 'security'.
- Merge similar comments and avoid duplicates.
- Add a short 'summary' (overall review sentiment).
- Add:
  - "effort_estimate": Rough effort required to fix (low / medium / high).
  - "flags": Array of flags like ["merge_ready"], ["needs_changes"], etc.

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
    "security": [...],
    "effort_estimate": "low|medium|high",
    "flags": ["..."]
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
                "effort_estimate": "medium",
                "flags": ["needs_human_review"],
            }

    except Exception as e:
        logger.error("Error consolidating review: %s", str(e))
        consolidated = {
            "summary": "⚠️ Error generating consolidated summary.",
            "must_do": list(set(all_must_do)),
            "good_to_have": list(set(all_good_to_have)),
            "security": list(set(all_security)),
            "effort_estimate": "medium",
            "flags": ["needs_human_review"],
        }

    # --- Step 3: Final return (Markdown-friendly) ---
    return {
        "title": "🤖 AI Code Review",
        "summary": consolidated.get("summary", "Automated review across all diff chunks."),
        "must_do": consolidated.get("must_do", list(set(all_must_do))),
        "good_to_have": consolidated.get("good_to_have", list(set(all_good_to_have))),
        "security": consolidated.get("security", list(set(all_security))),
        "effort_estimate": consolidated.get("effort_estimate", "medium"),
        "flags": consolidated.get("flags", ["needs_human_review"]),
        "final_thoughts": "Treat this as assistance, not a replacement for human review.",
    }


def generate_test_cases(epic_no: str, epic_title: str, pr_desc: str, pr_code: str):
    """
    Generate micro-level business/technical test cases from PR details.
    Returns structured JSON.
    """
    prompt = f"""
You are an expert QA engineer. Based on the software change details below, generate **micro-level test cases**. 
Ensure comprehensive coverage including **functional scenarios, edge cases, negative cases, boundary conditions, and possible regressions**.

Epic: {epic_no} - {epic_title}

Requirement Description:
{pr_desc}

Relevant Code Changes:
{pr_code}

For each test case, include:
- "description": A concise summary of what is being tested.
- "preconditions": Any setup required before executing the test.
- "steps": Step-by-step actions to perform the test.
- "expected_result": The expected outcome after performing the steps.
- "priority": High, Medium, or Low.

Format your response as a **JSON array** only, like this:

[
  {{
    "description": "Test case 1 description",
    "preconditions": "Any setup or state required",
    "steps": ["Step 1", "Step 2", "..."],
    "expected_result": "Expected outcome",
    "priority": "High"
  }},
  {{
    "description": "Test case 2 description",
    "preconditions": "",
    "steps": ["Step 1", "Step 2", "..."],
    "expected_result": "Expected outcome",
    "priority": "Medium"
  }}
]

Do not include any text outside the JSON array. Generate **all relevant test cases** needed to cover the requirement thoroughly.
"""


    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )

        raw_content = resp.choices[0].message.content.strip()

        # Try parsing as JSON
        try:
            test_cases = json.loads(raw_content)
        except json.JSONDecodeError:
            # fallback: wrap into a single test case
            test_cases = [{
                "description": "Generated test case (raw response)",
                "steps": [raw_content],
                "expected_result": "See description"
            }]
        
        return test_cases

    except Exception as e:
        return [{
            "description": f"⚠️ Error generating test cases: {str(e)}",
            "steps": [],
            "expected_result": "N/A"
        }]
    

def generate_test_cases_gemini(epic_no: str, epic_title: str, pr_desc: str, pr_code: str):
    """
    Generate micro-level business/technical test cases from PR details using the Gemini API.
    Returns structured JSON.
    """
    # Configure the Gemini API with your API key
    # It's recommended to store your API key in an environment variable
    genai.configure(api_key=GOOGLE_API_KEY)

    # Define the prompt for the Gemini model
    prompt = f"""
You are an expert QA engineer. Based on the software change details below, generate **micro-level test cases**.
Ensure comprehensive coverage including **functional scenarios, edge cases, negative cases, boundary conditions, and possible regressions**.

Epic: {epic_no} - {epic_title}

Requirement Description:
{pr_desc}

Relevant Code Changes:
{pr_code}

For each test case, include:
- "description": A concise summary of what is being tested.
- "preconditions": Any setup required before executing the test.
- "steps": Step-by-step actions to perform the test.
- "expected_result": The expected outcome after performing the steps.
- "priority": High, Medium, or Low.

Format your response as a **JSON array** only, like this:

[
  {{
    "description": "Test case 1 description",
    "preconditions": "Any setup or state required",
    "steps": ["Step 1", "Step 2", "..."],
    "expected_result": "Expected outcome",
    "priority": "High"
  }},
  {{
    "description": "Test case 2 description",
    "preconditions": "",
    "steps": ["Step 1", "Step 2", "..."],
    "expected_result": "Expected outcome",
    "priority": "Medium"
  }}
]

Do not include any text outside the JSON array. Generate **all relevant test cases** needed to cover the requirement thoroughly.
"""

    try:
        # Initialize the Gemini model
        model = genai.GenerativeModel('gemini-pro')

        # Make the API call
        # The prompt is passed directly to the generate_content method
        response = model.generate_content(prompt)

        # Access the raw content from the response
        raw_content = response.text.strip()

        # Try parsing as JSON
        try:
            test_cases = json.loads(raw_content)
        except json.JSONDecodeError:
            # Fallback for when the model doesn't return perfect JSON
            print("Warning: Failed to parse JSON. Attempting to fix or use raw content.")
            # This is a good place to add more robust parsing logic if needed
            test_cases = [{
                "description": "Generated test case (raw response)",
                "steps": [raw_content],
                "expected_result": "See description",
                "priority": "High"
            }]

        return test_cases

    except Exception as e:
        return [{
            "description": f"⚠️ Error generating test cases: {str(e)}",
            "preconditions": "",
            "steps": [],
            "expected_result": "N/A",
            "priority": "High"
        }]

# Example usage:
if __name__ == '__main__':
    # Assuming these variables hold your PR details
    epic_number = "EPIC-001"
    epic_title = "Guided Conversations Feature"
    pr_description = """This feature enables companies to toggle the use of Guided Conversation (GC) Question Suggestions at the company level. When enabled, nudges assigned to users will automatically generate suggested actions in the form of questions derived from a similarity model. These questions will be added to the Guided Conversations system, mapped to users and participants, and integrated with notifications and answering workflows.
    
    Functional Requirements:
    1. Company-level Toggle and GC Package Check
    - Add a flag in the Company Admin Dashboard:Name: Enable GC Question Suggestions, Type: Boolean (On/Off), Default: Off.
    ... (rest of the detailed requirements)
    """
    pr_code = """
    # Example code snippet for demonstration
    class NudgeProcessor:
        def process_nudges(self, company_id):
            company_settings = get_company_settings(company_id)
            if company_settings.enable_gc_suggestions:
                nudges = get_active_nudges()
                for nudge in nudges:
                    question = similarity_model.get_best_match(nudge.title, nudge.subtheme_id)
                    if question:
                        # ... mapping logic ...
    """
    
    test_cases_output = generate_test_cases_gemini(epic_number, epic_title, pr_description, pr_code)
    print(json.dumps(test_cases_output, indent=2))