import json
import os

agents = [
    {
        "id": "fundamentals-analyst",
        "name": "Fundamentals Analyst",
        "prompt": "You are a Fundamentals Analyst. Fetch financial statements and evaluate company health, focusing on metrics that might cause significant price movement within the next 24 hours.",
        "tool": "Yahoo Deep Research Tool",
        "url": "http://localhost:8001/research?ticker={{$json.ticker}}",
        "credType": "none",
        "credId": "",
        "credName": ""
    },
    {
        "id": "research-manager",
        "name": "Research Manager",
        "prompt": "You are a Research Manager. Synthesize all reports and present them to the Portfolio Manager, keeping a strict 24-hour trading horizon in mind.",
        "tool": "Yahoo Deep Research Tool",
        "url": "http://localhost:8001/research?ticker={{$json.ticker}}",
        "credType": "none",
        "credId": "",
        "credName": ""
    },
    {
        "id": "portfolio-manager",
        "name": "Portfolio Manager",
        "prompt": "You are the Portfolio Manager. Make the final BUY, SELL, or HOLD decision for a strict 24-hour trading horizon based on all research. You MUST output your final decision in strict JSON format: {\"decision\": \"BUY|SELL|HOLD\", \"confidence\": \"High|Medium|Low\", \"thesis\": \"Your detailed explanation here...\"}",
        "tool": "Yahoo Deep Research Tool",
        "url": "http://localhost:8001/research?ticker={{$json.ticker}}",
        "credType": "none",
        "credId": "",
        "credName": ""
    },
    {
        "id": "news-analyst",
        "name": "News Analyst",
        "prompt": "You are a News Analyst. Fetch the latest news and assess market sentiment, focusing on catalysts likely to impact the stock over the next 24 hours.",
        "tool": "Get News Tool (Alpaca)",
        "url": "https://data.alpaca.markets/v1beta1/news?symbols={{$json.ticker}}",
        "credType": "httpCustomAuth",
        "credId": "Fn81k84jOum8RfUU",
        "credName": "Alpaca Key"
    },
    {
        "id": "social-media-analyst",
        "name": "Social Media Analyst",
        "prompt": "You are a Social Media Analyst. Review social sentiment and return a mood summary, emphasizing short-term hype or panic for a 24-hour trade.",
        "tool": "Social Sentiment Tool (LunarCrush)",
        "url": "https://lunarcrush.com/api/4/public/coins/{{$json.ticker}}/meta",
        "credType": "httpHeaderAuth",
        "credId": "p9h7gEqpN0UA9E32",
        "credName": "LunarCrush Key"
    },
    {
        "id": "technical-analyst",
        "name": "Technical Analyst",
        "prompt": "You are a Technical Analyst. Review technical indicators and provide a technical rating for a short-term 24-hour hold.",
        "tool": "Technical Indicator Tool (Tiingo)",
        "url": "https://api.tiingo.com/tiingo/daily/{{$json.ticker}}/prices",
        "credType": "httpHeaderAuth",
        "credId": "jEo9N4yIEkuPj5Df",
        "credName": "Tiingo Key"
    },
    {
        "id": "bull-researcher",
        "name": "Bull Researcher",
        "prompt": "You are a Bull Researcher. Construct the strongest possible bullish argument for holding the asset over the next 24 hours.",
        "tool": "Bullish Context Tool (NewsAPI)",
        "url": "https://newsapi.org/v2/everything?q={{$json.ticker}}&sortBy=relevancy",
        "credType": "httpHeaderAuth",
        "credId": "jFJNE26xGZnWlJNQ",
        "credName": "NewsAPI Key"
    },
    {
        "id": "bear-researcher",
        "name": "Bear Researcher",
        "prompt": "You are a Bear Researcher. Construct the strongest possible bearish argument against holding the asset over the next 24 hours.",
        "tool": "Bearish Context Tool (EODHD)",
        "url": "https://eodhd.com/api/news?s={{$json.ticker}}",
        "credType": "httpQueryAuth",
        "credId": "jNeJqu0SLOpdQKgH",
        "credName": "EODHD Key"
    },
    {
        "id": "recon-screener",
        "name": "Recon Screener",
        "prompt": "You are a Reconnaissance Screener. Analyze a batch of tickers and return the top 3 with the strongest momentum or deepest discount for a 24-hour trade. Format output as a JSON array of tickers.",
        "tool": "Batch Quote Tool (FMP)",
        "url": "https://financialmodelingprep.com/api/v3/quote/{{$json.tickers}}",
        "credType": "httpQueryAuth",
        "credId": "flJx7pYglGHQZrTL",
        "credName": "FMP Key"
    }
]

definitions_dir = "/Users/sakshamagrawal/Documents/Projects/n8n-workflows/definitions"
os.makedirs(definitions_dir, exist_ok=True)

for agent in agents:
    workflow = {
        "name": f"TradingAgents - {agent['name']}",
        "nodes": [
            {
                "parameters": {},
                "id": "execute-workflow-trigger",
                "name": "Execute Workflow Trigger",
                "type": "n8n-nodes-base.executeWorkflowTrigger",
                "typeVersion": 1,
                "position": [200, 300]
            },
            {
                "parameters": {
                    "promptType": "define",
                    "text": "={{$json.ticker}} on {{$json.date}}",
                    "hasOutputParser": False,
                    "options": {
                        "systemMessage": agent['prompt']
                    }
                },
                "id": "agent-node",
                "name": agent['name'],
                "type": "@n8n/n8n-nodes-langchain.agent",
                "typeVersion": 1.7,
                "position": [500, 300]
            },
            {
                "parameters": {
                    "model": "gpt-4o",
                    "options": {
                        "temperature": 0.2
                    }
                },
                "id": "llm-node",
                "name": "OpenAI Model",
                "type": "@n8n/n8n-nodes-langchain.lmChatOpenAi",
                "typeVersion": 1,
                "position": [500, 500],
                "credentials": {
                    "openAiApi": {
                        "id": "F8K5WXRWzmnY0vcZ",
                        "name": "Saksham OpenAI Account"
                    }
                }
            },
            {
                "parameters": {
                    "method": "GET",
                    "url": agent['url'],
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {
                                "name": "Accept",
                                "value": "application/json"
                            }
                        ]
                    },
                    "options": {},
                    "authentication": "predefinedCredentialType",
                    "nodeCredentialType": agent['credType']
                },
                "id": "tool-node",
                "name": agent['tool'],
                "type": "@n8n/n8n-nodes-langchain.toolHttpRequest",
                "typeVersion": 1.1,
                "position": [700, 500],
                "credentials": {
                    agent['credType']: {
                        "id": agent['credId'],
                        "name": agent['credName']
                    }
                }
            }
        ],
        "connections": {
            "Execute Workflow Trigger": {
                "main": [[{"node": agent['name'], "type": "main", "index": 0}]]
            },
            "OpenAI Model": {
                "ai_languageModel": [[{"node": agent['name'], "type": "ai_languageModel", "index": 0}]]
            },
            agent['tool']: {
                "ai_tool": [[{"node": agent['name'], "type": "ai_tool", "index": 0}]]
            }
        },
        "active": False,
        "settings": {}
    }
    
    file_path = os.path.join(definitions_dir, f"TradingAgents_{agent['name'].replace(' ', '_')}.json")
    with open(file_path, "w") as f:
        json.dump(workflow, f, indent=2)

print("Generated all workflow definitions.")
