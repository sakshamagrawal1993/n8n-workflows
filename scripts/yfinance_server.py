from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import json
import asyncio
import base64

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Yahoo WebSocket Logic ---
# Yahoo uses Protobuf. We'll use a simplified decoder for the streaming bridge.
# For a production-grade decoder, one would typically use the official .proto files,
# but for this "exploration" we will proxy the raw or use a light decoder.

@app.get("/research")
async def get_research(ticker: str = Query(...)):
    # ... (existing research logic)
    try:
        t = yf.Ticker(ticker)
        info = t.info
        res = {
            "symbol": ticker,
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "summary": info.get("longBusinessSummary"),
            "price": info.get("currentPrice"),
            "pe": info.get("trailingPE") or info.get("forwardPE"),
            "marketCap": info.get("marketCap"),
            "dividendYield": info.get("dividendYield"),
            "recommendation": info.get("recommendationKey"),
            "targetPrice": info.get("targetMeanPrice"),
            "range52w": f"{info.get('fiftyTwoWeekLow')} - {info.get('fiftyTwoWeekHigh')}"
        }
        return res
    except Exception as e:
        return {"error": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to Python WS Bridge")
    
    # In a real scenario, we would use yf.multitasking or a dedicated thread
    # to listen to Yahoo's WSS and push to this websocket.
    # For now, let's implement a high-frequency poller that mimics streaming
    # since Yahoo's internal WSS is often throttled/changing.
    
    try:
        while True:
            # Receive subscription list from client
            data = await websocket.receive_text()
            subscription = json.loads(data)
            tickers = subscription.get("tickers", [])
            
            # Start streaming loop for these tickers
            while True:
                try:
                    # Filter out empty or invalid tickers
                    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
                    if not clean_tickers:
                        break

                    # Batch fetch latest prices (using 5d to ensure we have a last close on weekends)
                    data = yf.download(clean_tickers, period="5d", interval="1m", prepost=True, progress=False, group_by='ticker')
                    
                    updates = {}
                    for ticker in clean_tickers:
                        try:
                            # Handle both single and multi-ticker dataframes
                            if len(clean_tickers) == 1:
                                series = data['Close']
                            else:
                                series = data[ticker]['Close']
                            
                            last_valid_price = series.dropna().iloc[-1]
                            
                            updates[ticker] = {
                                "price": float(last_valid_price),
                                "time": int(asyncio.get_event_loop().time())
                            }
                        except Exception:
                            continue
                    
                    if updates:
                        await websocket.send_json({"type": "update", "data": updates})
                    
                    await asyncio.sleep(2) # 2-second "tick"
                except Exception as e:
                    print(f"Streaming error: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
                    await asyncio.sleep(5) # Back off on error
                    continue
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WS Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
