# Bharat Scout Product Requirements Document

## 1. Product summary

Bharat Scout is a responsive Indian equity watchlist and value-screening web app. The frontend is a static GitHub Pages-compatible application that can run in demo mode without a backend, and it can optionally connect to a secure Node.js backend proxy for Zerodha Kite quote data.

The product is intended for retail investors who want a lightweight NSE-focused dashboard to track selected symbols, compare basic valuation/fundamental indicators, sort/filter opportunities, and export a watchlist snapshot.

## 2. Goals and success criteria

### 2.1 Product goals

- Provide a polished stock screening dashboard that works from a static host such as GitHub Pages.
- Keep Zerodha Kite credentials out of the browser by routing live quote requests through a backend proxy.
- Allow users to use the product immediately in demo mode before configuring live data.
- Persist user watchlist and backend URL preferences locally in the browser.
- Make the app easy to deploy using free or low-cost hosting options.

### 2.2 Success metrics

- A first-time user can open the GitHub Pages app and see a populated demo dashboard without setup.
- A user can add, remove, search, filter, sort, refresh, auto-refresh, and export stocks without a page reload.
- A user can configure a backend proxy URL once and have it persist across browser refreshes.
- No API key or access token is requested or stored by the frontend.
- The backend can return normalized quote data for up to 50 symbols per request.
- The UI remains usable on desktop, tablet, and mobile widths.

## 3. Target users

### 3.1 Primary user

A retail investor or self-directed trader in India who tracks NSE stocks and wants a simple watchlist/screener that can be hosted for personal use.

### 3.2 Secondary user

A developer or technical user who wants to deploy a static finance dashboard and connect it to a private broker API proxy.

## 4. User problems

- Static sites cannot safely store broker credentials.
- Opening an ES module app with `file://` often causes browser loading issues.
- Users need a clear distinction between demo data and live broker data.
- Watchlists should not reset after every page refresh.
- Mobile tables and cramped controls make finance dashboards hard to use.
- Users need clear deployment instructions for GitHub Pages and the optional backend.

## 5. Product scope

### 5.1 In scope

- Static frontend hosted from `index.html`, `style.css`, and modular JavaScript under `src/`.
- Demo quote generation when no backend URL is configured.
- Optional live quote mode through a backend proxy.
- Watchlist add/remove with LocalStorage persistence.
- Backend proxy URL persistence.
- Search, filter, preset filters, sorting, refresh, auto-refresh, and CSV export.
- Loading, empty, success, and error states.
- Responsive layout for common desktop and mobile viewports.
- GitHub Pages deployment workflow.
- Node/Express backend proxy for Zerodha Kite quote requests.
- README deployment documentation.

### 5.2 Out of scope for the current release

- Placing trades or order management.
- Portfolio holdings, positions, P&L, or tax reporting.
- User authentication for the frontend.
- Cloud database sync across devices.
- Full fundamental data provider integration.
- Historical charting and technical indicators.
- Real-time WebSocket streaming.
- Automated Zerodha login/session generation.
- Push notifications or alerts.

## 6. User journeys

### 6.1 Demo-mode visitor

1. User opens the GitHub Pages URL.
2. App loads with the default watchlist.
3. App displays demo prices and a “Demo” status.
4. User filters, sorts, adds symbols, removes symbols, and exports CSV.
5. Watchlist changes persist in the same browser.

### 6.2 Live-data user

1. User deploys the Node backend proxy to a server.
2. User stores Kite credentials as backend environment variables.
3. User opens the frontend and enters the backend base URL.
4. Frontend saves the backend URL to LocalStorage.
5. Frontend calls `/api/quotes` on refresh and displays live quote data.
6. If the backend fails, the UI shows an error state and toast.

### 6.3 Mobile user

1. User opens the app on a phone.
2. Header actions wrap instead of overflowing.
3. Sidebar and dashboard stack vertically.
4. Table remains horizontally scrollable.
5. Filters and action controls remain tappable.

## 7. Functional requirements

### 7.1 Frontend shell

- The app must load from `index.html` as a static page.
- The app must import frontend logic using ES modules.
- The app must not require a frontend build step.
- The page must include semantic header, main, aside, section, and footer regions.
- The app must include user-facing copy that warns not to put Zerodha credentials in the frontend.

### 7.2 Data source selection

- The app must display the current data mode/status.
- The app must provide a backend proxy URL input.
- The app must save the backend proxy URL in LocalStorage.
- The app must allow users to clear the backend URL and return to demo mode.
- The frontend must never ask for a Kite API key or Kite access token.

