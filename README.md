# Bharat Scout

Bharat Scout is a responsive NSE watchlist and value screener that can be hosted as a static site on GitHub Pages. It runs in two modes:

- **Demo mode:** no backend required; useful for UI checks and GitHub Pages previews.
- **Kite live mode:** the frontend calls a private Node/Express proxy, and the proxy calls Zerodha Kite with credentials stored in backend environment variables.

> Never put a Zerodha API key or access token in frontend code. GitHub Pages is public static hosting, so every secret shipped to the browser is exposed.

## Project structure

```text
index.html                 Static app shell
style.css                  Responsive glassmorphism UI
src/app.js                 UI state, filters, watchlist, CSV export
src/api.js                 Demo quotes and backend quote client
src/data.js                Seed fundamentals and symbol suggestions
src/storage.js             LocalStorage helpers
server/server.js           Optional secure Kite proxy
.github/workflows/pages.yml GitHub Pages deployment workflow
```

## Product requirements

See [`docs/PRD.md`](docs/PRD.md) for the complete product requirements document, including goals, scope, functional requirements, API contracts, release plan, risks, and acceptance criteria.
## Run locally

Because the app uses ES modules, serve it over HTTP instead of opening `index.html` with `file://`.

```bash
python3 -m http.server 8080
```

Then open <http://localhost:8080>.

## Deploy the frontend to GitHub Pages

1. Push this repository to GitHub.
2. In GitHub, open **Settings → Pages**.
3. Set **Source** to **GitHub Actions**.
4. Push to the `main` branch, or run the `Deploy static frontend to GitHub Pages` workflow manually.
5. Open the deployed Pages URL.

The included workflow uploads the static frontend files directly; no build step is required.

## Deploy the Kite proxy

GitHub Pages cannot safely call Zerodha Kite directly because credentials would be exposed and browser CORS can block direct API calls. Deploy `server/` to a backend host such as Render, Railway, Fly.io, or a VPS.

1. Copy `server/.env.example` to environment variables on your host.
2. Set `KITE_API_KEY` and the daily `KITE_ACCESS_TOKEN` on the backend only.
3. Set `ALLOWED_ORIGINS` to your GitHub Pages URL and any local development URLs.
4. Deploy and verify `/api/health` returns `{ "ok": true }`.
5. Paste the backend URL into Bharat Scout's **Backend proxy URL** field and click **Save Backend**.

## Notes

- Kite access tokens expire and must be refreshed according to Zerodha's authentication flow.
- The sample fundamentals are static seed data. Extend `src/data.js` or add backend endpoints if you need richer fundamentals.
- The watchlist and backend URL are persisted in the browser with LocalStorage.
