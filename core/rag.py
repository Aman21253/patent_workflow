import re
import google.generativeai as genai
import time
from django.conf import settings
from .solr_client import (
    search_by_query,
    search_by_application_id,
    search_by_multiple_application_ids,
    search_by_registration_number,
    search_by_multiple_registration_numbers,
)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")


# ── Regex patterns based on your actual data format ──────────────────────────
APP_ID_PATTERN     = re.compile(r'\bUS\d{7,}\b', re.IGNORECASE)
REG_NO_PATTERN     = re.compile(r'\b\d{4,6}\b')          # 4-6 digit registration numbers


def smart_search(user_question: str) -> list[dict]:
    """
    Detects what kind of identifiers are in the question
    and routes to the most specific Solr query.
    """
    app_ids = APP_ID_PATTERN.findall(user_question)
    reg_nos = REG_NO_PATTERN.findall(user_question)

    # Priority 1: Specific application IDs found
    if len(app_ids) > 1:
        return search_by_multiple_application_ids(app_ids)
    if len(app_ids) == 1:
        return search_by_application_id(app_ids[0])

    # Priority 2: Attorney registration numbers found
    if len(reg_nos) > 1:
        return search_by_multiple_registration_numbers(reg_nos)
    if len(reg_nos) == 1:
        return search_by_registration_number(reg_nos[0])

    # Priority 3: General keyword search
    return search_by_query(user_question, rows=5)


def build_context(docs: list[dict]) -> str:
    """
    Convert Solr docs into a structured context string for Gemini.
    Field names are based on triangleipv2 core schema.
    """
    if not docs:
        return "No relevant patents found in the database."

    lines = []
    for i, doc in enumerate(docs, 1):
        # Safely handle fields that may be lists or strings
        def get(field):
            val = doc.get(field, "N/A")
            if isinstance(val, list):
                return ", ".join(str(v) for v in val)
            return str(val) if val else "N/A"

        lines.append(
            f"--- Patent {i} ---\n"
            f"  Application ID       : {get('id')}\n"
            f"  Title                : {get('title')}\n"
            f"  Applicant            : {get('applicant_name')}\n"
            f"  Inventor             : {get('inventor_name')}\n"
            f"  GAU                  : {get('gau')}\n"
            f"  Status               : {get('status')}\n"
            f"  Attorney Reg Numbers : {get('all_attorney_registration_numbers')}\n"
            f"  Abstract             : {get('abstract')}\n"
            f"  Description          : {get('description')}\n"
        )
    return "\n".join(lines)


def ask_rag(user_question: str) -> str:
    try:
        docs = smart_search(user_question)
        print(f"[Solr] Found {len(docs)} docs for: {user_question}")

        context = build_context(docs)

        prompt = f"""You are a professional patent assistant for the Velocity patent management system.
Your job is to help users find accurate information about patents, inventors, applicants, attorneys, and application statuses.

Rules:
- Answer ONLY using the context provided below.
- If the answer is not found in the context, clearly say: "I couldn't find that information in the patent database."
- Be concise, accurate, and professional.
- When listing multiple patents or attorneys, use a numbered list.
- Never make up patent IDs, names, or statuses.

--- Context from Patent Database ---
{context}
------------------------------------

User Question: {user_question}
"""
        # ── Retry up to 3 times on quota errors ──────────────
        for attempt in range(3):
            try:
                response = model.generate_content(prompt)
                return response.text.strip()

            except Exception as e:
                error_str = str(e)

                if "429" in error_str:
                    wait = (attempt + 1) * 5   # wait 5s, 10s, 15s
                    print(f"[Gemini] Quota hit, retrying in {wait}s... (attempt {attempt+1}/3)")
                    time.sleep(wait)
                    continue

                # Any other error — raise immediately
                raise e

        return "I'm currently rate limited. Please try again in a minute."

    except Exception as e:
        print(f"[Gemini Error] {type(e).__name__}: {e}")
        return "Sorry, I couldn't process your request right now. Please try again later."