const DEMO_PRICES = {
  RELIANCE: 2894.25,
  TCS: 3862.5,
  INFY: 1468.8,
  HDFCBANK: 1535.4,
  ICICIBANK: 1128.7,
  ITC: 437.9,
  SBIN: 821.35,
  WIPRO: 466.2,
  TATAMOTORS: 959.6,
  HINDUNILVR: 2346.3,
  LT: 3564.2,
  AXISBANK: 1178.9,
};

function normaliseBaseUrl(baseUrl) {
  return baseUrl.trim().replace(/\/+$/, "");
}

function createDemoQuote(symbol, index) {
  const seed = [...symbol].reduce((total, char) => total + char.charCodeAt(0), 0);
  const base = DEMO_PRICES[symbol] ?? 250 + (seed % 1800);
  const wave = Math.sin((Date.now() / 60000 + seed) / 3) * 1.8;
  const drift = ((seed + index * 7) % 90) / 100 - 0.45;
  const change = Number((wave + drift).toFixed(2));
  const ltp = Number((base * (1 + change / 100)).toFixed(2));

  return { symbol, ltp, change, source: "demo" };
}

export async function fetchQuotes({ backendUrl, symbols }) {
  if (!symbols.length) return { source: "empty", quotes: {} };

  if (!backendUrl) {
    return {
      source: "demo",
      quotes: Object.fromEntries(symbols.map((symbol, index) => [symbol, createDemoQuote(symbol, index)])),
    };
  }

  const url = new URL(`${normaliseBaseUrl(backendUrl)}/api/quotes`);
  url.searchParams.set("symbols", symbols.join(","));

  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.error || `Backend returned ${response.status}`);
  }

  return { source: "kite", quotes: payload.quotes || {} };
}
