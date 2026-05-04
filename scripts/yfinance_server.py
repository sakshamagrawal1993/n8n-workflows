"""
FastAPI server for Yahoo Finance data via yfinance (`/research`, WebSocket `/ws`).

Time between stock price fetches (this process only; Yahoo may additionally delay quotes
vs the exchange by exchange/data-tier rules):

| Constant | Default | Role |
|----------|---------|------|
| YAHOO_MIN_INTERVAL_SEC | 0.85 s | Minimum gap between any two Yahoo-backed yfinance calls |
| WS_POLL_INTERVAL_SEC | 12 s | Sleep after each WebSocket batch over the watchlist |
| WS_PRICE_CACHE_TTL_SEC | 30 s | Reuse last quote for a symbol without calling Yahoo |
| RESEARCH_MIN_INTERVAL_SEC | 2 s | Minimum gap between `.info` research fetches |
| RESEARCH_CACHE_TTL_SEC | 600 s | `/research` response cache per ticker |

WebSocket prices: symbols are polled sequentially; each symbol may use up to two throttled
Yahoo paths (`fast_info` then `history` fallback), so at least ~2 * YAHOO_MIN_INTERVAL_SEC of
enforced spacing between those two calls, plus network latency.

Observability: set environment variable YFINANCE_WS_POLL_LOG=1 for INFO logs each WS poll
cycle (timestamps in docker logs or the uvicorn terminal show cadence).
"""

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
import yfinance as yf
import json
import os
import asyncio
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("yfinance_server")

app = FastAPI()

# --- Process-wide spacing for every Yahoo call (yfinance -> Yahoo Finance). ---
YAHOO_MIN_INTERVAL_SEC = 0.85
_yahoo_throttle_lock = threading.Lock()
_last_yahoo_mono = 0.0


def _throttle_yahoo_call() -> None:
    """Ensure we do not hammer Yahoo from parallel WS tasks + /research."""
    global _last_yahoo_mono
    with _yahoo_throttle_lock:
        now = time.monotonic()
        wait = YAHOO_MIN_INTERVAL_SEC - (now - _last_yahoo_mono)
        if wait > 0:
            time.sleep(wait)
        _last_yahoo_mono = time.monotonic()


# --- /research: Yahoo rate-limits aggressive parallel .info calls. Cache + throttle. ---
RESEARCH_CACHE_TTL_SEC = 600  # 10 minutes per ticker
RESEARCH_MIN_INTERVAL_SEC = 2.0  # minimum gap between Yahoo "info" fetches in this process
_research_cache: dict[str, tuple[float, dict]] = {}
_research_cache_lock = threading.Lock()
_research_last_fetch_mono = 0.0
_research_fetch_lock = threading.Lock()

# --- WebSocket price loop: never fetch all symbols in parallel (instant 429 + huge logs). ---
WS_POLL_INTERVAL_SEC = 12.0
WS_PRICE_CACHE_TTL_SEC = 30.0  # reuse last quote longer to cut Yahoo calls
# Set YFINANCE_WS_POLL_LOG=1 to log each WS poll cycle (timestamps in docker logs show cadence).
_WS_POLL_LOG = os.environ.get("YFINANCE_WS_POLL_LOG", "").strip().lower() in ("1", "true", "yes", "on")
_ws_price_cache: dict[str, tuple[float, tuple]] = {}
_ws_price_lock = threading.Lock()

# Throttled logging for repeated Yahoo failures (stops disk fill from print-per-symbol).
_rate_warn_last_mono = 0.0
_rate_warn_lock = threading.Lock()
_RATE_WARN_INTERVAL_SEC = 45.0


