import requests
import json
import os

# Configuration
API_KEY = os.environ.get("N8N_API_KEY")
API_URL = os.environ.get("N8N_API_URL")

if not API_KEY or not API_URL:
    print("N8N_API_KEY or N8N_API_URL not set")
    exit(1)

def update_cred(cred_id, data):
    url = f"{API_URL}/api/v1/credentials/{cred_id}"
    headers = {
        "X-N8N-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"data": data}
    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"Successfully updated {cred_id}")
    else:
        print(f"Failed to update {cred_id}: {response.status_code} - {response.text}")

# Credentials to update
creds = [
    # Tiingo
    ("EsGCnfZqj2CxQzwn", {"name": "Authorization", "value": "Token 31b911660b154e0188bd1fc4d75f750811c08e85"}),
    # Polygon
    ("8MysHa1RsYucneka", {"name": "apiKey", "value": "2m1zQPNAWwlk3z_M47p_2xpAzvKR4XTD"}),
    # FMP
    ("flJx7pYglGHQZrTL", {"name": "apikey", "value": "KqnQDacRJUmyxAoFvfr1QfNJquwbe1ww"}),
    # Finnhub
    ("SR4cEU6bDqoofw6I", {"name": "X-Finnhub-Token", "value": "d7qe8q9r01qi8jan4910d7qe8q9r01qi8jan491g"}),
    # NewsAPI
    ("jFJNE26xGZnWlJNQ", {"name": "X-Api-Key", "value": "f3780986bb1444f693627b00c47d49b4"}),
    # EODHD
    ("jNeJqu0SLOpdQKgH", {"name": "api_token", "value": "69f51d32b3b751.88792528"}),
    # LunarCrush
    ("p9h7gEqpN0UA9E32", {"name": "Authorization", "value": "Bearer df0apn8og18cdk3dewfco0iwnvmongkzq10vft19"}),
    # TwelveData
    ("tbP5GLjoGhoInNOt", {"name": "apikey", "value": "72e66e5f22c8493c9b9dc5f8d3f88ea4"}),
]

# Alpaca (Custom Auth) - Need to be careful with the structure
# Typically n8n Custom Auth uses a 'json' string or internal object
alpaca_data = {
    "json": json.dumps({
        "headers": [
            {"name": "APCA-API-KEY-ID", "value": "PKEIOGQAMNAWDHMPKT6GYBWZDO"},
            {"name": "APCA-API-SECRET-KEY", "value": "3XG42TtY53hyq6gNsyqV4j93TTtpkZwSUjoGqAx8ra4w"}
        ]
    })
}
update_cred("Fn81k84jOum8RfUU", alpaca_data)

for cid, data in creds:
    update_cred(cid, data)
