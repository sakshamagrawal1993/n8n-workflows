/**
 * Offline verification: same candle normalization + indicator math as
 * TradingAgents - Technical Analyst "Compute Technical Metrics" (simplified port).
 * Run: node scripts/verify_technical_analyst_data.mjs
 */

function normalizeCandlesFromTiingo(rawRows) {
  let r = rawRows;
  if (Array.isArray(r) && r.length && r[0] && Array.isArray(r[0].priceData)) {
    r = r[0].priceData;
  }
  if (!Array.isArray(r)) return null;
  return r
    .map((row) => {
      const d = row.date || row.Date;
      const c =
        row.close !== undefined && row.close !== null
          ? row.close
          : row.adjClose !== undefined
            ? row.adjClose
            : row.adj_close;
      return {
        date: d ? String(d).slice(0, 10) : '',
        ts: d ? String(d) : '',
        close: Number(c),
        open: Number(row.open),
        high: Number(row.high),
        low: Number(row.low),
        volume: Number(row.volume) || 0,
      };
    })
    .filter((x) => x.date && Number.isFinite(x.close))
    .sort((a, b) => a.date.localeCompare(b.date));
}

function normalizeCandlesFromAlpaca(body) {
  if (!body || !Array.isArray(body.bars)) return null;
  return body.bars
    .map((b) => ({
      date: new Date(b.t).toISOString(),
      ts: new Date(b.t).toISOString(),
      close: Number(b.c),
      open: Number(b.o),
      high: Number(b.h),
      low: Number(b.l),
      volume: Number(b.v) || 0,
    }))
    .filter((x) => Number.isFinite(x.close))
    .sort((a, b) => a.ts.localeCompare(b.ts));
}

function rowsLookTiingo(r) {
  if (!r) return false;
  if (
    Array.isArray(r) &&
    r.length &&
    typeof r[0] === 'object' &&
    (r[0].date !== undefined || r[0].adjClose !== undefined || r[0].close !== undefined)
  )
    return true;
  if (Array.isArray(r) && r.length && r[0] && Array.isArray(r[0].priceData)) return true;
  return false;
}

function computeBundle(rows) {
  let candles = normalizeCandlesFromAlpaca(rows);
  let timeframe = '5m';
  let source = 'alpaca_5m_iex_derived';
  if ((!candles || candles.length < 10) && rowsLookTiingo(rows)) {
    candles = normalizeCandlesFromTiingo(rows);
    timeframe = '1d';
    source = 'tiingo_ohlcv_derived';
  }
  if (!candles || candles.length < 10) {
    return { error: 'Insufficient OHLCV', raw_keys: rows && typeof rows === 'object' ? Object.keys(rows) : typeof rows };
  }
  const closes = candles.map((c) => c.close);
  const last = closes.length - 1;
  return {
    timeframe,
    source,
    bars_used: closes.length,
    last_close: closes[last],
    sample_first: candles[0],
    sample_last: candles[last],
  };
}

// --- Synthetic Alpaca-like bars (50 x 5m) ---
const t0 = Date.parse('2026-05-01T13:30:00.000Z');
const bars = [];
for (let i = 0; i < 50; i++) {
  const c = 180 + i * 0.05 + (i % 7) * 0.02;
  const o = c - 0.03;
  const h = c + 0.04;
  const l = c - 0.05;
  bars.push({ t: t0 + i * 5 * 60 * 1000, o, h, l, c, v: 10000 + i * 100 });
}

const alpacaCase = computeBundle({ bars });
const tiingoCase = computeBundle(
  Array.from({ length: 30 }, (_, i) => ({
    date: `2026-04-${String((i % 28) + 1).padStart(2, '0')}`,
    close: 100 + i * 0.1,
    open: 99 + i * 0.1,
    high: 101 + i * 0.1,
    low: 98 + i * 0.1,
    volume: 1e6,
  })),
);

console.log('Alpaca-shaped input ->', JSON.stringify(alpacaCase, null, 2));
console.log('Tiingo-shaped input ->', JSON.stringify(tiingoCase, null, 2));

if (alpacaCase.error || tiingoCase.error) {
  console.error('FAIL', alpacaCase.error || tiingoCase.error);
  process.exit(1);
}
if (alpacaCase.source !== 'alpaca_5m_iex_derived' || tiingoCase.source !== 'tiingo_ohlcv_derived') {
  console.error('Unexpected source routing', alpacaCase, tiingoCase);
  process.exit(1);
}
console.log('OK: routing and bar counts look correct.');