### 7.3 Demo quote mode

- If no backend URL is configured, the quote client must return demo quotes.
- Demo quotes should be deterministic enough to keep the UI stable but dynamic enough to simulate market movement.
- Demo quotes must include symbol, last traded price, change percentage, and source.

### 7.4 Live quote mode

- If a backend URL is configured, the frontend must call `${backendUrl}/api/quotes` with a comma-separated `symbols` query parameter.
- The frontend must parse JSON responses from the backend.
- The frontend must show an error toast and backend error status for failed live quote requests.
- The frontend must not send Kite credentials to the browser or store them in LocalStorage.

### 7.5 Watchlist management

- The app must initialize with a default NSE watchlist.
- Users must be able to add a symbol by typing and pressing Enter or clicking Add.
- Symbols must be normalized to uppercase and stripped of unsupported characters.
- Duplicate symbols must be rejected with a visible error message.
- Users must be able to remove symbols from the watchlist.
- Watchlist changes must persist in LocalStorage.

### 7.6 Symbol suggestions

- The stock input must provide suggestions from the local fundamentals seed data.
- Suggestions must include symbol values and company names.

### 7.7 Screener table

- The table must show symbol, company, LTP, change percentage, P/E, ROE, margin, and score.
- The table must handle missing values using an em dash.
- Positive change values must be visually distinct from negative values.
- The score must render with both a number and a progress-style bar.
- The table must support horizontal scrolling on narrow screens.

### 7.8 Filtering and sorting

- Users must be able to filter by minimum ROE.
- Users must be able to filter by maximum P/E.
- Users must be able to search by symbol or company name.
- Users must be able to sort by value score, change percentage, ROE, P/E, and symbol.
- Preset buttons must update filter/sort fields for value, profitability, and quality screens.

### 7.9 Refresh behavior

- Users must be able to manually refresh quote data.
- Users must be able to toggle auto-refresh.
- Auto-refresh interval must be 30 seconds.
- Manual refresh must disable the refresh button while loading.
- The app must show the last successful update time.

### 7.10 CSV export

- Users must be able to export the currently displayed rows to a CSV file.
- CSV export must include the visible screener columns.
- CSV file names must include the current date.

### 7.11 UI states

- The app must show a loading spinner during quote refresh.
- The app must show toast notifications for successful and failed user actions.
- The app must show an empty state when filters produce no matching rows.
- The app must show status variants for demo, live, and error modes.

### 7.12 Backend proxy

- The backend must be a Node.js service.
- The backend must expose `GET /api/health`.
- The backend must expose `GET /api/quotes?symbols=RELIANCE,TCS`.
- The backend must read `KITE_API_KEY` and `KITE_ACCESS_TOKEN` from environment variables.
- The backend must reject quote requests when credentials are missing.
- The backend must sanitize requested symbols.
- The backend must limit quote requests to 50 symbols.
- The backend must call Zerodha Kite's quote API with server-side authorization.
- The backend must return normalized quote objects keyed by symbol.
- The backend must support CORS allow-listing through `ALLOWED_ORIGINS`.

### 7.13 Deployment

- The repository must include a GitHub Actions workflow for GitHub Pages deployment.
- The frontend deployment must not require a build step.
- The backend must include a package manifest with a start script.
- The backend must include an example environment file.
- Documentation must explain local serving, GitHub Pages deployment, backend deployment, and credential safety.

## 8. Non-functional requirements

### 8.1 Security

- No broker secrets may be committed to the repository.
- No broker secrets may be requested by the frontend.
- Broker secrets must be stored only as backend environment variables.
- The backend should restrict browser origins where practical.
- Error responses must avoid exposing secrets.

### 8.2 Performance

- The frontend should remain lightweight and avoid a build system for the current release.
- Rendering should use a document fragment when rebuilding table rows.
- Quote refreshes should avoid duplicate manual refresh requests by disabling the refresh button during loading.
- The backend should cap quote batch size to prevent overly large upstream requests.

### 8.3 Reliability

- Demo mode must continue to work without network access to a backend.
- Backend errors must not crash the frontend.
- LocalStorage failures must fall back to defaults.
- Unknown symbols should still render with symbol-only company names and missing fundamentals.

### 8.4 Accessibility and usability

