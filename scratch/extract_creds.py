import json
import glob
import os

creds = set()
for f in glob.glob("definitions/*.json"):
    with open(f, "r") as j:
        data = json.load(j)
        for node in data.get("nodes", []):
            if "credentials" in node:
                for cred_type in node["credentials"]:
                    creds.add(cred_type)

print("\n".join(sorted(list(creds))))
