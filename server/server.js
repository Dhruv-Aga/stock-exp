import cors from "cors";
import "dotenv/config";
import express from "express";
import helmet from "helmet";

const app = express();
const port = process.env.PORT || 3000;
const allowedOrigins = (process.env.ALLOWED_ORIGINS || "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

app.use(helmet());
app.use(
  cors({
    origin(origin, callback) {
      if (!origin || allowedOrigins.length === 0 || allowedOrigins.includes(origin)) {
        callback(null, true);
        return;
      }
      callback(new Error("Origin not allowed by CORS"));
    },
  }),
);

function requireKiteCredentials() {
  const apiKey = process.env.KITE_API_KEY;
  const accessToken = process.env.KITE_ACCESS_TOKEN;
  if (!apiKey || !accessToken) {
    const error = new Error("KITE_API_KEY and KITE_ACCESS_TOKEN must be configured on the backend.");
    error.status = 500;
    throw error;
  }
  return { apiKey, accessToken };
}

function normalizeSymbol(symbol) {
  return symbol.toUpperCase().replace(/[^A-Z0-9-]/g, "").trim();
}

app.get("/api/health", (_request, response) => {
  response.json({ ok: true });
});

app.get("/api/quotes", async (request, response, next) => {
  try {
    const { apiKey, accessToken } = requireKiteCredentials();
    const symbols = String(request.query.symbols || "")
      .split(",")
      .map(normalizeSymbol)
      .filter(Boolean)
      .slice(0, 50);

    if (symbols.length === 0) {
      response.status(400).json({ error: "Pass at least one symbol in ?symbols=RELIANCE,TCS" });
      return;
    }

    const kiteUrl = new URL("https://api.kite.trade/quote");
    symbols.forEach((symbol) => kiteUrl.searchParams.append("i", `NSE:${symbol}`));

    const kiteResponse = await fetch(kiteUrl, {
      headers: {
        "X-Kite-Version": "3",
        Authorization: `token ${apiKey}:${accessToken}`,
      },
    });
    const payload = await kiteResponse.json();

    if (!kiteResponse.ok || payload.status === "error") {
      response.status(kiteResponse.status || 502).json({ error: payload.message || "Kite quote request failed." });
      return;
    }

    const quotes = {};
    for (const symbol of symbols) {
      const quote = payload.data?.[`NSE:${symbol}`];
      if (!quote) continue;
      const previousClose = quote.ohlc?.close;
      const change = previousClose ? ((quote.last_price - previousClose) / previousClose) * 100 : 0;
      quotes[symbol] = {
        symbol,
        ltp: quote.last_price,
        change: Number(change.toFixed(2)),
        source: "kite",
      };
    }

    response.json({ quotes });
  } catch (error) {
    next(error);
  }
});

app.use((error, _request, response, _next) => {
  response.status(error.status || 500).json({ error: error.message || "Unexpected backend error." });
});

app.listen(port, () => {
  console.log(`Bharat Scout Kite proxy listening on port ${port}`);
});
