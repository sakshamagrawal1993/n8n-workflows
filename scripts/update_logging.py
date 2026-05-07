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
        "last_node": "agent-node"
    },
    "tradingagents-technical-analyst__YeGEiKF7ZndLF8YN.json": {
        "role": "Technical Analyst",
        "log_type": "research",
        "last_node": "agent-node"
    },
    "tradingagents-fundamentals-analyst__qXgHkMpiqmOJqDqv.json": {
        "role": "Fundamentals Analyst",
        "log_type": "research",
        "last_node": "agent-node"
    },
    "tradingagents-social-media-analyst__bREGC66gC2ppRSio.json": {
        "role": "Social Media Analyst",
        "log_type": "research",
        "last_node": "agent-node"
    },
    "tradingagents-bull-researcher__AUTiS5Q4Eh5r2KXQ.json": {
        "role": "Bull Researcher",
        "log_type": "debate",
        "last_node": "agent-node"
    },
    "tradingagents-bear-researcher__IgQ0ooBfvg4oPsST.json": {
        "role": "Bear Researcher",
        "log_type": "debate",
        "last_node": "agent-node"
    },
    "tradingagents-research-manager__DXp8YLaipORggHwr.json": {
        "role": "Research Manager",
        "log_type": "research",
        "last_node": "agent-node"
    },
    "tradingagents-portfolio-manager__53Li8sbHz5IsPyNr.json": {
        "role": "Portfolio Manager",
        "log_type": "decision",
        "last_node": "agent-node"
    }
}

def create_postgres_node(role, log_type, position):
    # Robust session_id lookup that checks trigger nodes
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

    # 1. Find the last node to get its position
    last_node = next((n for n in wf['nodes'] if n['name'] == config['last_node'] or n['id'] == config['last_node']), None)
    if not last_node:
        print(f"Could not find last node {config['last_node']} in {filepath}")
        return

    # 2. Upsert logging node
    log_node_index = next((i for i, n in enumerate(wf['nodes']) if n['name'] == "Push Log — Internal"), None)
    new_log_node = create_postgres_node(config['role'], config['log_type'], last_node['position'])
    
    if log_node_index is not None:
        wf['nodes'][log_node_index] = new_log_node
    else:
        wf['nodes'].append(new_log_node)

        # 3. Connect last node to log node
        source_name = last_node['name']
        if source_name not in wf['connections']:
            wf['connections'][source_name] = { "main": [] }
        
        wf['connections'][source_name]['main'].append([
            {
                "node": new_log_node['name'],
                "type": "main",
                "index": 0
            }
        ])

    # 4. Save locally
    with open(filepath, 'w') as f:
        json.dump(wf, f, indent=2)

    # 5. Push to n8n
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

def clean_supervisor():
    filepath = "definitions/tradingagents-supervisor-orchestrator__UDRkHgYzqs3GBaat.json"
    print(f"Cleaning supervisor {filepath}...")
    with open(filepath, 'r') as f:
        wf = json.load(f)

    # Remove Push Log nodes
    original_count = len(wf['nodes'])
    wf['nodes'] = [n for n in wf['nodes'] if not (n['name'].startswith("Push Log —") and n['type'] == "n8n-nodes-base.postgres")]
    print(f"Removed {original_count - len(wf['nodes'])} logging nodes from supervisor.")

    with open(filepath, 'w') as f:
        json.dump(wf, f, indent=2)
    
    wf_id = wf.get('id')
    if wf_id:
        allowed_fields = ['name', 'nodes', 'connections', 'settings']
        payload = {k: v for k, v in wf.items() if k in allowed_fields}
        url = f"{API_URL}/api/v1/workflows/{wf_id}"
        response = requests.put(url, headers=HEADERS, json=payload)
        print(f"Supervisor push: {response.status_code}")

if __name__ == "__main__":
    for filename, config in WORKFLOW_UPDATES.items():
        path = os.path.join("definitions", filename)
        if os.path.exists(path):
            update_workflow_json(path, config)
    
    clean_supervisor()