def _log_yahoo_noise(message: str) -> None:
    """One warning per window instead of thousands of identical lines."""
    global _rate_warn_last_mono
    with _rate_warn_lock:
        now = time.monotonic()
        if now - _rate_warn_last_mono < _RATE_WARN_INTERVAL_SEC:
            return
        _rate_warn_last_mono = now
    log.warning("%s (suppressing similar messages for ~%ss)", message, int(_RATE_WARN_INTERVAL_SEC))

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
            _throttle_yahoo_call()
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

    Each call respects WS_PRICE_CACHE_TTL_SEC. On a cache miss, uses `_throttle_yahoo_call`
    before `fast_info`, and again before `history` if no usable price—so two Yahoo calls
    are spaced by at least YAHOO_MIN_INTERVAL_SEC each time.
    """
    sym = symbol.strip().upper()
    now = time.time()
    with _ws_price_lock:
        cached = _ws_price_cache.get(sym)
        if cached and (now - cached[0]) < WS_PRICE_CACHE_TTL_SEC:
            return cached[1]

    try:
        _throttle_yahoo_call()
        t = yf.Ticker(sym)
        fi = getattr(t, "fast_info", None) or {}
        p = fi.get("last_price") or fi.get("lastPrice") or fi.get("last_price")
        if p is not None and not (isinstance(p, float) and (p != p)):  # not NaN
            out = (sym, float(p), int(time.time() * 1000))
            with _ws_price_lock:
                _ws_price_cache[sym] = (time.time(), out)
            return out
        _throttle_yahoo_call()
        h = t.history(period="5d", interval="1h", auto_adjust=False)
        if h is not None and not h.empty and "Close" in h.columns:
            last = h["Close"].dropna().iloc[-1]
            out = (sym, float(last), int(time.time() * 1000))
            with _ws_price_lock:
                _ws_price_cache[sym] = (time.time(), out)
            return out
    except Exception as ex:
        msg = str(ex).lower()
        if "too many" in msg or "rate limit" in msg or "429" in msg:
            _log_yahoo_noise(f"Yahoo rate limited while fetching {sym}")
        else:
            log.debug("price fetch %s: %s", sym, ex)
    return None


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    if websocket.client_state != WebSocketState.CONNECTED:
        return False
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
        log.debug("WS send skipped: %s", e)
        return False


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    log.info("Client connected to Python WS Bridge")

    # Single worker: WS loop is sequential per symbol; avoids parallel Yahoo blast.
    executor = ThreadPoolExecutor(max_workers=1)

    try:
        while True:
            data = await websocket.receive_text()
            subscription = json.loads(data)
            tickers = subscription.get("tickers", [])

            while True:
                try:
                    if websocket.client_state != WebSocketState.CONNECTED:
                        return

                    clean_tickers = [t.strip().upper() for t in tickers if t.strip()]
                    if not clean_tickers:
                        break

                    loop = asyncio.get_running_loop()
                    updates = {}
                    for sym in clean_tickers:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            return
                        r = await loop.run_in_executor(executor, _last_price_sync, sym)
                        if r:
                            s, price, ts = r
                            updates[s] = {"price": price, "time": ts}

                    if updates:
                        if not await _safe_send_json(websocket, {"type": "update", "data": updates}):
                            return

                    if _WS_POLL_LOG:
                        log.info(
                            "ws poll cycle tickers=%d priced=%d sent_update=%s next_sleep_s=%.1f",
                            len(clean_tickers),
                            len(updates),
                            bool(updates),
                            WS_POLL_INTERVAL_SEC,
                        )

                    await asyncio.sleep(WS_POLL_INTERVAL_SEC)
                except WebSocketDisconnect:
                    return
                except Exception as e:
                    log.exception("Streaming error: %s", e)
                    if not await _safe_send_json(
                        websocket, {"type": "error", "message": str(e)}
                    ):
                        return
                    await asyncio.sleep(5)
                    continue
    except WebSocketDisconnect:
        log.info("Client disconnected")
    except Exception as e:
        log.exception("WS Error: %s", e)
    finally:
        executor.shutdown(wait=True, cancel_futures=False)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
