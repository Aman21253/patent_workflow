import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings

# Basic auth using credentials from .env
SOLR_AUTH = HTTPBasicAuth(settings.SOLR_USERNAME, settings.SOLR_PASSWORD)


def search_by_query(query: str, rows: int = 5) -> list[dict]:
    """
    General full-text search across patent fields.
    Used for chatbot RAG context retrieval.
    """
    params = {
        "q": query,
        "rows": rows,
        "wt": "json",
        "defType": "edismax",
        # Boost important fields — update weights once you confirm field names from schema
        "qf": (
            "title^4 "
            "abstract^3 "
            "applicant_name^2 "
            "inventor_name^2 "
            "all_attorney_registration_numbers^2 "
            "id^3 "
            "status "
            "gau "
            "description"
        ),
    }

    return _execute_query(params)


def search_by_application_id(application_id: str) -> list[dict]:
    """
    Fetch a single patent by application ID.
    e.g., id:US19457764
    """
    params = {
        "q": f"id:{application_id}",
        "rows": 1,
        "wt": "json",
    }
    return _execute_query(params)


def search_by_multiple_application_ids(ids: list[str]) -> list[dict]:
    """
    Fetch multiple patents by application IDs.
    e.g., {!terms f=id}US19457764,US19447545
    """
    ids_str = ",".join(ids)
    params = {
        "q": f"{{!terms f=id}}{ids_str}",
        "rows": len(ids),
        "wt": "json",
    }
    return _execute_query(params)


def search_by_registration_number(reg_no: str) -> list[dict]:
    """
    Fetch patents by single attorney registration number.
    e.g., all_attorney_registration_numbers:54459
    """
    params = {
        "q": f"all_attorney_registration_numbers:{reg_no}",
        "rows": 10,
        "wt": "json",
    }
    return _execute_query(params)


def search_by_multiple_registration_numbers(reg_nos: list[str]) -> list[dict]:
    """
    Fetch patents by multiple attorney registration numbers.
    e.g., {!terms f=all_attorney_registration_numbers}54459,53937
    """
    reg_str = ",".join(reg_nos)
    params = {
        "q": f"{{!terms f=all_attorney_registration_numbers}}{reg_str}",
        "rows": 20,
        "wt": "json",
    }
    return _execute_query(params)


def _execute_query(params: dict) -> list[dict]:
    """
    Internal helper — executes any Solr query with auth and returns docs.
    """
    try:
        response = requests.get(
            settings.SOLR_BASE_URL,
            params=params,
            auth=SOLR_AUTH,
            timeout=8,
        )
        response.raise_for_status()
        docs = response.json().get("response", {}).get("docs", [])
        return docs

    except requests.exceptions.ConnectionError:
        print("[Solr Error] Cannot connect to Solr instance.")
        return []
    except requests.exceptions.Timeout:
        print("[Solr Error] Solr request timed out.")
        return []
    except Exception as e:
        print(f"[Solr Error] {e}")
        return []