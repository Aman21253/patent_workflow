import re
from groq import Groq
from django.conf import settings
from .solr_client import (
    search_by_query,
    search_by_application_id,
    search_by_multiple_application_ids,
    search_by_registration_number,
    search_by_multiple_registration_numbers,
)

# ── Groq client ───────────────────────────────────────────
client = Groq(api_key=settings.GROQ_API_KEY)
MODEL  = "llama-3.3-70b-versatile"

# ── Regex patterns ────────────────────────────────────────
APP_ID_PATTERN = re.compile(r'\bUS\d{7,}\b', re.IGNORECASE)
REG_NO_PATTERN = re.compile(r'\b\d{4,6}\b')


def smart_search(user_question: str) -> list[dict]:
    """Route to the most specific Solr query based on question content."""
    app_ids = APP_ID_PATTERN.findall(user_question)
    reg_nos = REG_NO_PATTERN.findall(user_question)

    if len(app_ids) > 1:
        return search_by_multiple_application_ids(app_ids)
    if len(app_ids) == 1:
        return search_by_application_id(app_ids[0])
    if len(reg_nos) > 1:
        return search_by_multiple_registration_numbers(reg_nos)
    if len(reg_nos) == 1:
        return search_by_registration_number(reg_nos[0])

    return search_by_query(user_question, rows=5)


def build_context(docs: list[dict]) -> str:
    """Convert Solr docs into structured context string."""
    if not docs:
        return "No relevant patents found in the database."

    lines = []
    for i, doc in enumerate(docs, 1):
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
        )
    return "\n".join(lines)


def ask_rag(user_question: str) -> str:
    """Full RAG pipeline: Solr search → build context → Groq LLM answer."""
    try:
        docs = smart_search(user_question)
        print(f"[Solr] Found {len(docs)} docs for: '{user_question}'")

        context = build_context(docs)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional patent assistant for the Velocity patent management system. "
                        "Answer ONLY using the context provided. "
                        "If the answer is not in the context, say: 'I couldn't find that information in the patent database.' "
                        "Be concise, accurate, and professional. "
                        "Use numbered lists when listing multiple items. "
                        "Never make up patent IDs, names, or statuses."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Context from patent database:\n{context}\n\n"
                        f"Question: {user_question}"
                    )
                }
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        answer = response.choices[0].message.content.strip()
        print(f"[Groq] Answer: {answer[:100]}...")
        return answer

    except Exception as e:
        print(f"[Groq Error] {type(e).__name__}: {e}")
        return "Sorry, I couldn't process your request right now. Please try again later."