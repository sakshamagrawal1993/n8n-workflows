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

# Credentials to update, reading from environment variables
creds = [
    # Tiingo
    ("EsGCnfZqj2CxQzwn", {"name": "Authorization", "value": f"Token {os.environ.get('TIINGO_TOKEN')}"}),
    # Polygon
    ("8MysHa1RsYucneka", {"name": "apiKey", "value": os.environ.get('POLYGON_API_KEY')}),
    # FMP
    ("flJx7pYglGHQZrTL", {"name": "apikey", "value": os.environ.get('FMP_API_KEY')}),
    # Finnhub
    ("SR4cEU6bDqoofw6I", {"name": "X-Finnhub-Token", "value": os.environ.get('FINNHUB_TOKEN')}),
    # NewsAPI
    ("jFJNE26xGZnWlJNQ", {"name": "X-Api-Key", "value": os.environ.get('NEWSAPI_KEY')}),
    # EODHD
    ("jNeJqu0SLOpdQKgH", {"name": "api_token", "value": os.environ.get('EODHD_TOKEN')}),
    # LunarCrush
    ("p9h7gEqpN0UA9E32", {"name": "Authorization", "value": f"Bearer {os.environ.get('LUNARCRUSH_TOKEN')}"}),
    # TwelveData
    ("tbP5GLjoGhoInNOt", {"name": "apikey", "value": os.environ.get('TWELVEDATA_API_KEY')}),
]

# Alpaca (Custom Auth)
alpaca_key_id = os.environ.get('ALPACA_API_KEY_ID')
alpaca_secret_key = os.environ.get('ALPACA_API_SECRET_KEY')

if alpaca_key_id and alpaca_secret_key:
    alpaca_data = {
        "json": json.dumps({
            "headers": [
                {"name": "APCA-API-KEY-ID", "value": alpaca_key_id},
                {"name": "APCA-API-SECRET-KEY", "value": alpaca_secret_key}
            ]
        })
    }
    update_cred("Fn81k84jOum8RfUU", alpaca_data)
else:
    print("Skipping Alpaca update: ALPACA_API_KEY_ID or ALPACA_API_SECRET_KEY not set")

for cid, data in creds:
    # Check if value is set before trying to update
    if data["value"] and "None" not in data["value"]:
        update_cred(cid, data)
    else:
        print(f"Skipping update for {cid}: Environment variable not set")
