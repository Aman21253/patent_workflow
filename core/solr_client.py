import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings

SOLR_AUTH = HTTPBasicAuth(settings.SOLR_USERNAME, settings.SOLR_PASSWORD)


def get_total_patents() -> int:
    """Get total number of patents in Solr."""
    params = {"q": "*:*", "rows": 0, "wt": "json"}
    result = _execute_query(params)
    return result.get("numFound", 0)


def get_all_attorney_names(rows: int = 1000) -> list[str]:
    """Fetch all unique attorney names from Solr."""
    params = {
        "q": "*:*",
        "rows": rows,
        "wt": "json",
        "fl": "all_attorney_names",
    }
    docs = _execute_query(params)
    names = set()
    for doc in docs:
        attorneys = doc.get("all_attorney_names", [])
        if isinstance(attorneys, list):
            for name in attorneys:
                names.add(name.strip().title())
        elif isinstance(attorneys, str):
            names.add(attorneys.strip().title())
    return sorted(names)


def get_all_attorney_registration_numbers(rows: int = 1000) -> list[str]:
    """Fetch all unique attorney registration numbers."""
    params = {
        "q": "*:*",
        "rows": rows,
        "wt": "json",
        "fl": "all_attorney_registration_numbers",
    }
    docs = _execute_query(params)
    reg_nos = set()
    for doc in docs:
        regs = doc.get("all_attorney_registration_numbers", [])
        if isinstance(regs, list):
            for r in regs:
                reg_nos.add(str(r))
        elif regs:
            reg_nos.add(str(regs))
    return sorted(reg_nos)


def get_patents_by_status(status: str, rows: int = 10) -> list[dict]:
    """Fetch patents filtered by application_status."""
    params = {
        "q": f"application_status:*{status}*",
        "rows": rows,
        "wt": "json",
        "fl": "id,title,application_status,first_named_applicant,first_named_inventor,gau,all_attorney_names",
    }
    return _execute_query(params)


def get_patents_by_applicant(applicant: str, rows: int = 10) -> list[dict]:
    """Fetch patents by applicant name."""
    params = {
        "q": f"first_named_applicant:*{applicant}*",
        "rows": rows,
        "wt": "json",
        "fl": "id,title,application_status,first_named_applicant,first_named_inventor,gau,all_attorney_names",
    }
    return _execute_query(params)


def get_patents_by_inventor(inventor: str, rows: int = 10) -> list[dict]:
    """Fetch patents by inventor name."""
    params = {
        "q": f"first_named_inventor:*{inventor}*",
        "rows": rows,
        "wt": "json",
        "fl": "id,title,application_status,first_named_applicant,first_named_inventor,gau,all_attorney_names",
    }
    return _execute_query(params)


def get_patents_by_gau(gau: str, rows: int = 10) -> list[dict]:
    """Fetch patents by GAU number."""
    params = {
        "q": f"gau:{gau}",
        "rows": rows,
        "wt": "json",
        "fl": "id,title,application_status,first_named_applicant,first_named_inventor,gau,all_attorney_names",
    }
    return _execute_query(params)


def get_patents_by_attorney_name(name: str, rows: int = 10) -> list[dict]:
    """Fetch patents by attorney name."""
    params = {
        "q": f"all_attorney_names:*{name}*",
        "rows": rows,
        "wt": "json",
        "fl": "id,title,application_status,first_named_applicant,first_named_inventor,gau,all_attorney_names,all_attorney_registration_numbers",
    }
    return _execute_query(params)


def search_by_query(query: str, rows: int = 5) -> list[dict]:
    """General full-text search."""
    params = {
        "q": query,
        "rows": rows,
        "wt": "json",
        "defType": "edismax",
        "qf": (
            "title^4 "
            "first_named_inventor^3 "
            "first_named_applicant^3 "
            "all_attorney_names^2 "
            "all_attorney_registration_numbers^2 "
            "application_status^2 "
            "id^3 "
            "gau "
            "examiner"
        ),
        "fl": "id,title,application_status,first_named_applicant,first_named_inventor,gau,all_attorney_names,all_attorney_registration_numbers,examiner",
    }
    return _execute_query(params)


def search_by_application_id(application_id: str) -> list[dict]:
    params = {"q": f"id:{application_id}", "rows": 1, "wt": "json"}
    return _execute_query(params)


def search_by_multiple_application_ids(ids: list[str]) -> list[dict]:
    ids_str = ",".join(ids)
    params = {"q": f"{{!terms f=id}}{ids_str}", "rows": len(ids), "wt": "json"}
    return _execute_query(params)


def search_by_registration_number(reg_no: str) -> list[dict]:
    params = {"q": f"all_attorney_registration_numbers:{reg_no}", "rows": 10, "wt": "json"}
    return _execute_query(params)


def search_by_multiple_registration_numbers(reg_nos: list[str]) -> list[dict]:
    reg_str = ",".join(reg_nos)
    params = {"q": f"{{!terms f=all_attorney_registration_numbers}}{reg_str}", "rows": 20, "wt": "json"}
    return _execute_query(params)


def _execute_query(params: dict):
    """Internal helper — handles both docs list and full response."""
    try:
        response = requests.get(
            settings.SOLR_BASE_URL,
            params=params,
            auth=SOLR_AUTH,
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()

        # Return full response for aggregate queries
        if params.get("rows") == 0:
            return data.get("response", {})

        return data.get("response", {}).get("docs", [])

    except requests.exceptions.ConnectionError:
        print("[Solr Error] Cannot connect to Solr instance.")
        return []
    except requests.exceptions.Timeout:
        print("[Solr Error] Solr request timed out.")
        return []
    except Exception as e:
        print(f"[Solr Error] {e}")
        return []