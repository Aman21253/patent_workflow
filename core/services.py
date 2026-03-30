import requests
from requests.auth import HTTPBasicAuth

SOLR_URL = "http://44.214.190.56:7412/solr/triangleipv2/select"

# 🔑 ADD YOUR CREDENTIALS HERE
USERNAME = "admin"
PASSWORD = "tipuser2023"


def fetch_patents():
    params = {
        "q": "*:*",
        "wt": "json",
        "rows": 100,
    }

    response = requests.get(
        SOLR_URL,
        params=params,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        timeout=60,
    )

    response.raise_for_status()

    return response.json().get("response", {}).get("docs", [])