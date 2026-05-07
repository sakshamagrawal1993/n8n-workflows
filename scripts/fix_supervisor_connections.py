import json
import os
import requests
import sys

# Configuration
API_KEY = os.environ.get("N8N_API_KEY")
API_URL = os.environ.get("N8N_API_URL")

if not API_KEY or not API_URL:
    print("N8N_API_KEY or N8N_API_URL not set")
    sys.exit(1)

HEADERS = {
    "X-N8N-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

FILEPATH = "definitions/tradingagents-supervisor-orchestrator__UDRkHgYzqs3GBaat.json"

def fix_connections():
    print(f"Fixing connections in {FILEPATH}...")
    with open(FILEPATH, 'r') as f:
        wf = json.load(f)

    # 1. Prune connections
    new_connections = {}
    for source_node, conn_types in wf['connections'].items():
        new_conn_types = {}
        for conn_type, outputs in conn_types.items():
            new_outputs = []
            for output_index_group in outputs:
                new_group = []
                for target in output_index_group:
                    target_name = target.get('node', '')
                    # Remove anything starting with "Push Log"
                    if not target_name.startswith("Push Log"):
                        new_group.append(target)
                new_outputs.append(new_group)
            new_conn_types[conn_type] = new_outputs
        new_connections[source_node] = new_conn_types
    
    wf['connections'] = new_connections

    # 2. Save locally
    with open(FILEPATH, 'w') as f:
        json.dump(wf, f, indent=2)
    print("Saved locally.")

    # 3. Push to n8n
    wf_id = wf.get('id')
    if wf_id:
        allowed_fields = ['name', 'nodes', 'connections', 'settings']
        payload = {k: v for k, v in wf.items() if k in allowed_fields}
        url = f"{API_URL}/api/v1/workflows/{wf_id}"
        response = requests.put(url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            print(f"Successfully pushed {wf_id} to n8n")
        else:
            print(f"Failed to push {wf_id}: {response.status_code} - {response.text}")

if __name__ == "__main__":
    fix_connections()
