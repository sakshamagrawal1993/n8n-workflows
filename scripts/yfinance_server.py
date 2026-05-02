from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import json
import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

# --- /research: Yahoo rate-limits aggressive parallel .info calls. Cache + throttle. ---
RESEARCH_CACHE_TTL_SEC = 600  # 10 minutes per ticker
RESEARCH_MIN_INTERVAL_SEC = 2.0  # minimum gap between Yahoo "info" fetches in this process
_research_cache: dict[str, tuple[float, dict]] = {}
_research_cache_lock = threading.Lock()
_research_last_fetch_mono = 0.0
_research_fetch_lock = threading.Lock()

# --- WebSocket price loop: polling 50 symbols every few seconds still hits Yahoo. ---
WS_POLL_INTERVAL_SEC = 6.0
WS_PRICE_CACHE_TTL_SEC = 12.0  # reuse last quote if younger than this
_ws_price_cache: dict[str, tuple[float, tuple]] = {}
_ws_price_lock = threading.Lock()

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

def _research_payload_from_info(ticker_key: str, info: dict) -> dict:
    return {
        "symbol": ticker_key,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "summary": info.get("longBusinessSummary"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "pe": info.get("trailingPE") or info.get("forwardPE"),
        "marketCap": info.get("marketCap"),
        "dividendYield": info.get("dividendYield"),
        "recommendation": info.get("recommendationKey"),
        "targetPrice": info.get("targetMeanPrice"),
        "range52w": f"{info.get('fiftyTwoWeekLow')} - {info.get('fiftyTwoWeekHigh')}",
    }


def _fetch_info_throttled(ticker_key: str) -> dict:
    """
    Blocking Yahoo fetch with process-wide spacing to reduce 429s.
    yfinance surfaces Yahoo 'Too Many Requests' as exceptions or empty info.
    """
    global _research_last_fetch_mono
    with _research_fetch_lock:
        now = time.monotonic()
        gap = now - _research_last_fetch_mono
        if gap < RESEARCH_MIN_INTERVAL_SEC:
            time.sleep(RESEARCH_MIN_INTERVAL_SEC - gap)
        _research_last_fetch_mono = time.monotonic()

    last_err = None
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker_key)
            info = t.info if isinstance(t.info, dict) else {}
            has_data = bool(
                info.get("longName")
                or info.get("shortName")
                or info.get("currentPrice") is not None
                or info.get("regularMarketPrice") is not None
                or info.get("longBusinessSummary")
            )
            if has_data:
                return info
            last_err = RuntimeError("empty or throttled Yahoo response")
            time.sleep(2.0 * (attempt + 1))
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "too many" in msg or "rate limit" in msg or "429" in msg:
                time.sleep(2.0 * (attempt + 1))
            else:
                time.sleep(0.5 * (attempt + 1))
    raise last_err if last_err else RuntimeError("Unknown research fetch error")


@app.get("/research")
async def get_research(ticker: str = Query(...)):
    ticker_key = ticker.strip().upper()
    if not ticker_key:
        return {"error": "ticker required"}

    now = time.time()
    with _research_cache_lock:
        hit = _research_cache.get(ticker_key)
        if hit and (now - hit[0]) < RESEARCH_CACHE_TTL_SEC:
            return hit[1]

    loop = asyncio.get_event_loop()

    try:
        info = await loop.run_in_executor(None, lambda: _fetch_info_throttled(ticker_key))
    except Exception as e:
        err_text = str(e)
        if "too many" in err_text.lower() or "rate limit" in err_text.lower() or "429" in err_text:
            return {"error": "Too Many Requests. Rate limited. Try after a while."}
        return {"error": err_text}

    try:
        res = _research_payload_from_info(ticker_key, info if isinstance(info, dict) else {})
        err_hint = res.get("name") is None and res.get("price") is None
        if err_hint and not res.get("summary"):
            return {"error": "Too Many Requests. Rate limited. Try after a while."}
        with _research_cache_lock:
            _research_cache[ticker_key] = (time.time(), res)
        return res
    except Exception as e:
        return {"error": str(e)}

def _last_price_sync(symbol: str):
    """
    Fast path for live-ish quotes. Avoids yf.download(50 tickers, 1m) every few seconds,
    which is too slow for the Trading Agents UI (Hostinger VPS).
    """
    sym = symbol.strip().upper()
    now = time.time()
    with _ws_price_lock:
        cached = _ws_price_cache.get(sym)
        if cached and (now - cached[0]) < WS_PRICE_CACHE_TTL_SEC:
            return cached[1]

    try:
        t = yf.Ticker(sym)
        fi = getattr(t, "fast_info", None) or {}
        p = fi.get("last_price") or fi.get("lastPrice") or fi.get("last_price")
        if p is not None and not (isinstance(p, float) and (p != p)):  # not NaN
            out = (sym, float(p), int(time.time() * 1000))
            with _ws_price_lock:
                _ws_price_cache[sym] = (time.time(), out)
            return out
        h = t.history(period="5d", interval="1h", auto_adjust=False)
        if h is not None and not h.empty and "Close" in h.columns:
            last = h["Close"].dropna().iloc[-1]
            out = (sym, float(last), int(time.time() * 1000))
            with _ws_price_lock:
                _ws_price_cache[sym] = (time.time(), out)
            return out
    except Exception as ex:
        print(f"price fetch {sym}: {ex}")
    return None


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to Python WS Bridge")

    # Bounded thread pool: Yahoo rate-limits; fewer workers + longer interval between rounds.
    executor = ThreadPoolExecutor(max_workers=4)

    try:
        while True:
            data = await websocket.receive_text()
            subscription = json.loads(data)
            tickers = subscription.get("tickers", [])

            while True:
                try:
                    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
                    if not clean_tickers:
                        break

                    loop = asyncio.get_running_loop()
                    futures = [
                        loop.run_in_executor(executor, _last_price_sync, sym)
                        for sym in clean_tickers
                    ]
                    results = await asyncio.gather(*futures)

                    updates = {}
                    for r in results:
                        if r:
                            sym, price, ts = r
                            updates[sym] = {"price": price, "time": ts}

                    if updates:
                        await websocket.send_json({"type": "update", "data": updates})

                    await asyncio.sleep(WS_POLL_INTERVAL_SEC)
                except Exception as e:
                    print(f"Streaming error: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
                    await asyncio.sleep(5)
                    continue
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WS Error: {e}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
