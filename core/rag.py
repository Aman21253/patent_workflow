import re
from groq import Groq
from django.conf import settings
from .solr_client import (
    get_total_patents,
    get_all_attorney_names,
    get_all_attorney_registration_numbers,
    get_patents_by_status,
    get_patents_by_applicant,
    get_patents_by_inventor,
    get_patents_by_gau,
    get_patents_by_attorney_name,
    search_by_query,
    search_by_application_id,
    search_by_multiple_application_ids,
    search_by_registration_number,
    search_by_multiple_registration_numbers,
)

client = Groq(api_key=settings.GROQ_API_KEY)
MODEL  = "llama-3.3-70b-versatile"

# ── Regex patterns ─────────────────────────────────────────────
APP_ID_PATTERN = re.compile(r'\bUS\d{7,}\b', re.IGNORECASE)
REG_NO_PATTERN = re.compile(r'\b\d{4,6}\b')


def extract_keyword(question: str, trigger_words: list[str]) -> str:
    """
    Extract the meaningful keyword from a question by removing
    trigger/filler words so Solr doesn't get full sentences.
    """
    q = question.lower().strip()

    # Remove filler phrases
    fillers = [
        "give me", "show me", "list", "find", "search", "get",
        "tell me", "what is", "what are", "who is", "who are",
        "i want", "please", "can you", "some", "all", "best",
        "top", "10", "5", "20", "patents for", "patents by",
        "patents of", "attorney named", "attorney name",
        "attorneys named", "for attorney", "by attorney",
    ]
    for filler in fillers:
        q = q.replace(filler, " ")

    # Remove trigger words themselves
    for word in trigger_words:
        q = q.replace(word, " ")

    # Clean up extra spaces
    q = " ".join(q.split()).strip()
    return q if q else question


def detect_intent(question: str) -> str:
    """Detect what the user is asking about."""
    q = question.lower()

    # ── Specific Application ID (highest priority) ─────────────
    if APP_ID_PATTERN.search(question):
        return "app_id_search"

    # ── Attorney registration numbers LIST ─────────────────────
    if any(phrase in q for phrase in [
        "all attorney registration",
        "all registration number",
        "all reg number",
        "list registration",
        "give me registration",
        "show registration",
        "attorney registration number",
        "registration number of attorney",
    ]):
        return "attorney_reg_numbers"

    # ── Attorney NAMES LIST ────────────────────────────────────
    if any(phrase in q for phrase in [
        "all attorney name",
        "all attorneys name",
        "list attorney name",
        "list attorneys",
        "give me attorney name",
        "give me attorneys name",
        "show attorney name",
        "show attorneys",
        "attorney names",
    ]):
        return "attorney_names"

    # ── TOTAL PATENTS ──────────────────────────────────────────
    if any(phrase in q for phrase in [
        "total patent",
        "how many patent",
        "count patent",
        "number of patent",
        "total number of patent",
    ]):
        return "total_patents"

    # ── TOTAL ATTORNEYS ────────────────────────────────────────
    if any(phrase in q for phrase in [
        "total attorney",
        "how many attorney",
        "count attorney",
        "number of attorney",
        "total number of attorney",
    ]):
        return "total_attorneys"

    # ── STATUS based ───────────────────────────────────────────
    if any(w in q for w in [
        "pending", "granted", "rejected", "docketed",
        "abandoned", "allowed", "preexam", "under examination",
    ]):
        return "status_search"

    # ── APPLICANT based ────────────────────────────────────────
    if any(w in q for w in ["applicant", "company", "assignee", "filed by"]):
        return "applicant_search"

    # ── INVENTOR based ─────────────────────────────────────────
    if any(w in q for w in ["inventor", "invented by"]):
        return "inventor_search"

    # ── GAU based ──────────────────────────────────────────────
    if "gau" in q:
        return "gau_search"

    # ── Specific REGISTRATION NUMBER ───────────────────────────
    if REG_NO_PATTERN.search(question) and any(w in q for w in ["attorney", "registration", "reg"]):
        return "reg_no_search"

    # ── Specific ATTORNEY NAME search ──────────────────────────
    if any(w in q for w in ["attorney", "lawyer", "counsel"]):
        return "attorney_name_search"

    # ── Bare registration number ───────────────────────────────
    if REG_NO_PATTERN.search(question):
        return "reg_no_search"

    return "general_search"


def build_context(docs: list[dict]) -> str:
    """Convert Solr docs into readable context for LLM."""
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
            f"  Application ID    : {get('id')}\n"
            f"  Title             : {get('title')}\n"
            f"  Applicant         : {get('first_named_applicant')}\n"
            f"  Inventor          : {get('first_named_inventor')}\n"
            f"  GAU               : {get('gau')}\n"
            f"  Status            : {get('application_status')}\n"
            f"  Examiner          : {get('examiner')}\n"
            f"  Attorney Names    : {get('all_attorney_names')}\n"
            f"  Attorney Reg Nos  : {get('all_attorney_registration_numbers')}\n"
        )
    return "\n".join(lines)


