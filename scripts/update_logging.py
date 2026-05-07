import requests
import json
import os
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

POSTGRES_CRED_ID = "TzhNsURks708nQk6"

# Workflow mappings: filename -> {role, type, last_node_id}
WORKFLOW_UPDATES = {
    "tradingagents-news-analyst__TIJbwjW9wXs7Nz0f.json": {
        "role": "News Analyst",
        "log_type": "research",
        "last_node": "News Analyst"
    },
    "tradingagents-technical-analyst__YeGEiKF7ZndLF8YN.json": {
        "role": "Technical Analyst",
        "log_type": "research",
        "last_node": "Format Technical Output"
    },
    "tradingagents-fundamentals-analyst__qXgHkMpiqmOJqDqv.json": {
        "role": "Fundamentals Analyst",
        "log_type": "research",
        "last_node": "Fundamentals Analyst"
    },
    "tradingagents-social-media-analyst__bREGC66gC2ppRSio.json": {
        "role": "Social Media Analyst",
        "log_type": "research",
        "last_node": "Social Media Analyst"
    },
    "tradingagents-bull-researcher__AUTiS5Q4Eh5r2KXQ.json": {
        "role": "Bull Researcher",
        "log_type": "debate",
        "last_node": "Bull Researcher"
    },
    "tradingagents-bear-researcher__IgQ0ooBfvg4oPsST.json": {
        "role": "Bear Researcher",
        "log_type": "debate",
        "last_node": "Bear Researcher"
    },
    "tradingagents-research-manager__DXp8YLaipORggHwr.json": {
        "role": "Research Manager",
        "log_type": "research",
        "last_node": "Research Manager"
    },
    "tradingagents-portfolio-manager__53Li8sbHz5IsPyNr.json": {
        "role": "Portfolio Manager",
        "log_type": "decision",
        "last_node": "Portfolio Manager"
    }
}

def create_postgres_node(role, log_type, position):
    session_id_expr = "={{ $node[\"Execute Workflow Trigger\"].json.session_id || $node[\"When Executed by Another Workflow\"].json.session_id || $node[\"[CLI Test] News Analyst Webhook\"].json.session_id || $node[\"[CLI Test] Technical Analyst Webhook\"].json.session_id || $json.session_id }}"
    
    return {
        "parameters": {
            "operation": "insert",
            "schema": { "__rl": True, "mode": "list", "value": "public" },
            "table": { "__rl": True, "mode": "list", "value": "trading_logs" },
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "session_id": session_id_expr,
                    "agent_role": role,
                    "log_type": log_type,
                    "content": "={{ String($json.output || $json.text || $json.content || '') }}"
                }
            }
        },
        "id": "push-log-internal-node",
        "name": "Push Log — Internal",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.5,
        "position": [position[0] + 250, position[1]],
        "credentials": {
            "postgres": { "id": POSTGRES_CRED_ID, "name": "Postgres account" }
        },
        "continueOnFail": True
    }

def update_workflow_json(filepath, config):
    print(f"Processing {filepath}...")
    with open(filepath, 'r') as f:
        wf = json.load(f)

    # 1. Remove any existing Push Log nodes and their connections
    wf['nodes'] = [n for n in wf['nodes'] if n['name'] != "Push Log — Internal"]
    
    new_connections = {}
    for source, targets in wf['connections'].items():
        new_targets = {}
        for conn_type, outputs in targets.items():
            new_outputs = []
            for group in outputs:
                new_group = [t for t in group if t.get('node') != "Push Log — Internal"]
                if new_group:
                    new_outputs.append(new_group)
            if new_outputs:
                new_targets[conn_type] = new_outputs
        if new_targets:
            new_connections[source] = new_targets
    wf['connections'] = new_connections

    # 2. Find the last node
    last_node_name = config['last_node']
    last_node = next((n for n in wf['nodes'] if n['name'] == last_node_name), None)
    if not last_node:
        print(f"Could not find node {last_node_name} in {filepath}")
        return

    # 3. Add fresh Push Log node
    log_node = create_postgres_node(config['role'], config['log_type'], last_node['position'])
    wf['nodes'].append(log_node)

    # 4. Connect last node to log node
    source_name = last_node['name']
    if source_name not in wf['connections']:
        wf['connections'][source_name] = { "main": [] }
    
    # Check if main connections already has outputs
    if "main" not in wf['connections'][source_name]:
         wf['connections'][source_name]["main"] = []
    
    if not wf['connections'][source_name]["main"]:
        wf['connections'][source_name]["main"].append([])
    
    # We always append to the first output index's group
    wf['connections'][source_name]["main"][0].append({
        "node": "Push Log — Internal",
        "type": "main",
        "index": 0
    })

    # 5. Save locally
    with open(filepath, 'w') as f:
        json.dump(wf, f, indent=2)

    # 6. Push to n8n
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
    for filename, config in WORKFLOW_UPDATES.items():
        path = os.path.join("definitions", filename)
        if os.path.exists(path):
            update_workflow_json(path, config)
