import requests
from requests.auth import HTTPBasicAuth

SOLR_URL = "http://44.214.190.56:7412/solr/triangleipv2/select"

USERNAME = "admin"
PASSWORD = "tipuser2023"


def search_solr(query="*:*", rows=5):
    params = {
        "q": query,
        "wt": "json",
        "rows": rows,
    }

    try:
        response = requests.get(
            SOLR_URL,
            params=params,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=10,
        )

        print("🔍 STATUS:", response.status_code)

        if response.status_code != 200:
            print("❌ Solr Error:", response.text[:300])
            return []

        if not response.text.strip():
            print("❌ Empty response from Solr")
            return []

        try:
            data = response.json()
        except Exception:
            print("❌ Not JSON response:", response.text[:300])
            return []

        docs = data.get("response", {}).get("docs", [])
        print(f"✅ Found {len(docs)} docs")

        return docs

    except Exception as e:
        print("❌ Solr Exception:", e)
        return []