def ask_rag(user_question: str) -> str:
    """Full RAG pipeline with intent detection."""
    try:
        intent = detect_intent(user_question)
        q = user_question.lower()
        context = ""
        direct_answer = None

        print(f"[Intent] {intent} for: '{user_question}'")

        # ── TOTAL PATENTS ──────────────────────────────────────
        if intent == "total_patents":
            total = get_total_patents()
            direct_answer = f"There are a total of {total:,} patents in the database."

        # ── TOTAL ATTORNEYS ────────────────────────────────────
        elif intent == "total_attorneys":
            names = get_all_attorney_names(rows=1000)
            direct_answer = f"There are approximately {len(names):,} unique attorneys found in the sampled records."

        # ── LIST ATTORNEY NAMES ────────────────────────────────
        elif intent == "attorney_names":
            names = get_all_attorney_names(rows=500)
            preview = names[:50]
            direct_answer = (
                f"Here are the first 50 attorney names "
                f"(total sampled: {len(names)}):\n\n" +
                "\n".join(f"{i+1}. {n}" for i, n in enumerate(preview))
            )

        # ── LIST ATTORNEY REGISTRATION NUMBERS ────────────────
        elif intent == "attorney_reg_numbers":
            reg_nos = get_all_attorney_registration_numbers(rows=500)
            preview = reg_nos[:50]
            direct_answer = (
                f"Here are the first 50 attorney registration numbers "
                f"(total sampled: {len(reg_nos)}):\n\n" +
                "\n".join(f"{i+1}. {r}" for i, r in enumerate(preview))
            )

        # ── STATUS SEARCH ──────────────────────────────────────
        elif intent == "status_search":
            status_keywords = [
                "pending", "granted", "rejected", "docketed",
                "abandoned", "allowed", "preexam", "examination",
            ]
            status = next((w for w in status_keywords if w in q), "pending")
            docs = get_patents_by_status(status, rows=10)
            context = build_context(docs)

        # ── APPLICANT SEARCH ───────────────────────────────────
        elif intent == "applicant_search":
            keyword = extract_keyword(
                user_question,
                ["applicant", "company", "assignee", "filed by", "patent"]
            )
            docs = get_patents_by_applicant(keyword, rows=10) if keyword else []
            context = build_context(docs)

        # ── INVENTOR SEARCH ────────────────────────────────────
        elif intent == "inventor_search":
            keyword = extract_keyword(
                user_question,
                ["inventor", "invented by", "patent"]
            )
            docs = get_patents_by_inventor(keyword, rows=10) if keyword else []
            context = build_context(docs)

        # ── GAU SEARCH ─────────────────────────────────────────
        elif intent == "gau_search":
            match = re.search(r'gau\s*[:\-]?\s*(\d+)', q)
            gau = match.group(1) if match else ""
            docs = get_patents_by_gau(gau, rows=10) if gau else []
            context = build_context(docs)

        # ── SPECIFIC ATTORNEY NAME SEARCH ──────────────────────
        elif intent == "attorney_name_search":
            keyword = extract_keyword(
                user_question,
                ["attorney", "lawyer", "counsel", "patent", "find", "search"]
            )
            # Only search if we have a meaningful name keyword (not empty/short)
            if keyword and len(keyword) > 2:
                docs = get_patents_by_attorney_name(keyword, rows=10)
                context = build_context(docs)
            else:
                # Fallback: return sample attorney names
                names = get_all_attorney_names(rows=100)
                preview = names[:20]
                direct_answer = (
                    f"Here are some attorney names from the database:\n\n" +
                    "\n".join(f"{i+1}. {n}" for i, n in enumerate(preview)) +
                    "\n\nTip: Ask about a specific attorney by name, e.g. 'Patents by Kevin Costanza'"
                )

        # ── APPLICATION ID SEARCH ──────────────────────────────
        elif intent == "app_id_search":
            app_ids = APP_ID_PATTERN.findall(user_question)
            if len(app_ids) > 1:
                docs = search_by_multiple_application_ids(app_ids)
            else:
                docs = search_by_application_id(app_ids[0])
            context = build_context(docs)

        # ── REGISTRATION NUMBER SEARCH ─────────────────────────
        elif intent == "reg_no_search":
            reg_nos = REG_NO_PATTERN.findall(user_question)
            if len(reg_nos) > 1:
                docs = search_by_multiple_registration_numbers(reg_nos)
            else:
                docs = search_by_registration_number(reg_nos[0])
            context = build_context(docs)

        # ── GENERAL SEARCH ─────────────────────────────────────
        else:
            keyword = extract_keyword(user_question, [])
            docs = search_by_query(keyword or user_question, rows=5)
            context = build_context(docs)

        # ── Return direct answer if available ──────────────────
        if direct_answer:
            return direct_answer

        # ── Pass context to Groq ───────────────────────────────
        if not context or context == "No relevant patents found in the database.":
            return (
                "I couldn't find relevant information for your query. "
                "Try asking with a specific Application ID (e.g. US19457764), "
                "attorney name, registration number, or applicant company name."
            )

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional patent assistant for the Velocity patent management system. "
                        "Answer ONLY using the context provided. "
                        "If the answer is not in the context, say so clearly. "
                        "Be concise and professional. "
                        "Use numbered lists when listing multiple items. "
                        "Never make up patent IDs, names, or statuses."
                    )
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {user_question}"
                }
            ],
            temperature=0.2,
            max_tokens=1024,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[Groq Error] {type(e).__name__}: {e}")
        return "Sorry, I couldn't process your request right now. Please try again later."