- Interactive elements should be buttons or form controls.
- Remove buttons should include accessible labels.
- Toast region should use polite live-region announcements.
- Controls should remain usable on small screens.
- Table overflow should be scrollable rather than breaking layout.

### 8.5 Browser support

- The app should support modern evergreen browsers with ES module support.
- The app should be served over HTTP or HTTPS, not opened directly as `file://`.

## 9. Data model

### 9.1 Watchlist item

```json
"RELIANCE"
```

### 9.2 Fundamental seed item

```json
{
  "name": "Reliance Industries",
  "pe": 29.2,
  "roe": 18.5,
  "margin": 8.6
}
```

### 9.3 Quote item

```json
{
  "symbol": "RELIANCE",
  "ltp": 2894.25,
  "change": 1.24,
  "source": "kite"
}
```

### 9.4 Rendered screener row

```json
{
  "symbol": "RELIANCE",
  "name": "Reliance Industries",
  "pe": 29.2,
  "roe": 18.5,
  "margin": 8.6,
  "ltp": 2894.25,
  "change": 1.24,
  "score": 38,
  "source": "kite"
}
```

## 10. API contract

### 10.1 Health check

```http
GET /api/health
```

Expected response:

```json
{
  "ok": true
}
```

### 10.2 Quotes

```http
GET /api/quotes?symbols=RELIANCE,TCS
```

Expected success response:

```json
{
  "quotes": {
    "RELIANCE": {
      "symbol": "RELIANCE",
      "ltp": 2894.25,
      "change": 1.24,
      "source": "kite"
    }
  }
}
```

Expected error response:

```json
{
  "error": "KITE_API_KEY and KITE_ACCESS_TOKEN must be configured on the backend."
}
```

## 11. Configuration

### 11.1 Frontend LocalStorage keys

- `bharat-scout:watchlist`
- `bharat-scout:backendUrl`

### 11.2 Backend environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `KITE_API_KEY` | Yes for live data | Zerodha Kite API key stored only on the backend. |
| `KITE_ACCESS_TOKEN` | Yes for live data | Daily Kite access token stored only on the backend. |
| `ALLOWED_ORIGINS` | Recommended | Comma-separated browser origins allowed by CORS. |
| `PORT` | No | Server port; defaults to `3000`. |

## 12. Release plan

### 12.1 Version 1: Static screener and optional live quotes

- Static GitHub Pages frontend.
- Demo quote mode.
- Backend URL mode.
- Watchlist persistence.
- Filters, sorting, presets, auto-refresh, CSV export.
- Optional Kite proxy.

### 12.2 Version 2 candidates

- Instrument search backed by a full NSE/Kite instrument dump.
- Sector and market-cap filters.
- Real fundamentals data provider integration.
- Historical charts.
- Backend token refresh helper flow.
- WebSocket quote streaming where supported by the user's Kite plan.
- Portfolio and holdings view.
- Price alerts.
- Unit and integration test suite.

## 13. Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Users try to deploy with credentials in the frontend | High security risk | Keep credential fields out of the UI and document backend-only secrets. |
| Free backend sleeps when idle | Slow first refresh | Show loading states and document free-tier limitations. |
| Kite access token expires daily | Live data stops working | Show backend error messages and document token refresh requirement. |
| Static fundamentals become outdated | Misleading scores | Label fundamentals as seed data and plan provider integration. |
| Browser CORS misconfiguration | Live mode fails | Document exact `ALLOWED_ORIGINS` setup and provide health endpoint. |

## 14. Acceptance criteria

- The app opens from GitHub Pages and renders a dashboard without backend configuration.
- The frontend does not contain Kite API key or access-token input fields.
- Saving a backend URL causes quote refreshes to use the backend proxy.
- Clearing the backend URL returns the app to demo mode.
- Watchlist and backend URL survive a browser refresh.
- Add/remove/search/filter/sort/preset/export actions work without reloading the page.
- Backend `/api/health` returns `{ "ok": true }`.
- Backend `/api/quotes` returns normalized quote data when valid credentials are configured.
- Backend returns a clear error when credentials are missing.
- GitHub Pages workflow can deploy the static frontend.
- README explains both frontend-only and backend-enabled deployments.

## 15. Open questions

- Which data provider should supply production-grade fundamentals?
- Should watchlists sync across devices in a future authenticated version?
- Should the backend support multiple users or remain a single-user private proxy?
- Should alerts and notifications be browser-local or backend-driven?
- Should the next release prioritize charts, full instrument search, or portfolio tracking?
